"""Keyboard-only contracts. No SSH, microphone, USB, robot API or settings I/O."""

import ast
import base64
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import shlex
import socket
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools import reachy_keyboard_probe as probe
from scripts import check_reachy_keyboard as launch


class ReaderTests(unittest.TestCase):
    def exercise(self, times, ready, reader=None):
        selector = Mock()
        selector.select.return_value = [(object(), 1)] if ready else []
        reader = Mock(return_value=True) if reader is None else reader
        record = probe.wait_for_enter(object(), reader, timeout=10,
                                      selector_factory=lambda: selector,
                                      clock=Mock(side_effect=times))
        selector.close.assert_called_once()
        return record, selector, reader

    def test_ready_on_time_even_if_read_finishes_after_deadline(self):
        record, _, reader = self.exercise([0, 9.98, 9.99, 10.01], True)
        self.assertEqual(record["status"], "received")
        self.assertEqual(record["readiness_observed_ms"], 9990)
        self.assertEqual(record["read_finished_ms"], 10010)
        self.assertFalse(record["physical_keypress_time_known"])
        reader.assert_called_once()

    def test_queued_at_expiry_is_observed_not_mislabelled_missing_or_accepted(self):
        record, selector, reader = self.exercise([0, 10.01, 10.01, 10.02], True)
        self.assertEqual(record["status"], "input_present_at_expiry_time_unknown")
        selector.select.assert_called_once_with(timeout=0.0)
        reader.assert_called_once()

    def test_no_input_at_expiry_is_separate(self):
        record, selector, reader = self.exercise([0, 10.01, 10.01], False)
        self.assertEqual(record["status"], "no_input_observed_before_deadline")
        selector.select.assert_called_once_with(timeout=0.0)
        reader.assert_not_called()

    def test_text_is_not_retained(self):
        record, _, _ = self.exercise([0, 0, 1, 1], True, Mock(return_value=False))
        self.assertEqual(record["status"], "unexpected_text")
        self.assertNotIn("content", record)

    def test_eof_is_not_success(self):
        record, _, _ = self.exercise([0, 0, 1, 1], True, Mock(side_effect=EOFError))
        self.assertEqual(record["status"], "terminal_closed")

    def test_selector_closes_on_registration_failure(self):
        selector = Mock()
        selector.register.side_effect = OSError("fixture")
        with self.assertRaises(OSError):
            probe.wait_for_enter(object(), lambda: True, selector_factory=lambda: selector)
        selector.close.assert_called_once()

    def test_real_selector_and_text_reader_using_local_socketpair(self):
        # Real readiness and readline on this host; NOT a Linux PTY/SSH validation.
        left, right = socket.socketpair()
        try:
            with left.makefile("r", encoding="utf-8", newline="\n") as stream:
                right.sendall(b"\n")
                result = probe.wait_for_enter(stream, lambda: probe.selector_line(stream), timeout=1)
                self.assertEqual(result["status"], "received")
        finally:
            left.close()
            right.close()

    def test_only_empty_lines_accepted(self):
        for value in ("\n", "\r\n"):
            self.assertTrue(probe.selector_line(io.StringIO(value)))
        for value in ("secret\n", " \n"):
            self.assertFalse(probe.selector_line(io.StringIO(value)))
        with self.assertRaises(EOFError):
            probe.selector_line(io.StringIO(""))


