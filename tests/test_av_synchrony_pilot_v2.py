from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from reachy_avsync.pilot_v2 import (
    analyze_pilot_v2,
    assess_pilot_v2_quality,
    load_pilot_v2_trial,
    pilot_v2_candidate_specs,
)
from reachy_avsync.pilot_v2_protocol import (
    canonical_pilot_v2_trials,
    pilot_v2_protocol_payload,
    randomized_pilot_v2_trials,
)
from reachy_avsync.pilot_v2_synthetic import write_synthetic_pilot_v2
from scripts.run_av_synchrony_pilot_v2_dry_run import matches_frozen_analysis


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class AudioMouthSynchronyPilotV2Tests(unittest.TestCase):
    def test_frozen_dry_run_allows_roundoff_but_rejects_source_or_gate_changes(self) -> None:
        stored = (
            PROJECT_ROOT / "evidence" / "analysis" / "av_synchrony_pilot_v2_synthetic_dry_run.json"
        ).read_bytes()
        report = json.loads(stored)
        report["trial_quality"][0]["audio_dbfs_std"] += 5e-13
        self.assertTrue(matches_frozen_analysis(stored, json.dumps(report).encode("utf-8")))

        report["selected_candidate"]["spec"]["min_correlation"] += 1e-13
        self.assertFalse(matches_frozen_analysis(stored, json.dumps(report).encode("utf-8")))

        report = json.loads(stored)
        report["source_bundle_sha256"] = "0" * 64
        self.assertFalse(matches_frozen_analysis(stored, json.dumps(report).encode("utf-8")))

    def test_protocol_has_frozen_development_validation_split(self) -> None:
        canonical = canonical_pilot_v2_trials()
        randomized = randomized_pilot_v2_trials()
        self.assertEqual(len(canonical), 12)
        self.assertEqual(sum(item["split"] == "development" for item in canonical), 8)
        self.assertEqual(sum(item["split"] == "internal_validation" for item in canonical), 4)
        self.assertEqual(
            sorted(item["trial_id"] for item in canonical),
            sorted(item["trial_id"] for item in randomized),
        )
        self.assertNotEqual(canonical, randomized)
        payload = pilot_v2_protocol_payload()
        self.assertFalse(payload["scope"]["reachy_power_required"])
        self.assertTrue(payload["privacy"]["runtime_and_model_served_from_localhost"])
        self.assertEqual(payload["instrument_revision"], 3)
        self.assertEqual(
            payload["instrument_revision_history"]["commissioning_attempt_sample_counts"],
            [90, 86, 86, 142, 146, 138],
        )
        self.assertTrue(all(item["duration_s"] == 10 for item in canonical))
        self.assertFalse(
            payload["instrument_revision_history"]["quality_or_selection_threshold_changed"]
        )

    def test_grid_contains_45_unique_settings_without_amplitude_search(self) -> None:
        settings = pilot_v2_candidate_specs()
        self.assertEqual(len(settings), 45)
        keys = {
            (spec.min_correlation, spec.max_abs_lag_ms, smoothing)
            for spec, smoothing in settings
        }
        self.assertEqual(len(keys), 45)
        self.assertNotIn("min_audio_std", pilot_v2_protocol_payload()["threshold_grid"])

    def test_synthetic_pipeline_passes_development_and_internal_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_synthetic_pilot_v2(root)
            report = analyze_pilot_v2(root)
        self.assertTrue(report["development_selection_succeeded"])
        self.assertTrue(report["internal_validation_passed"])
        self.assertEqual(report["candidate_count"], 45)
        self.assertEqual(report["robot_connections"], 0)

    def test_multiple_faces_fail_objective_quality(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_synthetic_pilot_v2(root)
            trial = canonical_pilot_v2_trials()[0]
            path = root / f"{trial['trial_id']}.csv"
            with path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.reader(handle))
            rows[1][4] = "2"
            with path.open("w", encoding="utf-8", newline="") as handle:
                csv.writer(handle, lineterminator="\n").writerows(rows)
            quality = assess_pilot_v2_quality(trial, load_pilot_v2_trial(path))
        self.assertFalse(quality["passed"])
        self.assertIn("MULTIPLE_FACES_OBSERVED", quality["failures"])

    def test_out_of_range_audio_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(
                    ["timestamp_ms", "audio_dbfs", "lip_aperture", "face_scale", "face_count"]
                )
                writer.writerow([0, 5, 0.1, 0.2, 1])
            with self.assertRaisesRegex(ValueError, "audio_dbfs"):
                load_pilot_v2_trial(path)

    def test_nonincreasing_timestamps_fail_objective_quality(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_synthetic_pilot_v2(root)
            trial = canonical_pilot_v2_trials()[0]
            path = root / f"{trial['trial_id']}.csv"
            with path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.reader(handle))
            rows[2][0] = rows[1][0]
            with path.open("w", encoding="utf-8", newline="") as handle:
                csv.writer(handle, lineterminator="\n").writerows(rows)
            quality = assess_pilot_v2_quality(trial, load_pilot_v2_trial(path))
        self.assertFalse(quality["passed"])
        self.assertIn("TIMESTAMPS_NOT_STRICTLY_INCREASING", quality["failures"])

    def test_v2_recorder_is_local_numeric_only(self) -> None:
        source = (PROJECT_ROOT / "tools" / "avsync_pilot_recorder_v2.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("getUserMedia", source)
        self.assertIn("detectForVideo", source)
        self.assertIn("getTracks().forEach(track => track.stop())", source)
        self.assertIn('import(runtimeModuleUrl)', source)
        self.assertIn("acceptedCurrentTrial", source)
        self.assertIn("!repeatButton.disabled", source)
        self.assertIn("nextDeadline += manifest.sample_period_ms", source)
        self.assertIn("maximum_median_landmark_inference_ms", source)
        self.assertIn("delegate: manifest.instrument.delegate", source)
        self.assertNotIn("MediaRecorder", source)
        self.assertNotIn("WebSocket", source)
        self.assertNotIn("XMLHttpRequest", source)
        self.assertNotIn("https://", source)

    def test_v1_rejection_is_immutable_predecessor_context(self) -> None:
        predecessor = pilot_v2_protocol_payload()["predecessor"]
        self.assertEqual(predecessor["protocol"], "reachy-av-synchrony-off-robot-pilot-v1")
        self.assertIn("INSTRUMENT_REJECTED", predecessor["disposition"])


if __name__ == "__main__":
    unittest.main()
