"""Local source/transport/failure tests; real PTY/child checks require Linux."""
import ast
from contextlib import redirect_stdout
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts import check_reachy_input_linux as launcher
from tools import reachy_input_linux_selfcheck as harness


def case_fixture(name):
    enter = name == "generated_enter"
    observation = {"thread_alive": False, "last_error_stage": None, "reader_fault": None,
                   "counter_saturated": False,
                   "counts": {"thread_starts": 1, "thread_exits": 1,
                              "selector_close_calls": 1, "selector_close_returns": 1,
                              "select_calls": 100, "select_returns": 100,
                              "read_calls": int(enter), "read_returns": int(enter),
                              "bytes": int(enter), "lf": int(enter), "enter_events": int(enter)}}
    timing = {"reader_exit_verified": True,
              "reader_observability": {key: copy.deepcopy(observation) for key in
                                       ("at_start", "at_play", "before_close", "after_close")},
              "events": [{"kind": "enter", "accepted": True}] if enter else []}
    result = {"complete": enter, "capture_exit_verified": True, "operator_input": timing,
              "summaries": {"quiet": {"frames": 48000}}}
    if enter:
        result["summaries"]["playback"] = {"frames": 160000}
    return {"name": name, "outcome": "COMPLETE" if enter else "confirmation_deadline_no_observed_enter",
            "result": result, "terminal_modes_unchanged": True, "synthetic_sender_exited": True,
            "synthetic_input_written": enter, "child_reaped": True, "reader_threads_exited": True,
            "pipes_closed": True, "pty_closed": True, "ok": True}


def result_fixture():
    # Obtain the exact top-level fixed shape without Linux or process activity.
    with patch.object(harness.sys, "platform", "win32"):
        result = harness.run_check("")
    result.pop("reason")
    result.update(status="PASS", cases=[case_fixture(name) for name in harness.CASES])
    return result


def encoded(result):
    return (harness.RESULT_PREFIX + json.dumps(result) + "\n").encode()


class SourceTests(unittest.TestCase):
    def test_pins_exact_allowlisted_definitions_without_full_helper(self):
        bundle = launcher.source_bundle()
        original = ast.parse(launcher.HELPER.read_bytes())
        selected = ast.parse(bundle["definitions"])
        definitions = {n.name: ast.dump(n) for n in original.body
                       if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        self.assertEqual({n.name for n in selected.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))},
                         launcher.DEFINITIONS)
        for node in selected.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                self.assertEqual(ast.dump(node), definitions[node.name])
        self.assertNotIn("def capture_command", bundle["definitions"])
        self.assertNotIn("arecord", bundle["payload"].decode())
        self.assertNotIn("urllib", bundle["payload"].decode())
        self.assertNotIn("USBBoard", bundle["payload"].decode())
        self.assertNotIn("def execute", bundle["payload"].decode())
        self.assertNotIn("AUTHORIZATION_PATH", bundle["payload"].decode())
        self.assertLess(len(bundle["payload"]), 100000)
        compile(bundle["payload"], "<test-only-payload>", "exec")

    def test_hash_drift_stops_before_connection_or_latch(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(launcher, "HARNESS_SHA", "0" * 64), \
                patch.object(launcher.sys, "stdin", SimpleNamespace(isatty=lambda: True)):
            runner = Mock()
            with self.assertRaisesRegex(RuntimeError, "source_changed"):
                launcher.check_once(Path(folder), runner)
            runner.assert_not_called()
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_remote_bootstrap_short_pinned_stdin_noninteractive(self):
        bundle = launcher.source_bundle()
        command = launcher.ssh_command(bundle["payload"])
        self.assertLess(len(subprocess.list2cmdline(command)), 2000)
        self.assertIn("-T", command)
        self.assertNotIn("-t", command)
        self.assertIn("StrictHostKeyChecking=yes", command)
        self.assertIn("ConnectionAttempts=1", command)
        self.assertIn("NumberOfPasswordPrompts=1", command)
        self.assertIn(launcher.sha(bundle["payload"]), command[-1])
        self.assertIn("sys.stdin.buffer.read", command[-1])
        self.assertIn("-I -B", command[-1])

    def test_harness_has_no_device_network_file_or_terminal_mode_setters(self):
        source = launcher.HARNESS.read_text()
        tree = ast.parse(source)
        calls = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute)}
        self.assertFalse(calls & {"tcsetattr", "tcflush", "tcsetpgrp", "ioctl", "connect",
                                  "unlink", "remove", "mkdir", "write_text", "write_bytes"})
        self.assertEqual(source.count("subprocess.Popen("), 1)
        self.assertIn("command != generator_command()", source)
        self.assertIn('"start_new_session": True', source)
        self.assertEqual(harness.generator_command()[:4], [sys.executable, "-I", "-B", "-c"])
        generator_tree = ast.parse(harness.GENERATOR)
        imports = {alias.name for n in ast.walk(generator_tree) if isinstance(n, ast.Import) for alias in n.names}
        self.assertEqual(imports, {"os", "select", "struct", "time"})
        self.assertIn("< 39", harness.GENERATOR)
        self.assertIn("os.getppid() == parent", harness.GENERATOR)
        self.assertIn("os.set_blocking(1, False)", harness.GENERATOR)

    def test_inspect_and_help_cannot_connect(self):
        with patch.object(launcher.subprocess, "run", side_effect=AssertionError("connection")), redirect_stdout(io.StringIO()):
            self.assertEqual(launcher.main([]), 0)
            self.assertEqual(launcher.main(["--inspect"]), 0)


class ResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = launcher.source_bundle()

    def test_fixed_pass_and_expected_timeout_validate(self):
        result = result_fixture()
        for case in result["cases"]:
            self.assertTrue(harness.expected_case(case))
        self.assertEqual(launcher.validated_result(encoded(result), self.bundle, 0), result)

    def test_no_partial_cleanup_or_missing_samples_can_pass(self):
        for field in ("terminal_modes_unchanged", "synthetic_sender_exited", "child_reaped",
                      "reader_threads_exited", "pipes_closed", "pty_closed"):
            result = result_fixture()
            result["cases"][0][field] = False
            with self.subTest(field=field), self.assertRaises(ValueError):
                launcher.validated_result(encoded(result), self.bundle, 0)
        result = result_fixture()
        result["cases"][0]["result"]["summaries"]["playback"]["frames"] -= 1
        with self.assertRaises(ValueError):
            launcher.validated_result(encoded(result), self.bundle, 0)

    def test_scope_content_and_invalid_output_rejected(self):
        for change in ({"password": "private-secret"}, {"audio_opened": True},
                       {"cases": []}, {"status": "not-a-status"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                launcher.validated_result(encoded({**result_fixture(), **change}), self.bundle, 0)
        for output in (b"private-secret", b"x" * 65537, encoded(result_fixture()) * 2,
                       encoded(result_fixture()) + b"extra"):
            with self.subTest(size=len(output)), self.assertRaises(ValueError):
                launcher.validated_result(output, self.bundle, 0)
        with self.assertRaises(ValueError):
            launcher.validated_result(encoded(result_fixture()), self.bundle, 255)

    def test_unsupported_platform_is_no_action_fail(self):
        with patch.object(harness.sys, "platform", "win32"), patch.object(harness, "run_case") as case:
            report = harness.run_check("")
        case.assert_not_called()
        self.assertEqual(report["reason"], "LINUX_REQUIRED")
        self.assertEqual(launcher.validated_result(encoded(report), self.bundle, 20), report)


class TransportTests(unittest.TestCase):
    def exercise(self, runner):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        with patch.object(launcher.sys, "stdin", SimpleNamespace(isatty=lambda: True)), redirect_stdout(io.StringIO()):
            code = launcher.check_once(root, runner)
        report = json.loads((root / launcher.RUN_ID / "report.json").read_text())
        return code, report, root

    def test_pass_records_and_single_use_latch(self):
        runner = Mock(return_value=SimpleNamespace(returncode=0, stdout=encoded(result_fixture())))
        code, report, root = self.exercise(runner)
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "SYNTHETIC_PASS")
        kwargs = runner.call_args.kwargs
        self.assertEqual(kwargs["input"], launcher.source_bundle()["payload"])
        self.assertEqual(kwargs["stdout"], subprocess.PIPE)
        self.assertIsNone(kwargs["stderr"])
        self.assertEqual(kwargs["timeout"], 95)
        with patch.object(launcher.sys, "stdin", SimpleNamespace(isatty=lambda: True)):
            with self.assertRaises(FileExistsError):
                launcher.check_once(root, runner)
        self.assertEqual(runner.call_count, 1)

    def test_timeout_interrupt_and_auth_failure_preserve_spent_record(self):
        for fault in (subprocess.TimeoutExpired("ssh", 95), KeyboardInterrupt(), OSError()):
            with self.subTest(fault=type(fault).__name__):
                runner = Mock(side_effect=fault)
                code, report, root = self.exercise(runner)
                self.assertEqual(code, 1)
                self.assertEqual(report["status"], "INTERRUPTED_OR_CONNECTION_UNCERTAIN")
                self.assertEqual(runner.call_count, 1)
                self.assertTrue((root / launcher.RUN_ID / "started.json").exists())
        runner = Mock(return_value=SimpleNamespace(returncode=255, stdout=b"private-content"))
        code, report, root = self.exercise(runner)
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "CONNECTION_OR_RESULT_UNVERIFIED")
        self.assertNotIn("private-content", json.dumps(report))

    def test_no_console_refused_before_latch(self):
        runner = Mock()
        with patch.object(launcher.sys, "stdin", SimpleNamespace(isatty=lambda: False)):
            with self.assertRaisesRegex(RuntimeError, "interactive_PowerShell"):
                launcher.check_once(runner=runner)
        runner.assert_not_called()


@unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux PTY and real generated child")
class LinuxIntegrationTests(unittest.TestCase):
    def test_exact_unaccelerated_loop_with_real_pty_and_generated_child(self):
        bundle = launcher.source_bundle()
        report = harness.run_check(bundle["definitions"])
        self.assertEqual(report["status"], "PASS", report)
        self.assertEqual(launcher.validated_result(encoded(report), bundle, 0), report)


if __name__ == "__main__":
    unittest.main()
