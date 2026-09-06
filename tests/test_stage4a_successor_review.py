import ast
import math
from pathlib import Path
import unittest

import numpy as np

import reachy_stage4.successor_review as successor_review
from reachy_stage4.successor_review import (
    CANDIDATE_MIN_BASELINE_FRAMES,
    REQUIRED_REVIEW_RECORDS,
    REQUIRED_REVIEW_RECORD_FIELDS,
    assess_successor_review_packet,
)


def x_rotation(degrees: float, translation=(0.0, 0.0, 0.0)) -> np.ndarray:
    angle = math.radians(degrees)
    pose = np.eye(4)
    pose[:3, :3] = [
        [1.0, 0.0, 0.0],
        [0.0, math.cos(angle), -math.sin(angle)],
        [0.0, math.sin(angle), math.cos(angle)],
    ]
    pose[:3, 3] = translation
    return pose


def y_rotation(degrees: float) -> np.ndarray:
    angle = math.radians(degrees)
    pose = np.eye(4)
    pose[:3, :3] = [
        [math.cos(angle), 0.0, math.sin(angle)],
        [0.0, 1.0, 0.0],
        [-math.sin(angle), 0.0, math.cos(angle)],
    ]
    return pose


class Stage4ASuccessorReviewTests(unittest.TestCase):
    def test_stable_geometry_does_not_authorize_motion(self):
        frames = [x_rotation(2.7 + 0.001 * index) for index in range(CANDIDATE_MIN_BASELINE_FRAMES)]
        result = assess_successor_review_packet(frames, "UP")
        self.assertTrue(result["geometry_packet_complete"])
        self.assertFalse(result["review_packet_complete"])
        self.assertEqual(result["robot_connections"], 0)
        self.assertEqual(result["robot_commands_authorized"], 0)
        self.assertEqual(result["robot_commands_sent"], 0)
        self.assertAlmostEqual(result["observed"]["candidate_commanded_increment_deg"], 3.0, places=6)
        self.assertEqual(set(result["incomplete_review_records"]), set(REQUIRED_REVIEW_RECORDS))

    def test_complete_records_only_complete_the_packet(self):
        frames = [x_rotation(2.7) for _ in range(CANDIDATE_MIN_BASELINE_FRAMES)]
        result = assess_successor_review_packet(
            frames,
            "RIGHT",
            review_records={
                name: {
                    "artifact_reference": f"review/{name}.md#sha256-placeholder",
                    "artifact_sha256": "0" * 64,
                    "recorded_by": "reviewer-id",
                    "recorded_at_utc": "2026-09-02T12:00:00Z",
                }
                for name in REQUIRED_REVIEW_RECORDS
            },
        )
        self.assertTrue(result["review_packet_complete"])
        self.assertEqual(result["status"], "DESIGN_ONLY_NO_COMMAND_AUTHORITY")
        self.assertEqual(result["robot_commands_authorized"], 0)

    def test_boolean_review_flags_do_not_count_as_evidence(self):
        frames = [x_rotation(2.7) for _ in range(CANDIDATE_MIN_BASELINE_FRAMES)]
        result = assess_successor_review_packet(
            frames,
            "LEFT",
            review_records={name: True for name in REQUIRED_REVIEW_RECORDS},  # type: ignore[dict-item]
        )
        self.assertFalse(result["review_packet_complete"])
        self.assertEqual(
            set(result["incomplete_review_records"]),
            set(REQUIRED_REVIEW_RECORDS),
        )
        for missing_fields in result["incomplete_review_records"].values():
            self.assertEqual(set(missing_fields), set(REQUIRED_REVIEW_RECORD_FIELDS))

    def test_direction_mapping_is_explicit_and_three_degrees(self):
        frames = [np.eye(4) for _ in range(CANDIDATE_MIN_BASELINE_FRAMES)]
        expected = {
            "UP": (0.0, -3.0, 0.0),
            "DOWN": (0.0, 3.0, 0.0),
            "LEFT": (0.0, 0.0, 3.0),
            "RIGHT": (0.0, 0.0, -3.0),
        }
        for direction, expected_rpy in expected.items():
            with self.subTest(direction=direction):
                result = assess_successor_review_packet(frames, direction)
                np.testing.assert_allclose(
                    result["observed"]["target_rpy_deg"],
                    expected_rpy,
                    atol=1e-9,
                )
                self.assertAlmostEqual(
                    result["observed"]["candidate_commanded_increment_deg"],
                    3.0,
                    places=9,
                )

    def test_unstable_or_out_of_envelope_baseline_is_blocked(self):
        frames = [x_rotation(2.7) for _ in range(CANDIDATE_MIN_BASELINE_FRAMES)]
        frames[-1] = x_rotation(12.0, translation=(0.01, 0.0, 0.0))
        result = assess_successor_review_packet(frames, "UP")
        self.assertIn("BASELINE_ROTATION_UNSTABLE", result["blockers"])
        self.assertIn("BASELINE_TRANSLATION_UNSTABLE", result["blockers"])
        self.assertIn("CANDIDATE_ABSOLUTE_RPY_ENVELOPE_EXCEEDED", result["blockers"])
        self.assertIn("CANDIDATE_ABSOLUTE_ROTATION_ENVELOPE_EXCEEDED", result["blockers"])
        self.assertFalse(result["geometry_packet_complete"])

    def test_pairwise_spread_catches_opposite_drift_around_first_sample(self):
        frames = [x_rotation(2.7) for _ in range(CANDIDATE_MIN_BASELINE_FRAMES)]
        frames[1] = x_rotation(2.5)
        frames[-1] = x_rotation(2.9)
        result = assess_successor_review_packet(frames, "UP")
        self.assertIn("BASELINE_ROTATION_UNSTABLE", result["blockers"])
        self.assertAlmostEqual(
            result["observed"]["maximum_baseline_rotation_drift_deg"],
            0.4,
            places=6,
        )

    def test_geodesic_envelope_blocks_combined_rotation_below_axis_limits(self):
        combined = x_rotation(8.0) @ y_rotation(8.0)
        frames = [combined for _ in range(CANDIDATE_MIN_BASELINE_FRAMES)]
        result = assess_successor_review_packet(frames, "UP")
        self.assertNotIn("CANDIDATE_ABSOLUTE_RPY_ENVELOPE_EXCEEDED", result["blockers"])
        self.assertIn("CANDIDATE_ABSOLUTE_ROTATION_ENVELOPE_EXCEEDED", result["blockers"])

    def test_module_has_no_network_or_command_surface(self):
        tree = ast.parse(Path(successor_review.__file__).read_text(encoding="utf-8"))
        imported_roots = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported_roots.update(
            (node.module or "").split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.level == 0
        )
        self.assertTrue(imported_roots.isdisjoint({"requests", "urllib", "websocket", "websockets", "socket"}))
        called_attributes = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertTrue(called_attributes.isdisjoint({"send", "post", "put", "patch", "delete", "goto"}))


if __name__ == "__main__":
    unittest.main()
