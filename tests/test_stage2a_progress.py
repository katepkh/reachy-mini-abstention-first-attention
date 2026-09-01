import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reachy_stage2a.progress import load_matrix_progress, save_matrix_progress


class Stage2AProgressTests(unittest.TestCase):
    def test_progress_round_trip_and_privacy_markers(self):
        with tempfile.TemporaryDirectory() as temporary:
            data_dir = Path(temporary).resolve()
            progress_path = (data_dir / "matrix_progress.json").resolve()
            with (
                patch("reachy_stage2a.progress.STAGE2A_DATA_DIR", data_dir),
                patch("reachy_stage2a.progress.PROGRESS_PATH", progress_path),
            ):
                saved = save_matrix_progress(6, 15)
                self.assertEqual(saved, progress_path)
                self.assertEqual(load_matrix_progress(15), 6)
            payload = json.loads(progress_path.read_text(encoding="utf-8"))
            self.assertFalse(payload["contains_pixels"])
            self.assertFalse(payload["contains_audio"])
            self.assertFalse(payload["contains_transcript"])

    def test_invalid_or_out_of_bounds_progress_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            data_dir = Path(temporary).resolve()
            progress_path = (data_dir / "matrix_progress.json").resolve()
            progress_path.write_text('{"accepted_steps": 99}', encoding="utf-8")
            with patch("reachy_stage2a.progress.PROGRESS_PATH", progress_path):
                self.assertEqual(load_matrix_progress(15), 0)

    def test_invalid_save_is_rejected(self):
        with self.assertRaises(ValueError):
            save_matrix_progress(16, 15)


if __name__ == "__main__":
    unittest.main()
