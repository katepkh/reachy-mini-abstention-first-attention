"""Pure safety calculations for the Stage 4A one-shot motion envelope."""

from __future__ import annotations

import ipaddress
import math
from typing import Iterable

import numpy as np

from .config import MOVE_ANGLE_DEG, REACHY_HOST


DIRECTIONS = ("UP", "DOWN", "LEFT", "RIGHT")


def validate_host(host: str) -> str:
    value = str(host).strip()
    address = ipaddress.ip_address(value)
    if address.version != 4 or not address.is_private or value != REACHY_HOST:
        raise ValueError(f"Stage 4A is locked to the audited private Reachy address {REACHY_HOST}.")
    return value


def validate_direction(direction: str) -> str:
    value = str(direction).strip().upper()
    if value not in DIRECTIONS:
        raise ValueError(f"Direction must be one of {', '.join(DIRECTIONS)}.")
    return value


def target_point(direction: str, angle_deg: float = MOVE_ANGLE_DEG) -> tuple[float, float, float]:
    direction = validate_direction(direction)
    if not math.isclose(float(angle_deg), MOVE_ANGLE_DEG, abs_tol=1e-9):
        raise ValueError("The Stage 4A movement angle is frozen at exactly 3 degrees.")
    angle = math.radians(float(angle_deg))
    forward = math.cos(angle)
    lateral_or_vertical = math.sin(angle)
    if direction == "UP":
        return forward, 0.0, lateral_or_vertical
    if direction == "DOWN":
        return forward, 0.0, -lateral_or_vertical
    if direction == "LEFT":
        return forward, lateral_or_vertical, 0.0
    return forward, -lateral_or_vertical, 0.0


def neutral_point() -> tuple[float, float, float]:
    return 1.0, 0.0, 0.0


def look_at_world_pose(point: tuple[float, float, float]) -> np.ndarray:
    """Official 1.9.0 look-at geometry, implemented with Rodrigues' formula."""

    target = np.asarray(point, dtype=np.float64)
    norm = float(np.linalg.norm(target))
    if norm < 1e-12:
        return np.eye(4, dtype=np.float64)
    target /= norm
    forward = np.array([1.0, 0.0, 0.0], dtype=np.float64)
    axis = np.cross(forward, target)
    axis_norm = float(np.linalg.norm(axis))
    if axis_norm < 1e-8:
        if float(np.dot(forward, target)) <= 0.0:
            raise ValueError("Stage 4A never targets the singular rear direction.")
        rotation = np.eye(3, dtype=np.float64)
    else:
        axis /= axis_norm
        angle = math.acos(max(-1.0, min(1.0, float(np.dot(forward, target)))))
        x, y, z = axis
        skew = np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])
        rotation = np.eye(3) + math.sin(angle) * skew + (1.0 - math.cos(angle)) * (skew @ skew)
    pose = np.eye(4, dtype=np.float64)
    pose[:3, :3] = rotation
    return pose


def as_pose(value: Iterable[Iterable[float]] | np.ndarray) -> np.ndarray:
    pose = np.asarray(value, dtype=np.float64)
    if pose.shape != (4, 4) or not np.isfinite(pose).all():
        raise ValueError("A finite 4x4 head pose is required.")
    if not np.allclose(pose[3], [0.0, 0.0, 0.0, 1.0], atol=1e-5):
        raise ValueError("The head pose is not a homogeneous transform.")
    rotation = pose[:3, :3]
    if not np.allclose(rotation.T @ rotation, np.eye(3), atol=2e-3):
        raise ValueError("The head pose rotation is not orthonormal.")
    if not math.isclose(float(np.linalg.det(rotation)), 1.0, abs_tol=2e-3):
        raise ValueError("The head pose rotation determinant is invalid.")
    return pose


def rigid_pose(value: Iterable[Iterable[float]] | np.ndarray) -> np.ndarray:
    """Project a measured FK pose onto the nearest proper rigid transform."""

    pose = as_pose(value).copy()
    u, _, vt = np.linalg.svd(pose[:3, :3])
    rotation = u @ vt
    if float(np.linalg.det(rotation)) < 0.0:
        u[:, -1] *= -1.0
        rotation = u @ vt
    pose[:3, :3] = rotation
    return pose


def relative_target_pose(
    baseline: Iterable[Iterable[float]] | np.ndarray,
    direction: str,
) -> np.ndarray:
    """Apply the frozen 3° direction as a world-axis baseline-relative increment."""

    base = rigid_pose(baseline)
    delta = look_at_world_pose(target_point(direction))
    target = base.copy()
    target[:3, :3] = delta[:3, :3] @ base[:3, :3]
    return rigid_pose(target)


def rotation_distance_deg(first: np.ndarray, second: np.ndarray) -> float:
    a = rigid_pose(first)
    b = rigid_pose(second)
    relative = a[:3, :3].T @ b[:3, :3]
    cosine = max(-1.0, min(1.0, (float(np.trace(relative)) - 1.0) / 2.0))
    return math.degrees(math.acos(cosine))


def translation_distance_mm(first: np.ndarray, second: np.ndarray) -> float:
    a = as_pose(first)
    b = as_pose(second)
    return 1000.0 * float(np.linalg.norm(a[:3, 3] - b[:3, 3]))
