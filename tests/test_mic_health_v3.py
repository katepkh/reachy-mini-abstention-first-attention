"""Offline candidate tests: bounded read protocol and error propagation."""

import ast
from contextlib import ExitStack, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from tools import reachy_mic_health_v3 as m
from scripts import check_reachy_mic_retry as launch


class Clock:
    def __init__(self):
        self.now = 0.0
        self.waits = []
    def __call__(self):
        return self.now
    def sleep(self, delay):
        self.waits.append(delay)
        self.now += delay


class RetryTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.device = Mock()

    def read(self, **kwargs):
        return m.read_route_with_retry(self.device, m.ROUTES[0], clock=self.clock, sleep=self.clock.sleep, **kwargs)

    def test_immediate_success_is_one_read_no_wait(self):
        self.device.ctrl_transfer.return_value = b"\x00\x08\x00"
        result = self.read()
        self.assertEqual(result["values"], [8, 0])
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(self.clock.waits, [])
        self.device.ctrl_transfer.assert_called_once_with(0xC0, 0, 143, 35, 3, 500)

    def test_observed_64_then_success_uses_same_read_and_smaller_budget(self):
        self.device.ctrl_transfer.side_effect = [b"\x40\x00\x00", b"\x00\x08\x00"]
        result = self.read()
        self.assertEqual(result["status_bytes"], [64, 0])
        self.assertEqual(result["values"], [8, 0])
        self.assertEqual(result["timeouts_ms"], [500, 490])
        self.assertEqual(self.clock.waits, [0.01])
        self.assertTrue(all(call.args[:5] == (0xC0, 0, 143, 35, 3)
                            for call in self.device.ctrl_transfer.call_args_list))

    def test_repeated_64_has_fixed_attempt_limit(self):
        self.device.ctrl_transfer.return_value = b"\x40\x00\x00"
        with self.assertRaisesRegex(m.USBReadError, "usb_retry_limit") as caught:
            self.read()
        self.assertEqual(caught.exception.details["attempts"], 10)
        self.assertEqual(self.device.ctrl_transfer.call_count, 10)
        self.assertEqual(len(self.clock.waits), 9)

    def test_time_spent_in_transfers_counts_against_same_500ms(self):
        def slow(*args):
            self.clock.now += 0.245
            return b"\x40\x00\x00"
        self.device.ctrl_transfer.side_effect = slow
        with self.assertRaisesRegex(m.USBReadError, "usb_read_deadline"):
            self.read()
        self.assertEqual(self.device.ctrl_transfer.call_count, 2)
        self.assertLessEqual(self.device.ctrl_transfer.call_args_list[-1].args[-1], 245)

    def test_enclosing_deadline_only_shortens_budget(self):
        self.device.ctrl_transfer.return_value = b"\x00\x08\x00"
        result = self.read(deadline=0.03)
        self.assertLessEqual(result["timeouts_ms"][0], 30)
        self.device.ctrl_transfer.reset_mock()
        result = self.read(deadline=20)
        self.assertEqual(result["timeouts_ms"], [500])

    def test_expired_or_submillisecond_budget_never_sends_timeout_zero(self):
        for deadline in (-1, 0, 0.0009):
            with self.assertRaises(m.USBReadError):
                self.read(deadline=deadline)
        self.device.ctrl_transfer.assert_not_called()

    def test_late_success_is_not_accepted(self):
        def late(*args):
            self.clock.now = 0.501
            return b"\x00\x08\x00"
        self.device.ctrl_transfer.side_effect = late
        with self.assertRaisesRegex(m.USBReadError, "usb_read_deadline"):
            self.read()
        self.device.ctrl_transfer.assert_called_once()

    def test_busy_with_insufficient_wait_budget_stops_without_sleep(self):
        self.device.ctrl_transfer.return_value = b"\x40\x00\x00"
        with self.assertRaisesRegex(m.USBReadError, "usb_read_deadline"):
            self.read(deadline=0.0105)
        self.assertEqual(self.clock.waits, [])
        self.device.ctrl_transfer.assert_called_once()

    def test_short_unknown_and_oversized_responses_never_retry(self):
        for response in (b"", b"\x40", b"\x00\x08", b"\x01\x08\x00", b"\x00\x08\x00\x00"):
            self.device.ctrl_transfer.reset_mock()
            self.device.ctrl_transfer.return_value = response
            with self.assertRaises(m.USBReadError):
                self.read()
            self.device.ctrl_transfer.assert_called_once()

    def test_transfer_timeout_and_access_errors_never_retry_or_expose_message(self):
        for error in (TimeoutError(110, "private traceback"), PermissionError(13, "private path")):
            self.device.ctrl_transfer.reset_mock()
            self.device.ctrl_transfer.side_effect = error
            with self.assertRaises(m.USBReadError) as caught:
                self.read()
            self.assertEqual(caught.exception.details["errno"], error.errno)
            self.assertNotIn("private", json.dumps(caught.exception.details))
            self.device.ctrl_transfer.assert_called_once()

    def test_forbidden_parameter_is_rejected_before_io(self):
        for name in ("SAVE_CONFIGURATION", "AUDIO_MGR_MIC_GAIN", "REBOOT"):
            with self.assertRaises(m.USBReadError):
                m.read_route_with_retry(self.device, name)
        self.device.ctrl_transfer.assert_not_called()

    def test_fake_clock_stall_still_hits_attempt_limit(self):
        self.device.ctrl_transfer.return_value = b"\x40\x00\x00"
        with self.assertRaisesRegex(m.USBReadError, "usb_retry_limit"):
            m.read_route_with_retry(self.device, m.ROUTES[1], clock=lambda: 0, sleep=lambda _: None)
        self.assertEqual(self.device.ctrl_transfer.call_count, 10)


