"""Numeric-only data models for passive camera/acoustic fusion."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class FaceObservation:
    client_time_iso: str
    captured_monotonic: float
    detected: bool
    face_count: int
    center_x_norm: float | None
    center_y_norm: float | None
    heading_deg: float | None
    detector_confidence: float
    detector_score_raw: float | None
    processing_ms: float
    valid: bool
    error_code: str
    # YuNet supplies five numeric landmarks with every detection.  Retaining
    # only the midpoint of the two eyes aligns Stage 3P's numeric evidence with
    # its eye-line protocol without retaining pixels or identity embeddings.
    eye_midpoint_x_norm: float | None = None
    eye_midpoint_y_norm: float | None = None
    frame_width_px: int | None = None
    frame_height_px: int | None = None


@dataclass(slots=True, frozen=True)
class FusionDecision:
    state: str
    reason_code: str
    acoustic_axis_deg: float | None
    hypothesis_a_deg: float | None
    hypothesis_b_deg: float | None
    visual_heading_deg: float | None
    confirmed_heading_deg: float | None
    agreement_error_deg: float | None
    acoustic_confidence: float
    visual_confidence: float


STAGE2A_CSV_COLUMNS = [
    "sequence",
    "client_time_iso",
    "elapsed_ms",
    "raw_angle_rad",
    "raw_angle_deg",
    "speech_detected",
    "http_latency_ms",
    "http_status",
    "acoustic_state",
    "acoustic_confidence",
    "hypothesis_a_deg",
    "hypothesis_b_deg",
    "face_detected",
    "face_count",
    "face_center_x_norm",
    "face_center_y_norm",
    "face_eye_midpoint_x_norm",
    "face_eye_midpoint_y_norm",
    "camera_frame_width_px",
    "camera_frame_height_px",
    "face_heading_deg",
    "face_confidence",
    "face_score_raw",
    "face_age_ms",
    "fusion_state",
    "confirmed_heading_deg",
    "agreement_error_deg",
    "reason_code",
]
