"""Offline failure-path tests. No SSH, USB, robot or audio is opened."""

import ast
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import stat
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts import read_reachy_mic_startup as launch
from tools import reachy_mic_startup_probe as probe


def events(stream):
    return [json.loads(line) for line in stream.getvalue().splitlines()]


class ReadOnlyUSBTests(unittest.TestCase):
    def board(self, response=b"\x00\x08\x00"):
        board = object.__new__(probe.ReadOnlyUSB)
        board.device = Mock()
        board.device.ctrl_transfer.return_value = response
        board.attempted = set()
        board.util = Mock()
        return board

    def test_only_two_fixed_in_requests_and_500ms_timeout(self):
        board = self.board()
        for route in probe.ROUTES:
            self.assertEqual(board.read_route(route)["values"], [8, 0])
        self.assertEqual([call.args for call in board.device.ctrl_transfer.call_args_list],
                         [(0xC0, 0, 143, 35, 3, 500), (0xC0, 0, 147, 35, 3, 500)])
        for route in (probe.ROUTES[0], "VERSION", "SAVE_CONFIGURATION"):
            with self.assertRaises(probe.ProbeError):
                board.read_route(route)
        self.assertEqual(board.device.ctrl_transfer.call_count, 2)

    def test_busy_code_is_saved_without_retry(self):
        board = self.board(b"\x40\x00\x00")
        value = board.read_route(probe.ROUTES[0])
        self.assertEqual(value["status_byte"], 64)
        self.assertFalse(value["v2_read_would_accept"])
        self.assertIsNone(value["values"])
        board.device.ctrl_transfer.assert_called_once()

    def test_short_response_is_reported_not_misdecoded(self):
        for response in (b"", b"\x00", b"\x00\x08"):
            value = self.board(response).read_route(probe.ROUTES[0])
            self.assertFalse(value["v2_read_would_accept"])
            self.assertIsNone(value["values"])

    def test_failed_read_cannot_be_retried(self):
        board = self.board()
        board.device.ctrl_transfer.side_effect = PermissionError(13, "private error")
        with self.assertRaises(PermissionError):
            board.read_route(probe.ROUTES[0])
        with self.assertRaises(probe.ProbeError):
            board.read_route(probe.ROUTES[0])
        board.device.ctrl_transfer.assert_called_once()

    def test_close_only_disposes_own_handle(self):
        board = self.board()
        board.close()
        board.util.dispose_resources.assert_called_once_with(board.device)
        board.device.reset.assert_not_called()
        board.device.detach_kernel_driver.assert_not_called()

    def test_enumeration_requires_one_matching_board(self):
        for devices in ([], [Mock(), Mock()]):
            board = self.board()
            board.core, board.backend = Mock(), Mock()
            board.core.find.return_value = devices
            with self.assertRaises(probe.ProbeError):
                board.enumerate()
            self.assertEqual(board.core.find.call_args.kwargs["idVendor"], 0x38FB)
            self.assertEqual(board.core.find.call_args.kwargs["idProduct"], 0x1001)


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.stream = io.StringIO()
        self.usb = Mock()
        self.usb.enumerate.return_value = {"matching_devices": 1}
        self.usb.read_route.return_value = {"status_byte": 0, "values": [8, 0], "v2_read_would_accept": True}
        self.usb.close.return_value = None
        self.instance = probe.Probe(self.stream, lambda: self.usb)
        self.helper = {"inspect_platform": Mock(return_value=([{"ok": True}], None)),
                       "inventory": Mock(return_value=[])}
        self.baseline = {"fixture": "baseline"}

    def collect(self, *, checks=None, snapshot=None, lock=None):
        if checks is not None:
            self.helper["inspect_platform"].return_value = (checks, None)
        with patch.object(probe, "load_helper", return_value=self.helper), \
             patch.object(probe, "validate_scope", return_value=(self.baseline, [])), \
             patch.object(probe, "inspect_lock", return_value={"owners": []} if lock is None else lock), \
             patch.object(self.instance, "snapshot", return_value=self.baseline if snapshot is None else snapshot):
            self.instance.collect(Path("fixture-run"))
        return events(self.stream)

    def test_happy_probe_never_authorizes_execution_or_closes_failed_run(self):
        result = self.collect()
        self.assertEqual(self.usb.read_route.call_count, 2)
        self.usb.close.assert_called_once()
        self.assertTrue(all(row["execution_authorized"] is False for row in result))
        self.assertEqual(result[-1]["closeout_status"], "PENDING")
        self.assertFalse(result[-1]["guard_started"])
        self.assertFalse(result[-1]["original_exception_recovered"])
        self.helper["inspect_platform"].assert_called_with(Path("fixture-run"))

    def test_platform_blocker_skips_usb_reads_but_keeps_after_checks(self):
        result = self.collect(checks=[{"ok": False, "reason": "motor_mode_not_verified_disabled"}])
        self.usb.enumerate.assert_not_called()
        self.usb.read_route.assert_not_called()
        self.assertIn("robot_state_after", [row.get("stage") for row in result])

    def test_baseline_drift_skips_usb(self):
        self.collect(snapshot={"changed": True})
        self.usb.enumerate.assert_not_called()

    def test_existing_guard_owner_skips_usb_without_changing_lock(self):
        self.collect(lock={"owners": [123]})
        self.usb.enumerate.assert_not_called()

    def test_usb_exception_keeps_errno_and_runs_after_checks(self):
        self.usb.read_route.side_effect = OSError(13, "do not export secret")
        result = self.collect()
        failures = [row for row in result if row.get("status") == "unavailable"]
        self.assertEqual(failures[0]["errno"], 13)
        self.assertEqual(failures[0]["stage"], "usb_read_AUDIO_MGR_OP_L")
        self.assertNotIn("secret", self.stream.getvalue())
        self.assertEqual(result[-1]["event"], "finished")
        self.usb.close.assert_called_once()

    def test_missing_dependency_retained_with_stage(self):
        def missing():
            raise ModuleNotFoundError("private message", name="libusb_package")
        self.instance.usb_factory = missing
        result = self.collect()
        error = next(row for row in result if row.get("missing_module"))
        self.assertEqual(error["stage"], "usb_dependencies_and_backend")
        self.assertEqual(error["missing_module"], "libusb_package")
        self.assertNotIn("private message", self.stream.getvalue())
        self.assertIn("baseline_after", [row.get("stage") for row in result])

    def test_helper_identity_failure_stops_before_usb_or_scope(self):
        with patch.object(probe, "load_helper", side_effect=probe.ProbeError("helper_hash_changed")), \
             patch.object(probe, "validate_scope") as scope:
            self.instance.collect(Path("fixture"))
        scope.assert_not_called()
        self.usb.enumerate.assert_not_called()
        self.assertEqual(events(self.stream)[-1]["unavailable_stages"], ["helper_identity_and_account"])

    def test_started_event_survives_stage_failure(self):
        self.instance.stage("fixture", lambda: 1 / 0)
        result = events(self.stream)
        self.assertEqual(result[0]["event"], "stage_started")
        self.assertEqual(result[1]["error_type"], "ZeroDivisionError")

    def test_expired_budget_does_not_skip_handle_close(self):
        self.instance.deadline = 0
        action = Mock()
        self.instance.stage("read", action)
        action.assert_not_called()
        self.instance.stage("close", self.usb.close, closing=True)
        self.usb.close.assert_called_once()


