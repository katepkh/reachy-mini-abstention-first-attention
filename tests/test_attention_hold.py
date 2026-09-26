from __future__ import annotations

import unittest

from reachy_stage3v.attention_hold import (
    AttentionHoldController,
    FaceAttentionObservation,
)


class AttentionHoldTests(unittest.TestCase):
    def observation(self, elapsed: float, **changes: object) -> FaceAttentionObservation:
        values: dict[str, object] = {
            "elapsed_ms": elapsed,
            "healthy": True,
            "health_reason": "READY",
            "face_track_id": "face-a",
            "x_error_norm": 0.02,
            "y_error_norm": 0.01,
            "observation_age_ms": 20.0,
        }
        values.update(changes)
        return FaceAttentionObservation(**values)  # type: ignore[arg-type]

    def test_continuous_in_region_dwell_reaches_held(self) -> None:
        controller = AttentionHoldController("face-a")
        self.assertEqual(controller.process(self.observation(0.0)).state, "ACQUIRING")
        self.assertEqual(controller.process(self.observation(600.0)).state, "ACQUIRING")
        result = controller.process(self.observation(1200.0))
        self.assertEqual(result.state, "HELD")
        self.assertFalse(result.motion_authorized)
        self.assertFalse(result.response_authorized)

    def test_region_exit_resets_dwell_and_requests_no_command(self) -> None:
        controller = AttentionHoldController("face-a")
        controller.process(self.observation(0.0))
        result = controller.process(self.observation(800.0, x_error_norm=0.12))
        self.assertEqual(result.state, "CORRECTION_NEEDED")
        self.assertEqual(result.actuation_commands, 0)
        self.assertEqual(controller.process(self.observation(1200.0)).state, "ACQUIRING")

    def test_stale_unhealthy_or_far_observation_latches_abort(self) -> None:
        for changes in (
            {"observation_age_ms": 600.0},
            {"healthy": False, "health_reason": "STATE_STALE"},
            {"x_error_norm": 0.5},
        ):
            controller = AttentionHoldController("face-a")
            first = controller.process(self.observation(0.0, **changes))
            self.assertEqual(first.state, "ABORT")
            self.assertEqual(controller.process(self.observation(2000.0)).state, "ABORT")

    def test_face_loss_has_bounded_grace_then_aborts(self) -> None:
        controller = AttentionHoldController("face-a")
        controller.process(self.observation(0.0))
        pending = controller.process(self.observation(300.0, face_track_id=None))
        aborted = controller.process(self.observation(900.0, face_track_id=None))
        self.assertEqual(pending.state, "ACQUIRING")
        self.assertEqual(aborted.state, "ABORT")

    def test_oscillation_limit_fails_closed(self) -> None:
        controller = AttentionHoldController("face-a")
        result = None
        for index, value in enumerate((0.12, -0.12, 0.12, -0.12, 0.12)):
            result = controller.process(self.observation(index * 200.0, x_error_norm=value))
        self.assertIsNotNone(result)
        self.assertEqual(result.state, "ABORT")
        self.assertEqual(result.reason, "OSCILLATION_LIMIT_EXCEEDED")


if __name__ == "__main__":
    unittest.main()
