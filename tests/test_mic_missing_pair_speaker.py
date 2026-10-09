"""Offline missing-inputs-only contracts; all capture/SSH/device calls are fakes."""
import ast
import base64
from contextlib import ExitStack, redirect_stdout
import inspect
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from scripts import run_reachy_mic_missing_pair_speaker as launch
from tools import reachy_mic_health_missing_pair_speaker as m
from tools import reachy_mic_health_missing_pair_fixed as previous


class MissingPairTests(unittest.TestCase):
    def test_missing_private_approval_stops_before_connection_or_run_record(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(launch.sys.stdin, "isatty", return_value=True):
            directory = Path(tmp) / "new-session"
            directory.mkdir()
            runner = Mock(side_effect=AssertionError("no SSH without private approval"))
            with self.assertRaises(FileNotFoundError):
                launch.run_once(directory, runner)
            runner.assert_not_called()
            self.assertEqual(list(directory.iterdir()), [])

    def test_execution_gate_body_matches_tested_candidate(self):
        def body(module):
            node = ast.parse(inspect.getsource(module.require_execution_authorization)).body[0]
            node.body = node.body[1:]  # Only the explanatory docstring differs.
            return ast.dump(node)
        self.assertEqual(body(m), body(previous))
        self.assertIs(m.EXECUTION_RELEASED, True)
        self.assertIs(previous.EXECUTION_RELEASED, False)
        self.assertEqual(m.SESSION, "missing-pair-v3-03")
        self.assertNotEqual(m.AUTHORIZATION_PATH, previous.AUTHORIZATION_PATH)

    def test_speaker_check_is_same_start_confirmation_not_new_timed_input(self):
        from tools import reachy_mic_health_missing_pair_run as spent
        self.assertTrue(m.required_authorization()["phone_speaker_output_confirmation_required_at_start"])
        invalid = dict(m.required_authorization())
        del invalid["phone_speaker_output_confirmation_required_at_start"]
        with self.assertRaises(m.Stop):
            m.validate_session_authorization(invalid)
        class RemovePrint(ast.NodeTransformer):
            def visit_Expr(self, node):
                if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "print":
                    return None
                return self.generic_visit(node)
        def executable(module):
            return ast.dump(RemovePrint().visit(ast.parse(inspect.getsource(module.execute))))
        self.assertEqual(executable(m), executable(spent))
        self.assertEqual(inspect.getsource(m.capture_pair), inspect.getsource(spent.capture_pair))
        self.assertEqual(inspect.getsource(m.RouteGuard), inspect.getsource(spent.RouteGuard))
        source = inspect.getsource(m.execute)
        self.assertIn("PHONE BUILT-IN SPEAKER", source)
        self.assertLess(source.index("PHONE BUILT-IN SPEAKER"), source.index("if input() != ACK:"))
        self.assertEqual(launch.approval_contract(launch.LOCAL)["stimulus_session_closeout_sha256"], launch.STIMULUS_RECEIPT_SHA)
        self.assertNotEqual(m.SESSION, spent.SESSION)
        self.assertNotEqual(m.AUTHORIZATION_PATH, spent.AUTHORIZATION_PATH)

    def test_only_missing_routes_and_one_use(self):
        self.assertEqual(m.PAIRS, ({m.ROUTES[0]: [3, 2], m.ROUTES[1]: [3, 3]},))
        board = m.FakeBoard()
        guard = m.RouteGuard(board, lambda _: None)
        guard.begin(0)
        self.assertEqual(board.values, m.PAIRS[0])
        self.assertEqual(guard.restore(), "ROUTES_RESTORED")
        for invalid in (0, 1, -1, True, None):
            with self.assertRaises(m.Stop):
                guard.begin(invalid)
        self.assertEqual(board.writes, [(m.ROUTES[0], [3, 2]), (m.ROUTES[1], [3, 3]),
                                       (m.ROUTES[0], [8, 0]), (m.ROUTES[1], [8, 0])])

    def test_measurement_and_recovery_unchanged_except_scope(self):
        def definitions(module):
            return {n.name: ast.dump(n, include_attributes=False)
                    for n in ast.parse(Path(module.__file__).read_text()).body
                    if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        old, new = definitions(previous), definitions(m)
        self.assertEqual(set(old), set(new))
        self.assertEqual({k for k in old if old[k] != new[k]},
                         {"require_execution_authorization", "required_authorization", "execute"})
        self.assertEqual(inspect.getsource(m.RouteGuard), inspect.getsource(previous.RouteGuard).replace(
            "pair not in (0, 1)", "pair not in range(len(PAIRS))"))
        self.assertEqual(inspect.getsource(m.capture_pair), inspect.getsource(previous.capture_pair).replace(
            '"microphones": [pair * 2, pair * 2 + 1]', '"microphones": [PAIRS[pair][key][1] for key in ROUTES]'))
        self.assertEqual((m.PAIR_LIMIT, m.RESTORE_LIMIT, m.RATE), (40.0, 5.0, 16000))
        self.assertEqual(m.capture_command(), previous.capture_command())

    def test_private_contract_binds_one_missing_pair_not_old_approval(self):
        self.assertEqual(launch.ACK, m.ACK)
        self.assertEqual(launch.sha(launch.HELPER.read_bytes()), launch.EXPECTED)
        contract = m.required_authorization()
        self.assertEqual(contract["pair_limit"], 1)
        self.assertEqual(contract["microphone_indices"], [2, 3])
        self.assertTrue(contract["physical_setup_confirmation_required_at_start"])
        for change in ({"pair_limit": 2}, {"microphone_indices": [0, 1]}, {"run_limit": True}):
            with self.assertRaises(m.Stop):
                m.validate_session_authorization({**contract, **change})
        with self.assertRaises(m.Stop):
            m.validate_session_authorization(previous.required_authorization())
        self.assertEqual(launch.approval_contract(launch.LOCAL)["last_session_closeout_sha256"], launch.LAST_RECEIPT_SHA)

    def test_old_sources_untouched(self):
        for name, want in (("tools/reachy_mic_health_v3_ready.py", "95a37ca4aac2a4c76c5e24cb311d35ded2aaacf33fc1577c95ccffe7248f95cf"),
                           ("scripts/run_reachy_mic_v3_ready.py", "8bbb67c46ae973d0b2a165a527f8413c660e542a11099532635a2c0a8b51a521")):
            self.assertEqual(launch.sha((launch.ROOT / name).read_bytes()), want)

    def exercise(self, abort=False, approve=True):
        events = []
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            directory = Path(tmp) / "runs" / "one"
            for key, value in (("RUN_ROOT", directory.parent), ("SESSION_DIRECTORY", directory)):
                stack.enter_context(patch.object(m, key, value))
            stack.enter_context(patch.object(m.sys.stdin, "isatty", return_value=True))
            stack.enter_context(patch.object(m, "require_execution_authorization"))
            stack.enter_context(patch.object(m, "protect_own_process"))
            stack.enter_context(patch.object(m, "snapshot", return_value={"helper_sha256": "fixture"}))
            stack.enter_context(patch.object(m, "input", return_value=m.ACK if approve else "wrong", create=True))
            stack.enter_context(patch.object(m, "wait_enter", side_effect=AssertionError("no second pair prompt")))
            stack.enter_context(patch.object(m, "print"))
            def guard(path):
                self.assertEqual(json.loads((path / "closeout.json").read_text())["status"], "PENDING")
                def request(action, expected, **kwargs):
                    events.append((action, kwargs.get("pair")))
                    if action == "restore":
                        m.save_json(path / "guard.json", {"restoration": "ROUTES_RESTORED"})
                return types.SimpleNamespace(request=request, close=lambda: None)
            def capture(pair, result, _):
                events.append(("capture", pair))
                result.update(microphones=[2, 3], complete=not abort, capture_exit_verified=True)
                if abort:
                    raise m.Stop("operator_deadline")
            stack.enter_context(patch.object(m, "GuardClient", side_effect=guard))
            stack.enter_context(patch.object(m, "capture_pair", side_effect=capture))
            if not approve:
                with self.assertRaisesRegex(m.Stop, "approval_not_confirmed"):
                    m.execute()
                self.assertFalse(directory.exists())
                self.assertEqual(events, [])
                return
            code = m.execute()
            result = json.loads((directory / "result.json").read_text())
            self.assertEqual(events, [("begin", 0), ("capture", 0), ("restore", None)])
            self.assertEqual(len(result["pair_results"]), 1)
            self.assertEqual(result["route_restoration"], "ROUTES_RESTORED")
            self.assertEqual(result["ordinary_file_closeout"], "CHECKED_NO_UNEXPECTED_FILES")
            self.assertEqual(code, 2 if abort else 0)

    def test_single_pair_parent_success(self):
        self.exercise()

    def test_single_pair_abort_restores_without_repeat(self):
        self.exercise(abort=True)

    def test_wrong_live_confirmation_never_routes(self):
        self.exercise(approve=False)

    def test_eight_remote_predecessors_before_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            scopes = [Path(tmp) / str(i) for i in range(8)]
            for p in scopes:
                p.mkdir()
                (p / "closeout.json").write_text("{}")
            keys = ("PRIOR_SCOPE", "PREVIOUS_SCOPE", "LATEST_SCOPE", "RECENT_SCOPE", "PRECEDING_SCOPE", "LAST_SCOPE", "REPAIRED_SCOPE", "STIMULUS_SCOPE")
            for changed in (None, *range(8)):
                ns = {}
                exec(launch.remote_source("deploy").rsplit("\nremote_deploy()", 1)[0], ns)
                fake = {"require_robot_account": Mock(), "private_directory": Mock(),
                        "pending_runs": lambda: [], "inventory": lambda p: [],
                        "preflight_report": lambda: {"machine_checks_passed": True},
                        "required_authorization": lambda: {}, "require_execution_authorization": Mock()}
                prior = {str(p): {"inventory": [], "closeout": {}} for p in scopes}
                if changed is not None:
                    prior[str(scopes[changed])]["inventory"] = [{"changed": True}]
                source = b"fixture"
                packet = {"helper": base64.b64encode(source).decode(), "authorization": {}, "prior_runs": prior}
                install = Mock()
                ns.update({key: str(p) for key, p in zip(keys, scopes)})
                ns.update(REMOTE_SCOPE=str(Path(tmp) / "new"), EXPECTED=launch.sha(source), install_exact=install,
                          remote_namespace=lambda: fake, exec=lambda code, space: space.update(fake))
                with patch.object(ns["sys"], "stdin", types.SimpleNamespace(buffer=io.BytesIO(json.dumps(packet).encode()))), redirect_stdout(io.StringIO()):
                    if changed is None:
                        ns["remote_deploy"]()
                    else:
                        with self.assertRaises(RuntimeError):
                            ns["remote_deploy"]()
                self.assertEqual(install.call_count, 2 if changed is None else 0)

    def test_eight_local_predecessors_and_latest_receipt_required(self):
        identities = (("two-pair-v2-01", "PRIOR"), ("two-pair-v3-01", "PREVIOUS"),
                      ("two-pair-v3-02", "LATEST"), ("two-pair-v3-03", "RECENT"),
                      ("two-pair-v3-04", "PRECEDING"), ("two-pair-v3-05", "LAST"),
                      ("missing-pair-v3-01", "REPAIRED"), ("missing-pair-v3-02", "STIMULUS"))
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            stack.enter_context(patch.object(launch, "ROOT", root))
            for session, prefix in identities:
                directory = root / "data/private/mic_closeout" / session
                directory.mkdir(parents=True)
                closed = {"status": "CHECKED_NO_UNEXPECTED_FILES", "restoration_verified": True,
                          "capture_exit_verified": True, "local_scope": str(directory.resolve())}
                (directory / "closeout.json").write_text(json.dumps(closed))
                receipt = directory / "closeout-final-v1.json"
                receipt.write_text("{}")
                record = {"local_after_check": {"inventory_at_check": launch.local_inventory(directory)},
                          "remote_closeout": {**closed, "scope": getattr(launch, prefix + "_SCOPE")},
                          "remote_final_inventory": [], "remote_after_inventory": []}
                receipt.write_text(json.dumps(record))
                stack.enter_context(patch.object(launch, prefix + "_RECEIPT_SHA", launch.sha(receipt.read_bytes())))
            preflight = root / "data/private/mic_v3_preflight/two-pair-v2-01/report.json"
            preflight.parent.mkdir(parents=True)
            preflight.write_bytes(b"fixture")
            candidate = root / "tools/reachy_mic_health_v3.py"
            candidate.parent.mkdir()
            candidate.write_bytes(b"fixture")
            stack.enter_context(patch.object(launch, "PRIOR_PREFLIGHT_SHA", launch.sha(b"fixture")))
            stack.enter_context(patch.object(launch, "CANDIDATE_SHA", launch.sha(b"fixture")))
            fixed = root / "tools/reachy_mic_health_missing_pair_fixed.py"
            fixed.write_bytes(b"fixture")
            reconciliation = root / "data/private/mic_missing_pair_reconciliation/missing-pair-v3-01/report.json"
            reconciliation.parent.mkdir(parents=True)
            reconciliation.write_bytes(b"fixture")
            stack.enter_context(patch.object(launch, "ADAPTER_CANDIDATE_SHA", launch.sha(b"fixture")))
            stack.enter_context(patch.object(launch, "RECONCILIATION_SHA", launch.sha(b"fixture")))
            self.assertEqual(len(launch.prior_evidence()), 8)
            with patch.object(launch, "STIMULUS_RECEIPT_SHA", "changed"):
                with self.assertRaisesRegex(RuntimeError, "receipt_changed"):
                    launch.prior_evidence()
            extra = root / "data/private/mic_closeout/unknown-abort"
            extra.mkdir()
            (extra / "closeout.json").write_text('{"status":"PENDING"}')
            with self.assertRaisesRegex(RuntimeError, "unresolved"):
                launch.prior_evidence()


def load_tests(loader, standard_tests, pattern):
    # Reuse capture, numeric, guard and session transport cases with fake I/O.
    path = Path(__file__).with_name("test_mic_health.py")
    source = path.read_text().replace("from tools import reachy_mic_health as m", "from tools import reachy_mic_health_missing_pair_speaker as m")
    source = source.replace("value == [3, 1]", "value == [3, 3]").replace("value == [3, 0]", "value == [3, 2]")
    source = source.replace('messages = [{"action": "begin", "pair": 0}, {"action": "restore"},\n                    {"action": "begin", "pair": 1}, {"action": "restore"}]',
                            'messages = [{"action": "begin", "pair": 0}, {"action": "restore"}]')
    source = source.replace('self.assertEqual(len(self.board.writes), 8)', 'self.assertEqual(len(self.board.writes), 4)')
    module = types.ModuleType("missing_pair_capture_guard")
    module.__file__ = str(path)
    exec(compile(source, str(path), "exec"), module.__dict__)
    delattr(module.TestGuard, "test_two_pairs_and_restore")  # Replaced with exact one-pair write test above.
    for name in ("TestStats", "TestGuard", "TestCapture"):
        standard_tests.addTests(loader.loadTestsFromTestCase(getattr(module, name)))
    class LabelsAndInput(module.TestCapture):
        def test_labels_are_actual_indices_not_loop_ordinal(self):
            result = self.run_capture([("pcm", self.pcm(5)), ("operator", None), ("pcm", self.pcm(12))])
            self.assertEqual(result["microphones"], [2, 3])
        def test_extra_enter_during_playback_aborts_and_exits(self):
            with self.assertRaisesRegex(m.Stop, "unexpected_operator_input"):
                self.run_capture([("pcm", self.pcm(5)), ("operator", None), ("pcm", self.pcm(3)), ("operator", None)], operator="\n\n")
            self.assertTrue(self.result["capture_exit_verified"])
            self.assertEqual(self.result["partial_phase"]["phase"], "playback")
    for name in ("test_labels_are_actual_indices_not_loop_ordinal", "test_extra_enter_during_playback_aborts_and_exits"):
        standard_tests.addTest(LabelsAndInput(name))
    path = Path(__file__).with_name("test_mic_v3_session.py")
    source = path.read_text().replace("run_reachy_mic_v3 as launch", "run_reachy_mic_missing_pair_speaker as launch")
    source = source.replace("reachy_mic_health_v3_run as m", "reachy_mic_health_missing_pair_speaker as m").replace("/run-two-pair-v3-01", "/run-missing-pair-v3-03")
    module = types.ModuleType("missing_pair_session_contract")
    module.__file__ = str(path)
    exec(compile(source, str(path), "exec"), module.__dict__)
    for name in ("test_all_measurement_and_recovery_definitions_unchanged_from_candidate", "test_parent_flow_only_adds_authorization_and_fixed_one_shot_scope"):
        delattr(module.SessionHelperTests, name)
    for name in ("test_generated_deployment_blocks_on_old_scope_drift_and_never_starts_capture", "test_local_prior_missing_pending_changed_and_unexpected_records_refuse"):
        delattr(module.SessionLauncherTests, name)
    for name in ("SessionHelperTests", "SessionLauncherTests"):
        standard_tests.addTests(loader.loadTestsFromTestCase(getattr(module, name)))
    # Direct USBBoard tests are mandatory for the actual released session too.
    path = Path(__file__).with_name("test_mic_missing_pair_fixed.py")
    source = path.read_text().replace("reachy_mic_health_missing_pair_fixed as m", "reachy_mic_health_missing_pair_speaker as m")
    source = source.replace('{"USBBoard", "serve_guard", "require_execution_authorization"}',
                            '{"USBBoard", "serve_guard", "require_execution_authorization", "required_authorization", "execute"}')
    module = types.ModuleType("corrected_missing_pair_actual_adapter")
    module.__file__ = str(path)
    exec(compile(source, str(path), "exec"), module.__dict__)
    delattr(module.AdapterRepairTests, "test_candidate_execute_and_guard_stop_before_hardware_and_files")
    standard_tests.addTests(loader.loadTestsFromTestCase(module.AdapterRepairTests))
    return standard_tests


if __name__ == "__main__":
    unittest.main()