class ScopeTests(unittest.TestCase):
    def test_scope_is_exact_failed_directory_and_pending_records(self):
        root = Path("fixture")
        directory = root / "run-example"
        baseline = {"helper_sha256": probe.EXPECTED, "asoundrc_sha256": "a", "mixer_sha256": "b",
                    "parameters": {}, "privacy_profile": "fixture"}
        records = {
            "baseline.json": baseline,
            "approval.json": {"helper_sha256": probe.EXPECTED, "scope": "fixture ACK"},
            "result.json": {"helper_sha256": probe.EXPECTED, "schema": "reachy-mic-health-v2",
                            "reason": "guard_EOF", "pair_results": [], "status": "RESTORATION_UNVERIFIED"},
            "closeout.json": {"helper_sha256": probe.EXPECTED, "schema": "reachy-mic-closeout-v1",
                              "scope": str(directory), "status": "PENDING"}}
        helper = {"private_directory": Mock(), "ACK": "fixture ACK",
                  "inventory": Mock(return_value=[{"name": name, "kind": "file"} for name in records])}
        with patch.object(probe, "RUN_ROOT", root), \
             patch.object(probe, "read_regular", side_effect=lambda path: json.dumps(records[path.name]).encode()):
            self.assertEqual(probe.validate_scope(helper, directory)[0], baseline)
            for path in (root / "other", root / "nested" / "run-example"):
                with self.assertRaises(probe.ProbeError):
                    probe.validate_scope(helper, path)
            records["result.json"]["pair_results"] = [{"pair": 0}]
            with self.assertRaises(probe.ProbeError):
                probe.validate_scope(helper, directory)

    def test_lock_absence_never_creates_file_or_queries_fuser(self):
        with patch.object(Path, "lstat", side_effect=FileNotFoundError), patch.object(probe.subprocess, "run") as run:
            self.assertFalse(probe.inspect_lock()["present"])
            run.assert_not_called()

    def test_lock_owner_query_has_no_kill_flags_and_no_lock_acquisition(self):
        info = SimpleNamespace(st_mode=stat.S_IFREG | 0o600, st_uid=1000)
        with patch.object(Path, "lstat", return_value=info), patch.object(probe.os, "getuid", return_value=1000, create=True), \
             patch.object(probe.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=b"123")) as run:
            self.assertEqual(probe.inspect_lock()["owners"], [123])
            self.assertEqual(run.call_args.args[0], ["fuser", str(probe.LOCK)])

    def test_helper_remains_hash_pinned_and_original_reporting_defect_is_preserved(self):
        payload = (launch.ROOT / "tools/reachy_mic_health.py").read_bytes()
        self.assertEqual(hashlib.sha256(payload).hexdigest(), probe.EXPECTED)
        self.assertIn(b"stderr=subprocess.DEVNULL", payload)

    def test_probe_contains_no_write_reset_capture_or_guard_calls(self):
        tree = ast.parse(Path(probe.__file__).read_text())
        forbidden = {"setrlimit", "kill", "killpg", "unlink", "mkdir", "flock", "execv", "save_json",
                     "guard_main", "serve_guard", "RouteGuard", "USBBoard", "capture_pair", "execute",
                     "reset", "detach_kernel_driver", "set_configuration", "claim_interface", "write_text", "write_bytes"}
        helper_calls = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            self.assertNotIn(getattr(node.func, "attr", getattr(node.func, "id", "")), forbidden)
            if isinstance(node.func, ast.Subscript) and isinstance(node.func.slice, ast.Constant):
                helper_calls.add(node.func.slice.value)
            if getattr(node.func, "attr", "") == "ctrl_transfer":
                self.assertEqual(node.args[0].value, 0xC0)
        self.assertLessEqual(helper_calls, {"require_robot_account", "private_directory", "inventory",
                                           "inspect_platform", "mixer_digest", "read_parameters"})


