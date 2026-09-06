import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reachy_stage3v.progress import (
    _write_json_atomic,
    complete_step_replacement,
    load_pending_replacement,
    load_progress_state,
    save_progress,
    stage_step_replacement,
    synchronise_pending_replacement,
)


class Stage3VProgressTests(unittest.TestCase):
    def test_atomic_progress_write_retries_a_transient_windows_share_violation(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "progress.json"
            original_replace = Path.replace
            attempts = 0

            def transient_replace(path, destination):
                nonlocal attempts
                attempts += 1
                if attempts < 3:
                    raise PermissionError(5, "temporarily locked")
                return original_replace(path, destination)

            with (
                patch.object(Path, "replace", transient_replace),
                patch("reachy_stage3v.progress.time.sleep"),
            ):
                _write_json_atomic(target, {"accepted_steps": 1})

            self.assertEqual(attempts, 3)
            self.assertEqual(
                json.loads(target.read_text(encoding="utf-8"))["accepted_steps"],
                1,
            )

    def test_one_step_replacement_preserves_prefix_and_suffix(self):
        with tempfile.TemporaryDirectory() as temporary:
            data_dir = Path(temporary).resolve()
            progress_path = data_dir / "progress.json"
            plan_path = data_dir / "replacement_plan.json"
            files = [f"step-{index}.csv" for index in range(1, 6)]
            for filename in files:
                (data_dir / filename).write_text("sequence\n", encoding="utf-8")
            replacement = "step-3-corrected.csv"
            (data_dir / replacement).write_text("sequence\n", encoding="utf-8")
            with (
                patch("reachy_stage3v.progress.DATA_DIR", data_dir),
                patch("reachy_stage3v.progress.PROGRESS_PATH", progress_path),
                patch("reachy_stage3v.progress.REPLACEMENT_PLAN_PATH", plan_path),
            ):
                save_progress(5, 5, files)
                plan = stage_step_replacement(3, 5, "operator-reported deviation")
                self.assertEqual(plan["original_file"], "step-3.csv")
                self.assertEqual(load_progress_state(5)["accepted_csv_files"], files[:2])
                self.assertIsNotNone(load_pending_replacement(5))

                combined = complete_step_replacement(3, replacement, files[:2], 5)
                self.assertEqual(combined, [*files[:2], replacement, *files[3:]])
                self.assertEqual(load_progress_state(5)["accepted_steps"], 5)
                self.assertIsNone(load_pending_replacement(5))
                completed = json.loads(plan_path.read_text(encoding="utf-8"))
                self.assertEqual(completed["status"], "COMPLETED")
                self.assertEqual(completed["replacement_file"], replacement)

    def test_replacement_requires_target_to_be_already_accepted(self):
        with tempfile.TemporaryDirectory() as temporary:
            data_dir = Path(temporary).resolve()
            progress_path = data_dir / "progress.json"
            plan_path = data_dir / "replacement_plan.json"
            with (
                patch("reachy_stage3v.progress.DATA_DIR", data_dir),
                patch("reachy_stage3v.progress.PROGRESS_PATH", progress_path),
                patch("reachy_stage3v.progress.REPLACEMENT_PLAN_PATH", plan_path),
            ):
                save_progress(2, 5, ["one.csv", "two.csv"])
                with self.assertRaises(ValueError):
                    stage_step_replacement(3, 5, "not accepted")

    def test_in_progress_replacement_restores_later_accepted_steps(self):
        with tempfile.TemporaryDirectory() as temporary:
            data_dir = Path(temporary).resolve()
            progress_path = data_dir / "progress.json"
            plan_path = data_dir / "replacement_plan.json"
            files = [f"step-{index}.csv" for index in range(1, 9)]
            for filename in files:
                (data_dir / filename).write_text("sequence\n", encoding="utf-8")
            replacement = "step-7-corrected.csv"
            (data_dir / replacement).write_text("sequence\n", encoding="utf-8")
            with (
                patch("reachy_stage3v.progress.DATA_DIR", data_dir),
                patch("reachy_stage3v.progress.PROGRESS_PATH", progress_path),
                patch("reachy_stage3v.progress.REPLACEMENT_PLAN_PATH", plan_path),
            ):
                save_progress(8, 18, files)
                plan = stage_step_replacement(7, 18, "operator stood at +20 instead of +10")
                self.assertEqual(plan["resume_accepted_steps"], 8)
                self.assertEqual(load_progress_state(18)["accepted_steps"], 6)
                combined = complete_step_replacement(7, replacement, files[:6], 18)
                self.assertEqual(combined, [*files[:6], replacement, files[7]])
                restored = load_progress_state(18)
                self.assertEqual(restored["accepted_steps"], 8)
                self.assertEqual(restored["accepted_csv_files"], combined)

    def test_pending_replacement_absorbs_later_steps_from_a_stale_session(self):
        with tempfile.TemporaryDirectory() as temporary:
            data_dir = Path(temporary).resolve()
            progress_path = data_dir / "progress.json"
            plan_path = data_dir / "replacement_plan.json"
            files = [f"step-{index}.csv" for index in range(1, 19)]
            for filename in files:
                (data_dir / filename).write_text("sequence\n", encoding="utf-8")
            with (
                patch("reachy_stage3v.progress.DATA_DIR", data_dir),
                patch("reachy_stage3v.progress.PROGRESS_PATH", progress_path),
                patch("reachy_stage3v.progress.REPLACEMENT_PLAN_PATH", plan_path),
            ):
                save_progress(12, 18, files[:12])
                stage_step_replacement(7, 18, "operator correction")
                # Simulate an older browser session reaching completion before
                # it observes the replacement checkpoint.
                save_progress(18, 18, files)
                plan = synchronise_pending_replacement(18)
                self.assertEqual(plan["resume_accepted_steps"], 18)
                self.assertEqual(plan["suffix_files"], files[7:])
                checkpoint = load_progress_state(18)
                self.assertEqual(checkpoint["accepted_steps"], 6)
                self.assertEqual(checkpoint["accepted_csv_files"], files[:6])


if __name__ == "__main__":
    unittest.main()
