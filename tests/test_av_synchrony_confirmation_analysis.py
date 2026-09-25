import csv
import tempfile
import unittest
from pathlib import Path

import numpy as np

from reachy_avsync.confirmation_analysis import (
    assess_quality,
    evaluate_trial,
    exact_mcnemar_pvalue,
    load_numeric_trial,
    wilson_interval,
)
from reachy_avsync.confirmation_protocol import canonical_trials


class AVSynchronyConfirmationAnalysisTests(unittest.TestCase):
    def _write_trial(self, path: Path) -> None:
        timestamps = np.arange(0.0, 10040.0, 40.0)
        phase = np.arange(len(timestamps), dtype=float) / 4.0
        audio = -45.0 + 4.0 * np.sin(phase)
        lip = 0.02 + 0.01 * np.sin(phase)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                ["timestamp_ms", "audio_dbfs", "lip_aperture", "face_scale", "face_count"]
            )
            for values in zip(timestamps, audio, lip, np.full(len(timestamps), 0.2), np.ones(len(timestamps)), strict=True):
                writer.writerow(values)

    def test_quality_and_frozen_candidate_pass_on_synchronous_signal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "trial.csv"
            self._write_trial(path)
            trial = next(
                item
                for item in canonical_trials()
                if item["condition_id"] == "live_visible_continuous"
            )
            data = load_numeric_trial(path)
            self.assertTrue(assess_quality(trial, data)["passed"])
            result = evaluate_trial(trial, data)
            self.assertTrue(result["candidate_proposed"])
            self.assertTrue(result["acoustic_only_proposed"])
            self.assertTrue(result["visual_only_proposed"])

    def test_exact_intervals_and_paired_test(self) -> None:
        low, high = wilson_interval(0, 36)
        self.assertEqual(low, 0.0)
        self.assertGreater(high, 0.0)
        self.assertEqual(exact_mcnemar_pvalue(0, 0), 1.0)
        self.assertAlmostEqual(exact_mcnemar_pvalue(0, 5), 0.0625)

    def test_rejects_wrong_column_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "trial.csv"
            path.write_text("audio_dbfs,timestamp_ms\n-40,0\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "columns must be exactly"):
                load_numeric_trial(path)


if __name__ == "__main__":
    unittest.main()
