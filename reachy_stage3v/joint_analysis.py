"""Commissioning analysis for command-free joint numeric captures.

This analysis checks whether the required endpoints are observable together.
It deliberately does not call a commissioning file validation evidence and it
does not tune or approve an end-to-end decision policy.
"""

from __future__ import annotations

import csv
import hashlib
import math
from dataclasses import asdict, replace
from pathlib import Path
from statistics import median
from typing import Any

import numpy as np

from reachy_avsync.synchrony import NumericSeries, SynchronySpec, evaluate_synchrony
from reachy_doa.angles import doa_to_physical_hypotheses
from reachy_stage2a.calibration import circular_distance_degrees

from .joint_instrument import JOINT_INSTRUMENT_SPEC_V1, JOINT_REQUIRED_COLUMNS


PILOT_TRANSFER_SYNCHRONY_SPEC = replace(
    SynchronySpec(),
    min_correlation=0.25,
    max_abs_lag_ms=120.0,
    min_audio_std=0.5,
    min_mouth_std=0.002,
)
PILOT_TRANSFER_MOVING_AVERAGE_SAMPLES = 3


def _number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _integer(value: object) -> int:
    number = _number(value)
    return int(number) if number is not None else 0


def _truth(value: object) -> bool:
    return value is True or str(value).strip().lower() == "true"


def _percentile(values: list[float], quantile: float) -> float | None:
    finite = [item for item in values if math.isfinite(item)]
    return float(np.percentile(finite, quantile * 100.0)) if finite else None


def _smooth(values: list[float], samples: int) -> list[float]:
    array = np.asarray(values, dtype=float)
    if samples <= 1 or len(array) == 0:
        return array.tolist()
    left = samples // 2
    right = samples - 1 - left
    padded = np.pad(array, (left, right), mode="edge")
    return np.convolve(padded, np.ones(samples) / samples, mode="valid").tolist()


def load_joint_csv(path: Path) -> list[dict[str, str]]:
    resolved = path.resolve()
    with resolved.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or ())
        missing = set(JOINT_REQUIRED_COLUMNS) - fieldnames
        if missing:
            raise ValueError("Joint CSV is missing required columns: " + ", ".join(sorted(missing)))
        rows = list(reader)
    if not rows:
        raise ValueError("Joint CSV contains no observations.")
    return rows


