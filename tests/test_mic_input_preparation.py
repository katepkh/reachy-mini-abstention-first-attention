"""Preparation transport tests use fake SSH/readiness; no device is opened."""
from contextlib import ExitStack, redirect_stdout
import base64
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from scripts import prepare_reachy_mic_input as p
from tools import reachy_mic_input_selfcheck as probe
from tools import reachy_mic_health_input_candidate as candidate


def terminal_report():
    names = ("one_enter", "split_blank_line", "duplicate_enters_visible", "text_classified_not_saved", "canonical_eof")
    return {"schema": "reachy-input-pty-selfcheck-v1", "status": "PASS",
            "checks": [{"name": n, "ok": True, "reader_exited": True, "terminal_modes_unchanged": True} for n in names],
            "input_source": "isolated_synthetic_pty", "physical_keyboard_tested": False,
            "capture_load_tested": False, "audio_opened": False, "settings_changed": False}


def report():
    return {"schema": "reachy-input-preparation-v1", "candidate_sha256": p.EXPECTED,
            "selfcheck_sha256": p.SELFCHECK_SHA, "status": "PREPARATION_OK",
            "audio_opened": False, "settings_changed": False, "execution_authorized": False,
            "candidate_path": p.REMOTE, "candidate_present_verified": True,
            "previous_scopes_verified": 9, "terminal": terminal_report(),
            "preflight": {"schema": "reachy-mic-health-v3-session", "mode": "READ_ONLY",
                          "helper_sha256": p.EXPECTED, "machine_checks_passed": True,
                          "execution_authorized": False, "consumer_isolation_verified": False,
                          "checks": [{"name": name, "ok": True} for name in sorted(p.PREFLIGHT_CHECKS)]}}


class ReportTests(unittest.TestCase):
    def test_valid_preparation_never_authorizes_recording(self):
        r = report()
        self.assertTrue(p.validate_report(r))
        self.assertFalse(r["execution_authorized"])

    def test_source_identity_and_scope_drift_rejected(self):
        for key in ("schema", "candidate_sha256", "selfcheck_sha256", "candidate_path"):
            r = report()
            r[key] = "changed"
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                p.validate_report(r)

    def test_permission_or_capture_claim_rejected(self):
        for key in ("audio_opened", "settings_changed", "execution_authorized"):
            r = report()
            r[key] = True
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                p.validate_report(r)

    def test_failed_check_cannot_be_mislabeled_success(self):
        for section in ("terminal", "preflight"):
            for change in ("missing", "failed", "duplicated"):
                r = report()
                checks = r[section]["checks"]
                if change == "missing":
                    checks.pop()
                elif change == "failed":
                    checks[0]["ok"] = False
                else:
                    checks[1] = dict(checks[0])
                with self.subTest(section=section, change=change), self.assertRaises(RuntimeError):
                    p.validate_report(r)

    def test_partial_preparation_is_not_pass(self):
        for status in ("FAILED", "INCOMPLETE", "CHECKS_FAILED"):
            r = report()
            r["status"] = status
            self.assertFalse(p.validate_report(r))

    def test_malformed_nested_reports_fail_explicitly(self):
        for section in ("terminal", "preflight"):
            for value in (None, [], {"checks": None}, {"checks": [None]}, {"checks": [{"name": []}]}):
                r = report()
                r[section] = value
                with self.subTest(section=section, value=value), self.assertRaises(RuntimeError):
                    p.validate_report(r)

    def test_freshness_is_not_inferred_from_saved_readiness(self):
        r = report()
        r["preflight"]["consumer_isolation_verified"] = True
        with self.assertRaises(RuntimeError):
            p.validate_report(r)


