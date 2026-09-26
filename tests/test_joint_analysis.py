from __future__ import annotations

import csv
import math
import tempfile
import unittest
from pathlib import Path

from reachy_stage3v.joint_analysis import assess_joint_commissioning, load_joint_csv
from reachy_stage3v.joint_instrument import JOINT_REQUIRED_COLUMNS


class JointAnalysisTests(unittest.TestCase):
    def write_rows(self, root: Path, *, count: int = 201, doa_valid: bool = True) -> Path:
        path = root / "joint.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=JOINT_REQUIRED_COLUMNS)
            writer.writeheader()
            for index in range(count):
                timestamp = index * 40.0
                phase = 2.0 * math.pi * index / 25.0
                row = {column: "" for column in JOINT_REQUIRED_COLUMNS}
                row.update(
                    {
                        "timestamp_ms": timestamp,
                        "wall_time_iso": "2026-09-26T10:00:00.000Z",
                        "scheduler_lateness_ms": 1.0,
                        "sample_gap_ms": 0.0 if index == 0 else 40.0,
                        "audio_context_time_ms": timestamp,
                        "audio_dbfs": -40.0 + 4.0 * math.sin(phase),
                        "face_count": 1,
                        "face_center_x_norm": 0.5,
                        "face_center_y_norm": 0.5,
                        "face_heading_estimate_deg": 0.0,
                        "face_scale": 0.2,
                        "lip_aperture": 0.02 + 0.01 * math.sin(phase),
                        "lip_motion": 0.002,
                        "landmark_inference_ms": 20.0,
                        "video_frame_age_ms": 10.0,
                        "video_presented_frames": index,
                        "video_dropped_frames": 0,
                        "doa_valid": str(doa_valid).lower(),
                        "doa_raw_angle_rad": math.pi / 2.0 if doa_valid else "",
                        "doa_axis_deg": 90.0 if doa_valid else "",
                        "doa_speech_detected": str(doa_valid).lower(),
                        "doa_observed_ms": timestamp - 50.0,
                        "doa_received_ms": timestamp - 45.0,
                        "doa_age_ms": 50.0,
                        "doa_roundtrip_ms": 10.0,
                        "doa_clock_uncertainty_ms": 5.0,
                        "doa_robot_http_latency_ms": 4.0,
                        "doa_http_status": 200 if doa_valid else "",
                        "doa_error_code": "" if doa_valid else "timeout",
                        "doa_poll_failures": 0 if doa_valid else index,
                        "doa_poll_skips": 0,
                    }
                )
                writer.writerow(row)
        return path

    def test_passing_commissioning_file_proves_observability_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = assess_joint_commissioning(self.write_rows(Path(directory)))
        self.assertTrue(result["checks_passed"])
        self.assertGreater(result["observability"]["joint_spatial_rows"], 0)
        self.assertIsNotNone(result["pilot_transfer_synchrony"])
        self.assertFalse(result["motion_authorized"])
        self.assertIn("does not validate", result["claim_boundary"])

    def test_unavailable_doa_fails_separately_from_synchrony(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = assess_joint_commissioning(
                self.write_rows(Path(directory), doa_valid=False)
            )
        self.assertFalse(result["checks_passed"])
        self.assertIn("DOA_AVAILABILITY_TOO_LOW", result["failures"])
        self.assertIn("NO_JOINT_SPATIAL_ROWS", result["failures"])
        self.assertIsNotNone(result["pilot_transfer_synchrony"])

    def test_missing_column_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.csv"
            path.write_text("timestamp_ms\n0\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_joint_csv(path)


if __name__ == "__main__":
    unittest.main()
