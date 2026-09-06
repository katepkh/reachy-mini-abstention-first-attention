"""Offline-only Stage 3P V3 candidate policies.

V3 preserves the frozen and successful Stage 3V V3 visual yaw target.  It
repairs three vertical-specific problems exposed by the failed Stage 3P
held-out result:

* use a monotonic piecewise eye-line calibration through all three audited
  calibration anchors instead of a least-squares line that missed the centre;
* allow a conservative repeated-speech fallback to establish the same
  acoustic/visual association after transient disagreement lockout;
* once associated, maintain the one fresh visible face for the already-bounded
  ten-second interval without letting sparse VAD false positives erase it.

The module consumes saved numeric rows only.  It has no network, media, robot
SDK, or actuation capability.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import deque
from dataclasses import asdict, dataclass
from statistics import median
from typing import Any

from reachy_stage2a.calibration import circular_distance_degrees
from reachy_stage3v.revised_policy import geometry_for_row
from reachy_stage3v.revised_policy_v2 import RevisedPolicyV2Spec
from reachy_stage3v.revised_policy_v3 import (
    FROZEN_REVISED_POLICY_V3,
    RevisedReplayPolicyV3,
    calibrated_row,
)

from .calibration import face_center_to_pitch
from .policy import Stage3PEvidence
from .policy_v2 import (
    CALIBRATION_BUNDLE_SHA256,
    CALIBRATION_PROTOCOL_FINGERPRINT,
    LEGACY_BOX_REPLAY_INTERCEPT_DEG,
    LEGACY_BOX_REPLAY_SLOPE,
    calibrated_replay_pitch,
)


CALIBRATION_RAW_DOWN_DEG = -0.2967419573808101
CALIBRATION_RAW_CENTRE_DEG = 8.604733157109903
CALIBRATION_RAW_UP_DEG = 14.014124015824853


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


def _truth(value: object) -> bool:
    return value is True or str(value).strip().lower() == "true"


def anchored_eye_pitch(row: dict[str, Any]) -> float | None:
    """Map an eye midpoint through the three audited calibration anchors.

    Extrapolation is clipped to the tested ±10° envelope.  This is a bounded
    mapping, not a claim that geometry outside the pilot range is calibrated.
    """

    value = _number(row, "face_eye_midpoint_y_norm")
    if value is None:
        return None
    raw = face_center_to_pitch(value)
    if raw <= CALIBRATION_RAW_CENTRE_DEG:
        fraction = (raw - CALIBRATION_RAW_DOWN_DEG) / (
            CALIBRATION_RAW_CENTRE_DEG - CALIBRATION_RAW_DOWN_DEG
        )
        mapped = -10.0 + 10.0 * fraction
    else:
        fraction = (raw - CALIBRATION_RAW_CENTRE_DEG) / (
            CALIBRATION_RAW_UP_DEG - CALIBRATION_RAW_CENTRE_DEG
        )
        mapped = 10.0 * fraction
    return max(-10.0, min(10.0, mapped))


@dataclass(frozen=True, slots=True)
class Stage3PCandidateV3Spec:
    name: str
    status: str
    source_yaw_policy_fingerprint: str
    source_failed_result_bundle_sha256: str
    source_eye_calibration_fingerprint: str
    source_eye_calibration_bundle_sha256: str
    runtime_requires_eye_landmarks: bool
    eye_mapping: str
    calibration_raw_down_deg: float
    calibration_raw_centre_deg: float
    calibration_raw_up_deg: float
    maximum_abs_pitch_target_deg: float
    fallback_geometry_error_deg: float
    fallback_required_speech_onsets: int
    fallback_speech_onset_window_ms: float
    speech_latch_ms: float
    association_consensus_hits: int
    association_consensus_window_ms: float
    association_heading_tolerance_deg: float
    pitch_consensus_hits: int
    pitch_consensus_window_ms: float
    pitch_consensus_tolerance_deg: float
    maximum_maintenance_ms: float
    minimum_face_confidence: float
    maximum_face_age_ms: float
    retain_association_through_acoustic_conflict: bool

    def payload(self) -> dict[str, Any]:
        core = asdict(self)
        encoded = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return {**core, "fingerprint": hashlib.sha256(encoded).hexdigest()}


def candidate_v3_spec(
    *,
    failed_result_bundle_sha256: str,
    fallback_geometry_error_deg: float,
    fallback_speech_onset_window_ms: float,
) -> Stage3PCandidateV3Spec:
    return Stage3PCandidateV3Spec(
        name=(
            "Stage 3P V3 anchored eye calibration with latched visual maintenance "
            f"and repeated-speech fallback ≤{fallback_geometry_error_deg:g}°/"
            f"{fallback_speech_onset_window_ms:g}ms"
        ),
        status="DEVELOPMENT_CANDIDATE_NOT_HELD_OUT_NOT_AUTHORISED_FOR_ACTUATION",
        source_yaw_policy_fingerprint=FROZEN_REVISED_POLICY_V3.payload()["fingerprint"],
        source_failed_result_bundle_sha256=failed_result_bundle_sha256,
        source_eye_calibration_fingerprint=CALIBRATION_PROTOCOL_FINGERPRINT,
        source_eye_calibration_bundle_sha256=CALIBRATION_BUNDLE_SHA256,
        runtime_requires_eye_landmarks=True,
        eye_mapping="MONOTONIC_PIECEWISE_LINEAR_THROUGH_THREE_AUDITED_ANCHORS_CLIPPED_TO_TESTED_ENVELOPE",
        calibration_raw_down_deg=CALIBRATION_RAW_DOWN_DEG,
        calibration_raw_centre_deg=CALIBRATION_RAW_CENTRE_DEG,
        calibration_raw_up_deg=CALIBRATION_RAW_UP_DEG,
        maximum_abs_pitch_target_deg=10.0,
        fallback_geometry_error_deg=float(fallback_geometry_error_deg),
        fallback_required_speech_onsets=2,
        fallback_speech_onset_window_ms=float(fallback_speech_onset_window_ms),
        speech_latch_ms=800.0,
        association_consensus_hits=3,
        association_consensus_window_ms=600.0,
        association_heading_tolerance_deg=8.0,
        pitch_consensus_hits=3,
        pitch_consensus_window_ms=600.0,
        pitch_consensus_tolerance_deg=4.0,
        maximum_maintenance_ms=10_000.0,
        minimum_face_confidence=0.55,
        maximum_face_age_ms=1500.0,
        retain_association_through_acoustic_conflict=True,
    )


class Stage3PReplayPolicyV3:
    """Acquire a speaker conservatively, then maintain one fresh visible face."""

    def __init__(
        self,
        spec: Stage3PCandidateV3Spec,
        *,
        allow_legacy_box_bridge: bool = False,
    ) -> None:
        self.spec = spec
        self.allow_legacy_box_bridge = bool(allow_legacy_box_bridge)
        self._yaw = RevisedReplayPolicyV3(FROZEN_REVISED_POLICY_V3)
        self._pitch_hits: deque[tuple[float, float]] = deque()
        self._association_hits: deque[tuple[float, float]] = deque()
        self._speech_onsets: deque[float] = deque()
        self._speech_was_positive = False
        self._last_speech_ms = -math.inf
        self._associated = False
        self._acquired_at_ms = -math.inf

    def _face_reason(self, row: dict[str, Any]) -> str | None:
        if _integer(row, "face_count") == 0:
            return "NO_FACE"
        if _integer(row, "face_count") != 1:
            return "MULTIPLE_FACES"
        if (_number(row, "face_confidence") or 0.0) < self.spec.minimum_face_confidence:
            return "FACE_LOW_CONFIDENCE"
        age = _number(row, "face_age_ms")
        if age is None or age < 0.0 or age > self.spec.maximum_face_age_ms:
            return "CAMERA_OBSERVATION_STALE"
        if (
            _number(row, "face_eye_midpoint_y_norm") is None
            and not (
                self.allow_legacy_box_bridge
                and _number(row, "face_center_y_norm") is not None
            )
        ):
            return "EYE_LANDMARKS_UNAVAILABLE"
        return None

    def _clear_association(self) -> None:
        self._associated = False
        self._acquired_at_ms = -math.inf
        self._association_hits.clear()
        self._pitch_hits.clear()

    def _pitch(self, row: dict[str, Any]) -> float | None:
        eye = anchored_eye_pitch(row)
        if eye is not None:
            return eye
        if not self.allow_legacy_box_bridge:
            return None
        return calibrated_replay_pitch(row, allow_legacy_box_bridge=True)

    def _fallback_geometry(self, row: dict[str, Any]):
        yaw_spec = RevisedPolicyV2Spec(
            name="Stage 3P V3 vertical-association fallback",
            face_heading_multiplier=FROZEN_REVISED_POLICY_V3.face_heading_multiplier,
            maximum_geometry_error_deg=self.spec.fallback_geometry_error_deg,
            required_hits=self.spec.association_consensus_hits,
            window_ms=self.spec.association_consensus_window_ms,
            heading_tolerance_deg=self.spec.association_heading_tolerance_deg,
            disagreement_lockout_ms=0.0,
            speech_latch_ms=self.spec.speech_latch_ms,
            clear_speech_latch_on_fault=True,
            target_source="visual",
        )
        return geometry_for_row(calibrated_row(row, FROZEN_REVISED_POLICY_V3), yaw_spec)

    def _fallback_association(self, row: dict[str, Any], elapsed: float) -> bool:
        geometry = self._fallback_geometry(row)
        while (
            self._association_hits
            and elapsed - self._association_hits[0][0]
            > self.spec.association_consensus_window_ms
        ):
            self._association_hits.popleft()
        repeated_speech = (
            len(self._speech_onsets) >= self.spec.fallback_required_speech_onsets
        )
        recent_speech = elapsed - self._last_speech_ms <= self.spec.speech_latch_ms
        if geometry.heading_deg is None or not (repeated_speech and recent_speech):
            return False
        self._association_hits.append((elapsed, float(geometry.heading_deg)))
        stable = [
            value
            for _, value in self._association_hits
            if circular_distance_degrees(value, float(geometry.heading_deg))
            <= self.spec.association_heading_tolerance_deg
        ]
        return len(stable) >= self.spec.association_consensus_hits

    def process(self, row: dict[str, Any]) -> Stage3PEvidence:
        elapsed = _number(row, "elapsed_ms") or 0.0
        speech = _truth(row.get("speech_detected"))
        if speech:
            self._last_speech_ms = elapsed
        if speech and not self._speech_was_positive:
            self._speech_onsets.append(elapsed)
        self._speech_was_positive = speech
        while (
            self._speech_onsets
            and elapsed - self._speech_onsets[0]
            > self.spec.fallback_speech_onset_window_ms
        ):
            self._speech_onsets.popleft()

        horizontal = self._yaw.process(row)
        face_reason = self._face_reason(row)
        if face_reason is not None:
            self._clear_association()
            return Stage3PEvidence(False, None, None, "UNASSOCIATED", face_reason)

        pitch = self._pitch(row)
        raw_yaw = _number(row, "face_heading_deg")
        if pitch is None or raw_yaw is None:
            self._clear_association()
            return Stage3PEvidence(False, None, None, "UNASSOCIATED", "FACE_GEOMETRY_UNAVAILABLE")

        self._pitch_hits.append((elapsed, pitch))
        while (
            self._pitch_hits
            and elapsed - self._pitch_hits[0][0] > self.spec.pitch_consensus_window_ms
        ):
            self._pitch_hits.popleft()

        if not self._associated:
            source_association = False
            if horizontal.confirmed and horizontal.agreement_error_deg is not None:
                source_association = (
                    float(horizontal.agreement_error_deg)
                    <= self.spec.fallback_geometry_error_deg
                )
            if source_association or self._fallback_association(row, elapsed):
                self._associated = True
                self._acquired_at_ms = elapsed

        if not self._associated:
            return Stage3PEvidence(False, None, None, "UNASSOCIATED", horizontal.reason)
        if elapsed - self._acquired_at_ms > self.spec.maximum_maintenance_ms:
            self._clear_association()
            return Stage3PEvidence(False, None, None, "EXPIRED", "SPEAKER_ASSOCIATION_EXPIRED")

        stable = [
            value
            for _, value in self._pitch_hits
            if abs(value - pitch) <= self.spec.pitch_consensus_tolerance_deg
        ]
        if len(stable) < self.spec.pitch_consensus_hits:
            return Stage3PEvidence(False, None, None, "ACQUISITION", "PITCH_CONSENSUS_PENDING")

        target_pitch = median(stable[-self.spec.pitch_consensus_hits :])
        target_pitch = max(
            -self.spec.maximum_abs_pitch_target_deg,
            min(self.spec.maximum_abs_pitch_target_deg, target_pitch),
        )
        target_yaw = (
            FROZEN_REVISED_POLICY_V3.face_heading_multiplier * raw_yaw
            + FROZEN_REVISED_POLICY_V3.face_heading_offset_deg
        )
        phase = "ACQUISITION" if horizontal.confirmed else "MAINTENANCE"
        return Stage3PEvidence(
            True,
            target_yaw,
            target_pitch,
            phase,
            "ANCHORED_COUPLED_TARGET_CONFIRMED",
        )