class LauncherTests(unittest.TestCase):
    def test_exact_sources_are_pinned(self):
        helper, checker = p.sources()
        self.assertEqual(p.sha(helper), p.EXPECTED)
        self.assertEqual(p.sha(checker), p.SELFCHECK_SHA)
        self.assertFalse(candidate.EXECUTION_RELEASED)

    def test_default_help_has_no_connection_or_files(self):
        with patch.object(p.subprocess, "run", side_effect=AssertionError("no SSH")), \
             patch.object(p, "prepare_once", side_effect=AssertionError("no preparation")), redirect_stdout(io.StringIO()):
            self.assertEqual(p.main([]), 0)

    def test_command_uses_one_authenticated_noninteractive_remote_program(self):
        command = p.ssh_command(["/fixture"])
        self.assertIn("-T", command)
        self.assertNotIn("-t", command)
        for value in ("StrictHostKeyChecking=yes", "ConnectionAttempts=1", "NumberOfPasswordPrompts=1"):
            self.assertIn(value, command)
        self.assertNotIn("--execute", p.remote_source(["/fixture"]))
        self.assertNotIn("os.execv", p.remote_source(["/fixture"]))

    def exercise(self, outcome=None, failure=None):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            stack.enter_context(patch.object(p.sys.stdin, "isatty", return_value=True))
            stack.enter_context(patch.object(p, "sources", return_value=(b"helper", b"check")))
            stack.enter_context(patch.object(p, "previous_runs", return_value={"/fixture": {}}))
            stack.enter_context(redirect_stdout(io.StringIO()))
            runner = Mock(return_value=outcome or types.SimpleNamespace(returncode=0, stdout=json.dumps(report()).encode()),
                          side_effect=failure)
            code = p.prepare_once(Path(tmp), runner)
            runner.assert_called_once()
            self.assertNotIn("stderr", runner.call_args.kwargs)  # Password stays in SSH console.
            folders = list(Path(tmp).iterdir())
            self.assertEqual(len(folders), 1)
            self.assertEqual(sorted(x.name for x in folders[0].iterdir()), ["report.json", "started.json"])
            result = json.loads((folders[0] / "report.json").read_text())
            self.assertFalse(result["recording_authorized"])
            return code, result

    def test_success_saves_report_and_stops(self):
        code, r = self.exercise()
        self.assertEqual(code, 0)
        self.assertEqual(r["status"], "PREPARATION_OK_REVIEW_REQUIRED")

    def test_timeout_or_interruption_saved_without_retry(self):
        for error in (p.subprocess.TimeoutExpired("fixture", 150), KeyboardInterrupt(), OSError("fixture")):
            with self.subTest(error=type(error).__name__):
                code, r = self.exercise(failure=error)
                self.assertEqual(code, 2)
                self.assertEqual(r["status"], "INTERRUPTED_OR_FAILED_REVIEW_REQUIRED")
                self.assertFalse(r["automatic_retry"])

    def test_failed_preflight_saved_not_hidden(self):
        r = report()
        r["status"] = "CHECKS_FAILED"
        r["preflight"]["checks"][0]["ok"] = False
        code, saved = self.exercise(types.SimpleNamespace(returncode=0, stdout=json.dumps(r).encode()))
        self.assertEqual(code, 2)
        self.assertEqual(saved["remote"], r)

    def test_malformed_or_oversized_output_saved_as_failure(self):
        for raw in (b"no JSON", b"x" * 262145):
            with self.subTest(size=len(raw)):
                code, _ = self.exercise(types.SimpleNamespace(returncode=0, stdout=raw))
                self.assertEqual(code, 2)

    def test_malformed_nested_output_has_explicit_failure_receipt(self):
        r = report()
        r["terminal"] = None
        code, saved = self.exercise(types.SimpleNamespace(returncode=0, stdout=json.dumps(r).encode()))
        self.assertEqual(code, 2)
        self.assertEqual(saved["status"], "INTERRUPTED_OR_FAILED_REVIEW_REQUIRED")
        self.assertEqual(saved["error_type"], "RuntimeError")

    def test_source_or_prior_error_stops_before_ssh_or_folder_creation(self):
        for fn in ("sources", "previous_runs"):
            with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
                stack.enter_context(patch.object(p.sys.stdin, "isatty", return_value=True))
                stack.enter_context(patch.object(p, "sources", return_value=(b"h", b"p")))
                stack.enter_context(patch.object(p, "previous_runs", return_value={}))
                stack.enter_context(patch.object(p, fn, side_effect=RuntimeError("drift")))
                runner = Mock()
                with self.assertRaisesRegex(RuntimeError, "drift"):
                    p.prepare_once(Path(tmp), runner)
                self.assertEqual(list(Path(tmp).iterdir()), [])
                runner.assert_not_called()


