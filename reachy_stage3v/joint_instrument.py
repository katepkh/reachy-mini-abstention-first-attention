"""Contract for the command-free joint shadow instrument.

The instrument joins Reachy's GET-only direction-of-arrival observation with
ephemeral laptop camera/microphone features on the browser's monotonic clock.
It neither authorizes nor sends robot or response commands.  This module is
pure: it opens no device, media stream, network connection, or output file.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from typing import Any

from reachy_doa.angles import doa_radians_to_degrees
from reachy_doa.models import DoAReading


JOINT_CONDITIONS: tuple[dict[str, str], ...] = (
    {
        "id": "live_visible_continuous",
        "role": "matching_positive",
        "instruction": "Keep one face visible and speak naturally throughout the capture.",
    },
    {
        "id": "live_visible_interrupted",
        "role": "matching_positive",
        "instruction": "Keep one face visible and alternate about one second of speech and silence.",
    },
    {
        "id": "silent_face_phone_playback",
        "role": "primary_hard_negative",
        "instruction": "Remain silent and keep one face visible while the fixed phone recording plays.",
    },
    {
        "id": "silent_mouthing_unrelated_playback",
        "role": "synchrony_hard_negative",
        "instruction": "Mouth silently out of time with the fixed phone recording while one face remains visible.",
    },
    {
        "id": "visible_silence",
        "role": "negative_control",
        "instruction": "Remain silent and still with one face visible; stop all playback.",
    },
    {
        "id": "speech_without_usable_face",
        "role": "unavailable_face_control",
        "instruction": "Keep every face outside the camera view while the declared live or playback speech source runs.",
    },
    {
        "id": "spatial_conflict",
        "role": "conflicting_cue_control",
        "instruction": "Keep one silent face visible while the fixed playback source runs from the declared conflicting direction.",
    },
    {
        "id": "sensor_unavailable_rehearsal",
        "role": "instrument_control",
        "instruction": "Use only during commissioning to verify that a declared unavailable input fails closed.",
    },
)


JOINT_REQUIRED_COLUMNS: tuple[str, ...] = (
    "timestamp_ms",
    "wall_time_iso",
    "scheduler_lateness_ms",
    "sample_gap_ms",
    "audio_context_time_ms",
    "audio_dbfs",
    "face_count",
    "face_center_x_norm",
    "face_center_y_norm",
    "face_heading_estimate_deg",
    "face_scale",
    "lip_aperture",
    "lip_motion",
    "landmark_inference_ms",
    "video_frame_age_ms",
    "video_presented_frames",
    "video_dropped_frames",
    "doa_valid",
    "doa_raw_angle_rad",
    "doa_axis_deg",
    "doa_speech_detected",
    "doa_observed_ms",
    "doa_received_ms",
    "doa_age_ms",
    "doa_roundtrip_ms",
    "doa_clock_uncertainty_ms",
    "doa_robot_http_latency_ms",
    "doa_http_status",
    "doa_error_code",
    "doa_poll_failures",
    "doa_poll_skips",
)

JOINT_STATIC_EXACT_PATHS = frozenset(
    {
        "/tools/joint_shadow_recorder.html",
        "/models/avsync_v2/face_landmarker.task",
    }
)
JOINT_STATIC_PREFIXES = ("/models/avsync_v2/runtime/",)


def joint_static_path_allowed(path: str) -> bool:
    """Allow only the recorder and its pinned local model/runtime assets."""

    normalized = str(path or "")
    if ".." in normalized or "\\" in normalized:
        return False
    return normalized in JOINT_STATIC_EXACT_PATHS or any(
        normalized.startswith(prefix) for prefix in JOINT_STATIC_PREFIXES
    )


@dataclass(frozen=True, slots=True)
class JointInstrumentSpec:
    name: str = "M5 command-free joint shadow instrument v1"
    schema: str = "reachy-joint-shadow-instrument-v1"
    sample_period_ms: int = 40
    doa_poll_period_ms: int = 200
    default_capture_seconds: int = 10
    maximum_capture_seconds: int = 30
    maximum_faces: int = 2
    camera_horizontal_fov_deg_default: float = 60.0
    motion_authority: bool = False
    response_authority: bool = False
    robot_mutating_requests: int = 0
    raw_media_saved: bool = False
    raw_media_uploaded: bool = False

    def payload(self) -> dict[str, Any]:
        core: dict[str, Any] = {
            **asdict(self),
            "conditions": list(JOINT_CONDITIONS),
            "required_columns": list(JOINT_REQUIRED_COLUMNS),
            "commissioning_checks": {
                "minimum_samples": 160,
                "minimum_span_ms": 7000.0,
                "maximum_sample_gap_ms": 160.0,
                "maximum_median_landmark_inference_ms": 45.0,
                "minimum_doa_valid_fraction": 0.80,
                "maximum_p95_doa_age_ms": 650.0,
                "scope": (
                    "Operational observability checks only. Passing does not validate "
                    "the fusion thresholds or establish a research result."
                ),
            },
            "timing_contract": {
                "browser_clock": "performance.now monotonic milliseconds",
                "doa_observation_time": "browser request midpoint",
                "doa_clock_uncertainty": "half of browser-observed bridge round trip",
                "capture_delay_fields": [
                    "video_frame_age_ms",
                    "landmark_inference_ms",
                    "doa_age_ms",
                    "doa_roundtrip_ms",
                    "doa_robot_http_latency_ms",
                    "scheduler_lateness_ms",
                    "sample_gap_ms",
                ],
                "limitation": (
                    "The endpoint does not expose a robot sensor-capture timestamp; "
                    "the browser request midpoint is an estimate with recorded uncertainty."
                ),
            },
            "privacy_contract": {
                "camera_and_microphone_samples": "transient in local browser",
                "doa_bridge_payload": "numeric endpoint state only",
                "download": "numeric CSV plus non-identifying numeric metadata",
                "network_scope": "localhost bridge plus allowlisted private Reachy GET endpoint",
                "contains_pixels": False,
                "contains_waveform": False,
                "contains_transcript": False,
                "contains_identity_embedding": False,
            },
            "claim_boundary": (
                "A successful commissioning capture establishes only that joint numeric "
                "inputs and timing diagnostics are observable. It does not validate speaker "
                "identity, liveness, fusion accuracy, motion, response, or robot behaviour."
            ),
        }
        encoded = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return {**core, "fingerprint": hashlib.sha256(encoded).hexdigest()}


JOINT_INSTRUMENT_SPEC_V1 = JointInstrumentSpec()


def doa_bridge_payload(
    reading: DoAReading,
    *,
    bridge_request_started_monotonic: float,
    bridge_response_ready_monotonic: float,
) -> dict[str, object]:
    """Convert one GET-only reading into a bounded numeric browser payload."""

    started = float(bridge_request_started_monotonic)
    finished = float(bridge_response_ready_monotonic)
    if not all(math.isfinite(value) for value in (started, finished)) or finished < started:
        raise ValueError("Bridge timing must be finite and nondecreasing.")
    raw = reading.raw_angle_rad
    axis = None
    if reading.valid and raw is not None and math.isfinite(float(raw)):
        axis = doa_radians_to_degrees(float(raw))
    return {
        "schema": "reachy-read-only-doa-bridge-v1",
        "valid": bool(reading.valid),
        "raw_angle_rad": float(raw) if axis is not None else None,
        "axis_deg": axis,
        "speech_detected": reading.speech_detected if reading.valid else None,
        "robot_http_latency_ms": max(0.0, float(reading.http_latency_ms)),
        "http_status": reading.http_status,
        "error_code": str(reading.error or "")[:160],
        "bridge_processing_ms": 1000.0 * (finished - started),
        "motion_authorized": False,
        "response_authorized": False,
        "robot_mutating_requests": 0,
    }


def validate_joint_instrument_contract() -> None:
    condition_ids = [item["id"] for item in JOINT_CONDITIONS]
    if len(condition_ids) != len(set(condition_ids)):
        raise ValueError("Joint instrument condition identifiers must be unique.")
    required = set(JOINT_REQUIRED_COLUMNS)
    timing = {
        "timestamp_ms",
        "scheduler_lateness_ms",
        "sample_gap_ms",
        "video_frame_age_ms",
        "doa_observed_ms",
        "doa_received_ms",
        "doa_age_ms",
        "doa_clock_uncertainty_ms",
    }
    if not timing.issubset(required):
        raise ValueError("Joint instrument must expose every timing-quality field.")
    payload = JOINT_INSTRUMENT_SPEC_V1.payload()
    if payload["motion_authority"] or payload["response_authority"]:
        raise ValueError("The joint instrument must remain command-free.")
    if payload["robot_mutating_requests"] != 0:
        raise ValueError("The joint instrument may not declare mutating robot requests.")


validate_joint_instrument_contract()
