"""Pure, offline motion-shadow state machine.

The controller emits labels and numeric targets only.  It deliberately has no
method capable of sending a command or opening a connection.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from reachy_stage2a.tournament import CounterfactualDecision


@dataclass(frozen=True, slots=True)
class MotionEnvelope:
    """Conservative envelope proposed for a future supervised head-only test."""

    max_abs_yaw_deg: float = 20.0
    deadband_deg: float = 3.0
    duration_s: float = 1.25
    cooldown_ms: float = 2000.0
    quiet_return_ms: float = 1500.0


@dataclass(frozen=True, slots=True)
class MotionShadowDecision:
    action: str
    desired_heading_deg: float | None
    target_yaw_deg: float | None
    target_x_right: float | None
    target_y_forward: float | None
    target_z_up: float | None
    duration_s: float | None
    reason: str
    source_reason: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def signed_heading_degrees(value: float) -> float:
    """Normalize a heading to [-180, 180), preserving the front-zero frame."""

    return (float(value) + 180.0) % 360.0 - 180.0


def heading_unit_vector(heading_deg: float) -> tuple[float, float, float]:
    """Return (right, forward, up) for the Stage 2A front-zero convention."""

    radians = math.radians(heading_deg)
    return math.sin(radians), math.cos(radians), 0.0


class MotionShadowController:
    """Convert safe evidence into non-executable motion proposals."""

    _FAULT_REASONS = {
        "NETWORK_INVALID",
        "ACOUSTIC_VISUAL_DISAGREEMENT",
        "DISAGREEMENT_LOCKOUT",
        "NO_FACE",
        "MULTIPLE_FACES",
        "FACE_LOW_CONFIDENCE",
        "CAMERA_OBSERVATION_STALE",
        "VISUAL_HYPOTHESIS_AMBIGUOUS",
    }

    def __init__(self, envelope: MotionEnvelope | None = None) -> None:
        self.envelope = envelope or MotionEnvelope()
        self.shadow_yaw_deg = 0.0
        self.last_motion_ms = -math.inf
        self.last_confirmed_ms: float | None = None
        self.has_left_neutral = False

    def _hold(self, reason: str, source_reason: str) -> MotionShadowDecision:
        return MotionShadowDecision(
            action="HOLD",
            desired_heading_deg=None,
            target_yaw_deg=None,
            target_x_right=None,
            target_y_forward=None,
            target_z_up=None,
            duration_s=None,
            reason=reason,
            source_reason=source_reason,
        )

    def process(
        self,
        elapsed_ms: float,
        evidence: CounterfactualDecision,
    ) -> MotionShadowDecision:
        elapsed_ms = float(elapsed_ms)
        if evidence.confirmed and evidence.heading_deg is not None:
            desired = signed_heading_degrees(float(evidence.heading_deg))
            self.last_confirmed_ms = elapsed_ms
            bounded = max(
                -self.envelope.max_abs_yaw_deg,
                min(self.envelope.max_abs_yaw_deg, desired),
            )
            if abs(bounded - self.shadow_yaw_deg) <= self.envelope.deadband_deg:
                return self._hold("ALREADY_ALIGNED", evidence.reason)
            if elapsed_ms - self.last_motion_ms < self.envelope.cooldown_ms:
                return self._hold("MOTION_COOLDOWN", evidence.reason)
            vector = heading_unit_vector(desired)
            self.shadow_yaw_deg = bounded
            self.last_motion_ms = elapsed_ms
            self.has_left_neutral = abs(bounded) > self.envelope.deadband_deg
            return MotionShadowDecision(
                action="WOULD_MOVE",
                desired_heading_deg=desired,
                target_yaw_deg=bounded,
                target_x_right=vector[0],
                target_y_forward=vector[1],
                target_z_up=vector[2],
                duration_s=self.envelope.duration_s,
                reason="BOUNDED_HEAD_ONLY_SHADOW_TARGET",
                source_reason=evidence.reason,
            )

        if evidence.reason in self._FAULT_REASONS:
            return self._hold("FAIL_CLOSED", evidence.reason)

        quiet_long_enough = (
            self.has_left_neutral
            and self.last_confirmed_ms is not None
            and elapsed_ms - self.last_confirmed_ms >= self.envelope.quiet_return_ms
        )
        cooldown_complete = elapsed_ms - self.last_motion_ms >= self.envelope.cooldown_ms
        if quiet_long_enough and cooldown_complete:
            self.shadow_yaw_deg = 0.0
            self.last_motion_ms = elapsed_ms
            self.has_left_neutral = False
            vector = heading_unit_vector(0.0)
            return MotionShadowDecision(
                action="RETURN_NEUTRAL",
                desired_heading_deg=0.0,
                target_yaw_deg=0.0,
                target_x_right=vector[0],
                target_y_forward=vector[1],
                target_z_up=vector[2],
                duration_s=self.envelope.duration_s,
                reason="SUSTAINED_QUIET_RETURN_SHADOW",
                source_reason=evidence.reason,
            )
        return self._hold("EVIDENCE_WITHHELD", evidence.reason)
