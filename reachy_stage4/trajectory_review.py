"""Pure reconstruction and joint-margin analysis for daemon 1.9.0 moves.

The pose interpolation below mirrors Reachy Mini 1.9.0 ``GotoMove``:
minimum-jerk time scaling followed by signed-scalar yaw interpolation and a
rotation-vector interpolation of the residual roll/pitch rotation.  This file
has no transport, command, arming, or robot-discovery surface.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

import numpy as np
from scipy.spatial.transform import Rotation

from .safety import rigid_pose


SCHEMA_VERSION = "reachy-stage4a-v190-offline-trajectory-review-v1"
STATUS_OFFLINE = "OFFLINE_ONLY_NO_COMMAND_AUTHORITY"
JOINT_NAMES = (
    "body_yaw",
    "stewart_1",
    "stewart_2",
    "stewart_3",
    "stewart_4",
    "stewart_5",
    "stewart_6",
)


def minimum_jerk_progress(normalized_time: float) -> float:
    """Return daemon 1.9.0's normalized minimum-jerk time trajectory."""

    value = float(normalized_time)
    if not 0.0 <= value <= 1.0:
        raise ValueError("Normalized time must be in [0, 1].")
    return 10.0 * value**3 - 15.0 * value**4 + 6.0 * value**5


def interpolate_pose_v190(
    start_pose: np.ndarray,
    target_pose: np.ndarray,
    progress: float,
) -> np.ndarray:
    """Mirror daemon 1.9.0 ``linear_pose_interpolation(..., True)``."""

    start = rigid_pose(start_pose)
    target = rigid_pose(target_pose)
    amount = float(progress)
    if not 0.0 <= amount <= 1.0:
        raise ValueError("Interpolation progress must be in [0, 1].")

    start_rotation = Rotation.from_matrix(start[:3, :3])
    target_rotation = Rotation.from_matrix(target[:3, :3])
    start_yaw = float(start_rotation.as_euler("xyz")[2])
    target_yaw = float(target_rotation.as_euler("xyz")[2])
    yaw = start_yaw + (target_yaw - start_yaw) * amount
    start_residual = Rotation.from_euler("z", -start_yaw) * start_rotation
    target_residual = Rotation.from_euler("z", -target_yaw) * target_rotation
    residual_delta = (start_residual.inv() * target_residual).as_rotvec()
    residual = start_residual * Rotation.from_rotvec(residual_delta * amount)

    result = np.eye(4, dtype=np.float64)
    result[:3, :3] = (Rotation.from_euler("z", yaw) * residual).as_matrix()
    result[:3, 3] = start[:3, 3] + (target[:3, 3] - start[:3, 3]) * amount
    return result


def reconstruct_ideal_leg_v190(
    start_pose: np.ndarray,
    target_pose: np.ndarray,
    *,
    start_body_yaw: float,
    target_body_yaw: float,
    duration_s: float,
    sample_hz: float = 100.0,
) -> dict[str, Any]:
    """Sample the exact continuous 1.9.0 path on an explicit ideal grid.

    The daemon's real loop evaluates wall-clock times while ``t < duration``.
    Therefore this inclusive grid is a deterministic path-envelope review, not
    a claim about the exact timestamps or final write made by a live process.
    """

    duration = float(duration_s)
    frequency = float(sample_hz)
    if duration <= 0.0:
        raise ValueError("Duration must be positive.")
    if frequency <= 0.0:
        raise ValueError("Sample frequency must be positive.")
    intervals = int(round(duration * frequency))
    if intervals < 1 or not np.isclose(intervals / frequency, duration, atol=1e-12):
        raise ValueError("Duration times sample frequency must be a positive integer.")

    times = np.linspace(0.0, duration, intervals + 1, dtype=np.float64)
    progresses = np.array(
        [minimum_jerk_progress(float(value / duration)) for value in times],
        dtype=np.float64,
    )
    poses = np.stack(
        [interpolate_pose_v190(start_pose, target_pose, float(value)) for value in progresses]
    )
    body_yaws = float(start_body_yaw) + (
        float(target_body_yaw) - float(start_body_yaw)
    ) * progresses
    return {
        "duration_s": duration,
        "sample_hz": frequency,
        "sample_count_including_endpoint": len(times),
        "times_s": times,
        "progress": progresses,
        "poses": poses,
        "body_yaws_rad": body_yaws,
        "grid_semantics": (
            "inclusive ideal grid for continuous-path envelope; live daemon writes occur "
            "at runtime-dependent wall-clock instants while t < duration"
        ),
    }


def analyze_joint_margins(
    leg: Mapping[str, Any],
    *,
    inverse_kinematics: Callable[[np.ndarray, float], Sequence[float]],
    joint_bounds_rad: Mapping[str, tuple[float, float]],
) -> dict[str, Any]:
    """Evaluate IK along a reconstructed leg and report signed limit margins."""

    missing = [name for name in JOINT_NAMES if name not in joint_bounds_rad]
    if missing:
        raise ValueError("Missing joint bounds: " + ", ".join(missing))
    poses = np.asarray(leg["poses"], dtype=np.float64)
    body_yaws = np.asarray(leg["body_yaws_rad"], dtype=np.float64)
    times = np.asarray(leg["times_s"], dtype=np.float64)
    if poses.ndim != 3 or poses.shape[1:] != (4, 4) or len(poses) != len(body_yaws):
        raise ValueError("Leg arrays are inconsistent.")

    joint_rows: list[np.ndarray] = []
    for pose, body_yaw in zip(poses, body_yaws):
        row = np.asarray(inverse_kinematics(pose, float(body_yaw)), dtype=np.float64)
        if row.shape != (7,) or not np.isfinite(row).all():
            raise ValueError("Inverse kinematics must return seven finite joints.")
        joint_rows.append(row)
    joints = np.stack(joint_rows)

    per_joint: dict[str, Any] = {}
    global_margin = float("inf")
    global_joint = ""
    global_index = -1
    for column, name in enumerate(JOINT_NAMES):
        lower, upper = map(float, joint_bounds_rad[name])
        if not lower < upper:
            raise ValueError(f"Invalid bounds for {name}.")
        lower_margins = joints[:, column] - lower
        upper_margins = upper - joints[:, column]
        margins = np.minimum(lower_margins, upper_margins)
        index = int(np.argmin(margins))
        margin = float(margins[index])
        side = "lower" if lower_margins[index] <= upper_margins[index] else "upper"
        per_joint[name] = {
            "minimum_margin_rad": margin,
            "minimum_margin_deg": float(np.degrees(margin)),
            "limiting_side": side,
            "sample_index": index,
            "time_s": float(times[index]),
            "joint_position_rad": float(joints[index, column]),
            "joint_position_deg": float(np.degrees(joints[index, column])),
            "lower_bound_deg": float(np.degrees(lower)),
            "upper_bound_deg": float(np.degrees(upper)),
        }
        if margin < global_margin:
            global_margin = margin
            global_joint = name
            global_index = index

    return {
        "within_all_supplied_joint_bounds": bool(global_margin >= 0.0),
        "minimum_margin_rad": global_margin,
        "minimum_margin_deg": float(np.degrees(global_margin)),
        "limiting_joint": global_joint,
        "limiting_sample_index": global_index,
        "limiting_time_s": float(times[global_index]),
        "per_joint": per_joint,
        "joint_positions_rad": joints,
        "epistemic_boundary": (
            "geometric IK/configured-limit analysis only; not collision, load, tracking, "
            "thermal, cable-routing, timing, or physical-safety validation"
        ),
    }
