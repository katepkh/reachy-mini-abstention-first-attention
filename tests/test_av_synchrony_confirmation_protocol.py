import unittest
from collections import Counter

from reachy_avsync.confirmation_protocol import (
    CONDITIONS,
    canonical_trials,
    confirmation_protocol_payload,
    randomized_schedule,
)


class AVSynchronyConfirmationProtocolTests(unittest.TestCase):
    def test_schedule_is_complete_unique_and_deterministic(self):
        canonical = canonical_trials()
        randomized = randomized_schedule()
        self.assertEqual(len(canonical), 54)
        self.assertEqual(len({item["trial_id"] for item in canonical}), 54)
        self.assertEqual(randomized, randomized_schedule())
        self.assertEqual(
            {item["trial_id"] for item in canonical},
            {item["trial_id"] for item in randomized},
        )

    def test_each_room_heading_block_contains_every_condition(self):
        expected = {condition["id"] for condition in CONDITIONS}
        for room in ("room_a", "room_b", "room_c"):
            for heading in (-20, 0, 20):
                observed = {
                    item["condition_id"]
                    for item in canonical_trials()
                    if item["room"] == room and item["visible_heading_deg"] == heading
                }
                self.assertEqual(observed, expected)

    def test_voice_allocation_is_balanced(self):
        playback = [item for item in canonical_trials() if item["playback_voice_id"]]
        self.assertEqual(Counter(item["playback_voice_id"] for item in playback), {"voice_a": 18, "voice_b": 18})
        for room in ("room_a", "room_b", "room_c"):
            for heading in (-20, 0, 20):
                block = [
                    item
                    for item in playback
                    if item["room"] == room and item["visible_heading_deg"] == heading
                ]
                self.assertEqual(Counter(item["playback_voice_id"] for item in block), {"voice_a": 2, "voice_b": 2})

    def test_opposite_playback_is_never_colocated(self):
        opposite_ids = {
            "silent_face_opposite_playback",
            "live_speech_plus_opposite_playback",
        }
        for item in canonical_trials():
            if item["condition_id"] in opposite_ids:
                self.assertNotEqual(item["visible_heading_deg"], item["playback_heading_deg"])

    def test_protocol_binds_candidate_and_forbids_motion_and_retuning(self):
        payload = confirmation_protocol_payload()
        self.assertEqual(len(payload["fingerprint"]), 64)
        self.assertEqual(payload["trial_counts"], {"total": 54, "matching_positive": 18, "hard_negative": 36, "per_room": 18, "per_room_heading": 6})
        self.assertEqual(payload["frozen_candidate"]["selection_or_retuning_during_confirmation"], "PROHIBITED")
        self.assertEqual(payload["scope"]["robot_motion_commands"], 0)
        self.assertEqual(payload["scope"]["torque_calibration_or_motor_mode_commands"], 0)


if __name__ == "__main__":
    unittest.main()