class ProbeTests(unittest.TestCase):
    def exercise(self, *, statuses=("received", "received"), tty=True):
        lines = []
        stream = io.StringIO("\n")
        first = Mock(return_value="")
        statuses = iter(statuses)
        def wait(actual, reader):
            self.assertIs(actual, stream)
            self.assertTrue(reader())
            return {"status": next(statuses), "readiness_observed_ms": 1,
                    "physical_keypress_time_known": False}
        waiter = Mock(side_effect=wait)
        code = probe.run_probe(stream=stream, first_input=first,
                               terminal=lambda _: {"tty": tty, "canonical": tty},
                               output=lambda s, **_: lines.append(s), wait=waiter)
        result = json.loads(next(s.split(" ", 1)[1] for s in lines if s.startswith("KEYBOARD_CHECK_RESULT ")))
        return code, result, lines, waiter, first

    def test_two_acks_use_both_input_apis(self):
        code, result, lines, wait, first = self.exercise()
        self.assertEqual(code, 0)
        self.assertEqual([r["reader"] for r in result["steps"]], ["input", "selector_readline"])
        self.assertEqual(wait.call_count, 2)
        first.assert_called_once()
        self.assertEqual(sum("ENTER RECEIVED" in s for s in lines), 2)
        for field in ("audio_opened", "settings_changed", "remote_files_written", "recording_authorized", "keypress_contents_retained"):
            self.assertIs(result[field], False)

    def test_timeout_stops_without_retry_or_second_prompt(self):
        code, result, lines, wait, _ = self.exercise(statuses=("no_input_observed_before_deadline",))
        self.assertEqual(code, 20)
        self.assertEqual(len(result["steps"]), 1)
        self.assertFalse(any("STEP 2/2" in s for s in lines))
        wait.assert_called_once()

    def test_non_tty_never_reads(self):
        code, _, _, wait, first = self.exercise(tty=False)
        self.assertEqual(code, 22)
        wait.assert_not_called()
        first.assert_not_called()

    def test_remote_has_no_hardware_file_process_or_network_interfaces(self):
        tree = ast.parse(Path(probe.__file__).read_text())
        imports = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        self.assertEqual(imports, {"json", "os", "selectors", "sys", "time", "termios"})
        calls = {ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
        forbidden = {"open", "exec", "eval", "os.open", "os.system", "os.execv", "termios.tcsetattr"}
        self.assertFalse(calls & forbidden)


class LauncherTests(unittest.TestCase):
    def test_source_pinned_and_command_matches_existing_console_transport(self):
        from scripts import run_reachy_mic_missing_pair_speaker as old
        self.assertEqual(hashlib.sha256(launch.PROBE.read_bytes()).hexdigest(), launch.EXPECTED)
        command = launch.ssh_command()
        self.assertEqual(command[:-1], old.ssh_command("run")[:-1])
        remote = shlex.split(command[-1])
        self.assertEqual(remote[:4], [old.PYTHON, "-I", "-B", "-c"])
        tree = ast.parse(remote[4])
        encoded = next(n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
                       and isinstance(n.value, str) and len(n.value) > 100)
        self.assertEqual(base64.b64decode(encoded), launch.PROBE.read_bytes())

    def test_one_ssh_inherits_all_console_streams_and_saves_only_status(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(launch.sys.stdin, "isatty", return_value=True), redirect_stdout(io.StringIO()):
            runner = Mock(return_value=SimpleNamespace(returncode=0))
            self.assertEqual(launch.check_once(Path(tmp), runner), 0)
            runner.assert_called_once_with(launch.ssh_command(), timeout=300)
            directory, = Path(tmp).iterdir()
            self.assertEqual(sorted(p.name for p in directory.iterdir()), ["report.json", "started.json"])
            record = json.loads((directory / "report.json").read_text())
            self.assertEqual(record["status"], "BOTH_ENTER_ACKNOWLEDGED")
            self.assertFalse(record["recording_authorized"])
            self.assertFalse(record["key_contents_or_passwords_captured"])
            self.assertIn("not captured", record["result_basis"])

    def test_failure_and_interrupt_saved_without_retry(self):
        for error in (subprocess.TimeoutExpired("ssh", 300), KeyboardInterrupt(), OSError("private-error"), None):
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as tmp, \
                    patch.object(launch.sys.stdin, "isatty", return_value=True), redirect_stdout(io.StringIO()):
                runner = Mock(side_effect=error, return_value=SimpleNamespace(returncode=255))
                self.assertNotEqual(launch.check_once(Path(tmp), runner), 0)
                runner.assert_called_once()
                directory, = Path(tmp).iterdir()
                text = (directory / "report.json").read_text()
                self.assertNotIn("private-error", text)
                self.assertFalse(json.loads(text)["both_enters_acknowledged"])

    def test_noninteractive_or_changed_source_stops_before_creating_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "not-created"
            runner = Mock()
            with patch.object(launch.sys.stdin, "isatty", return_value=False), self.assertRaises(RuntimeError):
                launch.check_once(target, runner)
            with patch.object(launch.sys.stdin, "isatty", return_value=True), \
                    patch.object(launch, "EXPECTED", "changed"), self.assertRaises(RuntimeError):
                launch.check_once(target, runner)
            self.assertFalse(target.exists())
            runner.assert_not_called()

    def test_default_and_inspect_are_offline(self):
        with patch.object(launch.subprocess, "run", side_effect=AssertionError("no SSH")), \
                patch.object(launch, "safe_local_directory", side_effect=AssertionError("no writes")), redirect_stdout(io.StringIO()):
            self.assertEqual(launch.main([]), 0)
            self.assertEqual(launch.main(["--inspect"]), 0)

    def test_existing_microphone_source_is_unchanged(self):
        path = launch.ROOT / "tools/reachy_mic_health_missing_pair_speaker.py"
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                         "320939f520bb702d306cab05c0a3fa9134289d5d3de38871feab63e8cf15fe90")


if __name__ == "__main__":
    unittest.main()
