"""Pure review gate for a possible baseline-relative Stage 4A successor.

This module deliberately contains no robot transport, execution function, file
write, or arming mechanism.  Its numeric bounds are transparent design
candidates selected after the V3/V4 evidence; they are not manufacturer limits
or validated safety guarantees.
"""

from __future__ import annotations

import math
import re
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from .safety import (
    as_pose,
    rigid_pose,
    rotation_distance_deg,
    translation_distance_mm,
    validate_direction,
)


SCHEMA_VERSION = "reachy-stage4a-baseline-relative-successor-review-v1"
STATUS_DESIGN_ONLY = "DESIGN_ONLY_NO_COMMAND_AUTHORITY"

# Post-V4 candidate values.  These can make a proposal reviewable; they cannot
# make it safe.  Any executable successor must freeze independently reviewed
# values in a new protocol before observing a new hardware outcome.
CANDIDATE_ABSOLUTE_RPY_LIMIT_DEG = 10.0
CANDIDATE_ABSOLUTE_ROTATION_LIMIT_DEG = 10.0
CANDIDATE_TRANSLATION_LIMIT_MM = 8.0
CANDIDATE_INCREMENT_DEG = 3.0
CANDIDATE_BASELINE_DRIFT_LIMIT_DEG = 0.25
CANDIDATE_BASELINE_TRANSLATION_DRIFT_LIMIT_MM = 1.0
CANDIDATE_MIN_BASELINE_FRAMES = 50

REQUIRED_REVIEW_RECORDS = (
    "frozen_v4_outcome_preserved",
    "expected_post_wake_accuracy_reviewed",
    "target_state_strategy_reviewed",
    "continuous_path_and_joint_margin_reviewed",
    "failure_and_return_strategy_reviewed",
    "borrowed_robot_scope_confirmed",
    "independent_robotics_review_recorded",
)

REQUIRED_REVIEW_RECORD_FIELDS = (
    "artifact_reference",
    "artifact_sha256",
    "recorded_by",
    "recorded_at_utc",
)


def candidate_target_pose(
    baseline: Iterable[Iterable[float]] | np.ndarray,
    direction: str,
) -> np.ndarray:
    """Apply this draft's own frozen 3-degree world-axis increment."""

    direction = validate_direction(direction)
    angle = math.radians(CANDIDATE_INCREMENT_DEG)
    if direction in {"UP", "RIGHT"}:
        angle = -angle
    cosine = math.cos(angle)
    sine = math.sin(angle)
    delta = np.eye(4, dtype=np.float64)
    if direction in {"LEFT", "RIGHT"}:
        delta[:3, :3] = [
            [cosine, -sine, 0.0],
            [sine, cosine, 0.0],
            [0.0, 0.0, 1.0],
        ]
    else:
        # Positive UP is a negative world-y rotation, matching look-at geometry.
        delta[:3, :3] = [
            [cosine, 0.0, sine],
            [0.0, 1.0, 0.0],
            [-sine, 0.0, cosine],
        ]
    base = rigid_pose(baseline)
    target = base.copy()
    target[:3, :3] = delta[:3, :3] @ base[:3, :3]
    return rigid_pose(target)


def _review_record_missing_fields(value: object) -> list[str]:
    if not isinstance(value, Mapping):
        return list(REQUIRED_REVIEW_RECORD_FIELDS)
    missing: list[str] = []
    for field in REQUIRED_REVIEW_RECORD_FIELDS:
        field_value = value.get(field)
        if not isinstance(field_value, str) or not field_value.strip():
            missing.append(field)
    digest = value.get("artifact_sha256")
    if "artifact_sha256" not in missing and not re.fullmatch(r"[0-9a-fA-F]{64}", str(digest)):
        missing.append("artifact_sha256")
    recorded_at = value.get("recorded_at_utc")
    if "recorded_at_utc" not in missing and not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",
        str(recorded_at),
    ):
        missing.append("recorded_at_utc")
    return missing


def _rpy_deg(value: Iterable[Iterable[float]] | np.ndarray) -> tuple[float, float, float]:
    """Return intrinsic xyz roll/pitch/yaw for a rigid pose."""

    rotation = rigid_pose(value)[:3, :3]
    pitch = math.asin(max(-1.0, min(1.0, -float(rotation[2, 0]))))
    cosine_pitch = math.cos(pitch)
    if abs(cosine_pitch) > 1e-9:
        roll = math.atan2(float(rotation[2, 1]), float(rotation[2, 2]))
        yaw = math.atan2(float(rotation[1, 0]), float(rotation[0, 0]))
    else:
        roll = math.atan2(-float(rotation[1, 2]), float(rotation[1, 1]))
        yaw = 0.0
    return tuple(math.degrees(angle) for angle in (roll, pitch, yaw))


