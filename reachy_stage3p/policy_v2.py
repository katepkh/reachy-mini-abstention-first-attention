"""Offline-only calibrated Stage 3P candidate policy tournament.

The policy keeps frozen Stage 3V V3 unchanged.  Stage 3P adds a stricter
association layer, the frozen eye-line calibration, and visual-only bounded
maintenance after an acoustic/visual speaker association is established.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import deque
from dataclasses import asdict, dataclass
from statistics import median
from typing import Any

from reachy_stage3v.revised_policy_v3 import FROZEN_REVISED_POLICY_V3, RevisedReplayPolicyV3

from .calibration import face_center_to_pitch
from .policy import Stage3PEvidence


CALIBRATION_PROTOCOL_FINGERPRINT = (
    "f6d0f15e352740b8f1d3c7e25a96e81f060b757246817b813c23d439615cf3a8"
)
CALIBRATION_BUNDLE_SHA256 = (
    "f6b9b06ce68b851a062b867200485a9e680c1385ff70c16ad15caa9d7046f80c"
)
EYE_PITCH_SLOPE = 1.358646423830366
EYE_PITCH_INTERCEPT_DEG = -10.04101369157813
# The development collection predates eye-landmark instrumentation.  These
# coefficients were fitted only on the nine accepted, audited calibration
# trials so the old files can be used to test association/state-machine logic.
# They are not the runtime measurement path: held-out validation and any later
# runtime must supply eye landmarks and use the mapping above.
LEGACY_BOX_REPLAY_SLOPE = 1.37826380450398
LEGACY_BOX_REPLAY_INTERCEPT_DEG = -8.69089752743638


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


def calibrated_eye_pitch(row: dict[str, Any]) -> float | None:
    value = _number(row, "face_eye_midpoint_y_norm")
    if value is None:
        return None
    raw = face_center_to_pitch(value)
    return EYE_PITCH_SLOPE * raw + EYE_PITCH_INTERCEPT_DEG


def calibrated_replay_pitch(
    row: dict[str, Any], *, allow_legacy_box_bridge: bool = False
) -> float | None:
    """Return calibrated pitch, optionally bridging pre-landmark dev files.

    The bridge is deliberately opt-in and exists only for offline replay of
    Stage 3P development data collected before eye landmarks were recorded.
    """

    eye_pitch = calibrated_eye_pitch(row)
    if eye_pitch is not None:
        return eye_pitch
    if not allow_legacy_box_bridge:
        return None
    value = _number(row, "face_center_y_norm")
    if value is None:
        return None
    raw = face_center_to_pitch(value)
    return LEGACY_BOX_REPLAY_SLOPE * raw + LEGACY_BOX_REPLAY_INTERCEPT_DEG


@dataclass(frozen=True, slots=True)
class Stage3PCandidateV2Spec:
    name: str
    status: str
    source_yaw_policy_fingerprint: str
    source_eye_calibration_fingerprint: str
    source_eye_calibration_bundle_sha256: str
    runtime_requires_eye_landmarks: bool
    legacy_box_bridge_offline_replay_only: bool
    legacy_box_replay_slope: float
    legacy_box_replay_intercept_deg: float
    strong_geometry_error_deg: float
    weak_geometry_error_deg: float
    weak_geometry_minimum_speech_bursts: int
    speech_burst_window_ms: float
    pitch_consensus_hits: int
    pitch_consensus_window_ms: float
    pitch_consensus_tolerance_deg: float
    maximum_abs_pitch_deg: float
    maximum_maintenance_ms: float
    minimum_face_confidence: float
    maximum_face_age_ms: float

    def payload(self) -> dict[str, Any]:
        core = asdict(self)
        encoded = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return {**core, "fingerprint": hashlib.sha256(encoded).hexdigest()}


def candidate_v2_spec(
    *, strong_geometry_error_deg: float, speech_burst_window_ms: float
) -> Stage3PCandidateV2Spec:
    return Stage3PCandidateV2Spec(
        name=(
            "Stage 3P V2 calibrated eye tracking with confidence-tiered speaker association "
            f"(strong≤{strong_geometry_error_deg:g}°, weak-two-burst≤10°/{speech_burst_window_ms:g}ms)"
        ),
        status="DEVELOPMENT_CANDIDATE_NOT_HELD_OUT_NOT_AUTHORISED_FOR_ACTUATION",
        source_yaw_policy_fingerprint=FROZEN_REVISED_POLICY_V3.payload()["fingerprint"],
        source_eye_calibration_fingerprint=CALIBRATION_PROTOCOL_FINGERPRINT,
        source_eye_calibration_bundle_sha256=CALIBRATION_BUNDLE_SHA256,
        runtime_requires_eye_landmarks=True,
        legacy_box_bridge_offline_replay_only=True,
        legacy_box_replay_slope=LEGACY_BOX_REPLAY_SLOPE,
        legacy_box_replay_intercept_deg=LEGACY_BOX_REPLAY_INTERCEPT_DEG,
        strong_geometry_error_deg=float(strong_geometry_error_deg),
        weak_geometry_error_deg=10.0,
        weak_geometry_minimum_speech_bursts=2,
        speech_burst_window_ms=float(speech_burst_window_ms),
        pitch_consensus_hits=3,
        pitch_consensus_window_ms=600.0,
        pitch_consensus_tolerance_deg=4.0,
        maximum_abs_pitch_deg=20.0,
        maximum_maintenance_ms=10_000.0,
        minimum_face_confidence=0.55,
        maximum_face_age_ms=1500.0,
    )


CANDIDATE_V2_SPECS = tuple(
    candidate_v2_spec(
        strong_geometry_error_deg=geometry,
        speech_burst_window_ms=window,
    )
    for geometry in (4.0, 6.0)
    for window in (2500.0, 4000.0)
)


class Stage3PReplayPolicyV2:
    """Acquire conservatively, then maintain one fresh visible face without audio."""

    _FACE_FAULTS = {
        "NO_FACE", "MULTIPLE_FACES", "FACE_LOW_CONFIDENCE", "CAMERA_OBSERVATION_STALE",
        "EYE_LANDMARKS_UNAVAILABLE", "PITCH_OUTSIDE_VALIDATED_ENVELOPE",
    }

    def __init__(
        self,
        spec: Stage3PCandidateV2Spec,
        *,
        allow_legacy_box_bridge: bool = False,
    ) -> None:
        self.spec = spec
        self.allow_legacy_box_bridge = bool(allow_legacy_box_bridge)
        self._yaw = RevisedReplayPolicyV3(FROZEN_REVISED_POLICY_V3)
        self._pitch_hits: deque[tuple[float, float]] = deque()
        self._speech_onsets: deque[float] = deque()
        self._speech_was_positive = False
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
        self._pitch_hits.clear()

    def process(self, row: dict[str, Any]) -> Stage3PEvidence:
        elapsed = _number(row, "elapsed_ms") or 0.0
        speech = _truth(row.get("speech_detected"))
        if speech and not self._speech_was_positive:
            self._speech_onsets.append(elapsed)
        self._speech_was_positive = speech
        while self._speech_onsets and elapsed - self._speech_onsets[0] > self.spec.speech_burst_window_ms:
            self._speech_onsets.popleft()

        horizontal = self._yaw.process(row)
        face_reason = self._face_reason(row)
        if face_reason is not None:
            self._clear_association()
            return Stage3PEvidence(False, None, None, "UNASSOCIATED", face_reason)

        pitch = calibrated_replay_pitch(
            row, allow_legacy_box_bridge=self.allow_legacy_box_bridge
        )
        raw_yaw = _number(row, "face_heading_deg")
        if pitch is None or raw_yaw is None:
            self._clear_association()
            return Stage3PEvidence(False, None, None, "UNASSOCIATED", "FACE_GEOMETRY_UNAVAILABLE")
        if abs(pitch) > self.spec.maximum_abs_pitch_deg:
            self._clear_association()
            return Stage3PEvidence(
                False, None, None, "UNASSOCIATED", "PITCH_OUTSIDE_VALIDATED_ENVELOPE"
            )

        self._pitch_hits.append((elapsed, pitch))
        while self._pitch_hits and elapsed - self._pitch_hits[0][0] > self.spec.pitch_consensus_window_ms:
            self._pitch_hits.popleft()

        # During active speech, a true acoustic/visual conflict cancels any
        # association. During silence, wandering DoA cannot break visual
        # maintenance because the endpoint supplies no meaningful sound target.
        if speech and horizontal.reason in {
            "ACOUSTIC_VISUAL_DISAGREEMENT", "DISAGREEMENT_LOCKOUT"
        }:
            self._clear_association()
            return Stage3PEvidence(False, None, None, "UNASSOCIATED", horizontal.reason)

        if horizontal.confirmed and horizontal.agreement_error_deg is not None:
            error = float(horizontal.agreement_error_deg)
            strong = error <= self.spec.strong_geometry_error_deg
            weak_repeated = (
                error <= self.spec.weak_geometry_error_deg
                and len(self._speech_onsets) >= self.spec.weak_geometry_minimum_speech_bursts
            )
            if strong or weak_repeated:
                self._associated = True
                self._acquired_at_ms = elapsed
            elif not self._associated:
                return Stage3PEvidence(
                    False, None, None, "UNASSOCIATED", "ASSOCIATION_CONFIDENCE_INSUFFICIENT"
                )

        if not self._associated:
            return Stage3PEvidence(False, None, None, "UNASSOCIATED", horizontal.reason)
        if elapsed - self._acquired_at_ms > self.spec.maximum_maintenance_ms:
            self._clear_association()
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
        return Stage3PEvidence(
            True, target_yaw, target_pitch, phase, "CALIBRATED_COUPLED_TARGET_CONFIRMED"
        )