class RemoteTests(unittest.TestCase):
    def exercise(self, *, changed=False, probe_error=False, passed=True, released=False):
        namespace = {}
        exec(p.remote_source(["/fixture"]).rsplit("\nremote_prepare()", 1)[0], namespace)
        calls = []
        helper_source = b"fixture helper"
        checker_source = b"fixture checker"
        preflight = report()["preflight"]
        preflight["machine_checks_passed"] = passed
        helper = {"EXECUTION_RELEASED": released, "require_robot_account": lambda: calls.append("account"),
                  "private_directory": lambda _: None, "pending_runs": lambda: [],
                  "inventory": lambda _: ["different"] if changed else [],
                  "TerminalInputReader": object(), "preflight_report": lambda: (calls.append("readiness"), preflight)[1]}
        def check(_):
            calls.append("pty")
            if probe_error:
                raise RuntimeError("fixture failure")
            return terminal_report()
        def fake_exec(code, target):
            target.update(helper if code.co_filename == p.REMOTE else {"terminal_selfcheck": check})
        namespace.update(EXPECTED=p.sha(helper_source), SELFCHECK_SHA=p.sha(checker_source),
                         compile=lambda text, filename, mode: types.SimpleNamespace(co_filename=filename),
                         exec=fake_exec, read_regular=lambda _: b"{}",
                         install_exact=lambda *args: (calls.append("install"), True)[1])
        packet = {"helper": base64.b64encode(helper_source).decode(),
                  "selfcheck": base64.b64encode(checker_source).decode(),
                  "prior_runs": {"/fixture": {"inventory": [], "closeout": {}}}}
        output = io.StringIO()
        with patch.object(namespace["sys"], "stdin", types.SimpleNamespace(buffer=io.BytesIO(json.dumps(packet).encode()))), redirect_stdout(output):
            namespace["remote_prepare"]()
        return json.loads(output.getvalue()), calls

    def test_success_orders_prior_checks_terminal_copy_then_readiness(self):
        r, calls = self.exercise()
        self.assertEqual(calls, ["account", "pty", "install", "readiness"])
        self.assertEqual(r["status"], "PREPARATION_OK")
        self.assertFalse(r["execution_authorized"])

    def test_terminal_failure_prevents_install_and_preflight(self):
        r, calls = self.exercise(probe_error=True)
        self.assertEqual(calls, ["account", "pty"])
        self.assertEqual(r["failed_stage"], "synthetic_terminal")

    def test_prior_drift_prevents_terminal_install_and_preflight(self):
        r, calls = self.exercise(changed=True)
        self.assertEqual(calls, ["account"])
        self.assertEqual(r["failed_stage"], "previous_closeouts")

    def test_released_candidate_is_rejected_before_device_access(self):
        r, calls = self.exercise(released=True)
        self.assertEqual(calls, [])
        self.assertEqual(r["status"], "FAILED")

    def test_failed_readiness_never_creates_permission(self):
        r, calls = self.exercise(passed=False)
        self.assertEqual(r["status"], "CHECKS_FAILED")
        self.assertNotIn("execute", calls)


class TerminalProbeTests(unittest.TestCase):
    def test_unsupported_platform_does_not_fake_pass(self):
        with patch.object(probe, "os", types.SimpleNamespace(name="nt")):
            reader = Mock()
            with self.assertRaisesRegex(RuntimeError, "posix_terminal_required"):
                probe.terminal_selfcheck(reader)
            reader.assert_not_called()

    @unittest.skipUnless(os.name == "posix", "Requires real POSIX PTYs; operator preparation runs this on Reachy")
    def test_actual_linux_terminal_reader_cases(self):
        result = probe.terminal_selfcheck(candidate.TerminalInputReader)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(len(result["checks"]), 5)
        self.assertFalse(result["audio_opened"])


if __name__ == "__main__":
    unittest.main()
