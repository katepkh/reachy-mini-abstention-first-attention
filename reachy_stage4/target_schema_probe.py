"""Isolated Pydantic reproduction of the Reachy Mini 1.9.0 target-field loss.

This is a schema-only probe. It does not import the Reachy SDK, connect to a
daemon, or expose a robot-command surface.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from pydantic import BaseModel


TARGET_FIELDS = (
    "target_head_pose",
    "target_head_joints",
    "target_body_yaw",
    "target_antennas_position",
)


class XYZRPYPoseProbe(BaseModel):
    """Minimal copy of the released xyz/RPY pose field shape."""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0


class Matrix4x4PoseProbe(BaseModel):
    """Minimal matrix pose shape needed for the serialization contract."""

    m: list[list[float]]


AnyPoseProbe = XYZRPYPoseProbe | Matrix4x4PoseProbe


class ReleasedFullStateProbe(BaseModel):
    """Relevant fields in Reachy Mini 1.9.0's released FullState."""

    head_pose: AnyPoseProbe | None = None
    head_joints: list[float] | None = None
    body_yaw: float | None = None
    antennas_position: list[float] | None = None
    timestamp: datetime | None = None


class PatchedFullStateProbe(BaseModel):
    """The same contract with the four route-produced target fields declared."""

    head_pose: AnyPoseProbe | None = None
    target_head_pose: AnyPoseProbe | None = None
    head_joints: list[float] | None = None
    target_head_joints: list[float] | None = None
    body_yaw: float | None = None
    target_body_yaw: float | None = None
    antennas_position: list[float] | None = None
    target_antennas_position: list[float] | None = None
    timestamp: datetime | None = None


def compare_schema_serialization(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Show which requested target keys survive released versus patched models."""

    released = ReleasedFullStateProbe.model_validate(dict(payload)).model_dump(
        mode="json", exclude_none=True
    )
    patched = PatchedFullStateProbe.model_validate(dict(payload)).model_dump(
        mode="json", exclude_none=True
    )
    return {
        "released_target_fields_present": sorted(set(released) & set(TARGET_FIELDS)),
        "patched_target_fields_present": sorted(set(patched) & set(TARGET_FIELDS)),
        "released_payload": released,
        "patched_payload": patched,
        "robot_commands_authorized": 0,
    }
