from __future__ import annotations

import unittest

from reachy_stage3v.attention_hold import AttentionHoldResult
from reachy_stage3v.fused_shadow import ShadowDecision
from reachy_stage3v.interaction_shadow import InteractionShadowController


class InteractionShadowTests(unittest.TestCase):
    def select(self) -> ShadowDecision:
        return ShadowDecision(
            state="SELECT",
            reason="SUPPORTED",
            candidate_face_track_id="face-a",
            candidate_heading_deg=5.0,
        )

    def held(self) -> AttentionHoldResult:
        return AttentionHoldResult(
            state="HELD",
            reason="BOUNDED_FACE_DIRECTED_ATTENTION_HELD",
            dwell_ms=1200.0,
        )

    def test_positive_shadow_path_orders_orientation_hold_and_response(self) -> None:
        controller = InteractionShadowController()
        orientation = controller.observe_selection(self.select())
        self.assertTrue(orientation.would_orient)
        self.assertEqual(orientation.actuation_commands, 0)
        self.assertEqual(
            controller.report_orientation(succeeded=True, fresh_and_healthy=True).state,
            "ATTEND",
        )
        response = controller.observe_attention(self.held())
        self.assertEqual(response.state, "WOULD_RESPOND")
        self.assertTrue(response.would_respond)
        self.assertEqual(response.response_text, "I heard you.")
        self.assertEqual(response.response_commands, 0)
        self.assertEqual(controller.report_response(succeeded=True).state, "COMPLETE")

    def test_abstention_never_reaches_motion_or_response(self) -> None:
        controller = InteractionShadowController()
        output = controller.observe_selection(ShadowDecision("ABSTAIN", "PLAYBACK_REJECTED"))
        self.assertEqual(output.state, "OBSERVE")
        self.assertFalse(output.would_orient)
        self.assertFalse(output.would_respond)

    def test_failed_orientation_latches_fault_and_cannot_return(self) -> None:
        controller = InteractionShadowController()
        controller.observe_selection(self.select())
        failed = controller.report_orientation(succeeded=False, fresh_and_healthy=True)
        self.assertEqual(failed.state, "FAULT")
        later = controller.report_orientation(succeeded=True, fresh_and_healthy=True)
        self.assertEqual(later.state, "FAULT")

    def test_response_before_attention_is_a_fault(self) -> None:
        controller = InteractionShadowController()
        self.assertEqual(controller.report_response(succeeded=True).state, "FAULT")


if __name__ == "__main__":
    unittest.main()
