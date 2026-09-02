"""Pure counterfactual planner for a rejected Reachy centring proposal.

The planner has no robot transport and cannot actuate hardware. It produces at
most one rotational waypoint from a measured pose so that the rejected design
remains auditable. A source-backed review rejected physical execution; this
module must not be used as a precursor to a hardware command.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping

import numpy as np

from .safety import as_pose, rigid_pose, rotation_distance_deg, translation_distance_mm


SCHEMA_VERSION = "reachy-stage4-centering-plan-reviewed-v1"
STATUS_REVIEWED_REJECTED = "REVIEWED_REJECTED_FOR_HARDWARE_EXECUTION"

# These are rejected design candidates retained for audit, not validated
# hardware-safety guarantees.
NEUTRAL_ROTATION_GATE_DEG = 1.0
MAX_START_ROTATION_DEG = 6.0
MAX_START_TRANSLATION_MM = 8.0
MAX_PLANNED_STEP_DEG = 1.5
MAX_MEASURED_STEP_DEG = 2.0
MAX_TARGET_ERROR_DEG = 1.0
MAX_TRANSLATION_DRIFT_MM = 2.0
MIN_PROGRESS_DEG = 0.25
MAX_SEPARATELY_ARMED_SESSIONS = 4


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _axis_angle(rotation: np.ndarray) -> tuple[np.ndarray, float]:
    checked = np.asarray(rotation, dtype=np.float64)
    if checked.shape != (3, 3):
        raise ValueError("A 3x3 rotation is required.")
    cosine = max(-1.0, min(1.0, (float(np.trace(checked)) - 1.0) / 2.0))
    angle = math.acos(cosine)
    if angle < 1e-12:
        return np.array([1.0, 0.0, 0.0], dtype=np.float64), 0.0
    if abs(math.sin(angle)) < 1e-8:
        eigenvalues, eigenvectors = np.linalg.eig(checked)
        index = int(np.argmin(np.abs(eigenvalues - 1.0)))
        axis = np.real(eigenvectors[:, index]).astype(np.float64)
        axis /= float(np.linalg.norm(axis))
        return axis, angle
    axis = np.array(
        [
            checked[2, 1] - checked[1, 2],
            checked[0, 2] - checked[2, 0],
            checked[1, 0] - checked[0, 1],
        ],
        dtype=np.float64,
    )
    axis /= 2.0 * math.sin(angle)
    axis /= float(np.linalg.norm(axis))
    return axis, angle


def _rodrigues(axis: np.ndarray, angle: float) -> np.ndarray:
    x, y, z = np.asarray(axis, dtype=np.float64)
    skew = np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]], dtype=np.float64)
    return np.eye(3) + math.sin(angle) * skew + (1.0 - math.cos(angle)) * (skew @ skew)


def one_step_toward_identity(
    measured_pose: np.ndarray,
    *,
    maximum_step_deg: float = MAX_PLANNED_STEP_DEG,
) -> np.ndarray:
    """Return one SO(3)-geodesic waypoint while preserving translation."""

    baseline = rigid_pose(measured_pose)
    step_limit = float(maximum_step_deg)
    if not 0.0 < step_limit <= MAX_PLANNED_STEP_DEG:
        raise ValueError(f"A rejected centring candidate step must be in (0, {MAX_PLANNED_STEP_DEG}] degrees.")
    relative_to_identity = baseline[:3, :3].T
    axis, error_rad = _axis_angle(relative_to_identity)
    step_rad = min(error_rad, math.radians(step_limit))
    waypoint = baseline.copy()
    waypoint[:3, :3] = baseline[:3, :3] @ _rodrigues(axis, step_rad)
    return rigid_pose(waypoint)


def draft_centering_plan(measured_pose: np.ndarray) -> dict[str, Any]:
    """Build one deterministic review artifact; never authorize execution."""

    baseline = rigid_pose(measured_pose)
    identity = np.eye(4, dtype=np.float64)
    initial_error = rotation_distance_deg(baseline, identity)
    initial_translation = translation_distance_mm(baseline, identity)
    if initial_translation > MAX_START_TRANSLATION_MM:
        raise ValueError(
            f"Start translation {initial_translation:.3f} mm exceeds the rejected candidate "
            f"{MAX_START_TRANSLATION_MM:.3f} mm eligibility ceiling."
        )
    if initial_error > MAX_START_ROTATION_DEG:
        raise ValueError(
            f"Start rotation {initial_error:.3f} degrees exceeds the rejected candidate "
            f"{MAX_START_ROTATION_DEG:.3f} degree eligibility ceiling."
        )

    already_within_gate = initial_error <= NEUTRAL_ROTATION_GATE_DEG
    waypoint = None if already_within_gate else one_step_toward_identity(baseline)
    planned_step = 0.0 if waypoint is None else rotation_distance_deg(baseline, waypoint)
    planned_remaining = initial_error if waypoint is None else rotation_distance_deg(waypoint, identity)
    core: dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "authorization_status": STATUS_REVIEWED_REJECTED,
        "decision": "NO_COMMAND_NEEDED" if already_within_gate else "INDEPENDENT_REVIEW_REQUIRED",
        "review_verdict": {
            "hardware_execution": "REJECT",
            "reason": (
                "The underlying target-versus-mechanism/calibration state is unresolved; "
                "the default analytical kinematics has no collision check; and the "
                "candidate thresholds and failure response are not validated."
            ),
            "maximum_commands_authorized_by_this_artifact": 0,
        },
        "baseline_pose": baseline.tolist(),
        "waypoint_pose": None if waypoint is None else waypoint.tolist(),
        "metrics": {
            "initial_rotation_from_identity_deg": initial_error,
            "initial_translation_from_identity_mm": initial_translation,
            "planned_rotation_step_deg": planned_step,
            "planned_rotation_remaining_deg": planned_remaining,
            "planned_translation_change_mm": 0.0,
        },
        "candidate_bounds": {
            "neutral_rotation_gate_deg": NEUTRAL_ROTATION_GATE_DEG,
            "maximum_start_rotation_deg": MAX_START_ROTATION_DEG,
            "maximum_start_translation_mm": MAX_START_TRANSLATION_MM,
            "maximum_planned_step_deg": MAX_PLANNED_STEP_DEG,
            "maximum_measured_step_deg": MAX_MEASURED_STEP_DEG,
            "maximum_target_error_deg": MAX_TARGET_ERROR_DEG,
            "maximum_translation_drift_mm": MAX_TRANSLATION_DRIFT_MM,
            "minimum_progress_deg": MIN_PROGRESS_DEG,
            "maximum_separately_armed_sessions": MAX_SEPARATELY_ARMED_SESSIONS,
        },
        "command_boundary": {
            "planner_robot_connections": 0,
            "planner_robot_commands": 0,
            "hardware_execution_commands_authorized": 0,
            "automatic_chaining": False,
            "automatic_return": False,
            "automatic_hardware_authorization": False,
        },
        "review_debt": [
            "The 6 degree start ceiling was proposed after observing a 4.18 degree case.",
            "The 1.5 degree waypoint and four-session cap are conservative design candidates, not validated safety limits.",
            "Fail-hold versus return-to-baseline requires independent robotics review.",
            "Endpoint bounds do not prove the continuous path stayed inside them.",
            "Analytical IK reachability does not establish collision freedom or mechanical calibration.",
            "Daemon 1.9.0 drops requested target pose/joint fields from the FullState response model.",
            "Separate zero-command captures observed materially different settled offsets, so a single correction target is not a diagnosed remedy.",
        ],
    }
    return {**core, "plan_fingerprint": hashlib.sha256(_canonical(core)).hexdigest()}


def assess_measured_step(plan: Mapping[str, Any], measured_pose: np.ndarray) -> dict[str, Any]:
    """Assess one hypothetical/recorded endpoint; never generate a next command."""

    if plan.get("schema") != SCHEMA_VERSION or plan.get("authorization_status") != STATUS_REVIEWED_REJECTED:
        raise ValueError("A valid reviewed-and-rejected centring record is required.")
    waypoint_value = plan.get("waypoint_pose")
    if waypoint_value is None:
        raise ValueError("This plan has no waypoint to assess.")
    baseline = as_pose(plan["baseline_pose"])
    waypoint = as_pose(waypoint_value)
    measured = rigid_pose(measured_pose)
    identity = np.eye(4, dtype=np.float64)
    initial_error = rotation_distance_deg(baseline, identity)
    measured_error = rotation_distance_deg(measured, identity)
    measured_step = rotation_distance_deg(baseline, measured)
    target_error = rotation_distance_deg(measured, waypoint)
    translation_drift = translation_distance_mm(baseline, measured)
    progress = initial_error - measured_error
    within_neutral_gate = measured_error <= NEUTRAL_ROTATION_GATE_DEG
    endpoint_bounds_pass = (
        measured_step <= MAX_MEASURED_STEP_DEG
        and target_error <= MAX_TARGET_ERROR_DEG
        and translation_drift <= MAX_TRANSLATION_DRIFT_MM
        and (within_neutral_gate or progress >= MIN_PROGRESS_DEG)
    )
    return {
        "schema": "reachy-stage4-centering-assessment-counterfactual-v1",
        "authorization_status": STATUS_REVIEWED_REJECTED,
        "plan_fingerprint": plan.get("plan_fingerprint"),
        "metrics": {
            "initial_rotation_from_identity_deg": initial_error,
            "measured_rotation_from_identity_deg": measured_error,
            "measured_step_deg": measured_step,
            "target_error_deg": target_error,
            "translation_drift_mm": translation_drift,
            "progress_toward_identity_deg": progress,
        },
        "within_neutral_gate": within_neutral_gate,
        "endpoint_bounds_pass": endpoint_bounds_pass,
        "operator_review": "REQUIRED" if endpoint_bounds_pass else "NOT_ELIGIBLE",
        "automatic_next_command_authorized": False,
    }
