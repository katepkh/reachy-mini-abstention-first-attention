import csv
import io
import math
import tempfile
import time
import unittest
from pathlib import Path

from reachy_doa.models import CSV_COLUMNS, DoAReading, TrialDefinition
from reachy_doa.recorder import TrialRecorder, safe_run_id


class RecorderTests(unittest.TestCase):
    def test_sanitises_run_id(self) -> None:
        self.assertEqual(safe_run_id("  quiet room / take 1  "), "quiet-room-take-1")

    def test_csv_has_exact_required_columns(self) -> None:
        now = time.perf_counter()
        recorder = TrialRecorder(TrialDefinition("test-01", 0.0, "Speech", "note"))
        recorder.start(now)
        recorder.add(
            DoAReading("2026-08-20T10:00:00+01:00", now + 0.1, 1.0, True, 12.0, 200, True, ""),
            sequence=1,
            smoothed_angle_deg=57.3,
        )
        reader = csv.DictReader(io.StringIO(recorder.csv_text()))
        self.assertEqual(reader.fieldnames, CSV_COLUMNS)
        self.assertEqual(len(list(reader)), 1)

    def test_saves_only_inside_project_data_tree(self) -> None:
        recorder = TrialRecorder(TrialDefinition("test-01", None, "Silence", ""))
        recorder.start(time.perf_counter())
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                recorder.save(Path(temporary))

    def test_csv_preserves_v19_right_edge_as_positive_180(self) -> None:
        now = time.perf_counter()
        recorder = TrialRecorder(TrialDefinition("right-edge", 90.0, "Speech", ""))
        recorder.start(now)
        recorder.add(
            DoAReading("2026-08-20T10:00:00+01:00", now + 0.1, math.pi, True, 12.0, 200, True, ""),
            sequence=1,
            smoothed_angle_deg=180.0,
        )
        row = next(csv.DictReader(io.StringIO(recorder.csv_text())))
        self.assertEqual(float(row["raw_angle_deg"]), 180.0)


if __name__ == "__main__":
    unittest.main()