def assess_joint_commissioning(path: Path) -> dict[str, Any]:
    """Assess endpoint observability without upgrading it to validation."""

    resolved = path.resolve()
    rows = load_joint_csv(resolved)
    checks = JOINT_INSTRUMENT_SPEC_V1.payload()["commissioning_checks"]
    timestamps = [_number(row["timestamp_ms"]) for row in rows]
    if any(value is None for value in timestamps):
        raise ValueError("Joint CSV contains a non-finite timestamp.")
    times = [float(value) for value in timestamps if value is not None]
    gaps = [right - left for left, right in zip(times, times[1:])]
    if any(gap < 0.0 for gap in gaps):
        raise ValueError("Joint CSV timestamps are not monotonic.")

    single_rows = [row for row in rows if _integer(row["face_count"]) == 1]
    doa_rows = [row for row in rows if _truth(row["doa_valid"])]
    joint_rows = [
        row
        for row in rows
        if _integer(row["face_count"]) == 1
        and _truth(row["doa_valid"])
        and _number(row["face_heading_estimate_deg"]) is not None
        and _number(row["doa_axis_deg"]) is not None
    ]

    geometry_errors: list[float] = []
    for row in joint_rows:
        heading = _number(row["face_heading_estimate_deg"])
        axis = _number(row["doa_axis_deg"])
        assert heading is not None and axis is not None
        hypotheses = doa_to_physical_hypotheses(axis)
        geometry_errors.append(min(circular_distance_degrees(heading, item) for item in hypotheses))

    av_rows = [
        row
        for row in single_rows
        if all(
            _number(row[key]) is not None
            for key in ("timestamp_ms", "audio_dbfs", "lip_aperture")
        )
    ]
    synchrony = None
    if len(av_rows) >= PILOT_TRANSFER_SYNCHRONY_SPEC.min_samples:
        av_times = [float(row["timestamp_ms"]) for row in av_rows]
        audio = _smooth(
            [float(row["audio_dbfs"]) for row in av_rows],
            PILOT_TRANSFER_MOVING_AVERAGE_SAMPLES,
        )
        lip = _smooth(
            [float(row["lip_aperture"]) for row in av_rows],
            PILOT_TRANSFER_MOVING_AVERAGE_SAMPLES,
        )
        synchrony = evaluate_synchrony(
            NumericSeries.from_sequences(av_times, audio),
            NumericSeries.from_sequences(av_times, lip),
            PILOT_TRANSFER_SYNCHRONY_SPEC,
        ).as_dict()

    span = times[-1] - times[0]
    doa_ages = [
        value
        for row in rows
        if (value := _number(row["doa_age_ms"])) is not None
    ]
    inference = [
        value
        for row in rows
        if (value := _number(row["landmark_inference_ms"])) is not None
    ]
    failures: list[str] = []
    if len(rows) < int(checks["minimum_samples"]):
        failures.append("INSUFFICIENT_SAMPLES")
    if span < float(checks["minimum_span_ms"]):
        failures.append("SPAN_TOO_SHORT")
    if gaps and max(gaps) > float(checks["maximum_sample_gap_ms"]):
        failures.append("SAMPLE_GAP_EXCESSIVE")
    if inference and median(inference) > float(checks["maximum_median_landmark_inference_ms"]):
        failures.append("LANDMARK_INFERENCE_TOO_SLOW")
    doa_fraction = len(doa_rows) / len(rows)
    if doa_fraction < float(checks["minimum_doa_valid_fraction"]):
        failures.append("DOA_AVAILABILITY_TOO_LOW")
    p95_doa_age = _percentile(doa_ages, 0.95)
    if p95_doa_age is None or p95_doa_age > float(checks["maximum_p95_doa_age_ms"]):
        failures.append("DOA_AGE_TOO_HIGH")
    if not joint_rows:
        failures.append("NO_JOINT_SPATIAL_ROWS")
    if synchrony is None:
        failures.append("NO_SYNCHRONY_WINDOW")

    return {
        "schema": "reachy-joint-shadow-commissioning-analysis-v1",
        "status": "COMMISSIONING_CHECKS_PASSED" if not failures else "COMMISSIONING_CHECKS_FAILED",
        "source_file": resolved.name,
        "source_sha256": hashlib.sha256(resolved.read_bytes()).hexdigest(),
        "instrument_fingerprint": JOINT_INSTRUMENT_SPEC_V1.payload()["fingerprint"],
        "checks_passed": not failures,
        "failures": failures,
        "observability": {
            "rows": len(rows),
            "span_ms": span,
            "maximum_sample_gap_ms": max(gaps, default=0.0),
            "single_face_fraction": len(single_rows) / len(rows),
            "doa_valid_fraction": doa_fraction,
            "joint_spatial_rows": len(joint_rows),
            "joint_spatial_fraction": len(joint_rows) / len(rows),
            "median_geometry_error_deg_unvalidated_alignment": (
                median(geometry_errors) if geometry_errors else None
            ),
            "median_landmark_inference_ms": median(inference) if inference else None,
            "p95_doa_age_ms": p95_doa_age,
        },
        "pilot_transfer_synchrony": synchrony,
        "pilot_transfer_spec": {
            **asdict(PILOT_TRANSFER_SYNCHRONY_SPEC),
            "moving_average_samples": PILOT_TRANSFER_MOVING_AVERAGE_SAMPLES,
            "boundary": (
                "Transferred only to check computability. The V2 laptop-pilot threshold "
                "is not validated for this joint instrument and may not be used as final evidence."
            ),
        },
        "motion_authorized": False,
        "response_authorized": False,
        "actuation_commands": 0,
        "response_commands": 0,
        "claim_boundary": (
            "Passing means the joint numeric endpoints and timing diagnostics were observable "
            "in this commissioning capture. It does not validate fusion accuracy, playback "
            "rejection, motion, attention, response, or the complete robot behaviour."
        ),
    }
