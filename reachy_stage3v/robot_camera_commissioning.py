"""Pure contract and offline checks for Reachy-camera joint commissioning.

The live server is deliberately separate.  This module opens no camera,
microphone, network connection, controller, or output file.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median, pstdev
from typing import Any

import numpy as np

from reachy_doa.angles import doa_to_physical_hypotheses
from reachy_stage2a.calibration import circular_distance_degrees


ROBOT_CAMERA_REQUIRED_COLUMNS: tuple[str, ...] = (
    "timestamp_ms",
    "wall_time_iso",
    "scheduler_lateness_ms",
    "sample_gap_ms",
    "audio_context_time_ms",
    "audio_dbfs",
    "robot_camera_status",
    "robot_frame_sequence",
    "robot_transport_frames",
    "robot_analysis_frames",
    "robot_frame_age_ms",
    "robot_frame_fetch_ms",
    "robot_frame_width_px",
    "robot_frame_height_px",
    "robot_frame_encode_ms",
    "robot_frame_duplicate",
    "robot_frames_skipped_since_previous",
    "face_count",
    "face_center_x_norm",
    "face_center_y_norm",
    "face_camera_right_deg",
    "face_heading_robot_deg",
    "face_scale",
    "lip_aperture",
    "lip_motion",
    "landmark_inference_ms",
    "face_observation_age_ms",
    "doa_valid",
    "doa_raw_angle_rad",
    "doa_axis_deg",
    "doa_speech_detected",
    "doa_age_ms",
    "doa_roundtrip_ms",
    "doa_robot_http_latency_ms",
    "doa_http_status",
    "doa_error_code",
)

ROBOT_CAMERA_STATIC_EXACT_PATHS = frozenset(
    {
        "/tools/robot_camera_commissioning.html",
        "/models/avsync_v2/face_landmarker.task",
    }
)
ROBOT_CAMERA_STATIC_PREFIXES = ("/models/avsync_v2/runtime/",)


def robot_camera_static_path_allowed(path: str) -> bool:
    normalized = str(path or "")
    if ".." in normalized or "\\" in normalized:
        return False
    return normalized in ROBOT_CAMERA_STATIC_EXACT_PATHS or any(
        normalized.startswith(prefix) for prefix in ROBOT_CAMERA_STATIC_PREFIXES
    )


@dataclass(frozen=True, slots=True)
class RobotCameraCommissioningSpec:
    name: str = "M5 Reachy-camera command-free commissioning v1"
    schema: str = "reachy-robot-camera-commissioning-v1"
    status: str = "COMMISSIONING_REQUIRED"
    sample_period_ms: int = 40
    robot_frame_poll_period_ms: int = 30
    doa_poll_period_ms: int = 200
    capture_seconds: int = 10
    motion_authority: bool = False
    response_authority: bool = False
    robot_mutating_requests: int = 0
    raw_media_saved: bool = False
    raw_media_uploaded: bool = False

    def payload(self) -> dict[str, Any]:
        core: dict[str, Any] = {
            **asdict(self),
            "required_columns": list(ROBOT_CAMERA_REQUIRED_COLUMNS),
            "commissioning_checks": {
                "minimum_samples": 160,
                "minimum_span_ms": 7000.0,
                "maximum_sample_gap_ms": 160.0,
                "minimum_robot_transport_fps": 15.0,
                "minimum_unique_analyzed_fps": 15.0,
                "maximum_p95_robot_frame_age_ms": 350.0,
                "maximum_duplicate_row_fraction": 0.50,
                "minimum_single_face_fraction": 0.80,
                "minimum_median_face_scale": 0.02,
                "minimum_audio_std_db": 0.50,
                "minimum_lip_aperture_std": 0.002,
                "maximum_median_landmark_inference_ms": 60.0,
                "minimum_doa_valid_fraction": 0.80,
                "maximum_p95_doa_age_ms": 650.0,
                "minimum_doa_speech_fraction": 0.25,
                "minimum_joint_spatial_fraction": 0.75,
                "maximum_median_geometry_error_deg": 20.0,
                "scope": (
                    "Robot-camera endpoint commissioning only. Passing does not validate "
                    "speaker selection, playback rejection, motion, attention, or response."
                ),
            },
            "coordinate_contract": {
                "camera_projection": (
                    "Pollen Reachy Mini Wireless intrinsics; image-right is camera-right positive"
                ),
                "robot_heading": (
                    "front=0 degrees; robot-right positive; face robot heading is the negative "
                    "of camera-right bearing; no outcome-derived offset is applied"
                ),
                "doa_axis": (
                    "Reachy linear-array axis 0=left, 90=front/back, 180=right; converted "
                    "to its two physical heading hypotheses before comparison"
                ),
            },
            "timing_contract": {
                "browser_clock": "performance.now monotonic milliseconds",
                "robot_frame_time": (
                    "server frame age at response plus half browser-observed localhost round trip"
                ),
                "doa_time": "browser request midpoint with half-round-trip uncertainty",
                "frame_loss_boundary": (
                    "transport and analyzed frame counters, unique-frame rate, duplicate rows, "
                    "sequence gaps, and stalls are measured; RTP packet-loss counters are not "
                    "exposed by the current local proxy and are not claimed"
                ),
            },
            "privacy_contract": {
                "robot_camera_frames": (
                    "receive-only private-LAN stream; latest downsized JPEG held transiently in "
                    "server RAM and served only on loopback; overwritten by the next frame"
                ),
                "laptop_microphone_samples": "transient in local browser",
                "retained_output": "derived numeric CSV and non-identifying metadata only",
                "contains_pixels": False,
                "contains_waveform": False,
                "contains_transcript": False,
                "contains_identity_embedding": False,
            },
            "claim_boundary": (
                "A pass establishes only that Reachy's real camera stream, transient lip/face "
                "features, Reachy DoA, and timing diagnostics were jointly observable. It does "
                "not validate the selector or any robot action."
            ),
        }
        encoded = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return {**core, "fingerprint": hashlib.sha256(encoded).hexdigest()}


ROBOT_CAMERA_COMMISSIONING_SPEC_V1 = RobotCameraCommissioningSpec()


def _number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _integer(value: object) -> int:
    value_number = _number(value)
    return int(value_number) if value_number is not None else 0


def _truth(value: object) -> bool:
    return value is True or str(value).strip().lower() == "true"


def _percentile(values: list[float], quantile: float) -> float | None:
    finite = [value for value in values if math.isfinite(value)]
    return float(np.percentile(finite, quantile * 100.0)) if finite else None


def load_robot_camera_csv(path: Path) -> list[dict[str, str]]:
    with path.resolve().open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = set(ROBOT_CAMERA_REQUIRED_COLUMNS) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(
                "Reachy-camera CSV is missing required columns: "
                + ", ".join(sorted(missing))
            )
        rows = list(reader)
    if not rows:
        raise ValueError("Reachy-camera CSV contains no observations.")
    return rows


def assess_robot_camera_commissioning(path: Path) -> dict[str, Any]:
    """Apply only the predeclared robot-camera observability checks."""

    resolved = path.resolve()
    rows = load_robot_camera_csv(resolved)
    checks = ROBOT_CAMERA_COMMISSIONING_SPEC_V1.payload()["commissioning_checks"]
    times = [_number(row["timestamp_ms"]) for row in rows]
    if any(value is None for value in times):
        raise ValueError("Reachy-camera CSV contains a non-finite timestamp.")
    timestamps = [float(value) for value in times if value is not None]
    gaps = [right - left for left, right in zip(timestamps, timestamps[1:])]
    if any(gap < 0.0 for gap in gaps):
        raise ValueError("Reachy-camera timestamps are not monotonic.")
    span_ms = timestamps[-1] - timestamps[0]
    span_s = max(span_ms / 1000.0, 1e-9)

    first_transport = _integer(rows[0]["robot_transport_frames"])
    last_transport = _integer(rows[-1]["robot_transport_frames"])
    transport_fps = max(0, last_transport - first_transport) / span_s
    unique_sequences = {
        _integer(row["robot_frame_sequence"])
        for row in rows
        if _integer(row["robot_frame_sequence"]) > 0
    }
    unique_fps = len(unique_sequences) / span_s
    duplicate_fraction = sum(
        _truth(row["robot_frame_duplicate"]) for row in rows
    ) / len(rows)
    frame_ages = [
        value
        for row in rows
        if (value := _number(row["robot_frame_age_ms"])) is not None
    ]
    single_rows = [row for row in rows if _integer(row["face_count"]) == 1]
    face_scales = [
        value
        for row in single_rows
        if (value := _number(row["face_scale"])) is not None
    ]
    lip_values = [
        value
        for row in single_rows
        if (value := _number(row["lip_aperture"])) is not None
    ]
    audio_values = [
        value
        for row in rows
        if (value := _number(row["audio_dbfs"])) is not None
    ]
    inference = [
        value
        for row in rows
        if (value := _number(row["landmark_inference_ms"])) is not None
    ]
    doa_rows = [row for row in rows if _truth(row["doa_valid"])]
    doa_ages = [
        value
        for row in rows
        if (value := _number(row["doa_age_ms"])) is not None
    ]
    speech_fraction = sum(
        _truth(row["doa_speech_detected"]) for row in doa_rows
    ) / max(len(doa_rows), 1)
    joint_rows = [
        row
        for row in rows
        if _integer(row["face_count"]) == 1
        and _truth(row["doa_valid"])
        and _number(row["face_heading_robot_deg"]) is not None
        and _number(row["doa_axis_deg"]) is not None
    ]
    geometry_errors: list[float] = []
    for row in joint_rows:
        face_heading = _number(row["face_heading_robot_deg"])
        doa_axis = _number(row["doa_axis_deg"])
        assert face_heading is not None and doa_axis is not None
        hypotheses = doa_to_physical_hypotheses(doa_axis)
        geometry_errors.append(
            min(circular_distance_degrees(face_heading, item) for item in hypotheses)
        )

    p95_frame_age = _percentile(frame_ages, 0.95)
    p95_doa_age = _percentile(doa_ages, 0.95)
    single_fraction = len(single_rows) / len(rows)
    joint_fraction = len(joint_rows) / len(rows)
    median_scale = median(face_scales) if face_scales else None
    median_inference = median(inference) if inference else None
    median_geometry = median(geometry_errors) if geometry_errors else None
    audio_std = pstdev(audio_values) if len(audio_values) >= 2 else 0.0
    lip_std = pstdev(lip_values) if len(lip_values) >= 2 else 0.0

    failures: list[str] = []
    if len(rows) < int(checks["minimum_samples"]):
        failures.append("INSUFFICIENT_SAMPLES")
    if span_ms < float(checks["minimum_span_ms"]):
        failures.append("SPAN_TOO_SHORT")
    if gaps and max(gaps) > float(checks["maximum_sample_gap_ms"]):
        failures.append("SAMPLE_GAP_EXCESSIVE")
    if transport_fps < float(checks["minimum_robot_transport_fps"]):
        failures.append("ROBOT_CAMERA_TRANSPORT_RATE_TOO_LOW")
    if unique_fps < float(checks["minimum_unique_analyzed_fps"]):
        failures.append("ROBOT_CAMERA_ANALYSIS_RATE_TOO_LOW")
    if p95_frame_age is None or p95_frame_age > float(checks["maximum_p95_robot_frame_age_ms"]):
        failures.append("ROBOT_CAMERA_FRAME_AGE_TOO_HIGH")
    if duplicate_fraction > float(checks["maximum_duplicate_row_fraction"]):
        failures.append("ROBOT_CAMERA_DUPLICATE_FRACTION_TOO_HIGH")
    if single_fraction < float(checks["minimum_single_face_fraction"]):
        failures.append("SINGLE_FACE_FRACTION_TOO_LOW")
    if median_scale is None or median_scale < float(checks["minimum_median_face_scale"]):
        failures.append("FACE_SCALE_TOO_LOW")
    if audio_std < float(checks["minimum_audio_std_db"]):
        failures.append("AUDIO_DYNAMIC_RANGE_TOO_LOW")
    if lip_std < float(checks["minimum_lip_aperture_std"]):
        failures.append("LIP_DYNAMIC_RANGE_TOO_LOW")
    if median_inference is None or median_inference > float(checks["maximum_median_landmark_inference_ms"]):
        failures.append("LANDMARK_INFERENCE_TOO_SLOW")
    if len(doa_rows) / len(rows) < float(checks["minimum_doa_valid_fraction"]):
        failures.append("DOA_AVAILABILITY_TOO_LOW")
    if p95_doa_age is None or p95_doa_age > float(checks["maximum_p95_doa_age_ms"]):
        failures.append("DOA_AGE_TOO_HIGH")
    if speech_fraction < float(checks["minimum_doa_speech_fraction"]):
        failures.append("SPEECH_ACTIVITY_TOO_LOW")
    if joint_fraction < float(checks["minimum_joint_spatial_fraction"]):
        failures.append("JOINT_SPATIAL_FRACTION_TOO_LOW")
    if median_geometry is None or median_geometry > float(checks["maximum_median_geometry_error_deg"]):
        failures.append("CAMERA_DOA_GEOMETRY_MISMATCH")

    return {
        "schema": "reachy-robot-camera-commissioning-analysis-v1",
        "status": "COMMISSIONING_CHECKS_PASSED" if not failures else "COMMISSIONING_CHECKS_FAILED",
        "source_file": resolved.name,
        "source_sha256": hashlib.sha256(resolved.read_bytes()).hexdigest(),
        "instrument_fingerprint": ROBOT_CAMERA_COMMISSIONING_SPEC_V1.payload()["fingerprint"],
        "checks_passed": not failures,
        "failures": failures,
        "observability": {
            "rows": len(rows),
            "span_ms": span_ms,
            "maximum_sample_gap_ms": max(gaps, default=0.0),
            "robot_transport_fps": transport_fps,
            "unique_analyzed_frame_fps": unique_fps,
            "duplicate_row_fraction": duplicate_fraction,
            "p95_robot_frame_age_ms": p95_frame_age,
            "single_face_fraction": single_fraction,
            "median_face_scale": median_scale,
            "audio_std_db": audio_std,
            "lip_aperture_std": lip_std,
            "median_landmark_inference_ms": median_inference,
            "doa_valid_fraction": len(doa_rows) / len(rows),
            "p95_doa_age_ms": p95_doa_age,
            "doa_speech_fraction": speech_fraction,
            "joint_spatial_fraction": joint_fraction,
            "median_camera_doa_geometry_error_deg": median_geometry,
        },
        "motion_authorized": False,
        "response_authorized": False,
        "actuation_commands": 0,
        "response_commands": 0,
        "claim_boundary": ROBOT_CAMERA_COMMISSIONING_SPEC_V1.payload()["claim_boundary"],
    }


def validate_robot_camera_commissioning_contract() -> None:
    payload = ROBOT_CAMERA_COMMISSIONING_SPEC_V1.payload()
    if payload["motion_authority"] or payload["response_authority"]:
        raise ValueError("Reachy-camera commissioning must remain command-free.")
    if payload["robot_mutating_requests"] != 0:
        raise ValueError("Reachy-camera commissioning may not declare mutating requests.")
    if payload["raw_media_saved"] or payload["raw_media_uploaded"]:
        raise ValueError("Reachy-camera commissioning may retain only derived numeric output.")


validate_robot_camera_commissioning_contract()
