import math
import unittest

from reachy_stage2a.tournament import CounterfactualDecision
from reachy_stage3a.controller import (
    MotionEnvelope,
    MotionShadowController,
    heading_unit_vector,
    signed_heading_degrees,
)


def evidence(confirmed=True, heading=15.0, reason="TEMPORAL_CONSENSUS"):
    return CounterfactualDecision(confirmed, heading if confirmed else None, reason)


class Stage3AControllerTests(unittest.TestCase):
    def test_signed_heading_normalisation(self):
        self.assertEqual(signed_heading_degrees(190.0), -170.0)
        self.assertEqual(signed_heading_degrees(-190.0), 170.0)
        self.assertEqual(signed_heading_degrees(0.0), 0.0)

    def test_heading_vector_uses_front_zero_right_positive_frame(self):
        right, forward, up = heading_unit_vector(90.0)
        self.assertAlmostEqual(right, 1.0)
        self.assertAlmostEqual(forward, 0.0, places=7)
        self.assertEqual(up, 0.0)

    def test_confirmed_target_produces_bounded_shadow_move(self):
        controller = MotionShadowController()
        decision = controller.process(0.0, evidence(heading=35.0))
        self.assertEqual(decision.action, "WOULD_MOVE")
        self.assertEqual(decision.desired_heading_deg, 35.0)
        self.assertEqual(decision.target_yaw_deg, 20.0)
        self.assertEqual(decision.duration_s, 1.25)

    def test_aligned_target_holds(self):
        controller = MotionShadowController()
        decision = controller.process(0.0, evidence(heading=2.0))
        self.assertEqual(decision.action, "HOLD")
        self.assertEqual(decision.reason, "ALREADY_ALIGNED")

    def test_cooldown_blocks_a_second_target(self):
        controller = MotionShadowController()
        self.assertEqual(controller.process(0.0, evidence(heading=15.0)).action, "WOULD_MOVE")
        decision = controller.process(500.0, evidence(heading=-15.0))
        self.assertEqual(decision.action, "HOLD")
        self.assertEqual(decision.reason, "MOTION_COOLDOWN")

    def test_network_fault_fails_closed_even_after_a_move(self):
        controller = MotionShadowController()
        controller.process(0.0, evidence(heading=15.0))
        fault = evidence(False, reason="NETWORK_INVALID")
        decision = controller.process(3000.0, fault)
        self.assertEqual(decision.action, "HOLD")
        self.assertEqual(decision.reason, "FAIL_CLOSED")

    def test_sustained_quiet_can_propose_return_to_neutral(self):
        controller = MotionShadowController()
        controller.process(0.0, evidence(heading=15.0))
        quiet = evidence(False, reason="ACOUSTIC_NOT_TRACKING")
        decision = controller.process(2100.0, quiet)
        self.assertEqual(decision.action, "RETURN_NEUTRAL")
        self.assertEqual(decision.target_yaw_deg, 0.0)

    def test_default_envelope_is_conservative(self):
        envelope = MotionEnvelope()
        self.assertLessEqual(envelope.max_abs_yaw_deg, 20.0)
        self.assertGreaterEqual(envelope.duration_s, 1.0)
        self.assertGreaterEqual(envelope.cooldown_ms, 2000.0)
        self.assertTrue(math.isfinite(envelope.quiet_return_ms))


if __name__ == "__main__":
    unittest.main()
