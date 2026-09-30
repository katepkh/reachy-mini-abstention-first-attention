from __future__ import annotations

import unittest

from reachy_stage3v.joint_pilot_protocol import (
    JOINT_PILOT_CONDITION_IDS,
    canonical_joint_pilot_trials,
    joint_pilot_protocol_payload,
    randomized_joint_pilot_trials,
)


class JointPilotProtocolTests(unittest.TestCase):
    def test_schedule_contains_three_balanced_blocks(self) -> None:
        schedule = randomized_joint_pilot_trials()
        self.assertEqual(len(schedule), 21)
        self.assertEqual([item["schedule_index"] for item in schedule], list(range(1, 22)))
        for repetition in (1, 2, 3):
            block = [item for item in schedule if item["repetition"] == repetition]
            self.assertEqual(
                {item["condition_id"] for item in block},
                set(JOINT_PILOT_CONDITION_IDS),
            )

    def test_randomization_preserves_canonical_trials(self) -> None:
        canonical = canonical_joint_pilot_trials()
        schedule = randomized_joint_pilot_trials()
        self.assertEqual(
            {item["trial_id"] for item in schedule},
            {item["trial_id"] for item in canonical},
        )
        self.assertEqual(sum(item["split"] == "development" for item in canonical), 14)
        self.assertEqual(sum(item["split"] == "internal_validation" for item in canonical), 7)

    def test_protocol_is_command_free_and_fail_closed(self) -> None:
        payload = joint_pilot_protocol_payload()
        self.assertEqual(payload["schema"], "reachy-joint-shadow-no-motion-pilot-v2")
        self.assertTrue(
            all(
                trial["trial_id"].startswith("joint-shadow-pilot-v2-")
                for trial in payload["canonical_trials"]
            )
        )
        constraints = payload["capture_constraints"]
        self.assertEqual(constraints["motion_commands"], 0)
        self.assertEqual(constraints["response_commands"], 0)
        self.assertFalse(constraints["raw_media_saved"])
        self.assertFalse(constraints["raw_media_uploaded"])
        self.assertEqual(
            payload["opening_gate"]["analysis_code"],
            "IMPLEMENTED_AND_CONTENT_ADDRESSED",
        )
        selection = " ".join(payload["development_selection_rule"])
        self.assertIn("zero proposals", selection)
        self.assertIn("without relaxing", selection)

    def test_v2_face_scale_gate_has_pre_pilot_basis_and_excludes_v1(self) -> None:
        payload = joint_pilot_protocol_payload()
        self.assertEqual(
            payload["quality_gates"]["minimum_median_face_scale_when_required"],
            0.06,
        )
        revision = payload["revision_from_v1"]
        self.assertFalse(revision["v1_trial_ids_reusable"])
        self.assertFalse(revision["v1_attempts_reusable"])
        self.assertIn("pre-pilot commissioning", revision["independent_threshold_basis"])
        self.assertNotEqual(payload["randomization"]["seed"], 20260926)

    def test_fingerprint_is_deterministic(self) -> None:
        first = joint_pilot_protocol_payload()
        second = joint_pilot_protocol_payload()
        self.assertEqual(first["fingerprint"], second["fingerprint"])
        self.assertEqual(len(first["fingerprint"]), 64)


if __name__ == "__main__":
    unittest.main()
