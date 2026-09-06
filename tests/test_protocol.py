import unittest
from collections import Counter

from reachy_doa.protocol import PLANS


class ProtocolTests(unittest.TestCase):
    def test_direction_calibration_is_eight_by_five(self) -> None:
        steps = PLANS["direction-calibration"].steps
        self.assertEqual(len(steps), 40)
        counts = Counter(step.true_position_deg for step in steps)
        self.assertEqual(set(counts.values()), {5})
        self.assertEqual(len(counts), 8)

    def test_guided_names_are_deterministic_and_safe(self) -> None:
        step = PLANS["direction-calibration"].steps[0]
        self.assertIn("direction-calibration_01-of-40_front_take01", step.run_id)
        self.assertNotIn(" ", step.run_id)

    def test_front_back_fold_to_same_expected_doa(self) -> None:
        steps = PLANS["direction-calibration"].steps
        front = next(step for step in steps if step.true_position_deg == 0.0)
        back = next(step for step in steps if step.true_position_deg == 180.0)
        self.assertAlmostEqual(front.expected_doa_deg, 90.0)
        self.assertAlmostEqual(back.expected_doa_deg, 90.0)

    def test_displayed_right_maps_to_zero_degree_sensor_side(self) -> None:
        steps = PLANS["direction-calibration"].steps
        front_right = next(step for step in steps if step.true_position_deg == 45.0)
        right = next(step for step in steps if step.true_position_deg == 90.0)
        self.assertAlmostEqual(front_right.expected_doa_deg, 45.0)
        self.assertAlmostEqual(right.expected_doa_deg, 0.0)

    def test_endfire_diagnostic_is_two_sides_by_three(self) -> None:
        steps = PLANS["endfire-diagnostic"].steps
        self.assertEqual(len(steps), 6)
        counts = Counter(step.true_position_deg for step in steps)
        self.assertEqual(counts, {90.0: 3, -90.0: 3})
        self.assertTrue(all(step.duration_seconds == 10.0 for step in steps))
        self.assertTrue(all("continuously" in step.operator_instruction for step in steps))
        self.assertEqual(steps[0].expected_doa_deg, 0.0)
        self.assertEqual(steps[-1].expected_doa_deg, 180.0)

    def test_orientation_swap_reuses_two_room_marks(self) -> None:
        steps = PLANS["orientation-swap-control"].steps
        self.assertEqual(len(steps), 6)
        counts = Counter(step.true_position_deg for step in steps)
        self.assertEqual(counts, {-90.0: 3, 90.0: 3})
        self.assertTrue(all(step.duration_seconds == 10.0 for step in steps))
        self.assertEqual(steps[0].expected_doa_deg, 180.0)
        self.assertEqual(steps[-1].expected_doa_deg, 0.0)

    def test_front_back_plan_has_twelve_controlled_trials(self) -> None:
        steps = PLANS["front-back-ambiguity"].steps
        self.assertEqual(len(steps), 12)
        self.assertEqual([step.true_position_deg for step in steps[:3]], [0.0] * 3)
        self.assertEqual([step.true_position_deg for step in steps[3:6]], [180.0] * 3)
        self.assertTrue(all(step.expected_doa_deg == 90.0 for step in steps[:6]))
        self.assertTrue(all(step.true_position_deg is None for step in steps[6:]))
        self.assertTrue(all(step.duration_seconds == 10.0 for step in steps))

    def test_prompts_match_the_operator_action(self) -> None:
        self.assertTrue(all(step.prompt_text is None for step in PLANS["non-speech-confusion"].steps))
        rapid_side = [step for step in PLANS["two-speaker-conflict"].steps if step.label == "rapid-switch"]
        rapid_front_back = [
            step for step in PLANS["front-back-ambiguity"].steps if step.label == "front-back-rapid-switch"
        ]
        self.assertTrue(all(step.prompt_text == "Hello." for step in rapid_side + rapid_front_back))
        self.assertEqual(PLANS["silence-baseline"].steps[0].prompt_text, None)

    def test_all_current_plans_are_sensor_only(self) -> None:
        text = " ".join(
            step.operator_instruction.lower()
            for plan in PLANS.values()
            for step in plan.steps
        )
        for forbidden in ("start a robot app", "move reachy", "enable camera", "robot speaker"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
