import math
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from reachy_doa.analysis import analyse_frame, write_analysis_artifacts


def frame_for(condition: str, speech: list[bool], radians: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "run_id": ["trial-1"] * len(speech),
            "sequence": range(1, len(speech) + 1),
            "elapsed_ms": [index * 200 for index in range(len(speech))],
            "condition": [condition] * len(speech),
            "raw_angle_rad": radians,
            "raw_angle_deg": [math.degrees(value) for value in radians],
            "speech_detected": speech,
            "http_latency_ms": [20.0] * len(speech),
            "valid": [True] * len(speech),
        }
    )


class AnalysisTests(unittest.TestCase):
    def test_direction_error_uses_v19_axis(self) -> None:
        frame = frame_for("Normal speech", [True] * 5, [math.pi / 2] * 5)
        summary = analyse_frame(frame, {"run_id": "front", "true_position_deg": 0.0})
        self.assertEqual(summary["median_doa_deg"], 90.0)
        self.assertEqual(summary["median_abs_error_deg"], 0.0)
        self.assertEqual(summary["status"], "PASS")

    def test_silence_speech_positive_is_flagged(self) -> None:
        frame = frame_for("Silence", [True, False, True, False], [1.0] * 4)
        summary = analyse_frame(frame, {"run_id": "silence"})
        self.assertEqual(summary["status"], "FLAG")
        self.assertIn("Unexpected speech-positive", summary["findings"])

    def test_raw_radians_override_legacy_negative_degree_column(self) -> None:
        frame = frame_for("Normal speech", [True] * 4, [math.pi] * 4)
        frame["raw_angle_deg"] = -180.0
        summary = analyse_frame(frame, {"run_id": "diagram-left", "true_position_deg": -90.0})
        self.assertEqual(summary["median_doa_deg"], 180.0)
        self.assertEqual(summary["median_abs_error_deg"], 0.0)
        self.assertIn("Legacy CSV degree column", summary["findings"])

    def test_one_phrase_calibration_uses_protocol_specific_threshold(self) -> None:
        frame = frame_for("Normal speech", [True] * 5 + [False] * 20, [math.pi / 2] * 25)
        summary = analyse_frame(
            frame,
            {
                "run_id": "front",
                "true_position_deg": 0.0,
                "guided_trial": {"plan_id": "direction-calibration", "duration_target_seconds": 6.0},
            },
        )
        self.assertEqual(summary["speech_positive_rate_pct"], 20.0)
        self.assertNotIn("Low speech-positive", summary["findings"])

    def test_analysis_artifacts_cannot_escape_data_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                write_analysis_artifacts(Path(temporary))


if __name__ == "__main__":
    unittest.main()
