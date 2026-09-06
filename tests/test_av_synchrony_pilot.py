from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest

from reachy_avsync.pilot import analyze_pilot, candidate_specs, load_numeric_trial
from reachy_avsync.pilot_protocol import (
    canonical_pilot_trials,
    pilot_protocol_payload,
    randomized_pilot_trials,
)
from reachy_avsync.pilot_synthetic import write_synthetic_pilot


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class AudioMouthSynchronyPilotTests(unittest.TestCase):
    def test_protocol_has_twelve_balanced_randomized_trials(self) -> None:
        canonical = canonical_pilot_trials()
        randomized = randomized_pilot_trials()
        self.assertEqual(len(canonical), 12)
        self.assertEqual(sum(item["role"] == "matching_positive" for item in canonical), 6)
        self.assertEqual(sum(item["role"] == "hard_negative" for item in canonical), 6)
        self.assertEqual(
            sorted(item["trial_id"] for item in canonical),
            sorted(item["trial_id"] for item in randomized),
        )
        self.assertNotEqual(canonical, randomized)
        payload = pilot_protocol_payload()
        self.assertFalse(payload["scope"]["reachy_power_required"])
        self.assertEqual(payload["scope"]["robot_connections"], 0)

    def test_threshold_grid_has_240_unique_candidates(self) -> None:
        specs = candidate_specs()
        self.assertEqual(len(specs), 240)
        keys = {
            (spec.min_correlation, spec.max_abs_lag_ms, spec.min_audio_std, spec.min_mouth_std)
            for spec in specs
        }
        self.assertEqual(len(keys), 240)

    def test_synthetic_pilot_exercises_complete_selection_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_synthetic_pilot(root)
            report = analyze_pilot(root)
        self.assertTrue(report["selection_succeeded"])
        selected = report["selected_candidate"]
        assert selected is not None
        self.assertEqual(selected["matching_positive_candidates"], 6)
        self.assertEqual(selected["hard_negative_candidates"], 0)
        self.assertEqual(report["candidate_count"], 240)
        self.assertEqual(report["robot_connections"], 0)

    def test_missing_trial_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(FileNotFoundError, "Missing pilot trial"):
                analyze_pilot(Path(directory))

    def test_malformed_columns_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["timestamp_ms", "audio_energy"])
                writer.writerow([0, 0])
            with self.assertRaisesRegex(ValueError, "columns must be exactly"):
                load_numeric_trial(path)

    def test_browser_recorder_has_no_raw_media_encoder_or_remote_endpoint(self) -> None:
        source = (PROJECT_ROOT / "tools" / "avsync_pilot_recorder.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("getUserMedia", source)
        self.assertIn("getTracks().forEach(track => track.stop())", source)
        self.assertIn("numeric_csv_only", pilot_protocol_payload()["privacy"])
        self.assertNotIn("MediaRecorder", source)
        self.assertNotIn("WebSocket", source)
        self.assertNotIn("XMLHttpRequest", source)
        self.assertNotIn("https://", source)


if __name__ == "__main__":
    unittest.main()
