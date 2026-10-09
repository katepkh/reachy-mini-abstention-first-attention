"""Synthetic stock-sleep tests: no robot, network, sensors or motion."""

from datetime import datetime, timezone, timedelta
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import request_reachy_stock_sleep as m


MOVE = "12345678-1234-1234-1234-123456789abc"


class FakeRobot:
    def __init__(self):
        self.calls = []
        self.events = []
        self.elapsed = 0
        self.sent_at = None
        self.mode = "enabled"
        self.status = {"state": "running", "version": "1.9.0", "error": None,
                       "simulation_enabled": False, "mockup_sim_enabled": False,
                       "no_media": False, "media_released": False,
                       "backend_status": {"error": None, "ready": False}}
        self.app = None
        self.lock = {"state": "free"}
        self.foreign_moves = []
        self.post_error = False
        self.bad_uuid = False
        self.never_completes = False
        self.failed_task = False
        self.stale = False
        self.slow = False
        self.after_error = False

    def pause(self, seconds):
        self.elapsed += seconds

    def effective_mode(self):
        if self.sent_at is not None and self.elapsed - self.sent_at >= 3 and not self.never_completes and not self.failed_task:
            return "disabled"
        return self.mode

    def request(self, method, path):
        self.calls.append((method, path))
        if self.slow:
            self.elapsed += 1
        if method == "POST":
            self.sent_at = self.elapsed
            if self.post_error:
                raise TimeoutError("simulated lost reply")
            return {"uuid": "invalid" if self.bad_uuid else MOVE}
        if path.endswith("current-app-status"):
            return self.app
        if path.endswith("robot-app-lock-status"):
            return self.lock
        if path.endswith("/running"):
            if self.foreign_moves:
                return self.foreign_moves
            if self.sent_at is not None and not self.failed_task and (self.never_completes or self.elapsed - self.sent_at < 3):
                return [{"uuid": MOVE}]
            return []
        if path.startswith("/api/state/full?"):
            stamp = datetime.now(timezone.utc) - timedelta(seconds=10 if self.stale else 0)
            return {"timestamp": stamp.isoformat(), "control_mode": self.effective_mode()}
        if path.endswith("/status"):
            result = copy.deepcopy(self.status)
            if isinstance(result.get("backend_status"), dict):
                result["backend_status"]["motor_control_mode"] = self.effective_mode()
                if self.after_error and self.sent_at is not None:
                    result["backend_status"]["error"] = "synthetic fault"
            return result
        raise AssertionError(path)

    def run(self):
        return m.remote_once(self.request, self.events.append, self.pause, lambda: self.elapsed)

    def posts(self):
        return [call for call in self.calls if call[0] == "POST"]


