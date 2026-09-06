"""Frozen Stage 3V V3 policy selected by offline replay.

V3 changes only the camera-to-diagram calibration: after the already-audited
camera-right to diagram-right sign conversion, it applies a fixed -4 degree
yaw offset.  All V2 temporal consensus and safety behaviour is retained.
This module has no camera, network, robot SDK, media or actuation capability.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from .revised_policy import RevisedEvidence
from .revised_policy_v2 import (
    RevisedPolicyV2Spec,
    RevisedReplayPolicyV2,
    evaluate_revised_trial_v2,
)


@dataclass(frozen=True, slots=True)
class RevisedPolicyV3Spec:
    name: str
    face_heading_multiplier: float
    face_heading_offset_deg: float
    maximum_geometry_error_deg: float
    required_hits: int
    window_ms: float
    heading_tolerance_deg: float
    disagreement_lockout_ms: float
    speech_latch_ms: float
    clear_speech_latch_on_fault: bool
    target_source: str

    def payload(self) -> dict[str, Any]:
        core = asdict(self)
        encoded = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return {**core, "fingerprint": hashlib.sha256(encoded).hexdigest()}


FROZEN_REVISED_POLICY_V3 = RevisedPolicyV3Spec(
    name="Stage 3V V3 calibrated speech-latched three-hit visual-target consensus",
    face_heading_multiplier=-1.0,
    face_heading_offset_deg=-4.0,
    maximum_geometry_error_deg=10.0,
    required_hits=3,
    window_ms=600.0,
    heading_tolerance_deg=8.0,
    disagreement_lockout_ms=1500.0,
    speech_latch_ms=800.0,
    clear_speech_latch_on_fault=True,
    target_source="visual",
)


def _v2_spec(spec: RevisedPolicyV3Spec) -> RevisedPolicyV2Spec:
    return RevisedPolicyV2Spec(
        name=spec.name,
        face_heading_multiplier=spec.face_heading_multiplier,
        maximum_geometry_error_deg=spec.maximum_geometry_error_deg,
        required_hits=spec.required_hits,
        window_ms=spec.window_ms,
        heading_tolerance_deg=spec.heading_tolerance_deg,
        disagreement_lockout_ms=spec.disagreement_lockout_ms,
        speech_latch_ms=spec.speech_latch_ms,
        clear_speech_latch_on_fault=spec.clear_speech_latch_on_fault,
        target_source=spec.target_source,
    )


def calibrated_row(row: dict[str, Any], spec: RevisedPolicyV3Spec) -> dict[str, Any]:
    """Return a numeric-row copy whose V2 projection includes the V3 offset."""
    adjusted = dict(row)
    value = row.get("face_heading_deg")
    if value not in (None, ""):
        multiplier = float(spec.face_heading_multiplier)
        if multiplier == 0.0:
            raise ValueError("The face-heading multiplier cannot be zero.")
        # V2 computes multiplier * adjusted_heading.  This transformation makes
        # that equal multiplier * raw_heading + offset without changing raw data.
        adjusted["face_heading_deg"] = float(value) + spec.face_heading_offset_deg / multiplier
    return adjusted


class RevisedReplayPolicyV3:
    """Apply the frozen calibration before the unchanged V2 state machine."""

    def __init__(self, spec: RevisedPolicyV3Spec) -> None:
        self.spec = spec
        self._delegate = RevisedReplayPolicyV2(_v2_spec(spec))

    def process(self, row: dict[str, Any]) -> RevisedEvidence:
        return self._delegate.process(calibrated_row(row, self.spec))


def replay_revised_policy_v3(
    spec: RevisedPolicyV3Spec,
    rows: Iterable[dict[str, Any]],
) -> list[RevisedEvidence]:
    policy = RevisedReplayPolicyV3(spec)
    return [policy.process(row) for row in rows]


def evaluate_revised_trial_v3(
    step: Any,
    rows: list[dict[str, Any]],
    spec: RevisedPolicyV3Spec = FROZEN_REVISED_POLICY_V3,
) -> dict[str, Any]:
    calibrated = [calibrated_row(row, spec) for row in rows]
    return evaluate_revised_trial_v2(step, calibrated, _v2_spec(spec))
