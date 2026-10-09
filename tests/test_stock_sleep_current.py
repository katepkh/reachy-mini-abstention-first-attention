"""Offline tests only: fake SSH, temporary journals, no robot access."""

from contextlib import ExitStack, redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

from scripts import request_reachy_stock_sleep_current as m


class CurrentSleepTests(unittest.TestCase):
    def fixture(self, stack, root):
        directory = root / "data/private/stock_sleep"
        directory.mkdir(parents=True)
        journal = directory / (m.SESSION + ".jsonl")
        authorization = directory / (m.SESSION + "-authorization.json")
        for name, value in (("ROOT", root), ("DIRECTORY", directory), ("JOURNAL", journal),
                            ("AUTHORIZATION", authorization)):
            stack.enter_context(patch.object(m, name, value))
        approval = {"schema": "reachy-stock-sleep-session-authorization-v1", "session": m.SESSION,
                    "original_sha256": m.ORIGINAL_SHA, "remote_sha256": m.REMOTE_SHA,
                    "launcher_sha256": m.sha(m.read_regular(Path(m.__file__))),
                    "journal_name": journal.name, "attempt_limit": 1, "approved": True,
                    "live_confirmation_required": True, "automatic_retry": False,
                    "microphone_authorized": False}
        authorization.write_text(json.dumps(approval), encoding="utf-8")
        stack.enter_context(redirect_stdout(io.StringIO()))
        return journal, authorization, approval

    def test_remote_source_is_exactly_preserved(self):
        reviewed = m.load_reviewed()
        self.assertEqual(m.sha(reviewed["source_bytes"]()), m.REMOTE_SHA)
        self.assertNotEqual(reviewed["JOURNAL"], m.JOURNAL)

    def test_source_drift_rejected_before_import(self):
        with patch.object(m, "read_regular", return_value=b"raise AssertionError('not executed')"):
            with self.assertRaisesRegex(RuntimeError, "original_sleep_source_changed"):
                m.load_reviewed()

    def test_default_does_not_read_authorization_or_connect(self):
        with patch.object(m, "load_reviewed") as load, redirect_stdout(io.StringIO()):
            self.assertEqual(m.main([]), 0)
            load.assert_not_called()

    def test_inspect_never_contacts_ssh_or_creates_journal(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            journal, _, _ = self.fixture(stack, Path(tmp))
            run = stack.enter_context(patch.object(subprocess, "run"))
            self.assertEqual(m.main(["--inspect"]), 0)
            run.assert_not_called()
            self.assertFalse(journal.exists())

    def test_approval_changes_block(self):
        changes = {"session": "another", "attempt_limit": True, "approved": False,
                   "launcher_sha256": "other", "original_sha256": "other", "remote_sha256": "other",
                   "journal_name": "old.jsonl", "live_confirmation_required": False,
                   "automatic_retry": True, "microphone_authorized": True}
        for key, value in changes.items():
            with self.subTest(key=key), tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
                _, path, approval = self.fixture(stack, Path(tmp))
                approval[key] = value
                path.write_text(json.dumps(approval), encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "authorization"):
                    m.check_authorization()

    def test_missing_approval_blocks(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            self.fixture(stack, Path(tmp))
            stack.enter_context(patch.object(m, "AUTHORIZATION", Path(tmp) / "absent.json"))
            with self.assertRaises(FileNotFoundError):
                m.check_authorization()

    def test_cancel_before_ssh_leaves_attempt_available(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            journal, _, _ = self.fixture(stack, Path(tmp))
            stack.enter_context(patch("sys.stdin.isatty", return_value=True))
            stack.enter_context(patch("builtins.input", return_value="cancel"))
            run = stack.enter_context(patch.object(subprocess, "run"))
            self.assertEqual(m.main(["--sleep-once"]), 0)
            run.assert_not_called()
            self.assertFalse(journal.exists())

    def test_single_transport_and_existing_journal_blocks_rerun(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            journal, _, _ = self.fixture(stack, Path(tmp))
            old = journal.parent / "standard-sleep-once-v1-replacement.jsonl"
            old.write_bytes(b"preserve historical evidence")
            stack.enter_context(patch("sys.stdin.isatty", return_value=True))
            stack.enter_context(patch("builtins.input", return_value="SLEEP ONCE"))
            outcome = types.SimpleNamespace(returncode=0, stdout=b'{"event":"ALREADY_DISABLED_NO_COMMAND"}\n')
            run = stack.enter_context(patch.object(subprocess, "run", return_value=outcome))
            self.assertEqual(m.main(["--sleep-once"]), 0)
            run.assert_called_once()
            self.assertEqual(m.sha(run.call_args.kwargs["input"]), m.REMOTE_SHA)
            self.assertIn("StrictHostKeyChecking=yes", run.call_args.args[0])
            content = journal.read_bytes()
            with self.assertRaisesRegex(RuntimeError, "already attempted"):
                m.main(["--sleep-once"])
            self.assertEqual(journal.read_bytes(), content)
            self.assertEqual(old.read_bytes(), b"preserve historical evidence")
            run.assert_called_once()

    def test_timeout_and_interrupt_preserve_uncertain_attempt(self):
        for error in (subprocess.TimeoutExpired("fixture", 120), KeyboardInterrupt()):
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
                journal, _, _ = self.fixture(stack, Path(tmp))
                stack.enter_context(patch("sys.stdin.isatty", return_value=True))
                stack.enter_context(patch("builtins.input", return_value="SLEEP ONCE"))
                run = stack.enter_context(patch.object(subprocess, "run", side_effect=error))
                with self.assertRaisesRegex(RuntimeError, "Outcome unknown"):
                    m.main(["--sleep-once"])
                self.assertIn(b"LOCAL_INTERRUPTION_OUTCOME_UNKNOWN", journal.read_bytes())
                with self.assertRaisesRegex(RuntimeError, "already attempted"):
                    m.check_authorization()
                run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
