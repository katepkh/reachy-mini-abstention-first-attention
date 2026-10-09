"""Offline v2 contract tests. All devices, audio and network are fakes."""

from contextlib import ExitStack
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools import reachy_mic_health as m


def status():
    return {"state": "running", "version": "1.9.0", "error": None,
            "simulation_enabled": False, "mockup_sim_enabled": False,
            "no_media": False, "media_released": False,
            "backend_status": {"motor_control_mode": "disabled", "error": None, "ready": False}}


class TestStatusAndPreflight(unittest.TestCase):
    def test_real_schema_disabled_mode_not_stale_ready_flag(self):
        self.assertEqual(m.robot_blockers(status()), [])
        item = status()
        item["backend_status"]["ready"] = True
        self.assertEqual(m.robot_blockers(item), [])

    def test_all_other_motor_modes_and_unknown_block(self):
        for value in ("enabled", "gravity_compensation", None, False, 0, "DISABLED"):
            with self.subTest(value=value):
                item = status()
                item["backend_status"]["motor_control_mode"] = value
                self.assertIn("motor_mode_not_verified_disabled", m.robot_blockers(item))

    def test_missing_fields_never_imply_safe(self):
        for key in status():
            item = status()
            del item[key]
            self.assertTrue(m.robot_blockers(item), key)
        for key in ("motor_control_mode", "error"):
            item = status()
            del item["backend_status"][key]
            self.assertTrue(m.robot_blockers(item))

    def test_old_mockup_name_not_accepted(self):
        item = status()
        item["mockup"] = item.pop("mockup_sim_enabled")
        self.assertIn("not_verified_physical_backend", m.robot_blockers(item))

    def test_stopped_daemon_not_accepted_as_disabled_motor_evidence(self):
        item = status()
        item.update(state="stopped", backend_status=None)
        self.assertEqual(len(m.robot_blockers(item)), 2)

    def test_malformed_status_is_bounded_failure(self):
        for item in (None, [], "running", True):
            self.assertEqual(m.robot_blockers(item), ["invalid_daemon_status"])

    def test_multiple_faults_reported_without_raw_error_text(self):
        item = status()
        item["error"] = "private error body"
        item["backend_status"] = {"motor_control_mode": "enabled", "error": "private"}
        reasons = m.robot_blockers(item)
        self.assertEqual(len(reasons), 3)
        self.assertNotIn("private", str(reasons))

    def test_enabled_swap_is_disclosed_not_mutated_or_rejected(self):
        content = "Filename Type Size Used Priority\n/dev/zram0 partition 2097148 0 100\n"
        with patch.object(m.Path, "read_text", return_value=content), \
                patch.object(m.subprocess, "run") as run:
            result = m.swap_metadata()
        run.assert_not_called()
        self.assertEqual(result["active_swap"][0]["device"], "/dev/zram0")
        self.assertFalse(result["settings_changed"])
        self.assertTrue(result["os_residuals_possible"])

    def test_bad_swap_metadata_not_silently_ignored(self):
        for content in ("", "other\n", "Filename Type Size Used Priority\nbad\n"):
            with patch.object(m.Path, "read_text", return_value=content), self.assertRaises(m.Stop):
                m.swap_metadata()

    def test_inspection_continues_after_independent_failures(self):
        with ExitStack() as stack:
            stack.enter_context(patch.object(m, "require_robot_account"))
            stack.enter_context(patch.object(m, "swap_metadata", return_value={"active_swap": []}))
            stack.enter_context(patch.object(m, "check_core_pattern", side_effect=m.Stop("core_failed")))
            stack.enter_context(patch.object(m, "check_tool"))
            stack.enter_context(patch.object(m, "check_card", side_effect=m.Stop("card_failed")))
            stack.enter_context(patch.object(m.Path, "read_text", return_value="fixture config"))
            stack.enter_context(patch.object(m, "validate_asoundrc"))
            stack.enter_context(patch.object(m, "check_source"))
            stack.enter_context(patch.object(m, "capture_owner", return_value=940))
            stack.enter_context(patch.object(m, "check_robot_status", side_effect=m.Stop("motor_enabled")))
            app = stack.enter_context(patch.object(m, "check_app"))
            stack.enter_context(patch.object(m, "pending_runs", return_value=["run-pending"]))
            checks, config = m.inspect_platform()
        self.assertEqual(config, "fixture config")
        self.assertEqual([item["name"] for item in checks if not item["ok"]],
                         ["core_pattern", "audio_card", "robot_status", "previous_closeout"])
        app.assert_called_once()
        self.assertNotIn("fixture config", str(checks))

    def test_preflight_all_checks_never_authorize_execution(self):
        for passed in (True, False):
            with ExitStack() as stack:
                stack.enter_context(patch.object(m, "inspect_platform", return_value=(
                    [{"name": "fixture", "ok": passed, "reason": "fixture"}], None)))
                parameters = stack.enter_context(patch.object(m, "read_parameters", return_value={}))
                stack.enter_context(patch.object(m, "mixer_digest", return_value="fixture"))
                protect = stack.enter_context(patch.object(m, "protect_own_process"))
                hardware = stack.enter_context(patch.object(m, "USBBoard"))
                popen = stack.enter_context(patch.object(m.subprocess, "Popen"))
                result = m.preflight_report()
            self.assertEqual(result["machine_checks_passed"], passed)
            self.assertFalse(result["execution_authorized"])
            self.assertFalse(result["consumer_isolation_verified"])
            parameters.assert_called_once()
            protect.assert_not_called()
            hardware.assert_not_called()
            popen.assert_not_called()

    def test_preflight_reports_parameter_failure_and_continues_to_mixer(self):
        with patch.object(m, "inspect_platform", return_value=([], None)), \
                patch.object(m, "read_parameters", side_effect=m.Stop("parameter_failed")), \
                patch.object(m, "mixer_digest", return_value="fixture") as mixer:
            result = m.preflight_report()
        self.assertFalse(result["machine_checks_passed"])
        self.assertEqual(result["checks"][0]["reason"], "parameter_failed")
        mixer.assert_called_once()


