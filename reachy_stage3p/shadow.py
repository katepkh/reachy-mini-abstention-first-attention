"""Bounded offline motion shadow for Stage 3P evidence."""

from __future__ import annotations

from dataclasses import dataclass

from .policy import Stage3PEvidence


@dataclass(frozen=True, slots=True)
class PitchShadowDecision:
    action: str
    target_yaw_deg: float | None
    target_pitch_deg: float | None
    reason: str


class CoupledMotionShadow:
    """Describe what a bounded controller would do without controlling hardware."""

    def __init__(
        self,
        *,
        maximum_abs_yaw_deg: float = 30.0,
        maximum_abs_pitch_deg: float = 20.0,
        pitch_deadband_deg: float = 2.0,
        minimum_interval_ms: float = 1000.0,
    ) -> None:
        self.maximum_abs_yaw_deg = maximum_abs_yaw_deg
        self.maximum_abs_pitch_deg = maximum_abs_pitch_deg
        self.pitch_deadband_deg = pitch_deadband_deg
        self.minimum_interval_ms = minimum_interval_ms
        self._last_adjustment_ms = -float("inf")

    def process(self, elapsed_ms: float, evidence: Stage3PEvidence) -> PitchShadowDecision:
        if not evidence.confirmed or evidence.target_yaw_deg is None or evidence.target_pitch_deg is None:
            return PitchShadowDecision("HOLD", None, None, evidence.reason)
        if abs(evidence.target_yaw_deg) > self.maximum_abs_yaw_deg:
            return PitchShadowDecision("HOLD", None, None, "YAW_BOUND_EXCEEDED")
        if abs(evidence.target_pitch_deg) > self.maximum_abs_pitch_deg:
            return PitchShadowDecision("HOLD", None, None, "PITCH_BOUND_EXCEEDED")
        if abs(evidence.target_pitch_deg) <= self.pitch_deadband_deg:
            return PitchShadowDecision("HOLD", evidence.target_yaw_deg, 0.0, "ALIGNED_DEADBAND")
        if float(elapsed_ms) - self._last_adjustment_ms < self.minimum_interval_ms:
            return PitchShadowDecision("HOLD", None, None, "RATE_LIMIT")
        self._last_adjustment_ms = float(elapsed_ms)
        return PitchShadowDecision(
            "WOULD_ADJUST", evidence.target_yaw_deg, evidence.target_pitch_deg, "BOUNDED_SHADOW_TARGET"
        )