def assess_successor_review_packet(
    baseline_frames: Sequence[Iterable[Iterable[float]] | np.ndarray],
    direction: str,
    *,
    review_records: Mapping[str, Mapping[str, str]] | None = None,
) -> dict[str, Any]:
    """Assess whether a non-executable successor packet is ready for review.

    A clean result means only that the packet contains the listed evidence.  It
    never authorizes a robot command.
    """

    direction = validate_direction(direction)
    frames = [rigid_pose(frame) for frame in baseline_frames]
    records = dict(review_records or {})
    blockers: list[str] = []

    if len(frames) < CANDIDATE_MIN_BASELINE_FRAMES:
        blockers.append("INSUFFICIENT_BASELINE_FRAMES")

    if frames:
        # Use the full pairwise spread so an early central sample cannot hide
        # opposite drift later in the capture.  The freshest accepted sample is
        # the candidate command baseline; this still does not authorize its use.
        max_rotation_drift = max(
            rotation_distance_deg(first, second)
            for index, first in enumerate(frames)
            for second in frames[index:]
        )
        max_translation_drift = max(
            translation_distance_mm(first, second)
            for index, first in enumerate(frames)
            for second in frames[index:]
        )
        baseline = frames[-1]
        target = candidate_target_pose(baseline, direction)
        baseline_rpy = _rpy_deg(baseline)
        target_rpy = _rpy_deg(target)
        baseline_rotation = rotation_distance_deg(baseline, np.eye(4))
        target_rotation = rotation_distance_deg(target, np.eye(4))
        baseline_translation = translation_distance_mm(baseline, np.eye(4))
        target_translation = translation_distance_mm(target, np.eye(4))

        if max_rotation_drift > CANDIDATE_BASELINE_DRIFT_LIMIT_DEG:
            blockers.append("BASELINE_ROTATION_UNSTABLE")
        if max_translation_drift > CANDIDATE_BASELINE_TRANSLATION_DRIFT_LIMIT_MM:
            blockers.append("BASELINE_TRANSLATION_UNSTABLE")
        if max(abs(value) for value in baseline_rpy + target_rpy) > CANDIDATE_ABSOLUTE_RPY_LIMIT_DEG:
            blockers.append("CANDIDATE_ABSOLUTE_RPY_ENVELOPE_EXCEEDED")
        if max(baseline_rotation, target_rotation) > CANDIDATE_ABSOLUTE_ROTATION_LIMIT_DEG:
            blockers.append("CANDIDATE_ABSOLUTE_ROTATION_ENVELOPE_EXCEEDED")
        if max(baseline_translation, target_translation) > CANDIDATE_TRANSLATION_LIMIT_MM:
            blockers.append("CANDIDATE_TRANSLATION_ENVELOPE_EXCEEDED")
        commanded_increment = rotation_distance_deg(baseline, target)
    else:
        baseline = None
        target = None
        max_rotation_drift = None
        max_translation_drift = None
        baseline_rpy = None
        target_rpy = None
        baseline_rotation = None
        target_rotation = None
        baseline_translation = None
        target_translation = None
        commanded_increment = None

    incomplete_records = {
        name: _review_record_missing_fields(records.get(name))
        for name in REQUIRED_REVIEW_RECORDS
    }
    incomplete_records = {
        name: fields for name, fields in incomplete_records.items() if fields
    }
    blockers.extend(f"INCOMPLETE_REVIEW_RECORD:{name}" for name in incomplete_records)

    geometry_packet_complete = not any(
        blocker.startswith(("INSUFFICIENT_", "BASELINE_", "CANDIDATE_"))
        for blocker in blockers
    )
    review_packet_complete = not blockers
    return {
        "schema": SCHEMA_VERSION,
        "status": STATUS_DESIGN_ONLY,
        "direction": direction,
        "candidate_bounds": {
            "absolute_rpy_limit_deg": CANDIDATE_ABSOLUTE_RPY_LIMIT_DEG,
            "absolute_rotation_from_identity_limit_deg": CANDIDATE_ABSOLUTE_ROTATION_LIMIT_DEG,
            "translation_from_identity_limit_mm": CANDIDATE_TRANSLATION_LIMIT_MM,
            "baseline_rotation_drift_limit_deg": CANDIDATE_BASELINE_DRIFT_LIMIT_DEG,
            "baseline_translation_drift_limit_mm": CANDIDATE_BASELINE_TRANSLATION_DRIFT_LIMIT_MM,
            "minimum_baseline_frames": CANDIDATE_MIN_BASELINE_FRAMES,
            "candidate_increment_deg": CANDIDATE_INCREMENT_DEG,
            "epistemic_status": "post-V4 design candidates; not vendor or validated safety limits",
        },
        "observed": {
            "baseline_frames": len(frames),
            "maximum_baseline_rotation_drift_deg": max_rotation_drift,
            "maximum_baseline_translation_drift_mm": max_translation_drift,
            "baseline_rpy_deg": baseline_rpy,
            "target_rpy_deg": target_rpy,
            "baseline_rotation_from_identity_deg": baseline_rotation,
            "target_rotation_from_identity_deg": target_rotation,
            "baseline_translation_from_identity_mm": baseline_translation,
            "target_translation_from_identity_mm": target_translation,
            "candidate_commanded_increment_deg": commanded_increment,
        },
        "geometry_packet_complete": geometry_packet_complete,
        "review_packet_complete": review_packet_complete,
        "required_review_record_fields": list(REQUIRED_REVIEW_RECORD_FIELDS),
        "incomplete_review_records": incomplete_records,
        "blockers": blockers,
        "candidate_baseline_pose": None if baseline is None else as_pose(baseline).tolist(),
        "candidate_target_pose": None if target is None else as_pose(target).tolist(),
        "robot_connections": 0,
        "robot_commands_authorized": 0,
        "robot_commands_sent": 0,
    }
