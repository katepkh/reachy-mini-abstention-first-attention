"""Receive-only continuous present/target state tracing for a future successor.

The only live transport in this module is the daemon's read-only full-state
WebSocket.  The client never sends an application message and exposes no robot
command method.  Released daemon 1.9.0 drops target fields from ``FullState``;
the parser therefore fails closed until a separately reviewed observability
repair is present.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from websockets.sync.client import connect

from .config import REACHY_PORT
from .safety import rigid_pose, validate_host


SCHEMA_VERSION = "reachy-stage4a-receive-only-present-target-trace-v2"
MAX_CAPTURE_DURATION_S = 30.0
MAX_REQUESTED_FREQUENCY_HZ = 50.0
TARGET_REQUIREMENTS = {
    "ALLOW_UNSET",
    "DEFINED_AT_LEAST_ONCE",
    "UNSET_TO_DEFINED",
}
TARGET_FIELDS = (
    "target_head_pose",
    "target_head_joints",
    "target_body_yaw",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _matrix_pose(value: object, field: str) -> list[list[float]]:
    raw: object
    if isinstance(value, Mapping) and "m" in value:
        raw = value["m"]
    else:
        raw = value
    try:
        array = np.asarray(raw, dtype=np.float64)
        if array.shape == (16,):
            array = array.reshape(4, 4)
        return rigid_pose(array).tolist()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"INVALID_{field.upper()}") from exc


def _joint_vector(value: object, field: str) -> list[float]:
    try:
        array = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"INVALID_{field.upper()}") from exc
    if array.shape != (7,) or not np.isfinite(array).all():
        raise ValueError(f"INVALID_{field.upper()}")
    return array.tolist()


def _target_state(payload: Mapping[str, Any]) -> str:
    """Classify explicit target absence without inferring a replacement target."""

    missing = [field for field in TARGET_FIELDS if field not in payload]
    if missing:
        raise ValueError("TARGET_FIELDS_ABSENT:" + ",".join(missing))
    null_fields = [field for field in TARGET_FIELDS if payload[field] is None]
    if len(null_fields) == len(TARGET_FIELDS):
        return "UNSET"
    if null_fields:
        raise ValueError("INCONSISTENT_TARGET_STATE:" + ",".join(null_fields))
    return "DEFINED"


def parse_full_state_frame(
    raw: str | bytes | Mapping[str, Any],
    *,
    received_monotonic_s: float,
    received_at_utc: str,
) -> dict[str, Any]:
    """Validate one patched 1.9.0 full-state frame without inferring targets."""

    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("INVALID_FULL_STATE_JSON") from exc
    elif isinstance(raw, Mapping):
        payload = dict(raw)
    else:
        raise ValueError("INVALID_FULL_STATE_PAYLOAD")

    target_state = _target_state(payload)
    for field in ("head_pose", "head_joints", "body_yaw", "control_mode", "timestamp"):
        if payload.get(field) is None:
            raise ValueError(f"PRESENT_STATE_UNAVAILABLE:{field}")

    try:
        body_yaw = float(payload["body_yaw"])
    except (TypeError, ValueError) as exc:
        raise ValueError("INVALID_BODY_YAW") from exc
    if not np.isfinite(body_yaw):
        raise ValueError("INVALID_BODY_YAW")

    target_head_pose: list[list[float]] | None = None
    target_head_joints: list[float] | None = None
    target_body_yaw: float | None = None
    if target_state == "DEFINED":
        try:
            target_body_yaw = float(payload["target_body_yaw"])
        except (TypeError, ValueError) as exc:
            raise ValueError("INVALID_TARGET_BODY_YAW") from exc
        if not np.isfinite(target_body_yaw):
            raise ValueError("INVALID_TARGET_BODY_YAW")
        target_head_pose = _matrix_pose(
            payload["target_head_pose"], "target_head_pose"
        )
        target_head_joints = _joint_vector(
            payload["target_head_joints"], "target_head_joints"
        )

    return {
        "received_monotonic_s": float(received_monotonic_s),
        "received_at_utc": str(received_at_utc),
        "daemon_timestamp": str(payload["timestamp"]),
        "control_mode": str(payload["control_mode"]),
        "target_state": target_state,
        "present_head_pose": _matrix_pose(payload["head_pose"], "head_pose"),
        "target_head_pose": target_head_pose,
        "present_head_joints_rad": _joint_vector(payload["head_joints"], "head_joints"),
        "target_head_joints_rad": target_head_joints,
        "present_body_yaw_rad": body_yaw,
        "target_body_yaw_rad": target_body_yaw,
    }


def _validate_target_requirement(frames: list[dict[str, Any]], requirement: str) -> None:
    requirement = str(requirement).strip().upper()
    if requirement not in TARGET_REQUIREMENTS:
        raise ValueError(f"Unknown target requirement: {requirement}")
    states = [str(frame["target_state"]) for frame in frames]
    if requirement == "DEFINED_AT_LEAST_ONCE" and "DEFINED" not in states:
        raise RuntimeError("DEFINED_TARGET_NOT_OBSERVED")
    if requirement == "UNSET_TO_DEFINED":
        if not states or states[0] != "UNSET":
            raise RuntimeError("TRACE_DID_NOT_START_WITH_UNSET_TARGET")
        first_defined = next(
            (index for index, state in enumerate(states) if state == "DEFINED"),
            None,
        )
        if first_defined is None or "UNSET" not in states[:first_defined]:
            raise RuntimeError("UNSET_TO_DEFINED_TRANSITION_NOT_OBSERVED")


def build_receive_only_url(host: str, frequency_hz: float) -> str:
    host = validate_host(host)
    frequency = float(frequency_hz)
    if not 1.0 <= frequency <= MAX_REQUESTED_FREQUENCY_HZ:
        raise ValueError(
            f"Requested frequency must be in [1, {MAX_REQUESTED_FREQUENCY_HZ}] Hz."
        )
    query = urllib.parse.urlencode(
        {
            "frequency": frequency,
            "with_control_mode": "true",
            "with_head_pose": "true",
            "with_target_head_pose": "true",
            "with_head_joints": "true",
            "with_target_head_joints": "true",
            "with_body_yaw": "true",
            "with_target_body_yaw": "true",
            "with_antenna_positions": "false",
            "with_target_antenna_positions": "false",
            "with_passive_joints": "false",
            "with_doa": "false",
            "use_pose_matrix": "true",
        }
    )
    return f"ws://{host}:{REACHY_PORT}/api/state/ws/full?{query}"


def _write_immutable(path: Path, payload: dict[str, Any]) -> str:
    destination = path.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    digest = hashlib.sha256(encoded).hexdigest()
    sidecar = destination.with_suffix(destination.suffix + ".sha256")
    with destination.open("xb") as stream:
        stream.write(encoded)
    try:
        with sidecar.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(f"{digest}  {destination.name}\n")
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return digest


def capture_receive_only_trace(
    host: str,
    *,
    duration_s: float,
    frequency_hz: float,
    output: Path,
    target_requirement: str = "ALLOW_UNSET",
    connector: Callable[..., Any] = connect,
    monotonic: Callable[[], float] = time.monotonic,
) -> tuple[dict[str, Any], str]:
    """Capture a bounded stream and write it once; send zero app messages."""

    duration = float(duration_s)
    if not 0.0 < duration <= MAX_CAPTURE_DURATION_S:
        raise ValueError(f"Capture duration must be in (0, {MAX_CAPTURE_DURATION_S}] seconds.")
    url = build_receive_only_url(host, frequency_hz)
    started_monotonic = monotonic()
    deadline = started_monotonic + duration
    frames: list[dict[str, Any]] = []
    with connector(url, open_timeout=5.0, close_timeout=2.0) as websocket:
        while True:
            now = monotonic()
            if now >= deadline:
                break
            remaining = deadline - now
            try:
                raw = websocket.recv(timeout=max(0.001, min(1.0, remaining)))
            except TimeoutError:
                # The last receive is deliberately bounded by the capture
                # deadline.  If that deadline elapsed while waiting for the
                # next frame, completion is normal; an earlier timeout remains
                # a transport failure and must still fail closed.
                if monotonic() >= deadline:
                    break
                raise
            frames.append(
                parse_full_state_frame(
                    raw,
                    received_monotonic_s=monotonic(),
                    received_at_utc=_utc_now(),
                )
            )
    if len(frames) < 2:
        raise RuntimeError("TRACE_TOO_SHORT")
    if any(
        later["received_monotonic_s"] < earlier["received_monotonic_s"]
        for earlier, later in zip(frames, frames[1:])
    ):
        raise RuntimeError("NON_MONOTONIC_RECEIVE_CLOCK")

    requirement = str(target_requirement).strip().upper()
    _validate_target_requirement(frames, requirement)
    target_states = [str(frame["target_state"]) for frame in frames]
    target_state_counts = {
        state: target_states.count(state) for state in ("UNSET", "DEFINED")
    }
    target_transitions = [
        {
            "frame_index": index,
            "from": previous,
            "to": current,
        }
        for index, (previous, current) in enumerate(
            zip(target_states, target_states[1:]), start=1
        )
        if previous != current
    ]

    report = {
        "schema": SCHEMA_VERSION,
        "status": "RECEIVE_ONLY_CAPTURE",
        "started_at_utc": frames[0]["received_at_utc"],
        "completed_at_utc": frames[-1]["received_at_utc"],
        "requested_duration_s": duration,
        "requested_frequency_hz": float(frequency_hz),
        "frame_count": len(frames),
        "target_requirement": requirement,
        "target_state_counts": target_state_counts,
        "target_state_transitions": target_transitions,
        "target_inference_performed": False,
        "endpoint": url,
        "frames": frames,
        "transport": {
            "websocket_handshake": 1,
            "client_application_messages_sent": 0,
            "http_mutations": 0,
            "robot_commands_authorized": 0,
            "robot_commands_sent": 0,
        },
    }
    return report, _write_immutable(output, report)
