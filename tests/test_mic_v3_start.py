"""Single-start successor: synthetic-only tests, no robot connection or audio."""

import ast
import base64
from contextlib import ExitStack, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from scripts import run_reachy_mic_v3_start as launch
from tools import reachy_mic_health_v3_start as m
from tools import reachy_mic_health_v3_play as previous


class SingleStartTests(unittest.TestCase):
    def test_old_builds_preserved_and_new_session_separate(self):
        for name, digest in (("tools/reachy_mic_health_v3_play.py", "240a7bf400bab72bffd28c8db0def8decfcd37f35a0b62d115477d937606b7d8"),
                             ("scripts/run_reachy_mic_v3_play.py", "fd32183719369fe1d344b09d4de2dae3aa81b0092b4e7d12155dbcc87660e3aa")):
            self.assertEqual(launch.sha((launch.ROOT / name).read_bytes()), digest)
        self.assertEqual(launch.SESSION, "two-pair-v3-03")
        self.assertNotEqual(m.SESSION_DIRECTORY, previous.SESSION_DIRECTORY)
        self.assertNotEqual(m.AUTHORIZATION_PATH, previous.AUTHORIZATION_PATH)
        with self.assertRaises(m.Stop):
            m.validate_session_authorization(previous.required_authorization())

    def test_helper_changes_only_identity_prints_and_first_pair_redundant_prompt(self):
        class Normalize(ast.NodeTransformer):
            def visit_If(self, node):
                if ast.dump(node.test) == ast.dump(ast.parse("pair == 1", mode="eval").body):
                    # Require precisely the announced preparation branch, not an arbitrary bypass.
                    self_outer.assertEqual(len(node.body), 1)
                    self_outer.assertEqual(len(node.orelse), 1)
                    self_outer.assertEqual(node.body[0].value.func.id, "wait_enter")
                    self_outer.assertEqual(node.orelse[0].value.func.id, "print")
                    return self.visit(node.body[0])
                return self.generic_visit(node)

            def visit_Expr(self, node):
                if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
                    if node.value.func.id == "print":
                        return None
                    if node.value.func.id == "wait_enter":
                        node.value.args = [ast.Constant("operator preparation")]
                return self.generic_visit(node)

        self_outer = self
        def normalized(module):
            source = Path(module.__file__).read_text().replace("two-pair-v3-03", "two-pair-v3-02").replace("two_pair_v3_03", "two_pair_v3_02")
            return ast.dump(Normalize().visit(ast.parse(source)), include_attributes=False)
        self.assertEqual(normalized(m), normalized(previous))
        self.assertEqual(m.capture_command(), previous.capture_command())
        self.assertEqual((m.PAIR_LIMIT, m.RESTORE_LIMIT, m.RATE, m.PAIRS),
                         (previous.PAIR_LIMIT, previous.RESTORE_LIMIT, previous.RATE, previous.PAIRS))

    def exercise(self, *, approve=True, stop_pair2=False, drift_before_pair=False):
        events = []
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            root = Path(temp) / "runs"
            directory = root / "run-test"
            baseline = {"helper_sha256": "fixture", "privacy_profile": m.PRIVACY_PROFILE}
            def snapshot(current=None):
                events.append(("snapshot", current is not None))
                return {**baseline, "changed": True} if drift_before_pair and current is not None else baseline
            def guard_start(path):
                events.append(("guard",))
                self.assertEqual(json.loads((path / "closeout.json").read_text())["status"], "PENDING")
                m.save_json(path / "guard.json", {"restoration": "NOT_CHANGED"})
                def request(action, expected, **kwargs):
                    events.append((action, kwargs.get("pair")))
                    if action == "restore":
                        m.save_json(path / "guard.json", {"restoration": "ROUTES_RESTORED"})
                return types.SimpleNamespace(request=request, close=lambda: events.append(("guard_close",)))
            def capture(pair, result, guard):
                events.append(("capture", pair))
                result.update(complete=True, capture_exit_verified=True)
            def prepare(prompt):
                events.append(("prepare_pair2",))
                self.assertIn("LIVE PAIR 2 PREPARATION", prompt)
                self.assertIn("within 30 seconds", prompt)
                if stop_pair2:
                    raise m.Stop("preparation_not_confirmed")
            def confirm():
                events.append(("ack",))
                return m.ACK if approve else "wrong"
            for name, value in (("RUN_ROOT", root), ("SESSION_DIRECTORY", directory)):
                stack.enter_context(patch.object(m, name, value))
            stack.enter_context(patch.object(m.sys.stdin, "isatty", return_value=True))
            stack.enter_context(patch.object(m, "require_execution_authorization"))
            stack.enter_context(patch.object(m, "protect_own_process"))
            stack.enter_context(patch.object(m, "snapshot", side_effect=snapshot))
            stack.enter_context(patch.object(m, "input", side_effect=confirm, create=True))
            stack.enter_context(patch.object(m, "print", side_effect=lambda *args, **kw: events.append(("print", str(args[0])))))
            stack.enter_context(patch.object(m, "wait_enter", side_effect=prepare))
            stack.enter_context(patch.object(m, "GuardClient", side_effect=guard_start))
            stack.enter_context(patch.object(m, "capture_pair", side_effect=capture))
            if not approve:
                with self.assertRaisesRegex(m.Stop, "approval_not_confirmed"):
                    m.execute()
                self.assertFalse(directory.exists())
                return events, None, None
            code = m.execute()
            result = json.loads((directory / "result.json").read_text())
            return events, code, result

    def test_one_explicit_start_then_capture_without_first_pair_enter(self):
        events, code, result = self.exercise()
        self.assertEqual(code, 0)
        actions = [e for e in events if e[0] in ("ack", "prepare_pair2", "begin", "capture", "restore")]
        self.assertEqual(actions, [("ack",), ("begin", 0), ("capture", 0), ("restore", None),
                                   ("prepare_pair2",), ("begin", 1), ("capture", 1), ("restore", None)])
        start_index = events.index(("ack",))
        text_before = "\n".join(e[1] for e in events[:start_index] if e[0] == "print")
        self.assertIn("starts Pair 1 quiet measurement automatically", text_before)
        self.assertIn("phone PAUSED", text_before)
        self.assertIn("Do NOT press Enter again", text_before)
        self.assertEqual(result["ordinary_file_closeout"], "CHECKED_NO_UNEXPECTED_FILES")
        for pair in (0, 1):
            index = events.index(("begin", pair))
            self.assertEqual(events[index - 1], ("snapshot", True))

    def test_wrong_start_confirmation_never_opens_guard_or_capture(self):
        events, _, _ = self.exercise(approve=False)
        self.assertFalse(any(e[0] in ("guard", "begin", "capture") for e in events))

    def test_second_pair_still_requires_preparation_after_first_restore(self):
        events, code, result = self.exercise(stop_pair2=True)
        self.assertEqual(code, 2)
        self.assertEqual(result["reason"], "preparation_not_confirmed")
        self.assertEqual([e for e in events if e[0] == "capture"], [("capture", 0)])
        self.assertLess(events.index(("restore", None)), events.index(("prepare_pair2",)))
        self.assertEqual(result["route_restoration"], "ROUTES_RESTORED")

    def test_fresh_drift_still_blocks_first_capture_after_start_confirmation(self):
        events, code, result = self.exercise(drift_before_pair=True)
        self.assertEqual(code, 2)
        self.assertEqual(result["reason"], "baseline_drift_before_pair")
        self.assertFalse(any(e[0] in ("begin", "capture") for e in events))

    def test_overview_does_not_display_live_play_cue_or_accept_ready(self):
        output = io.StringIO()
        with patch.object(launch, "input", side_effect=AssertionError("unexpected local prompt"), create=True), \
                patch.object(launch, "run_once") as run, patch.object(launch, "collect") as collect, \
                patch.object(launch, "write_new") as write, redirect_stdout(output):
            self.assertEqual(launch.main(["--walkthrough"]), 0)
        run.assert_not_called()
        collect.assert_not_called()
        write.assert_not_called()
        self.assertIn("OVERVIEW ONLY", output.getvalue())
        self.assertNotIn("PLAY THE EXISTING CLIP NOW", output.getvalue())
        self.assertNotIn("Type READY", output.getvalue())

    def test_spent_session_refused_before_overview_input_or_ssh(self):
        runner = Mock()
        with patch.object(launch.sys.stdin, "isatty", return_value=True), \
                patch.object(launch, "begin_local", side_effect=RuntimeError("session_spent")), \
                patch.object(launch, "walkthrough") as overview, \
                patch.object(launch, "input", side_effect=AssertionError("unexpected local prompt"), create=True):
            with self.assertRaisesRegex(RuntimeError, "session_spent"):
                launch.run_once(launch.LOCAL, runner)
        overview.assert_not_called()
        runner.assert_not_called()


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
        for session, scope in (("two-pair-v2-01", launch.PRIOR_SCOPE), ("two-pair-v3-01", launch.PREVIOUS_SCOPE), ("two-pair-v3-02", launch.LATEST_SCOPE)):
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

    def test_all_three_closed_predecessors_verified_without_media_reads(self):
        registry, hashes, expected = self.local_fixture()
        with patch.object(launch, "ROOT", self.root), \
                patch.object(launch, "PRIOR_RECEIPT_SHA", hashes["two-pair-v2-01"]), \
                patch.object(launch, "PREVIOUS_RECEIPT_SHA", hashes["two-pair-v3-01"]), \
                patch.object(launch, "LATEST_RECEIPT_SHA", hashes["two-pair-v3-02"]), \
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
                patch.object(launch, "PREVIOUS_RECEIPT_SHA", hashes["two-pair-v3-01"]), \
                patch.object(launch, "LATEST_RECEIPT_SHA", "changed"):
            with self.assertRaisesRegex(RuntimeError, "receipt_changed"):
                launch.prior_evidence()

    def test_all_three_remote_predecessors_checked_before_installing_capability(self):
        for change in (None, "old_inventory", "middle_inventory", "latest_inventory", "latest_closeout", "missing_scope", "failed_preflight"):
            with self.subTest(change=change):
                ns = {}
                exec(launch.remote_source("deploy").rsplit("\nremote_deploy()", 1)[0], ns)
                scopes = (self.root / "prior-v2", self.root / "prior-v3-01", self.root / "prior-v3-02")
                for scope in scopes:
                    scope.mkdir(exist_ok=True)
                    (scope / "closeout.json").write_text("{}")
                source = b"fixture_verified_namespace"
                fake = {"require_robot_account": Mock(), "private_directory": Mock(),
                        "pending_runs": lambda: [], "inventory": lambda p: [],
                        "preflight_report": lambda: {"machine_checks_passed": change != "failed_preflight"},
                        "required_authorization": lambda: {}, "require_execution_authorization": Mock()}
                prior_runs = {str(p): {"inventory": [], "closeout": {}} for p in scopes}
                if change in ("old_inventory", "middle_inventory", "latest_inventory"):
                    prior_runs[str(scopes[{"old_inventory": 0, "middle_inventory": 1, "latest_inventory": 2}[change]])]["inventory"] = [{"changed": True}]
                if change == "latest_closeout":
                    prior_runs[str(scopes[2])]["closeout"] = {"changed": True}
                if change == "missing_scope":
                    prior_runs.pop(str(scopes[2]))
                packet = {"helper": base64.b64encode(source).decode(), "authorization": {}, "prior_runs": prior_runs}
                install = Mock()
                ns.update(REMOTE_SCOPE=str(self.root / "new-run"), PRIOR_SCOPE=str(scopes[0]),
                          PREVIOUS_SCOPE=str(scopes[1]), LATEST_SCOPE=str(scopes[2]), EXPECTED=launch.sha(source),
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
    parent prompt strings, three-predecessor inventories and remote reconciliation.
    The inherited loader also exercises all legacy guard/capture/close-out tests.
    """
    path = Path(__file__).with_name("test_mic_v3_session.py")
    source = path.read_text().replace("run_reachy_mic_v3 as launch", "run_reachy_mic_v3_start as launch")
    source = source.replace("reachy_mic_health_v3_run", "reachy_mic_health_v3_start")
    source = source.replace("/run-two-pair-v3-01", "/run-two-pair-v3-03")
    source = source.replace('with patch.object(sys.stdin, "isatty", return_value=True), redirect_stdout(io.StringIO()),',
                            'with patch.object(launch, "input", side_effect=AssertionError("unexpected local start prompt"), create=True), patch.object(sys.stdin, "isatty", return_value=True), redirect_stdout(io.StringIO()),')
    module = types.ModuleType("start_session_contract")
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