class LauncherTests(unittest.TestCase):
    def test_defaults_make_no_connection_or_device_access(self):
        with patch.object(launch, "collect") as collect, patch.object(probe, "Probe") as remote, redirect_stdout(io.StringIO()):
            self.assertEqual(launch.main([]), 0)
            self.assertEqual(probe.main([]), 0)
        collect.assert_not_called()
        remote.assert_not_called()

    def test_ssh_source_via_stdin_no_installed_file_or_guard(self):
        command = launch.ssh_command("/home/pollen/reachy-mic-health-runs-v2/run-example")
        self.assertIn("StrictHostKeyChecking=yes", command)
        self.assertIn("-I -B - --probe --run-directory", command[-1])
        for text in ("--execute", "--guard", "scp", "sudo"):
            self.assertNotIn(text, " ".join(command))

    def test_partial_events_survive_invalid_trailing_line_without_copying_text(self):
        good = {"schema": probe.SCHEMA, "execution_authorized": False, "event": "stage_started", "stage": "usb"}
        result, errors = launch.decode_events(json.dumps(good).encode() + b"\nprivate traceback\n{\"partial")
        self.assertEqual(result, [good])
        self.assertEqual(errors, 2)
        with self.assertRaises(ValueError):
            launch.decode_events(b"x" * (1024 * 1024 + 1))

    def test_success_preserves_failed_closeout_and_repeat_is_blocked(self):
        done = {"schema": probe.SCHEMA, "execution_authorized": False, "event": "finished"}
        result = SimpleNamespace(returncode=0, stdout=json.dumps(done).encode())
        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(launch, "OUTPUT", Path(temporary) / "probe"), \
             patch.object(launch, "reviewed_run", return_value=("fixture-run", "fixture-hash")), \
             patch.object(launch.subprocess, "run", return_value=result) as run, redirect_stdout(io.StringIO()):
            self.assertEqual(launch.collect(), 0)
            with self.assertRaises(FileExistsError):
                launch.collect()
            run.assert_called_once()
            report = json.loads((launch.OUTPUT / "report.json").read_text())
            self.assertEqual(report["closeout_status"], "PENDING")
            self.assertEqual(run.call_args.kwargs["input"], (launch.ROOT / "tools/reachy_mic_startup_probe.py").read_bytes())
            self.assertNotIn("stderr", run.call_args.kwargs)

    def test_ssh_timeout_keeps_partial_stage_report_without_retry(self):
        event = {"schema": probe.SCHEMA, "execution_authorized": False, "event": "stage_started", "stage": "usb"}
        error = subprocess.TimeoutExpired("ssh", 120, output=json.dumps(event).encode())
        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(launch, "OUTPUT", Path(temporary) / "probe"), \
             patch.object(launch, "reviewed_run", return_value=("fixture-run", "fixture-hash")), \
             patch.object(launch.subprocess, "run", side_effect=error) as run, redirect_stdout(io.StringIO()):
            self.assertEqual(launch.collect(), 2)
            report = json.loads((launch.OUTPUT / "report.json").read_text())
            self.assertEqual(report["events"], [event])
            self.assertEqual(report["transport_error"], "ssh_timeout")
            run.assert_called_once()

    def test_failed_authentication_saves_failure_not_success(self):
        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(launch, "OUTPUT", Path(temporary) / "probe"), \
             patch.object(launch, "reviewed_run", return_value=("fixture-run", "fixture-hash")), \
             patch.object(launch.subprocess, "run", return_value=SimpleNamespace(returncode=255, stdout=b"")), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(launch.collect(), 2)
            self.assertEqual(json.loads((launch.OUTPUT / "report.json").read_text())["ssh_exit_code"], 255)


if __name__ == "__main__":
    unittest.main()
