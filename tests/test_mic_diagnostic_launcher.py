"""Offline launcher tests: no real SSH, audio, USB, or robot action."""

from contextlib import redirect_stdout
import io
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts import run_reachy_mic_diagnostic as launch
from tools import reachy_mic_health as helper


def export_fixture():
    return {"schema": "reachy-mic-run-export-v1", "helper_sha256": launch.EXPECTED,
            "root": launch.REMOTE_ROOT, "run": None, "audio_exported": False,
            "deletion_performed": False, "fresh_read_only_preflight": {"mode": "READ_ONLY"}}


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="reachy-launcher-offline-")
        self.directory = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def make_authorization(self):
        launch.write_new(self.directory / "authorization.json", {"fixture": True})

    def begin(self):
        self.make_authorization()
        with patch.object(launch, "authorization", return_value={}):
            launch.begin_local(self.directory)

    def test_default_is_help_no_connection(self):
        with patch.object(launch, "run_once") as run, patch.object(launch, "collect") as collect, redirect_stdout(io.StringIO()):
            self.assertEqual(launch.main([]), 0)
        run.assert_not_called()
        collect.assert_not_called()

    def test_mode_exclusivity(self):
        with self.assertRaises(SystemExit), redirect_stdout(io.StringIO()):
            launch.main(["--run-once", "--collect-only"])

    def test_authorization_binding_uses_synthetic_private_fixture(self):
        # CI must never depend on a real operator's ignored approval records.
        project = self.directory / "project"
        (project / "tools").mkdir(parents=True)
        (project / "tools/reachy_mic_health.py").write_bytes((launch.ROOT / "tools/reachy_mic_health.py").read_bytes())
        preflights = project / "data/private/mic_preflight"
        preflights.mkdir(parents=True)
        payload = b'{"machine_checks_passed":true}'
        (preflights / launch.PREFLIGHT).write_bytes(payload)
        preflight_hash = hashlib.sha256(payload).hexdigest()
        scope = project / "data/private/mic_closeout" / launch.SESSION
        scope.mkdir(parents=True)
        approved = {"schema": "reachy-mic-operator-authorization-v1", "session": launch.SESSION,
                    "helper_sha256": launch.EXPECTED, "preflight_sha256": preflight_hash,
                    "run_limit": 1, "remote_inventory_root": launch.REMOTE_ROOT,
                    "local_inventory_scope": str(scope.resolve()),
                    "routing_and_transient_capture_approved": True, "consumer_isolation_confirmed": True,
                    "physical_setup_confirmed": True, "os_residuals_accepted": True,
                    "metadata_inventory_approved": True}
        path = scope / "authorization.json"
        path.write_text(json.dumps(approved))
        with patch.object(launch, "ROOT", project), patch.object(launch, "PREFLIGHT_HASH", preflight_hash):
            self.assertEqual(launch.authorization(scope)["run_limit"], 1)
            for field, value in (("run_limit", True), ("run_limit", 2), ("physical_setup_confirmed", False),
                                 ("local_inventory_scope", str(project)), ("helper_sha256", "changed")):
                path.write_text(json.dumps({**approved, field: value}))
                with self.subTest(field=field, value=value), self.assertRaises(RuntimeError):
                    launch.authorization(scope)
            path.write_text(json.dumps(approved))
            (preflights / launch.PREFLIGHT).write_bytes(b"changed")
            with self.assertRaises(RuntimeError):
                launch.authorization(scope)

    def test_helper_import_is_offline_and_hash_verified(self):
        namespace = launch.verified_helper(launch.ROOT / "tools/reachy_mic_health.py")
        self.assertEqual(namespace["SCHEMA"], "reachy-mic-health-v2")
        target = self.directory / "bad.py"
        target.write_bytes(b"raise Exception('must never execute')")
        with self.assertRaisesRegex(RuntimeError, "hash_changed"):
            launch.verified_helper(target)

    def test_directory_and_oversized_file_refused(self):
        with self.assertRaises(RuntimeError):
            launch.read_regular(self.directory)
        target = self.directory / "large.json"
        target.write_bytes(b"12345")
        with self.assertRaises(RuntimeError):
            launch.read_regular(target, 4)

    def test_generated_remote_sources_compile_and_modes_are_fixed(self):
        for mode in ("run", "collect"):
            source = launch.remote_source(mode)
            compile(source, "<offline-remote>", "exec")
            self.assertTrue(source.endswith("remote_main(" + repr(mode) + ")\n"))
        with self.assertRaises(ValueError):
            launch.remote_source("restart")

    def test_transport_is_interactive_only_for_run_and_never_saves_password(self):
        for mode, flag in (("run", "-t"), ("collect", "-T")):
            command = launch.ssh_command(mode)
            self.assertEqual(command[:2], ["ssh", flag])
            self.assertIn("StrictHostKeyChecking=yes", command)
            self.assertIn("ConnectionAttempts=1", command)
            self.assertLess(len(subprocess.list2cmdline(command)), 30000)
            self.assertNotIn("StrictHostKeyChecking=no", command)

    def test_durable_pending_record_blocks_every_second_attempt(self):
        self.begin()
        path = self.directory / "closeout.json"
        original = path.read_bytes()
        self.assertEqual(json.loads(original)["status"], "PENDING")
        with patch.object(launch, "authorization", return_value={}), self.assertRaises(RuntimeError):
            launch.begin_local(self.directory)
        self.assertEqual(path.read_bytes(), original)

    def test_unexpected_local_entry_blocks_before_ssh(self):
        self.make_authorization()
        (self.directory / "unexpected.wav").write_bytes(b"synthetic fixture not audio")
        with patch.object(launch, "authorization", return_value={}), self.assertRaises(RuntimeError):
            launch.begin_local(self.directory)
        self.assertFalse((self.directory / "closeout.json").exists())

    def test_missing_authorization_opens_no_ssh(self):
        runner = Mock()
        with patch.object(launch.sys.stdin, "isatty", return_value=True), self.assertRaises(OSError):
            launch.run_once(self.directory, runner)
        runner.assert_not_called()

    def test_success_invokes_one_run_then_only_read_only_collection(self):
        self.make_authorization()
        calls = []
        def runner(command, **kwargs):
            calls.append((command, kwargs))
            self.assertTrue((self.directory / "closeout.json").exists())
            if len(calls) == 1:
                self.assertEqual(command[1], "-t")
                self.assertNotIn("stdout", kwargs)
                self.assertNotIn("input", kwargs)
                return SimpleNamespace(returncode=0)
            self.assertEqual(command[1], "-T")
            return SimpleNamespace(returncode=0, stdout=json.dumps(export_fixture()).encode())
        with patch.object(launch, "authorization", return_value={}), patch.object(launch.sys.stdin, "isatty", return_value=True), redirect_stdout(io.StringIO()):
            self.assertEqual(launch.run_once(self.directory, runner), 0)
        self.assertEqual(len(calls), 2)
        bundles = list(self.directory.glob("review-*.json"))
        self.assertEqual(len(bundles), 1)
        self.assertEqual(json.loads(bundles[0].read_text())["execution_exit"]["ssh_run_exit_code"], 0)
        self.assertEqual(json.loads((self.directory / "closeout.json").read_text())["status"], "PENDING")

    def test_failed_run_still_collects_without_repeat(self):
        self.make_authorization()
        runner = Mock(side_effect=[SimpleNamespace(returncode=255), SimpleNamespace(returncode=0, stdout=json.dumps(export_fixture()).encode())])
        with patch.object(launch, "authorization", return_value={}), patch.object(launch.sys.stdin, "isatty", return_value=True), redirect_stdout(io.StringIO()):
            self.assertEqual(launch.run_once(self.directory, runner), 255)
        self.assertEqual(runner.call_count, 2)
        self.assertEqual(runner.call_args_list[1].args[0][1], "-T")

    def test_timeout_or_interrupt_remains_pending_no_automatic_second_connection(self):
        for error in (subprocess.TimeoutExpired("fixture", 300), KeyboardInterrupt(), OSError("fixture")):
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as name:
                directory = Path(name)
                launch.write_new(directory / "authorization.json", {})
                runner = Mock(side_effect=error)
                with patch.object(launch, "authorization", return_value={}), patch.object(launch.sys.stdin, "isatty", return_value=True), redirect_stdout(io.StringIO()), self.assertRaises(type(error)):
                    launch.run_once(directory, runner)
                self.assertEqual(runner.call_count, 1)
                self.assertEqual(json.loads((directory / "execution-interrupted.json").read_text())["outcome"], "UNKNOWN")
                self.assertEqual(json.loads((directory / "closeout.json").read_text())["status"], "PENDING")

    def test_collection_failure_preserves_latch_and_can_never_start_run(self):
        self.begin()
        runner = Mock(return_value=SimpleNamespace(returncode=255))
        with self.assertRaises(RuntimeError), redirect_stdout(io.StringIO()):
            launch.collect(self.directory, runner)
        self.assertEqual(runner.call_count, 1)
        self.assertEqual(runner.call_args.args[0][1], "-T")
        self.assertTrue((self.directory / "closeout.json").exists())

    def test_bad_export_and_path_escape_refused(self):
        for field, value in (("audio_exported", True), ("deletion_performed", True), ("helper_sha256", "wrong"), ("run", {"directory": launch.REMOTE_ROOT + "/../other"})):
            bundle = {**export_fixture(), field: value}
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                launch.decode_export(json.dumps(bundle).encode())
        with self.assertRaises(RuntimeError):
            launch.decode_export(b" " * (2 * 1024 * 1024 + 1))

    def test_export_unknown_files_metadata_only(self):
        (self.directory / "unexpected.wav").write_bytes(b"synthetic fixture; must not be read")
        launch.write_new(self.directory / "approval.json", {"scope": launch.ACK, "helper_sha256": launch.EXPECTED})
        original_read = launch.read_regular
        reads = []
        def watched_read(path, *args):
            reads.append(Path(path).name)
            return original_read(path, *args)
        with patch.object(launch, "read_regular", side_effect=watched_read):
            result = launch.export_records(self.directory, {"inventory": helper.inventory})
        self.assertEqual(reads, ["approval.json"])
        self.assertEqual(set(result["records"]), {"approval.json"})
        self.assertIn("unexpected.wav", [row["name"] for row in result["inventory"]])

    def test_invalid_record_not_exported_and_missing_records_visible(self):
        launch.write_new(self.directory / "result.json", {"audio_samples": [1, 2, 3]})
        result = launch.export_records(self.directory, {"inventory": helper.inventory})
        self.assertEqual(result["records"], {})
        self.assertEqual(result["record_errors"][0]["file"], "result.json")
        self.assertIn("result.json", result["missing_records"])

    def test_remote_run_refuses_nonempty_root_before_execution(self):
        (self.directory / "run-existing").mkdir()
        fake = {"require_robot_account": lambda: None, "private_directory": helper.private_directory}
        with patch.object(launch, "verified_helper", return_value=fake), patch.object(launch, "REMOTE_ROOT", str(self.directory)), patch.object(launch.os, "execv") as execute, self.assertRaises(RuntimeError):
            launch.remote_main("run")
        execute.assert_not_called()

    def test_remote_run_executes_only_pinned_helper_after_empty_root_check(self):
        fake = {"require_robot_account": lambda: None, "private_directory": helper.private_directory}
        with patch.object(launch, "verified_helper", return_value=fake), patch.object(launch, "REMOTE_ROOT", str(self.directory)), patch.object(launch.os, "execv") as execute, redirect_stdout(io.StringIO()):
            launch.remote_main("run")
        execute.assert_called_once_with(launch.PYTHON, [launch.PYTHON, "-I", "-B", launch.REMOTE, "--execute"])

    def test_remote_collect_never_executes_and_empty_root_is_not_pass(self):
        fake = {"require_robot_account": lambda: None, "private_directory": helper.private_directory, "preflight_report": lambda: {"mode": "READ_ONLY"}}
        output = io.StringIO()
        with patch.object(launch, "verified_helper", return_value=fake), patch.object(launch, "REMOTE_ROOT", str(self.directory)), patch.object(launch.os, "execv") as execute, redirect_stdout(output):
            launch.remote_main("collect")
        execute.assert_not_called()
        self.assertIsNone(json.loads(output.getvalue())["run"])


if __name__ == "__main__":
    unittest.main()
