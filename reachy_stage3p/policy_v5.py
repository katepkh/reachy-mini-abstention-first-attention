"""Offline-only relative visual-servo candidates for Stage 3P.

V5 keeps the frozen V4 speaker-association and face-fault boundaries, but
replaces the one-shot absolute pitch estimate with a bounded incremental
correction derived from signed eye displacement around a fixed neutral image
reference.  It emits numeric shadow evidence only.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from .calibration import face_center_to_pitch
from .policy import Stage3PEvidence
from .policy_v4 import Stage3PCandidateV4Spec, Stage3PReplayPolicyV4, _number


@dataclass(frozen=True, slots=True)
class Stage3PVisualServoV5Spec(Stage3PCandidateV4Spec):
    neutral_raw_eye_pitch_deg: float
    incremental_pitch_deadband_deg: float
    incremental_pitch_gain: float
    maximum_abs_increment_deg: float
    control_mode: str

    def payload(self) -> dict[str, Any]:
        core = asdict(self)
        encoded = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return {**core, "fingerprint": hashlib.sha256(encoded).hexdigest()}


def candidate_v5_spec(
    base: Stage3PCandidateV4Spec,
    *,
    association_geometry_error_deg: float,
    neutral_raw_eye_pitch_deg: float,
    incremental_pitch_deadband_deg: float,
    maximum_abs_increment_deg: float,
) -> Stage3PVisualServoV5Spec:
    fields = asdict(base)
    fields.update(
        {
            "name": (
                "Stage 3P V5 relative eye-error visual servo "
                f"association<={association_geometry_error_deg:g}deg "
                f"neutral={neutral_raw_eye_pitch_deg:g}deg "
                f"deadband={incremental_pitch_deadband_deg:g}deg "
                f"step<={maximum_abs_increment_deg:g}deg"
            ),
            "status": (
                "OFFLINE_DEVELOPMENT_CANDIDATE_NOT_HELD_OUT_"
                "NOT_AUTHORISED_FOR_ACTUATION"
            ),
            "fallback_geometry_error_deg": float(association_geometry_error_deg),
        }
    )
    return Stage3PVisualServoV5Spec(
        **fields,
        neutral_raw_eye_pitch_deg=float(neutral_raw_eye_pitch_deg),
        incremental_pitch_deadband_deg=float(incremental_pitch_deadband_deg),
        incremental_pitch_gain=1.0,
        maximum_abs_increment_deg=float(maximum_abs_increment_deg),
        control_mode="BOUNDED_INCREMENTAL_RELATIVE_EYE_ERROR",
    )


class Stage3PVisualServoPolicyV5(Stage3PReplayPolicyV4):
    """Associate as V4, then emit a bounded relative pitch increment."""

    def __init__(self, spec: Stage3PVisualServoV5Spec) -> None:
        super().__init__(spec)
        self.spec = spec

    def _pitch(self, row: dict[str, Any]) -> float | None:
        value = _number(row, "face_eye_midpoint_y_norm")
        if value is None:
            return None
        return face_center_to_pitch(value) - self.spec.neutral_raw_eye_pitch_deg

    def process(self, row: dict[str, Any]) -> Stage3PEvidence:
        evidence = super().process(row)
        if not evidence.confirmed or evidence.target_pitch_deg is None:
            return evidence
        error = float(evidence.target_pitch_deg)
        if abs(error) <= self.spec.incremental_pitch_deadband_deg:
            increment = 0.0
            reason = "RELATIVE_EYE_ERROR_ALIGNED"
        else:
            unbounded = self.spec.incremental_pitch_gain * error
            increment = max(
                -self.spec.maximum_abs_increment_deg,
                min(self.spec.maximum_abs_increment_deg, unbounded),
            )
            reason = "RELATIVE_EYE_ERROR_INCREMENT_CONFIRMED"
        return Stage3PEvidence(
            True,
            evidence.target_yaw_deg,
            increment,
            evidence.association_phase,
            reason,
        )