class StockSleepTests(unittest.TestCase):
    def test_success_one_stock_request_and_two_disabled_observations(self):
        fake = FakeRobot()
        self.assertEqual(fake.run(), 0)
        self.assertEqual(fake.posts(), [("POST", "/api/move/play/goto_sleep")])
        self.assertEqual(fake.events[-1]["event"], "DISABLED_OBSERVED_DAEMON_RUNNING")
        self.assertEqual([item["motor_mode"] for item in fake.events[-3:-1]], ["disabled", "disabled"])
        self.assertFalse(fake.events[-1]["microphone_test_started"])
        self.assertFalse(fake.events[-1]["sleep_pose_verified"])

    def test_already_disabled_never_sends_sleep(self):
        fake = FakeRobot()
        fake.mode = "disabled"
        self.assertEqual(fake.run(), 0)
        self.assertEqual(fake.posts(), [])
        self.assertEqual(fake.events[-1]["event"], "ALREADY_DISABLED_NO_COMMAND")

    def test_bad_status_blocks_before_any_post(self):
        cases = [("state", "stopped"), ("version", "other"), ("error", "fault"),
                 ("simulation_enabled", True), ("mockup_sim_enabled", None),
                 ("no_media", True), ("media_released", True), ("backend_status", None)]
        for key, value in cases:
            with self.subTest(key=key):
                fake = FakeRobot()
                fake.status[key] = value
                self.assertEqual(fake.run(), 2)
                self.assertEqual(fake.posts(), [])

    def test_missing_status_fields_block(self):
        for key in FakeRobot().status:
            with self.subTest(key=key):
                fake = FakeRobot()
                del fake.status[key]
                self.assertEqual(fake.run(), 2)
                self.assertEqual(fake.posts(), [])

    def test_unknown_mode_blocks(self):
        for mode in (None, "gravity_compensation", True, "unknown"):
            fake = FakeRobot()
            fake.mode = mode
            self.assertEqual(fake.run(), 2)
            self.assertEqual(fake.posts(), [])

    def test_other_app_session_move_and_stale_or_slow_state_block(self):
        cases = [("app", {}), ("lock", {"state": "remote_session"}),
                 ("lock", {}), ("foreign_moves", [{"uuid": MOVE}]),
                 ("stale", True), ("slow", True)]
        for key, value in cases:
            with self.subTest(key=key):
                fake = FakeRobot()
                setattr(fake, key, value)
                self.assertEqual(fake.run(), 2)
                self.assertEqual(fake.posts(), [])

    def test_lost_reply_and_invalid_ack_never_repeat(self):
        for attr in ("post_error", "bad_uuid"):
            fake = FakeRobot()
            setattr(fake, attr, True)
            self.assertEqual(fake.run(), 2)
            self.assertEqual(len(fake.posts()), 1)
            self.assertTrue(fake.events[-1]["request_may_have_been_sent"])

    def test_post_fault_or_unfinished_task_never_sends_recovery(self):
        for attr in ("after_error", "never_completes", "failed_task"):
            fake = FakeRobot()
            setattr(fake, attr, True)
            self.assertEqual(fake.run(), 2)
            self.assertEqual(len(fake.posts()), 1)
            self.assertFalse(fake.events[-1]["automatic_recovery_motion"])
            self.assertLess(fake.elapsed, 23)

    def test_interrupt_during_post_is_uncertain_no_retry(self):
        fake = FakeRobot()
        request = fake.request
        def interrupted(method, path):
            result = request(method, path)
            if method == "POST":
                raise KeyboardInterrupt()
            return result
        self.assertEqual(m.remote_once(interrupted, fake.events.append, fake.pause, lambda: fake.elapsed), 2)
        self.assertEqual(len(fake.posts()), 1)
        self.assertTrue(fake.events[-1]["request_may_have_been_sent"])

    def test_journal_is_exclusive_and_retained(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "run.jsonl"
            with m.create_journal(path, b"synthetic"):
                pass
            content = path.read_bytes()
            with self.assertRaises(FileExistsError):
                m.create_journal(path, b"another")
            self.assertEqual(path.read_bytes(), content)

    def test_remote_program_compiles_and_default_never_connects(self):
        compile(m.source_bytes(), "<stock-sleep-stdin>", "exec")
        with patch.object(m.subprocess, "run") as run, patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(m.main([]), 0)
            run.assert_not_called()

    def prepare_retry_fixture(self, directory):
        source = b"synthetic remote source"
        original = directory / "standard-sleep-once-v1.jsonl"
        with m.create_journal(original, source):
            pass
        review = {"schema": "reachy-stock-sleep-connect-timeout-review-v1",
                  "classification": "ssh_connection_timeout_before_remote_execution",
                  "failed_journal_sha256": hashlib.sha256(original.read_bytes()).hexdigest(),
                  "remote_source_sha256": hashlib.sha256(source).hexdigest(),
                  "replacement_attempt_limit": 1, "operator_confirmation_still_required": True}
        review_path = directory / "connect-timeout-review-v1.json"
        review_path.write_text(json.dumps(review), encoding="utf-8")
        return source, original, review_path, review

    def test_reviewed_retry_preserves_original_and_permits_only_one_new_log(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, original, _, _ = self.prepare_retry_fixture(root)
            before = original.read_bytes()
            replacement = m.reviewed_retry_journal(root, source)
            self.assertNotEqual(original, replacement)
            with m.create_journal(replacement, source):
                pass
            self.assertEqual(original.read_bytes(), before)
            with self.assertRaises(RuntimeError):
                m.reviewed_retry_journal(root, source)

    def test_missing_result_without_private_review_does_not_enable_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, _, review_path, _ = self.prepare_retry_fixture(root)
            review_path.unlink()
            with self.assertRaises(FileNotFoundError):
                m.reviewed_retry_journal(root, source)

    def test_changed_log_source_or_review_scope_blocks_retry(self):
        cases = [("classification", "unknown"), ("replacement_attempt_limit", 2),
                 ("replacement_attempt_limit", True), ("operator_confirmation_still_required", False),
                 ("failed_journal_sha256", "wrong"), ("remote_source_sha256", "wrong")]
        for key, value in cases:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                source, _, review_path, review = self.prepare_retry_fixture(root)
                review[key] = value
                review_path.write_text(json.dumps(review), encoding="utf-8")
                with self.assertRaises(RuntimeError):
                    m.reviewed_retry_journal(root, source)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, original, _, _ = self.prepare_retry_fixture(root)
            with self.assertRaises(RuntimeError):
                m.reviewed_retry_journal(root, source + b"changed")
            with original.open("a") as out:
                out.write('{"event":"SLEEP_REQUEST_MAY_BE_SENT"}\n')
            with self.assertRaises(RuntimeError):
                m.reviewed_retry_journal(root, source)


if __name__ == "__main__":
    unittest.main()