class GuardReportingTests(unittest.TestCase):
    def test_startup_error_is_structured_before_eof(self):
        output = io.StringIO()
        def fail(directory, progress):
            progress("guard_baseline_and_session")
            raise m.USBReadError("usb_retry_limit", {"status_bytes": [64] * 10, "attempts": 10})
        with patch.object(m, "guard_main", side_effect=fail):
            self.assertEqual(m.guard_entry("fixture", output), 2)
        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "GUARD_ERROR")
        self.assertEqual(result["stage"], "guard_baseline_and_session")
        self.assertEqual(result["details"]["attempts"], 10)

    def test_general_startup_exception_retains_class_not_arbitrary_text(self):
        output = io.StringIO()
        with patch.object(m, "guard_main", side_effect=PermissionError(13, "secret filename")):
            m.guard_entry("fixture", output)
        self.assertEqual(json.loads(output.getvalue())["errno"], 13)
        self.assertNotIn("secret", output.getvalue())

    def test_parent_does_not_reduce_structured_error_to_eof(self):
        client = object.__new__(m.GuardClient)
        client.messages = queue.Queue()
        value = {"status": "GUARD_ERROR", "stage": "guard_lock", "errno": 13}
        client.messages.put(value)
        client.messages.put({"status": "EOF"})
        with self.assertRaises(m.GuardFailure) as caught:
            client.expect("READY")
        self.assertEqual(caught.exception.details, value)

    def test_cleanup_error_keeps_preceding_structured_failure(self):
        try:
            try:
                raise m.GuardFailure({"stage": "guard_baseline_and_session", "reason": "usb_retry_limit"})
            finally:
                raise OSError(5, "private cleanup text")
        except OSError as error:
            value = m.safe_error_details(error)
        self.assertEqual(value["preceding_error"]["details"]["reason"], "usb_retry_limit")
        self.assertNotIn("private", json.dumps(value))

    def test_actual_parent_reader_consumes_error_and_waits_without_killing(self):
        value = {"status": "GUARD_ERROR", "stage": "usb_backend_and_device", "error_type": "ModuleNotFoundError"}
        process = Mock(stdin=io.StringIO(), stdout=io.StringIO(json.dumps(value) + "\n"))
        with patch.object(m.subprocess, "Popen", return_value=process):
            with self.assertRaises(m.GuardFailure):
                m.GuardClient(Path("fixture"))
        process.wait.assert_called_once_with(timeout=7)
        process.kill.assert_not_called()

    def test_parent_bad_json_reports_protocol_error(self):
        process = Mock(stdin=io.StringIO(), stdout=io.StringIO("not json\n"))
        with patch.object(m.subprocess, "Popen", return_value=process):
            with self.assertRaisesRegex(m.Stop, "PROTOCOL_ERROR"):
                m.GuardClient(Path("fixture"))

    def test_candidate_cli_cannot_start_capture_or_guard(self):
        for args in (["--execute"], ["--guard", "fixture"]):
            with patch.object(sys, "argv", ["candidate", *args]), patch.object(m, "execute") as execute, \
                 patch.object(m, "guard_entry") as guard:
                with self.assertRaisesRegex(m.Stop, "candidate_execution_not_released"):
                    m.main()
                execute.assert_not_called()
                guard.assert_not_called()

    def test_pair_and_restoration_budgets_reach_hardware_reader(self):
        clock = Clock()
        board = m.FakeBoard()
        guard = m.RouteGuard(board, lambda _: None, clock)
        board.read_before = Mock(side_effect=lambda key, end: board.read(key))
        guard.begin(0)
        self.assertIn(40.0, [call.args[1] for call in board.read_before.call_args_list])
        board.read_before.reset_mock()
        guard.restore()
        self.assertTrue(all(call.args[1] == 5.0 for call in board.read_before.call_args_list))

    def test_failure_details_are_saved_even_when_guard_record_is_missing(self):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            stack.enter_context(patch.object(m, "RUN_ROOT", Path(directory) / "runs"))
            stack.enter_context(patch.object(m.sys, "stdin", types.SimpleNamespace(isatty=lambda: True)))
            stack.enter_context(patch.object(m, "snapshot", return_value={"helper_sha256": "fixture"}))
            stack.enter_context(patch.object(m, "protect_own_process"))
            stack.enter_context(patch.object(m, "input", return_value=m.ACK, create=True))
            stack.enter_context(patch.object(m, "print"))
            stack.enter_context(patch.object(m, "GuardClient", side_effect=m.GuardFailure({"stage": "guard_lock", "errno": 13})))
            capture = stack.enter_context(patch.object(m, "capture_pair"))
            self.assertEqual(m.execute(), 2)
            run = next(m.RUN_ROOT.iterdir())
            report = json.loads((run / "result.json").read_text())
            self.assertEqual(report["failure_details"]["details"]["errno"], 13)
            self.assertEqual(report["ordinary_file_closeout"], "PENDING")
            capture.assert_not_called()


