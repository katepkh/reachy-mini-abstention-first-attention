"""Conservative passive fusion: agree or explicitly abstain."""

from __future__ import annotations

import time

from reachy_doa.policies import PolicyDecision

from .calibration import circular_distance_degrees
from .config import (
    MAX_FACE_AGE_MS,
    MAX_FUSION_ERROR_DEG,
    MIN_ACOUSTIC_CONFIDENCE,
    MIN_FACE_CONFIDENCE,
)
from .models import FaceObservation, FusionDecision


def _withhold(
    reason: str,
    acoustic: PolicyDecision,
    face: FaceObservation | None,
) -> FusionDecision:
    return FusionDecision(
        state="WITHHELD",
        reason_code=reason,
        acoustic_axis_deg=acoustic.axis_deg,
        hypothesis_a_deg=acoustic.hypothesis_a_deg,
        hypothesis_b_deg=acoustic.hypothesis_b_deg,
        visual_heading_deg=face.heading_deg if face else None,
        confirmed_heading_deg=None,
        agreement_error_deg=None,
        acoustic_confidence=acoustic.confidence,
        visual_confidence=face.detector_confidence if face else 0.0,
    )


def fuse_passive_evidence(
    acoustic: PolicyDecision,
    face: FaceObservation | None,
    *,
    now_monotonic: float | None = None,
    maximum_face_age_ms: float = MAX_FACE_AGE_MS,
) -> FusionDecision:
    """Confirm one physical hypothesis only when visual evidence agrees.

    A confirmation means only "one visible face aligns with the acoustic
    hypothesis." It does not establish identity, intent, or that the face is
    the source of the sound.
    """
    now = time.perf_counter() if now_monotonic is None else float(now_monotonic)
    if not acoustic.would_attend_axis or acoustic.axis_deg is None:
        return _withhold("ACOUSTIC_NOT_TRACKING", acoustic, face)
    if acoustic.confidence < MIN_ACOUSTIC_CONFIDENCE:
        return _withhold("ACOUSTIC_LOW_CONFIDENCE", acoustic, face)
    if acoustic.speech_evidence <= 0.0:
        return _withhold("NO_SPEECH_EVIDENCE", acoustic, face)
    if face is None:
        return _withhold("NO_CAMERA_OBSERVATION", acoustic, face)
    if not face.valid:
        return _withhold(face.error_code or "CAMERA_INVALID", acoustic, face)
    age_ms = max(0.0, (now - face.captured_monotonic) * 1000.0)
    if age_ms > maximum_face_age_ms:
        return _withhold("CAMERA_OBSERVATION_STALE", acoustic, face)
    if not face.detected or face.face_count == 0 or face.heading_deg is None:
        return _withhold("NO_FACE", acoustic, face)
    if face.face_count != 1:
        return _withhold("MULTIPLE_FACES", acoustic, face)
    if face.detector_confidence < MIN_FACE_CONFIDENCE:
        return _withhold("FACE_LOW_CONFIDENCE", acoustic, face)

    hypotheses = [
        value
        for value in (acoustic.hypothesis_a_deg, acoustic.hypothesis_b_deg)
        if value is not None
    ]
    matches = [
        (hypothesis, circular_distance_degrees(face.heading_deg, hypothesis))
        for hypothesis in hypotheses
        if circular_distance_degrees(face.heading_deg, hypothesis) <= MAX_FUSION_ERROR_DEG
    ]
    if len(matches) == 0:
        return _withhold("ACOUSTIC_VISUAL_DISAGREEMENT", acoustic, face)
    if len(matches) > 1:
        return _withhold("VISUAL_HYPOTHESIS_AMBIGUOUS", acoustic, face)

    confirmed, error = matches[0]
    return FusionDecision(
        state="CONFIRMED",
        reason_code="ACOUSTIC_VISUAL_AGREEMENT",
        acoustic_axis_deg=acoustic.axis_deg,
        hypothesis_a_deg=acoustic.hypothesis_a_deg,
        hypothesis_b_deg=acoustic.hypothesis_b_deg,
        visual_heading_deg=face.heading_deg,
        confirmed_heading_deg=confirmed,
        agreement_error_deg=error,
        acoustic_confidence=acoustic.confidence,
        visual_confidence=face.detector_confidence,
    )