class TestCloseout(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="reachy-closeout-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.run = self.root / "run-fixture"
        self.run.mkdir(mode=0o700)

    def test_pending_record_precedes_any_capture(self):
        record = m.begin_closeout(self.run)
        self.assertEqual(record["before"], [])
        self.assertEqual(record["status"], "PENDING")
        self.assertFalse(record["forensic_erasure_claim"])
        self.assertEqual(m.pending_runs(self.root), [self.run.name])
        self.assertEqual(m.pending_runs(self.root, self.run), [])

    def test_nonempty_run_cannot_forge_clean_baseline(self):
        (self.run / "existing.txt").write_text("synthetic")
        with self.assertRaises(m.Stop):
            m.begin_closeout(self.run)
        self.assertFalse((self.run / "closeout.json").exists())

    def test_closeout_is_scoped_metadata_not_media_inspection(self):
        record = m.begin_closeout(self.run)
        m.save_json(self.run / "result.json", {"frames": 12})
        with patch.object(m.Path, "read_bytes", side_effect=AssertionError("content read")), \
                patch.object(m.Path, "read_text", side_effect=AssertionError("content read")):
            closed = m.finish_closeout(self.run, record, restoration_verified=True, capture_exit_verified=True)
        self.assertEqual(closed["status"], "CHECKED_NO_UNEXPECTED_FILES")
        self.assertEqual(m.pending_runs(self.root), [])

    def test_unexpected_extensions_and_directories_block_without_deletion(self):
        record = m.begin_closeout(self.run)
        (self.run / "unexpected.bin").write_bytes(b"synthetic fixture, not audio")
        (self.run / "subfolder").mkdir()
        closed = m.finish_closeout(self.run, record, restoration_verified=True, capture_exit_verified=True)
        self.assertEqual(closed["status"], "PENDING")
        self.assertEqual(len(closed["unexpected"]), 2)
        self.assertTrue((self.run / "unexpected.bin").exists())
        self.assertEqual(closed["deleted_files"], [])

    def test_restore_or_exit_failure_keeps_pending(self):
        record = m.begin_closeout(self.run)
        for restored, exited in ((False, True), (True, False), (False, False)):
            closed = m.finish_closeout(self.run, record, restoration_verified=restored, capture_exit_verified=exited)
            self.assertEqual(closed["status"], "PENDING")

    def test_inventory_error_does_not_claim_clean(self):
        record = m.begin_closeout(self.run)
        with patch.object(m, "inventory", side_effect=PermissionError()):
            closed = m.finish_closeout(self.run, record, restoration_verified=True, capture_exit_verified=True)
        self.assertEqual(closed["reason"], "after_inventory_unavailable")
        self.assertEqual(m.pending_runs(self.root), [self.run.name])

    def test_missing_or_corrupt_record_is_pending(self):
        self.assertEqual(m.pending_runs(self.root), [self.run.name])
        (self.run / "closeout.json").write_text("invalid fixture")
        self.assertEqual(m.pending_runs(self.root), [self.run.name])

    def test_changed_scope_is_pending(self):
        record = m.begin_closeout(self.run)
        closed = m.finish_closeout(self.run, record, restoration_verified=True, capture_exit_verified=True)
        closed["scope"] = "/wrong"
        m.save_json(self.run / "closeout.json", closed)
        self.assertEqual(m.pending_runs(self.root), [self.run.name])

    def test_new_file_reopens_previous_closeout(self):
        record = m.begin_closeout(self.run)
        m.finish_closeout(self.run, record, restoration_verified=True, capture_exit_verified=True)
        (self.run / "later.wav").write_text("synthetic fixture, not audio")
        self.assertEqual(m.pending_runs(self.root), [self.run.name])

    def test_atomic_update_leftover_requires_review(self):
        record = m.begin_closeout(self.run)
        (self.run / "result.json.new").write_text("{}")
        closed = m.finish_closeout(self.run, record, restoration_verified=True, capture_exit_verified=True)
        self.assertEqual(closed["status"], "PENDING")

    def test_existing_temporary_file_is_not_overwritten(self):
        temporary = self.run / "result.json.new"
        temporary.write_text("preserve fixture")
        with self.assertRaises(FileExistsError):
            m.save_json(self.run / "result.json", {"frames": 0})
        self.assertEqual(temporary.read_text(), "preserve fixture")
        self.assertFalse((self.run / "result.json").exists())

    def test_inventory_is_bounded(self):
        for index in range(129):
            (self.run / str(index)).touch()
        with self.assertRaisesRegex(m.Stop, "inventory_limit"):
            m.inventory(self.run)

    def test_link_is_reported_not_followed(self):
        outside = self.root / "outside"
        outside.mkdir()
        try:
            (self.run / "link").symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("symlink creation unavailable on this host")
        self.assertEqual(m.inventory(self.run)[0]["kind"], "link")


class TestExecutionBookkeeping(unittest.TestCase):
    def execute_fake(self, directory, outcome="complete"):
        baseline = {"helper_sha256": "fixture", "privacy_profile": m.PRIVACY_PROFILE}
        def guard_start(run):
            self.assertEqual(json.loads((run / "closeout.json").read_text())["status"], "PENDING")
            m.save_json(run / "guard.json", {"restoration": "ROUTES_RESTORED"})
            return SimpleNamespace(request=Mock(), close=Mock())
        def capture(pair, result, guard):
            result.update(complete=True, capture_exit_verified=True)
            if outcome == "abort":
                raise KeyboardInterrupt()
            if outcome == "unexpected":
                run = next(directory.iterdir())
                (run / "unexpected.raw").write_text("synthetic fixture, not audio")
        with ExitStack() as stack:
            stack.enter_context(patch.object(m, "RUN_ROOT", directory))
            stack.enter_context(patch.object(m.sys, "stdin", SimpleNamespace(isatty=lambda: True)))
            stack.enter_context(patch.object(m, "snapshot", return_value=baseline))
            stack.enter_context(patch.object(m, "protect_own_process"))
            stack.enter_context(patch.object(m, "input", return_value=m.ACK, create=True))
            stack.enter_context(patch.object(m, "print"))
            stack.enter_context(patch.object(m, "wait_enter"))
            stack.enter_context(patch.object(m, "GuardClient", side_effect=guard_start))
            stack.enter_context(patch.object(m, "capture_pair", side_effect=capture))
            code = m.execute()
        run = next(directory.iterdir())
        return code, json.loads((run / "result.json").read_text()), json.loads((run / "closeout.json").read_text())

    def test_completed_run_closes_and_preserves_numeric_result(self):
        with tempfile.TemporaryDirectory() as root:
            code, result, closed = self.execute_fake(Path(root) / "runs")
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "COMPLETE_RESTORED")
        self.assertEqual(closed["status"], "CHECKED_NO_UNEXPECTED_FILES")

    def test_abort_still_checks_cleanup_without_repeating(self):
        with tempfile.TemporaryDirectory() as root:
            code, result, closed = self.execute_fake(Path(root) / "runs", "abort")
        self.assertEqual(code, 2)
        self.assertEqual(len(result["pair_results"]), 1)
        self.assertEqual(result["status"], "ABORTED_REVIEW_REQUIRED")
        self.assertEqual(closed["status"], "CHECKED_NO_UNEXPECTED_FILES")

    def test_unexpected_file_keeps_closeout_pending_even_after_completed_capture(self):
        with tempfile.TemporaryDirectory() as root:
            code, result, closed = self.execute_fake(Path(root) / "runs", "unexpected")
        self.assertEqual(code, 2)
        self.assertEqual(closed["status"], "PENDING")
        self.assertEqual(result["ordinary_file_closeout"], "PENDING")

    def test_pending_previous_run_prevents_guard_and_capture(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "runs"
            directory.mkdir(mode=0o700)
            previous = directory / "run-previous"
            previous.mkdir(mode=0o700)
            m.begin_closeout(previous)
            with patch.object(m, "GuardClient") as guard, patch.object(m, "capture_pair") as capture:
                with self.assertRaisesRegex(m.Stop, "previous_closeout_pending"):
                    self.execute_fake(directory)
                guard.assert_not_called()
                capture.assert_not_called()


class TestProcessExit(unittest.TestCase):
    def test_missing_group_is_verified_without_unrelated_process_kill(self):
        process = SimpleNamespace(pid=123456, wait=Mock())
        with patch.object(m.os, "killpg", side_effect=ProcessLookupError(), create=True) as kill, \
                patch.object(m.signal, "SIGKILL", 9, create=True):
            m.stop_own_capture(process)
        kill.assert_called_once_with(process.pid, m.signal.SIGTERM)
        process.wait.assert_called_once_with(timeout=1)

    def test_wrapper_exit_does_not_skip_remaining_group(self):
        process = SimpleNamespace(pid=123456, wait=Mock(), poll=lambda: 0)
        with patch.object(m.os, "killpg", side_effect=[None, ProcessLookupError()], create=True) as kill, \
                patch.object(m.signal, "SIGKILL", 9, create=True):
            m.stop_own_capture(process)
        self.assertEqual([call.args for call in kill.call_args_list],
                         [(process.pid, m.signal.SIGTERM), (process.pid, 0)])

    def test_unverified_group_exit_is_not_reported_as_clean(self):
        process = SimpleNamespace(pid=123456, wait=Mock())
        with patch.object(m.os, "killpg", create=True), \
                patch.object(m.signal, "SIGKILL", 9, create=True), \
                patch.object(m.time, "monotonic", side_effect=[0, 2, 3, 5]):
            with self.assertRaisesRegex(m.Stop, "capture_process_group_exit_unverified"):
                m.stop_own_capture(process)


if __name__ == "__main__":
    unittest.main()