class VerificationLauncherTests(unittest.TestCase):
    def test_default_has_no_connection(self):
        with patch.object(launch, "collect") as collect, redirect_stdout(io.StringIO()):
            self.assertEqual(launch.main([]), 0)
        collect.assert_not_called()

    def test_transported_reader_is_exact_candidate_function_not_the_writer(self):
        source = launch.reader_source()
        namespace = {"time": m.time, "re": m.re, "ROUTES": m.ROUTES}
        exec(source, namespace)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "ctrl_transfer":
                self.assertEqual(node.args[0].value, 0xC0)
        self.assertNotIn("def write", source)
        device = Mock()
        device.ctrl_transfer.side_effect = [b"\x40\x00\x00", b"\x00\x08\x00"]
        clock = Clock()
        result = namespace["read_route_with_retry"](device, m.ROUTES[0], clock=clock, sleep=clock.sleep)
        self.assertEqual(result["status_bytes"], [64, 0])

    def test_remote_bundle_compiles_and_is_read_only_by_construction(self):
        source = launch.remote_source()
        compile(source, "<fixture-bundle>", "exec")
        text = source.decode()
        for forbidden in ("def execute(", "def guard_main(", "def capture_pair(", "def write("):
            self.assertNotIn(forbidden, text)
        self.assertIn("candidate_sha256", text)

    def test_original_helper_and_probe_unchanged(self):
        self.assertEqual(hashlib.sha256((launch.ROOT / "tools/reachy_mic_health.py").read_bytes()).hexdigest(),
                         launch.original.EXPECTED)
        self.assertEqual(hashlib.sha256((launch.ROOT / "tools/reachy_mic_startup_probe.py").read_bytes()).hexdigest(),
                         launch.BASE_PROBE_HASH)
        self.assertEqual(m.RUN_ROOT, Path(launch.original.REMOTE_ROOT))

    def test_remote_bundle_links_adapter_and_errors_without_hardware(self):
        result = {}
        with patch.object(sys, "argv", ["probe"]), redirect_stdout(io.StringIO()):
            exec(launch.remote_source(), result)
        namespace = result["namespace"]
        self.assertEqual(namespace["SCHEMA"], launch.SCHEMA)
        board = object.__new__(namespace["RetryReadOnlyUSB"])
        board.device, board.attempted = Mock(), set()
        board.device.ctrl_transfer.side_effect = [b"\x40\x00\x00", b"\x00\x08\x00"]
        self.assertEqual(board.read_route(m.ROUTES[0])["status_bytes"], [64, 0])
        with self.assertRaises(namespace["ProbeError"]):
            board.read_route(m.ROUTES[0])
        board.device.ctrl_transfer.side_effect = PermissionError(13, "secret")
        with self.assertRaises(namespace["USBReadError"]) as caught:
            board.read_route(m.ROUTES[1])
        details = namespace["error_details"](caught.exception)
        self.assertEqual(details["details"]["errno"], 13)
        self.assertNotIn("secret", json.dumps(details))

    def test_one_shot_and_partial_timeout_report(self):
        event = {"schema": launch.SCHEMA, "execution_authorized": False, "event": "stage_started", "stage": "usb"}
        failure = subprocess.TimeoutExpired("ssh", 120, output=json.dumps(event).encode())
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(launch, "OUTPUT", Path(directory) / "check"), \
             patch.object(launch, "reviewed_failure", return_value=("fixture", {})), \
             patch.object(launch.subprocess, "run", side_effect=failure) as run, redirect_stdout(io.StringIO()):
            self.assertEqual(launch.collect(), 2)
            value = json.loads((launch.OUTPUT / "report.json").read_text())
            self.assertEqual(value["events"], [event])
            self.assertEqual(value["closeout_status"], "PENDING")
            with self.assertRaises(FileExistsError):
                launch.collect()
            run.assert_called_once()


class ConnectReplacementTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        folder = self.stack.enter_context(tempfile.TemporaryDirectory())
        self.output = Path(folder) / "check"
        self.output.mkdir()
        self.stack.enter_context(patch.object(launch, "OUTPUT", self.output))
        self.source = b"read-only fixture"
        self.source_hash = hashlib.sha256(self.source).hexdigest()
        self.evidence = {"failure_review_sha256": "failure", "startup_report_sha256": "probe"}
        self.started = {"schema": launch.SCHEMA, "source_sha256": self.source_hash,
                        "run_directory": "fixture", **self.evidence, "execution_authorized": False}
        self.report = {"schema": launch.SCHEMA, "source_sha256": self.source_hash,
                       "events": [], "invalid_lines": 0, "ssh_exit_code": 255,
                       "transport_error": None, "execution_authorized": False, "closeout_status": "PENDING"}
        for name, value, constant in (("started.json", self.started, "CONNECT_TIMEOUT_START_HASH"),
                                      ("report.json", self.report, "CONNECT_TIMEOUT_REPORT_HASH")):
            launch.original.write_new(self.output / name, value)
            digest = hashlib.sha256((self.output / name).read_bytes()).hexdigest()
            self.stack.enter_context(patch.object(launch, constant, digest))
        self.before = {path.name: path.read_bytes() for path in self.output.iterdir()}
        self.stack.enter_context(patch.object(launch, "reviewed_failure", return_value=("fixture", self.evidence)))
        self.stack.enter_context(patch.object(launch, "remote_source", return_value=self.source))
        self.run = self.stack.enter_context(patch.object(launch.subprocess, "run"))
        self.stack.enter_context(redirect_stdout(io.StringIO()))

    def test_single_replacement_keeps_original_and_pending_and_exact_source(self):
        event = {"schema": launch.SCHEMA, "execution_authorized": False, "event": "finished"}
        self.run.return_value = subprocess.CompletedProcess("fixture", 0, json.dumps(event).encode())
        self.assertEqual(launch.main(["--retry-reviewed-connect-timeout"]), 0)
        replacement = self.output.with_name("check-connect-replacement-01")
        saved = json.loads((replacement / "report.json").read_text())
        self.assertEqual(saved["closeout_status"], "PENDING")
        self.assertFalse(saved["execution_authorized"])
        self.assertFalse(saved["automatic_retry"])
        self.assertEqual(saved["previous_report_sha256"], launch.CONNECT_TIMEOUT_REPORT_HASH)
        self.assertEqual(self.run.call_args.kwargs["input"], self.source)
        self.assertEqual(self.run.call_args.args[0], launch.previous.ssh_command("fixture"))
        self.assertEqual(self.before, {path.name: path.read_bytes() for path in self.output.iterdir()})
        with self.assertRaises(FileExistsError):
            launch.collect(reviewed_replacement=True)
        self.run.assert_called_once()

    def test_failed_replacement_is_also_spent(self):
        self.run.return_value = subprocess.CompletedProcess("fixture", 255, b"")
        self.assertEqual(launch.collect(reviewed_replacement=True), 2)
        with self.assertRaises(FileExistsError):
            launch.collect(reviewed_replacement=True)
        self.run.assert_called_once()

    def test_default_collect_does_not_bypass_original_latch(self):
        with self.assertRaises(FileExistsError):
            launch.collect()
        self.run.assert_not_called()

    def test_changed_source_evidence_or_run_refuses_before_connection(self):
        for directory, evidence, source_hash in (("other", self.evidence, self.source_hash),
                                                 ("fixture", {"startup_report_sha256": "other"}, self.source_hash),
                                                 ("fixture", self.evidence, "other")):
            with self.assertRaisesRegex(RuntimeError, "binding_changed"):
                launch.reviewed_connect_timeout(directory, evidence, source_hash)
        self.run.assert_not_called()

    def test_different_or_missing_original_refuses_before_connection(self):
        (self.output / "report.json").write_text(json.dumps(self.report) + " ")
        with self.assertRaisesRegex(RuntimeError, "not_the_reviewed"):
            launch.collect(reviewed_replacement=True)
        (self.output / "report.json").unlink()
        with self.assertRaises(FileNotFoundError):
            launch.collect(reviewed_replacement=True)
        self.run.assert_not_called()

    def test_generic_255_partial_output_or_timeout_is_not_sufficient(self):
        for changes in ({"events": [{"event": "started"}]}, {"invalid_lines": 1},
                        {"transport_error": "ssh_timeout"}, {"ssh_exit_code": 0},
                        {"execution_authorized": True}, {"closeout_status": "CHECKED_NO_UNEXPECTED_FILES"}):
            payload = json.dumps({**self.report, **changes}).encode()
            (self.output / "report.json").write_bytes(payload)
            with patch.object(launch, "CONNECT_TIMEOUT_REPORT_HASH", hashlib.sha256(payload).hexdigest()):
                with self.assertRaisesRegex(RuntimeError, "binding_changed"):
                    launch.collect(reviewed_replacement=True)
        self.run.assert_not_called()

    def test_modes_are_mutually_exclusive(self):
        with patch.object(sys, "stderr", io.StringIO()), self.assertRaises(SystemExit):
            launch.main(["--collect", "--retry-reviewed-connect-timeout"])
        self.run.assert_not_called()


def load_tests(loader, standard_tests, pattern):
    """Run the SAME legacy synthetic contract against the separate candidate.

    Only the module import is substituted in memory, including the fake-board
    subprocess fixture. The preserved files and original tests are not edited.
    """
    for name in ("test_mic_health.py", "test_mic_health_v2.py"):
        path = Path(__file__).with_name(name)
        source = path.read_text().replace("from tools import reachy_mic_health as m",
                                         "from tools import reachy_mic_health_v3 as m")
        module = types.ModuleType("candidate_contract_" + path.stem)
        module.__file__ = str(path)
        exec(compile(source, str(path), "exec"), module.__dict__)
        standard_tests.addTests(loader.loadTestsFromModule(module))
    return standard_tests


if __name__ == "__main__":
    unittest.main()
