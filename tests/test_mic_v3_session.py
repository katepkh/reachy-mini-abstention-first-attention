"""Synthetic successor tests. Never connect to Reachy or open real media."""

import ast
from contextlib import ExitStack, redirect_stdout
import hashlib
import inspect
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from scripts import run_reachy_mic_v3 as launch
from tools import reachy_mic_health_v3 as candidate
from tools import reachy_mic_health_v3_run as m


def preflight(ok=True):
    return {"schema": launch.SCHEMA, "helper_sha256": launch.EXPECTED, "mode": "READ_ONLY",
            "execution_authorized": False, "consumer_isolation_verified": False,
            "checks": [{"name": str(i), "ok": ok} for i in range(17)], "machine_checks_passed": ok}


def bundle():
    return {"schema": "reachy-mic-session-export-v1", "session": launch.SESSION,
            "helper_sha256": launch.EXPECTED, "root": launch.REMOTE_ROOT, "run": None,
            "audio_exported": False, "deletion_performed": False}


class SessionHelperTests(unittest.TestCase):
    def test_candidate_preserved_and_successor_pinned(self):
        self.assertEqual(hashlib.sha256(Path(candidate.__file__).read_bytes()).hexdigest(), launch.CANDIDATE_SHA)
        self.assertFalse(candidate.EXECUTION_RELEASED)
        self.assertEqual(hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest(), launch.EXPECTED)
        self.assertTrue(m.EXECUTION_REQUIRES_PRIVATE_AUTHORIZATION)

    def test_all_measurement_and_recovery_definitions_unchanged_from_candidate(self):
        def definitions(module):
            return {node.name: ast.dump(node, include_attributes=False)
                    for node in ast.parse(Path(module.__file__).read_text()).body
                    if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
        original, current = definitions(candidate), definitions(m)
        changed = {name for name in original if original[name] != current[name]}
        self.assertEqual(changed, {"execute", "guard_main", "main"})
        self.assertEqual(set(current) - set(original), {"required_authorization", "validate_session_authorization",
                         "require_execution_authorization", "create_session_directory"})

    def test_parent_flow_only_adds_authorization_and_fixed_one_shot_scope(self):
        successor = inspect.getsource(m.execute).replace("    require_execution_authorization()\n", "")
        successor = successor.replace("    directory = create_session_directory()",
            '    directory = Path(tempfile.mkdtemp(prefix="run-", dir=RUN_ROOT))')
        successor = successor.replace('    print("Session " + SESSION + "; metadata-only inventory: " + str(SESSION_DIRECTORY))',
            '    print("Metadata-only inventory: each new private run directory under " + str(RUN_ROOT))')
        self.assertEqual(successor, inspect.getsource(candidate.execute))

    def test_exact_typed_session_authorization(self):
        valid = m.required_authorization()
        self.assertEqual(m.validate_session_authorization(valid), valid)
        for key, value in (("run_limit", True), ("pair_limit", 3), ("helper_sha256", "wrong"),
                ("session", "two-pair-v2-01"), ("physical_setup_confirmed", False),
                ("remote_scope", "/other"), ("os_residuals_accepted", 1)):
            with self.subTest(key=key), self.assertRaises(m.Stop):
                m.validate_session_authorization({**valid, key: value})
        for bad in (None, [], {}, {**valid, "extra": "not allowed"}):
            with self.assertRaises(m.Stop):
                m.validate_session_authorization(bad)

    def test_windows_prepared_authorization_matches_robot_posix_scope(self):
        approved = launch.approval_contract(launch.LOCAL)
        self.assertEqual(approved["remote_scope"], approved["session_authorization"]["remote_scope"])
        self.assertEqual(approved["session_authorization"]["remote_scope"],
                         "/home/pollen/reachy-mic-health-runs-v2/run-two-pair-v3-01")
        from pathlib import PureWindowsPath, PurePosixPath
        for path_type in (PureWindowsPath, PurePosixPath):
            with patch.object(m, "SESSION_DIRECTORY", path_type(launch.REMOTE_SCOPE)):
                self.assertEqual(m.required_authorization(), approved["session_authorization"])

    def test_missing_authorization_before_snapshot_or_guard(self):
        with patch.object(m.sys.stdin, "isatty", return_value=True), \
                patch.object(m, "require_execution_authorization", side_effect=m.Stop("missing_approval")), \
                patch.object(m, "snapshot") as snap, patch.object(m, "GuardClient") as guard:
            with self.assertRaisesRegex(m.Stop, "missing_approval"):
                m.execute()
        snap.assert_not_called()
        guard.assert_not_called()

    def test_actual_missing_authorization_file(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(m, "require_robot_account"), \
                patch.object(m, "AUTHORIZATION_PATH", Path(directory) / "absent.json"), \
                self.assertRaises(FileNotFoundError):
            m.require_execution_authorization()

    def test_guard_failure_reports_authorization_stage_without_hardware(self):
        output = io.StringIO()
        with patch.object(m, "require_execution_authorization", side_effect=m.Stop("missing_approval")), \
                patch.object(m, "USBBoard") as board:
            self.assertEqual(m.guard_entry(str(m.SESSION_DIRECTORY), output), 2)
        self.assertEqual(json.loads(output.getvalue())["stage"], "session_authorization")
        board.assert_not_called()

    def test_guard_refuses_other_run_even_with_approval(self):
        with patch.object(m, "require_execution_authorization"), patch.object(m, "platform_checks") as checks, \
                self.assertRaisesRegex(m.Stop, "wrong_session"):
            m.guard_main("/other/run")
        checks.assert_not_called()

    def test_remote_fixed_directory_exclusive_even_if_finished_or_empty(self):
        with tempfile.TemporaryDirectory() as root, patch.object(m, "SESSION_DIRECTORY", Path(root) / "run-test"):
            first = m.create_session_directory()
            with self.assertRaises(FileExistsError):
                m.create_session_directory()
            self.assertTrue(first.is_dir())

    def test_missing_guard_journal_retains_structured_error(self):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory) / "runs"
            for name, value in (("RUN_ROOT", root), ("SESSION_DIRECTORY", root / "run-test")):
                stack.enter_context(patch.object(m, name, value))
            stack.enter_context(patch.object(m, "require_execution_authorization"))
            stack.enter_context(patch.object(m.sys.stdin, "isatty", return_value=True))
            stack.enter_context(patch.object(m, "snapshot", return_value={"helper_sha256": "fixture"}))
            stack.enter_context(patch.object(m, "protect_own_process"))
            stack.enter_context(patch.object(m, "input", return_value=m.ACK, create=True))
            stack.enter_context(patch.object(m, "print"))
            stack.enter_context(patch.object(m, "GuardClient", side_effect=m.GuardFailure({"stage": "usb", "errno": 13})))
            capture = stack.enter_context(patch.object(m, "capture_pair"))
            self.assertEqual(m.execute(), 2)
            result = json.loads((m.SESSION_DIRECTORY / "result.json").read_text())
            self.assertEqual(result["failure_details"]["details"]["errno"], 13)
            self.assertEqual(result["ordinary_file_closeout"], "PENDING")
            capture.assert_not_called()


class SessionLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mic-session-offline-")
        self.directory = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def fixture_approval(self):
        approved = launch.approval_contract(self.directory)
        (self.directory / "authorization.json").write_text(json.dumps(approved))
        return approved

    def started(self):
        self.fixture_approval()
        with patch.object(launch, "prior_evidence", return_value={}):
            launch.begin_local(self.directory)

    def test_default_no_connection(self):
        with patch.object(launch, "run_once") as run, patch.object(launch, "collect") as collect, redirect_stdout(io.StringIO()):
            self.assertEqual(launch.main([]), 0)
        run.assert_not_called()
        collect.assert_not_called()

    def test_fresh_approval_required_no_network(self):
        runner = Mock()
        with patch.object(sys.stdin, "isatty", return_value=True), self.assertRaises(OSError):
            launch.run_once(self.directory, runner)
        runner.assert_not_called()

    def test_approval_binds_launcher_helper_scope_dependencies_and_types(self):
        approved = self.fixture_approval()
        with patch.object(launch, "prior_evidence", return_value={}):
            self.assertEqual(launch.authorization(self.directory), approved)
            for key, value in (("run_limit", True), ("launcher_sha256", "wrong"), ("deployment_approved", False),
                               ("local_scope", str(self.directory.parent)), ("transport_dependencies", {})):
                (self.directory / "authorization.json").write_text(json.dumps({**approved, key: value}))
                with self.subTest(key=key), self.assertRaises(RuntimeError):
                    launch.authorization(self.directory)

    def test_local_latch_prevents_repeat_and_preserves_record(self):
        self.started()
        original = (self.directory / "closeout.json").read_bytes()
        with patch.object(launch, "prior_evidence", return_value={}), self.assertRaises(RuntimeError):
            launch.begin_local(self.directory)
        self.assertEqual((self.directory / "closeout.json").read_bytes(), original)

    def test_unknown_entry_refused_without_opening_it(self):
        self.fixture_approval()
        (self.directory / "unexpected.wav").write_bytes(b"synthetic-not-audio")
        with patch.object(launch, "prior_evidence", return_value={}), self.assertRaises(RuntimeError):
            launch.begin_local(self.directory)
        self.assertFalse((self.directory / "closeout.json").exists())

    def test_transport_modes_compile_are_short_and_no_password_capture(self):
        for mode in ("deploy", "run", "collect"):
            source = launch.remote_source(mode)
            compile(source, "<session-remote>", "exec")
            namespace = {}
            # Exercise all generated definition/default bindings, not only compilation.
            exec(source.rsplit("\nremote_", 1)[0], namespace)
            self.assertEqual(namespace["EXPECTED"], launch.EXPECTED)
            command = launch.ssh_command(mode)
            self.assertEqual(command[1], "-t" if mode == "run" else "-T")
            self.assertIn("StrictHostKeyChecking=yes", command)
            self.assertLess(len(subprocess.list2cmdline(command)), 30000)
        with self.assertRaises(ValueError):
            launch.remote_source("retry")

    def test_changed_or_failed_preflight_rejected(self):
        self.assertEqual(launch.validate_preflight(json.dumps(preflight()).encode())["mode"], "READ_ONLY")
        for changes in ({"checks": []}, {"machine_checks_passed": False}, {"helper_sha256": "wrong"},
                        {"execution_authorized": True}, {"checks": [{"name": "x", "ok": 1}] * 17}):
            with self.assertRaises(RuntimeError):
                launch.validate_preflight(json.dumps({**preflight(), **changes}).encode())

    def run_fixture(self, runner):
        self.fixture_approval()
        with patch.object(sys.stdin, "isatty", return_value=True), redirect_stdout(io.StringIO()), \
                patch.object(launch, "prior_evidence", return_value={"remote_final_inventory": [], "remote_closeout": {}}):
            return launch.run_once(self.directory, runner)

    def test_success_deploy_run_collect_exactly_once_and_pending_review(self):
        def runner(command, **kwargs):
            self.assertTrue((self.directory / "closeout.json").exists())
            if "input" in kwargs:
                packet = json.loads(kwargs["input"])
                self.assertEqual(packet["authorization"], m.required_authorization())
                return types.SimpleNamespace(returncode=0, stdout=json.dumps(preflight()).encode())
            if command[1] == "-t":
                self.assertNotIn("stdout", kwargs)
                return types.SimpleNamespace(returncode=0)
            return types.SimpleNamespace(returncode=0, stdout=json.dumps(bundle()).encode())
        wrapped = Mock(side_effect=runner)
        self.assertEqual(self.run_fixture(wrapped), 0)
        self.assertEqual(wrapped.call_count, 3)
        self.assertEqual(json.loads((self.directory / "closeout.json").read_text())["status"], "PENDING")
        self.assertEqual(len(list(self.directory.glob("review-*.json"))), 1)

    def test_failed_preflight_never_opens_interactive_run(self):
        runner = Mock(return_value=types.SimpleNamespace(returncode=0, stdout=json.dumps(preflight(False)).encode()))
        with self.assertRaises(RuntimeError):
            self.run_fixture(runner)
        self.assertEqual(runner.call_count, 1)
        self.assertTrue((self.directory / "deployment.json").exists())
        self.assertEqual(json.loads((self.directory / "interrupted.json").read_text())["stage"], "deployment_preflight")

    def test_execution_disconnect_retains_latch_no_second_attempt(self):
        runner = Mock(side_effect=[types.SimpleNamespace(returncode=0, stdout=json.dumps(preflight()).encode()),
                                   subprocess.TimeoutExpired("synthetic", 300)])
        with self.assertRaises(subprocess.TimeoutExpired):
            self.run_fixture(runner)
        self.assertEqual(runner.call_count, 2)
        self.assertEqual(json.loads((self.directory / "interrupted.json").read_text())["stage"], "interactive_execution")
        self.assertEqual(json.loads((self.directory / "closeout.json").read_text())["status"], "PENDING")

    def test_deployment_timeout_or_interrupt_has_no_retry(self):
        for error in (subprocess.TimeoutExpired("synthetic", 120), KeyboardInterrupt(), OSError("synthetic")):
            with tempfile.TemporaryDirectory() as root, patch.object(self, "directory", Path(root)):
                runner = Mock(side_effect=error)
                with self.assertRaises(type(error)):
                    self.run_fixture(runner)
                self.assertEqual(runner.call_count, 1)
                self.assertTrue((self.directory / "closeout.json").exists())

    def test_collection_only_scoped_and_cannot_clear_latch(self):
        self.started()
        original = (self.directory / "closeout.json").read_bytes()
        runner = Mock(return_value=types.SimpleNamespace(returncode=0, stdout=json.dumps(bundle()).encode()))
        with redirect_stdout(io.StringIO()):
            launch.collect(self.directory, runner)
        self.assertEqual(runner.call_args.args[0], launch.ssh_command("collect"))
        self.assertEqual((self.directory / "closeout.json").read_bytes(), original)

    def test_collection_rejects_wrong_scope_without_recording_clean_result(self):
        self.started()
        bad = {**bundle(), "run": {"directory": launch.PRIOR_SCOPE}}
        runner = Mock(return_value=types.SimpleNamespace(returncode=0, stdout=json.dumps(bad).encode()))
        with redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
            launch.collect(self.directory, runner)
        self.assertFalse(list(self.directory.glob("review-*.json")))

    def test_generated_export_includes_structured_failures_unknown_media_metadata_only(self):
        source = launch.remote_source("collect").rsplit("\nremote_collect()", 1)[0]
        ns = {}
        exec(source, ns)
        (self.directory / "unexpected.raw").write_bytes(b"fixture-not-audio")
        (self.directory / "result.json").write_text(json.dumps({"schema": launch.SCHEMA,
            "helper_sha256": launch.EXPECTED, "failure_details": {"stage": "usb", "errno": 13}}))
        reader = Mock(wraps=ns["read_regular"])
        ns["read_regular"] = reader
        result = ns["export_records"](self.directory, {"inventory": m.inventory})
        self.assertEqual([Path(call.args[0]).name for call in reader.call_args_list], ["result.json"])
        self.assertIn("failure_details", result["records"]["result.json"])
        self.assertIn("unexpected.raw", [row["name"] for row in result["inventory"]])

    def test_remote_run_blocks_spent_or_pending_before_exec(self):
        scope = self.directory / "run-new"
        fake = {"require_execution_authorization": Mock(), "private_directory": Mock(), "pending_runs": lambda: ["pending"]}
        with patch.object(launch, "remote_namespace", return_value=fake), patch.object(launch, "REMOTE_SCOPE", str(scope)), \
                patch.object(launch.os, "execv") as execute:
            with self.assertRaisesRegex(RuntimeError, "unresolved"):
                launch.remote_run()
            scope.mkdir()
            fake["pending_runs"] = lambda: []
            with self.assertRaisesRegex(RuntimeError, "spent"):
                launch.remote_run()
            execute.assert_not_called()

    def test_remote_run_dispatches_only_session_helper(self):
        fake = {"require_execution_authorization": Mock(), "private_directory": Mock(), "pending_runs": lambda: []}
        with patch.object(launch, "remote_namespace", return_value=fake), \
                patch.object(launch, "REMOTE_SCOPE", str(self.directory / "absent")), patch.object(launch.os, "execv") as execute:
            launch.remote_run()
        execute.assert_called_once_with(launch.PYTHON, [launch.PYTHON, "-I", "-B", launch.REMOTE, "--execute"])
        fake["require_execution_authorization"].assert_called_once()

    def test_generated_deployment_blocks_on_old_scope_drift_and_never_starts_capture(self):
        for changed, passed in ((True, True), (False, False), (False, True)):
            with self.subTest(changed=changed, passed=passed):
                ns = {}
                exec(launch.remote_source("deploy").rsplit("\nremote_deploy()", 1)[0], ns)
                target = self.directory / "new-run"
                prior = self.directory / "prior"
                prior.mkdir(exist_ok=True)
                (prior / "closeout.json").write_text("{}")
                fake_source = b"fixture_verified_namespace"
                fake_helper = {"require_robot_account": Mock(), "private_directory": Mock(),
                    "pending_runs": lambda: [], "inventory": lambda p: [], "preflight_report": lambda: preflight(passed),
                    "required_authorization": lambda: {}, "require_execution_authorization": Mock()}
                packet = {"helper": __import__("base64").b64encode(fake_source).decode(), "authorization": {},
                          "prior_inventory": [{"changed": True}] if changed else [], "prior_closeout": {}}
                install = Mock()
                def fake_exec(code, space):
                    space.update(fake_helper)
                ns.update(REMOTE_SCOPE=str(target), PRIOR_SCOPE=str(prior), EXPECTED=launch.sha(fake_source),
                          install_exact=install, remote_namespace=lambda: fake_helper, exec=fake_exec)
                with patch.object(ns["sys"], "stdin", types.SimpleNamespace(buffer=io.BytesIO(json.dumps(packet).encode()))), \
                        patch.object(ns["os"], "execv") as execute, redirect_stdout(io.StringIO()):
                    if changed:
                        with self.assertRaisesRegex(RuntimeError, "closeout_changed"):
                            ns["remote_deploy"]()
                    else:
                        ns["remote_deploy"]()
                execute.assert_not_called()
                self.assertEqual(install.call_count, 0 if changed else 2 if passed else 1)
                self.assertEqual(fake_helper["require_execution_authorization"].call_count, int(passed and not changed))

    def test_local_prior_missing_pending_changed_and_unexpected_records_refuse(self):
        project = self.directory / "project"
        root = project / "data/private/mic_closeout"
        prior = root / "two-pair-v2-01"
        prior.mkdir(parents=True)
        state = {"status": "CHECKED_NO_UNEXPECTED_FILES", "restoration_verified": True,
                 "capture_exit_verified": True, "local_scope": str(prior.resolve())}
        (prior / "closeout.json").write_text(json.dumps(state))
        receipt_path = prior / "closeout-final-v1.json"
        receipt_path.write_text("{}")
        receipt = {"local_after_check": {"inventory_at_check": launch.local_inventory(prior)}}
        receipt_path.write_text(json.dumps(receipt))
        preflight_path = project / "data/private/mic_v3_preflight/two-pair-v2-01/report.json"
        preflight_path.parent.mkdir(parents=True)
        preflight_path.write_bytes(b"fixture")
        tools = project / "tools"
        tools.mkdir()
        (tools / "reachy_mic_health_v3.py").write_bytes(b"fixture")
        with patch.object(launch, "ROOT", project), patch.object(launch, "PRIOR_RECEIPT_SHA", launch.sha(receipt_path.read_bytes())), \
                patch.object(launch, "PRIOR_PREFLIGHT_SHA", launch.sha(b"fixture")), \
                patch.object(launch, "CANDIDATE_SHA", launch.sha(b"fixture")):
            self.assertEqual(launch.prior_evidence(), receipt)
            extra = root / "known-interrupted"
            extra.mkdir()
            with self.assertRaises(FileNotFoundError):
                launch.prior_evidence()
            (extra / "closeout.json").write_text(json.dumps({"status": "PENDING"}))
            with self.assertRaisesRegex(RuntimeError, "unresolved"):
                launch.prior_evidence()
            (extra / "closeout.json").write_text(json.dumps({**state, "local_scope": str(extra.resolve())}))
            (prior / "unexpected.wav").write_bytes(b"fixture-not-audio")
            with self.assertRaisesRegex(RuntimeError, "inventory_changed"):
                launch.prior_evidence()

    def test_failed_execution_collects_evidence_but_never_retries(self):
        runner = Mock(side_effect=[types.SimpleNamespace(returncode=0, stdout=json.dumps(preflight()).encode()),
                                   types.SimpleNamespace(returncode=255),
                                   types.SimpleNamespace(returncode=0, stdout=json.dumps(bundle()).encode())])
        self.assertEqual(self.run_fixture(runner), 255)
        self.assertEqual(runner.call_count, 3)
        self.assertEqual(runner.call_args_list[2].args[0], launch.ssh_command("collect"))


def load_tests(loader, standard_tests, pattern):
    """Re-run legacy synthetic behavior; replace only new session gates with fixtures."""
    for name in ("test_mic_health.py", "test_mic_health_v2.py"):
        path = Path(__file__).with_name(name)
        source = path.read_text().replace("from tools import reachy_mic_health as m",
                                         "from tools import reachy_mic_health_v3_run as m")
        marker = '            stack.enter_context(patch.object(m, "RUN_ROOT", directory))'
        source = source.replace(marker, marker + '\n            stack.enter_context(patch.object(m, "SESSION_DIRECTORY", directory / "run-test"))'
                               + '\n            stack.enter_context(patch.object(m, "require_execution_authorization"))')
        module = types.ModuleType("session_contract_" + path.stem)
        module.__file__ = str(path)
        exec(compile(source, str(path), "exec"), module.__dict__)
        standard_tests.addTests(loader.loadTestsFromModule(module))
    return standard_tests


if __name__ == "__main__":
    unittest.main()
