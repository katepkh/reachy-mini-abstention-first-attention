"""Offline phone-cue successor tests; never use real SSH, devices or media."""

import ast
import base64
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from scripts import run_reachy_mic_v3_play as launch
from tools import reachy_mic_health_v3_play as m
from tools import reachy_mic_health_v3_run as previous


class CueTests(unittest.TestCase):
    def test_preserved_predecessor_builds(self):
        for name, expected in (
                ("tools/reachy_mic_health_v3_run.py", "cb86a5ee1e067d4da2fc093fcfe6e07045e7781a7a177da72ba721af7004c5b3"),
                ("scripts/run_reachy_mic_v3.py", "e3a309fda35de5b04dfdaabd3b0bcdc0da0ad396f956ad2fe1cfa2eab92efa2c")):
            self.assertEqual(launch.sha((launch.ROOT / name).read_bytes()), expected)

    def test_only_identity_and_operator_text_change_in_standalone_helper(self):
        class WithoutPrompts(ast.NodeTransformer):
            def visit_Expr(self, node):
                if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
                    if node.value.func.id == "print":
                        return None
                    if node.value.func.id == "wait_enter":
                        node.value.args = [ast.Constant("operator prompt")]
                return self.generic_visit(node)

        def normalized(module):
            source = Path(module.__file__).read_text()
            source = source.replace("two-pair-v3-02", "two-pair-v3-01").replace("two_pair_v3_02", "two_pair_v3_01")
            tree = WithoutPrompts().visit(ast.parse(source))
            return ast.dump(tree, include_attributes=False)

        self.assertEqual(normalized(m), normalized(previous))
        self.assertEqual((m.PAIR_LIMIT, m.RESTORE_LIMIT, m.PAIRS, m.RATE),
                         (previous.PAIR_LIMIT, previous.RESTORE_LIMIT, previous.PAIRS, previous.RATE))
        self.assertEqual(m.capture_command(), previous.capture_command())

    def test_new_identity_and_approval_do_not_reopen_previous_run(self):
        self.assertEqual(launch.SESSION, "two-pair-v3-02")
        self.assertNotEqual(m.SESSION_DIRECTORY, previous.SESSION_DIRECTORY)
        self.assertNotEqual(m.AUTHORIZATION_PATH, previous.AUTHORIZATION_PATH)
        with self.assertRaises(m.Stop):
            m.validate_session_authorization(previous.required_authorization())
        self.assertEqual(launch.approval_contract(launch.LOCAL)["previous_session_closeout_sha256"],
                         launch.PREVIOUS_RECEIPT_SHA)

    def test_walkthrough_has_no_connection_file_write_or_authority(self):
        output = io.StringIO()
        with patch.object(launch, "run_once") as run, patch.object(launch, "collect") as collect, \
                patch.object(launch, "write_new") as write, patch.object(launch, "authorization") as approval, \
                redirect_stdout(output):
            self.assertEqual(launch.main(["--walkthrough"]), 0)
        for mocked in (run, collect, write, approval):
            mocked.assert_not_called()
        text = output.getvalue()
        self.assertIn("SAME EXISTING CLIP", text)
        self.assertIn("do not make a new recording", text)
        self.assertIn("THEN press Enter ONCE here within 10 seconds", text)
        self.assertIn("do NOT press Enter or pause until PAUSE", text)

    def test_walkthrough_confirmation_before_one_shot_latch_or_connection(self):
        for response in ("", "yes", "READY "):
            runner = Mock()
            with patch.object(launch.sys.stdin, "isatty", return_value=True), \
                    patch.object(launch, "authorization"), patch.object(launch, "input", return_value=response, create=True), \
                    patch.object(launch, "begin_local") as begin, redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(RuntimeError, "walkthrough_not_confirmed"):
                    launch.run_once(launch.LOCAL, runner)
            runner.assert_not_called()
            begin.assert_not_called()

    def test_missing_approval_cannot_be_bypassed_by_ready(self):
        runner = Mock()
        with patch.object(launch.sys.stdin, "isatty", return_value=True), \
                patch.object(launch, "authorization", side_effect=RuntimeError("missing_approval")), \
                patch.object(launch, "input", return_value="READY", create=True) as prompt:
            with self.assertRaisesRegex(RuntimeError, "missing_approval"):
                launch.run_once(launch.LOCAL, runner)
        prompt.assert_not_called()
        runner.assert_not_called()

    def capture_fixture(self):
        path = Path(__file__).with_name("test_mic_health.py")
        source = path.read_text().replace("from tools import reachy_mic_health as m",
                                         "from tools import reachy_mic_health_v3_play as m")
        source = source.replace('stack.enter_context(patch.object(m, "print"))',
                                'self.printed = stack.enter_context(patch.object(m, "print"))')
        module = types.ModuleType("cue_phase_fixture")
        module.__file__ = str(path)
        exec(compile(source, str(path), "exec"), module.__dict__)
        return module.TestCapture()

    def test_actual_phase_cues_and_numeric_lengths(self):
        case = self.capture_fixture()
        result = case.run_capture([("pcm", case.pcm(5)), ("operator", None), ("pcm", case.pcm(12))])
        cues = [call.args[0] for call in case.printed.call_args_list]
        self.assertEqual(len(cues), 3)
        self.assertTrue(cues[0].startswith("WAIT - keep the phone PAUSED"))
        self.assertTrue(cues[1].startswith("PLAY THE EXISTING CLIP NOW"))
        self.assertIn("THEN press Enter ONCE", cues[1])
        self.assertTrue(cues[2].startswith("WAIT - keep the clip PLAYING"))
        self.assertTrue(result["complete"])
        self.assertEqual(result["summaries"]["quiet"]["frames"], 3 * 16)
        self.assertEqual(result["summaries"]["playback"]["frames"], 10 * 16)
        self.assertTrue(result["capture_exit_verified"])

    def test_missed_play_cue_still_stops_at_unchanged_deadline(self):
        case = self.capture_fixture()
        events = [("pcm", case.pcm(5))] + [("time", 1), ("pcm", case.pcm(1))] * 11
        with self.assertRaisesRegex(m.Stop, "operator_deadline"):
            case.run_capture(events)
        self.assertEqual(len(case.printed.call_args_list), 2)
        self.assertFalse(case.result["complete"])
        self.assertTrue(case.result["capture_exit_verified"])
        self.assertNotIn("playback", case.result["summaries"])

    def test_early_or_extra_enter_during_quiet_still_aborts(self):
        case = self.capture_fixture()
        with self.assertRaisesRegex(m.Stop, "unexpected_operator_input"):
            case.run_capture([("operator", None)])
        self.assertTrue(case.result["capture_exit_verified"])


class PredecessorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mic-play-offline-")
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def local_fixture(self):
        registry = self.root / "data/private/mic_closeout"
        hashes = {}
        expected = {}
        for session, scope in (("two-pair-v2-01", launch.PRIOR_SCOPE), ("two-pair-v3-01", launch.PREVIOUS_SCOPE)):
            directory = registry / session
            directory.mkdir(parents=True)
            local = {"status": "CHECKED_NO_UNEXPECTED_FILES", "restoration_verified": True,
                     "capture_exit_verified": True, "local_scope": str(directory.resolve())}
            (directory / "closeout.json").write_text(json.dumps(local))
            receipt_path = directory / "closeout-final-v1.json"
            receipt_path.write_text("{}")
            closed = {"scope": scope, "status": "CHECKED_NO_UNEXPECTED_FILES",
                      "restoration_verified": True, "capture_exit_verified": True}
            receipt = {"local_after_check": {"inventory_at_check": launch.local_inventory(directory)},
                       "remote_closeout": closed, "remote_final_inventory": []}
            receipt_path.write_text(json.dumps(receipt))
            hashes[session] = launch.sha(receipt_path.read_bytes())
            expected[scope] = {"inventory": [], "closeout": closed}
        preflight_path = self.root / "data/private/mic_v3_preflight/two-pair-v2-01/report.json"
        preflight_path.parent.mkdir(parents=True)
        preflight_path.write_bytes(b"fixture")
        tools = self.root / "tools"
        tools.mkdir()
        (tools / "reachy_mic_health_v3.py").write_bytes(b"fixture")
        return registry, hashes, expected

    def test_both_closed_predecessors_verified_without_media_reads(self):
        registry, hashes, expected = self.local_fixture()
        with patch.object(launch, "ROOT", self.root), \
                patch.object(launch, "PRIOR_RECEIPT_SHA", hashes["two-pair-v2-01"]), \
                patch.object(launch, "PREVIOUS_RECEIPT_SHA", hashes["two-pair-v3-01"]), \
                patch.object(launch, "PRIOR_PREFLIGHT_SHA", launch.sha(b"fixture")), \
                patch.object(launch, "CANDIDATE_SHA", launch.sha(b"fixture")):
            self.assertEqual(launch.prior_evidence(), expected)
            for session in hashes:
                directory = registry / session
                with patch.object(launch, "local_inventory", side_effect=lambda p: (
                        [] if p == directory else launch.legacy.local_inventory(p))):
                    with self.assertRaisesRegex(RuntimeError, "inventory_changed"):
                        launch.prior_evidence()
            extra = registry / "known-interrupted"
            extra.mkdir()
            with self.assertRaises(FileNotFoundError):
                launch.prior_evidence()
            (extra / "closeout.json").write_text('{"status":"PENDING"}')
            with self.assertRaisesRegex(RuntimeError, "unresolved"):
                launch.prior_evidence()

    def test_latest_receipt_required_not_just_older_v2(self):
        registry, hashes, expected = self.local_fixture()
        with patch.object(launch, "ROOT", self.root), \
                patch.object(launch, "PRIOR_RECEIPT_SHA", hashes["two-pair-v2-01"]), \
                patch.object(launch, "PREVIOUS_RECEIPT_SHA", "changed"):
            with self.assertRaisesRegex(RuntimeError, "receipt_changed"):
                launch.prior_evidence()

    def test_both_remote_predecessors_checked_before_installing_capability(self):
        for change in (None, "old_inventory", "latest_inventory", "latest_closeout", "missing_scope", "failed_preflight"):
            with self.subTest(change=change):
                ns = {}
                exec(launch.remote_source("deploy").rsplit("\nremote_deploy()", 1)[0], ns)
                scopes = (self.root / "prior-v2", self.root / "prior-v3")
                for scope in scopes:
                    scope.mkdir(exist_ok=True)
                    (scope / "closeout.json").write_text("{}")
                source = b"fixture_verified_namespace"
                fake = {"require_robot_account": Mock(), "private_directory": Mock(),
                        "pending_runs": lambda: [], "inventory": lambda p: [],
                        "preflight_report": lambda: {"machine_checks_passed": change != "failed_preflight"},
                        "required_authorization": lambda: {}, "require_execution_authorization": Mock()}
                prior_runs = {str(p): {"inventory": [], "closeout": {}} for p in scopes}
                if change in ("old_inventory", "latest_inventory"):
                    prior_runs[str(scopes[change == "latest_inventory"])]["inventory"] = [{"changed": True}]
                if change == "latest_closeout":
                    prior_runs[str(scopes[1])]["closeout"] = {"changed": True}
                if change == "missing_scope":
                    prior_runs.pop(str(scopes[1]))
                packet = {"helper": base64.b64encode(source).decode(), "authorization": {}, "prior_runs": prior_runs}
                install = Mock()
                ns.update(REMOTE_SCOPE=str(self.root / "new-run"), PRIOR_SCOPE=str(scopes[0]),
                          PREVIOUS_SCOPE=str(scopes[1]), EXPECTED=launch.sha(source),
                          install_exact=install, remote_namespace=lambda: fake, exec=lambda code, space: space.update(fake))
                with patch.object(ns["sys"], "stdin", types.SimpleNamespace(buffer=io.BytesIO(json.dumps(packet).encode()))), \
                        patch.object(ns["os"], "execv") as execute, redirect_stdout(io.StringIO()):
                    if change not in (None, "failed_preflight"):
                        with self.assertRaises(RuntimeError):
                            ns["remote_deploy"]()
                    else:
                        ns["remote_deploy"]()
                execute.assert_not_called()
                self.assertEqual(install.call_count, 2 if change is None else 1 if change == "failed_preflight" else 0)
                self.assertEqual(fake["require_execution_authorization"].call_count, int(change is None))


