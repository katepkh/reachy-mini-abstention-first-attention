"""Offline-only candidate policy for coupled yaw/pitch face tracking."""

from __future__ import annotations

import hashlib
import json
import math
from collections import deque
from dataclasses import asdict, dataclass
from statistics import median
from typing import Any

from reachy_stage3v.revised_policy_v3 import (
    FROZEN_REVISED_POLICY_V3,
    RevisedReplayPolicyV3,
)

from .calibration import face_center_to_pitch


def _number(row: dict[str, Any], key: str) -> float | None:
    try:
        value = row.get(key)
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def _integer(row: dict[str, Any], key: str) -> int:
    try:
        return int(float(row.get(key) or 0))
    except (TypeError, ValueError):
        return 0


@dataclass(frozen=True, slots=True)
class Stage3PCandidateSpec:
    name: str
    status: str
    source_yaw_policy_fingerprint: str
    maximum_abs_pitch_deg: float
    pitch_deadband_deg: float
    pitch_consensus_hits: int
    pitch_consensus_window_ms: float
    pitch_consensus_tolerance_deg: float
    maximum_maintenance_ms: float
    minimum_face_confidence: float
    maximum_face_age_ms: float

    def payload(self) -> dict[str, Any]:
        core = asdict(self)
        encoded = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return {**core, "fingerprint": hashlib.sha256(encoded).hexdigest()}


CANDIDATE_POLICY_V1 = Stage3PCandidateSpec(
    name="Stage 3P candidate V1 speaker-gated bounded pitch tracking",
    status="DEVELOPMENT_CANDIDATE_MUST_NOT_BE_USED_FOR_HELD_OUT_INFERENCE_OR_ACTUATION",
    source_yaw_policy_fingerprint=FROZEN_REVISED_POLICY_V3.payload()["fingerprint"],
    maximum_abs_pitch_deg=20.0,
    pitch_deadband_deg=2.0,
    pitch_consensus_hits=3,
    pitch_consensus_window_ms=600.0,
    pitch_consensus_tolerance_deg=4.0,
    maximum_maintenance_ms=10_000.0,
    minimum_face_confidence=0.55,
    maximum_face_age_ms=1500.0,
)


@dataclass(frozen=True, slots=True)
class Stage3PEvidence:
    confirmed: bool
    target_yaw_deg: float | None
    target_pitch_deg: float | None
    association_phase: str
    reason: str


class Stage3PReplayPolicy:
    """Acquire with frozen V3 evidence, then maintain one fresh face briefly."""

    def __init__(self, spec: Stage3PCandidateSpec = CANDIDATE_POLICY_V1) -> None:
        self.spec = spec
        self._yaw = RevisedReplayPolicyV3(FROZEN_REVISED_POLICY_V3)
        self._pitch_hits: deque[tuple[float, float]] = deque()
        self._acquired_at_ms = -math.inf
        self._associated = False

    def _face_reason(self, row: dict[str, Any]) -> str | None:
        if _integer(row, "face_count") == 0 or _number(row, "face_center_y_norm") is None:
            return "NO_FACE"
        if _integer(row, "face_count") != 1:
            return "MULTIPLE_FACES"
        if (_number(row, "face_confidence") or 0.0) < self.spec.minimum_face_confidence:
            return "FACE_LOW_CONFIDENCE"
        age = _number(row, "face_age_ms")
        if age is None or age < 0.0 or age > self.spec.maximum_face_age_ms:
            return "CAMERA_OBSERVATION_STALE"
        return None

    def _clear(self) -> None:
        self._associated = False
        self._acquired_at_ms = -math.inf
        self._pitch_hits.clear()

    def process(self, row: dict[str, Any]) -> Stage3PEvidence:
        elapsed = _number(row, "elapsed_ms") or 0.0
        horizontal = self._yaw.process(row)
        face_reason = self._face_reason(row)
        if face_reason is not None:
            self._clear()
            return Stage3PEvidence(False, None, None, "UNASSOCIATED", face_reason)
        if horizontal.reason in {"ACOUSTIC_VISUAL_DISAGREEMENT", "DISAGREEMENT_LOCKOUT"}:
            self._clear()
            return Stage3PEvidence(False, None, None, "UNASSOCIATED", horizontal.reason)

        center_y = _number(row, "face_center_y_norm")
        raw_yaw = _number(row, "face_heading_deg")
        assert center_y is not None and raw_yaw is not None
        pitch = face_center_to_pitch(center_y)
        if abs(pitch) > self.spec.maximum_abs_pitch_deg:
            self._clear()
            return Stage3PEvidence(False, None, None, "UNASSOCIATED", "PITCH_OUTSIDE_VALIDATED_ENVELOPE")

        may_seed = self._associated or horizontal.visual_heading_deg is not None
        if may_seed:
            self._pitch_hits.append((elapsed, pitch))
        while self._pitch_hits and elapsed - self._pitch_hits[0][0] > self.spec.pitch_consensus_window_ms:
            self._pitch_hits.popleft()

        if horizontal.confirmed:
            self._associated = True
            self._acquired_at_ms = elapsed
        if not self._associated:
            return Stage3PEvidence(False, None, None, "UNASSOCIATED", horizontal.reason)
        if elapsed - self._acquired_at_ms > self.spec.maximum_maintenance_ms:
            self._clear()
            return Stage3PEvidence(False, None, None, "EXPIRED", "SPEAKER_ASSOCIATION_EXPIRED")

        stable = [
            value for _, value in self._pitch_hits
            if abs(value - pitch) <= self.spec.pitch_consensus_tolerance_deg
        ]
        if len(stable) < self.spec.pitch_consensus_hits:
            return Stage3PEvidence(False, None, None, "ACQUISITION", "PITCH_CONSENSUS_PENDING")

        target_pitch = median(stable[-self.spec.pitch_consensus_hits :])
        target_yaw = -raw_yaw + FROZEN_REVISED_POLICY_V3.face_heading_offset_deg
        phase = "ACQUISITION" if horizontal.confirmed else "MAINTENANCE"
        reason = "COUPLED_TARGET_CONFIRMED" if abs(target_pitch) > self.spec.pitch_deadband_deg else "ALIGNED_DEADBAND"
        return Stage3PEvidence(True, target_yaw, target_pitch, phase, reason)