def load_tests(loader, standard_tests, pattern):
    """Reuse unchanged synthetic contracts against this helper/launcher build.

    Four predecessor-specific tests are replaced above: AST prompt differences,
    parent prompt strings, two-predecessor inventories and remote reconciliation.
    The inherited loader also exercises all legacy guard/capture/close-out tests.
    """
    path = Path(__file__).with_name("test_mic_v3_session.py")
    source = path.read_text().replace("run_reachy_mic_v3 as launch", "run_reachy_mic_v3_play as launch")
    source = source.replace("reachy_mic_health_v3_run", "reachy_mic_health_v3_play")
    source = source.replace("/run-two-pair-v3-01", "/run-two-pair-v3-02")
    source = source.replace('with patch.object(sys.stdin, "isatty", return_value=True), redirect_stdout(io.StringIO()),',
                            'with patch.object(launch, "input", return_value="READY", create=True), patch.object(sys.stdin, "isatty", return_value=True), redirect_stdout(io.StringIO()),')
    module = types.ModuleType("play_session_contract")
    module.__file__ = str(path)
    exec(compile(source, str(path), "exec"), module.__dict__)
    for name in ("test_all_measurement_and_recovery_definitions_unchanged_from_candidate",
                 "test_parent_flow_only_adds_authorization_and_fixed_one_shot_scope"):
        delattr(module.SessionHelperTests, name)
    for name in ("test_generated_deployment_blocks_on_old_scope_drift_and_never_starts_capture",
                 "test_local_prior_missing_pending_changed_and_unexpected_records_refuse"):
        delattr(module.SessionLauncherTests, name)
    standard_tests.addTests(loader.loadTestsFromModule(module))
    return standard_tests


if __name__ == "__main__":
    unittest.main()
