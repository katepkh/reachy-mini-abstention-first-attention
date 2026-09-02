"""Command-free diagnosis of Reachy Mini's measured neutral head pose.

This module deliberately uses only HTTP GET and a server-to-client state
WebSocket.  It does not import the command-capable Stage 4 runtime adapter and
contains no motor, homing, torque, target, or movement operation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlencode

import numpy as np
import requests
from websockets.sync.client import connect as websocket_connect

from .config import OFFICIAL_PROTOCOL_VERSION, PROJECT_ROOT, REACHY_HOST, REACHY_PORT
from .safety import as_pose, rotation_distance_deg, translation_distance_mm, validate_host


SCHEMA_VERSION = "reachy-stage4-neutral-diagnostic-v2"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data/private/stage4a_neutral_diagnostic_v2"
STARTUP_KINDS = ("not_a_startup_capture", "physical_power_cycle", "daemon_restart", "unknown")
OBSERVATION_VALUES = ("yes", "no", "unknown")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def matrix_pose(payload: Mapping[str, Any] | list[float]) -> np.ndarray:
    """Parse the daemon's matrix pose representation without repairing it."""

    values: Any = payload.get("m") if isinstance(payload, Mapping) else payload
    array = np.asarray(values, dtype=np.float64)
    if array.size != 16:
        raise ValueError("Expected exactly 16 values in the daemon matrix pose.")
    return as_pose(array.reshape(4, 4))


def xyzrpy_pose(payload: Mapping[str, Any]) -> np.ndarray:
    """Reconstruct the daemon's documented xyz + extrinsic-xyz RPY pose."""

    required = ("x", "y", "z", "roll", "pitch", "yaw")
    if any(name not in payload for name in required):
        raise ValueError("The daemon xyz/rpy pose is incomplete.")
    x, y, z, roll, pitch, yaw = (float(payload[name]) for name in required)
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    # scipy Rotation.from_euler("xyz", ...), used by daemon 1.9.0,
    # produces Rz(yaw) @ Ry(pitch) @ Rx(roll).
    rotation = np.array(
        [
            [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
            [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
            [-sp, cp * sr, cp * cr],
        ],
        dtype=np.float64,
    )
    pose = np.eye(4, dtype=np.float64)
    pose[:3, :3] = rotation
    pose[:3, 3] = [x, y, z]
    return as_pose(pose)


def euler_xyz(pose: np.ndarray) -> tuple[float, float, float]:
    """Return roll, pitch, yaw matching scipy's non-singular xyz convention."""

    rotation = as_pose(pose)[:3, :3]
    pitch = math.asin(max(-1.0, min(1.0, -float(rotation[2, 0]))))
    if abs(math.cos(pitch)) > 1e-9:
        roll = math.atan2(float(rotation[2, 1]), float(rotation[2, 2]))
        yaw = math.atan2(float(rotation[1, 0]), float(rotation[0, 0]))
    else:
        roll = 0.0
        yaw = math.atan2(-float(rotation[0, 1]), float(rotation[1, 1]))
    return roll, pitch, yaw


def pose_summary(pose: np.ndarray) -> dict[str, Any]:
    checked = as_pose(pose)
    roll, pitch, yaw = euler_xyz(checked)
    identity = np.eye(4, dtype=np.float64)
    return {
        "matrix_row_major": checked.reshape(-1).tolist(),
        "translation_m": checked[:3, 3].tolist(),
        "rpy_rad": {"roll": roll, "pitch": pitch, "yaw": yaw},
        "rpy_deg": {
            "roll": math.degrees(roll),
            "pitch": math.degrees(pitch),
            "yaw": math.degrees(yaw),
        },
        "rotation_from_identity_deg": rotation_distance_deg(identity, checked),
        "translation_from_identity_mm": translation_distance_mm(identity, checked),
        "rotation_determinant": float(np.linalg.det(checked[:3, :3])),
        "orthogonality_residual": float(
            np.linalg.norm(checked[:3, :3].T @ checked[:3, :3] - np.eye(3))
        ),
    }


def normalize_startup_context(value: Mapping[str, Any] | None) -> dict[str, Any]:
    """Validate operator-recorded startup context without treating it as telemetry."""

    raw = dict(value or {})
    startup_kind = str(raw.get("startup_kind", "not_a_startup_capture"))
    if startup_kind not in STARTUP_KINDS:
        raise ValueError(f"startup_kind must be one of {STARTUP_KINDS}.")
    normalized: dict[str, Any] = {"startup_kind": startup_kind}
    index = raw.get("startup_index")
    if index is not None:
        index = int(index)
        if index < 1:
            raise ValueError("startup_index must be positive when provided.")
    normalized["startup_index"] = index
    age = raw.get("startup_age_seconds")
    if age is not None:
        age = float(age)
        if age < 0:
            raise ValueError("startup_age_seconds must be non-negative when provided.")
    normalized["startup_age_seconds"] = age
    for field in (
        "wake_animation_observed",
        "startup_app_observed",
        "controller_touched_since_start",
    ):
        observation = str(raw.get(field, "unknown"))
        if observation not in OBSERVATION_VALUES:
            raise ValueError(f"{field} must be one of {OBSERVATION_VALUES}.")
        normalized[field] = observation
    normalized["operator_notes"] = raw.get("operator_notes")
    normalized["epistemic_status"] = (
        "operator-reported context; not independently verified robot telemetry"
    )
    return normalized


class ReadOnlyReachyState:
    """Narrow transport surface: HTTP GET plus receive-only state streaming."""

    def __init__(
        self,
        host: str = REACHY_HOST,
        port: int = REACHY_PORT,
        *,
        timeout_s: float = 3.0,
        session: Any | None = None,
        websocket_factory: Callable[..., Any] = websocket_connect,
    ) -> None:
        self.host = validate_host(host)
        self.port = int(port)
        self.timeout_s = float(timeout_s)
        self.session = session if session is not None else requests.Session()
        self.websocket_factory = websocket_factory
        self.http_gets = 0
        self.websocket_messages_received = 0

    def get_json(self, path: str, *, params: Mapping[str, Any] | None = None) -> Any:
        if not path.startswith("/api/"):
            raise ValueError("Read-only diagnostic paths must remain under /api/.")
        response = self.session.get(
            f"http://{self.host}:{self.port}{path}",
            params=dict(params or {}),
            timeout=self.timeout_s,
        )
        self.http_gets += 1
        response.raise_for_status()
        return response.json()

    def daemon_status(self) -> Mapping[str, Any]:
        value = self.get_json("/api/daemon/status")
        if not isinstance(value, Mapping):
            raise ValueError("Daemon status was not a JSON object.")
        return value

    def present_pose(self, *, matrix: bool) -> Mapping[str, Any]:
        value = self.get_json(
            "/api/state/present_head_pose",
            params={"use_pose_matrix": str(matrix).lower()},
        )
        if not isinstance(value, Mapping):
            raise ValueError("Present head pose was not a JSON object.")
        return value

    def app_context(self) -> dict[str, Any]:
        """Read configured and currently running app state without changing it."""

        configured = self.get_json("/api/apps/startup-app")
        current = self.get_json("/api/apps/current-app-status")
        if not isinstance(configured, Mapping):
            raise ValueError("Configured startup-app state was not a JSON object.")
        if current is not None and not isinstance(current, Mapping):
            raise ValueError("Current app status was neither null nor a JSON object.")
        return {
            "configured_startup_app": configured.get("startup_app"),
            "current_app_status": None if current is None else dict(current),
        }

    def stream_frames(self, *, frame_count: int, frequency_hz: float) -> list[Mapping[str, Any]]:
        if not 1 <= int(frame_count) <= 200:
            raise ValueError("frame_count must be between 1 and 200.")
        if not 1.0 <= float(frequency_hz) <= 20.0:
            raise ValueError("frequency_hz must be between 1 and 20.")
        params = urlencode(
            {
                "frequency": float(frequency_hz),
                "with_head_pose": "true",
                "use_pose_matrix": "true",
                "with_head_joints": "true",
                "with_body_yaw": "true",
                "with_antenna_positions": "true",
                "with_passive_joints": "false",
                "with_doa": "false",
            }
        )
        url = f"ws://{self.host}:{self.port}/api/state/ws/full?{params}"
        frames: list[Mapping[str, Any]] = []
        with self.websocket_factory(url, open_timeout=self.timeout_s) as socket:
            for _ in range(int(frame_count)):
                raw = socket.recv(timeout=self.timeout_s)
                self.websocket_messages_received += 1
                value = json.loads(raw)
                if not isinstance(value, Mapping):
                    raise ValueError("State-stream frame was not a JSON object.")
                frames.append(value)
        return frames


def _clean_status(status: Mapping[str, Any]) -> dict[str, Any]:
    backend = status.get("backend_status")
    backend_status = dict(backend) if isinstance(backend, Mapping) else backend
    return {
        "state": status.get("state"),
        "version": status.get("version"),
        "robot_name": status.get("robot_name"),
        "simulation_enabled": status.get("simulation_enabled"),
        "mockup_sim_enabled": status.get("mockup_sim_enabled"),
        "backend_status": backend_status,
        "error": status.get("error"),
    }


def capture_neutral_diagnostic(
    client: ReadOnlyReachyState,
    *,
    frame_count: int = 20,
    frequency_hz: float = 10.0,
    label: str = "read_only_neutral_observation",
    controller_display_observation: str | None = None,
    startup_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Capture independent measured-pose representations without commanding Reachy."""

    started_at = utc_now()
    status_before = client.daemon_status()
    version = str(status_before.get("version"))
    if version != OFFICIAL_PROTOCOL_VERSION:
        raise RuntimeError(
            f"Expected daemon {OFFICIAL_PROTOCOL_VERSION}, received {version}; no capture made."
        )
    app_context = client.app_context()

    rest_matrix_before_raw = client.present_pose(matrix=True)
    rest_euler_before_raw = client.present_pose(matrix=False)
    stream_raw = client.stream_frames(frame_count=frame_count, frequency_hz=frequency_hz)
    rest_matrix_after_raw = client.present_pose(matrix=True)
    rest_euler_after_raw = client.present_pose(matrix=False)
    status_after = client.daemon_status()

    rest_matrix_before = matrix_pose(rest_matrix_before_raw)
    rest_euler_before = xyzrpy_pose(rest_euler_before_raw)
    rest_matrix_after = matrix_pose(rest_matrix_after_raw)
    rest_euler_after = xyzrpy_pose(rest_euler_after_raw)

    frames: list[dict[str, Any]] = []
    frame_poses: list[np.ndarray] = []
    for index, frame in enumerate(stream_raw):
        raw_pose = frame.get("head_pose")
        if not isinstance(raw_pose, (Mapping, list)):
            raise ValueError("State-stream frame omitted its matrix head pose.")
        pose = matrix_pose(raw_pose)
        frame_poses.append(pose)
        frames.append(
            {
                "index": index,
                "daemon_timestamp": frame.get("timestamp"),
                "control_mode": frame.get("control_mode"),
                "head_pose": pose_summary(pose),
                "head_joints_rad": frame.get("head_joints"),
                "body_yaw_rad": frame.get("body_yaw"),
                "antennas_position_rad": frame.get("antennas_position"),
            }
        )

    identity_errors = [
        rotation_distance_deg(np.eye(4, dtype=np.float64), pose) for pose in frame_poses
    ]
    first_pose = frame_poses[0]
    stream_drift = [rotation_distance_deg(first_pose, pose) for pose in frame_poses]
    matrix_euler_before_gap = rotation_distance_deg(rest_matrix_before, rest_euler_before)
    matrix_euler_after_gap = rotation_distance_deg(rest_matrix_after, rest_euler_after)

    return {
        "schema": SCHEMA_VERSION,
        "label": str(label),
        "started_at_utc": started_at,
        "completed_at_utc": utc_now(),
        "endpoint": {"host": client.host, "port": client.port},
        "requested": {"frame_count": int(frame_count), "frequency_hz": float(frequency_hz)},
        "operator_annotation": {
            "controller_display_observation": controller_display_observation,
            "startup_context": normalize_startup_context(startup_context),
            "epistemic_status": "operator-reported rounded UI text; not robot telemetry",
        },
        "transport_audit": {
            "http_methods": ["GET"],
            "websocket_endpoint": "/api/state/ws/full",
            "websocket_direction": "server_to_client_only",
            "http_gets": client.http_gets,
            "websocket_messages_received": client.websocket_messages_received,
            "websocket_messages_sent": 0,
            "robot_commands_sent": 0,
            "motor_mode_writes": 0,
            "media_requests": 0,
        },
        "daemon_status_before": _clean_status(status_before),
        "daemon_status_after": _clean_status(status_after),
        "app_context": app_context,
        "rest_observations": {
            "matrix_before": pose_summary(rest_matrix_before),
            "euler_before": {
                "raw": dict(rest_euler_before_raw),
                "reconstructed_pose": pose_summary(rest_euler_before),
            },
            "matrix_after": pose_summary(rest_matrix_after),
            "euler_after": {
                "raw": dict(rest_euler_after_raw),
                "reconstructed_pose": pose_summary(rest_euler_after),
            },
        },
        "stream_frames": frames,
        "summary": {
            "stream_rotation_from_identity_deg": {
                "minimum": min(identity_errors),
                "mean": float(np.mean(identity_errors)),
                "maximum": max(identity_errors),
            },
            "stream_rotation_drift_from_first_deg": {
                "mean": float(np.mean(stream_drift)),
                "maximum": max(stream_drift),
            },
            "rest_matrix_vs_euler_rotation_gap_deg": {
                "before": matrix_euler_before_gap,
                "after": matrix_euler_after_gap,
            },
            "rest_matrix_before_vs_after_rotation_gap_deg": rotation_distance_deg(
                rest_matrix_before, rest_matrix_after
            ),
            "rest_matrix_before_vs_after_translation_gap_mm": translation_distance_mm(
                rest_matrix_before, rest_matrix_after
            ),
        },
    }


def write_immutable_capture(record: Mapping[str, Any], output: Path) -> tuple[Path, Path, str]:
    """Write one canonical JSON record and SHA-256 sidecar without overwriting."""

    path = output.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(record, indent=2, sort_keys=True) + "\n").encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    checksum_path = path.with_suffix(path.suffix + ".sha256")
    with path.open("xb") as stream:
        stream.write(payload)
    try:
        with checksum_path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(f"{digest}  {path.name}\n")
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return path, checksum_path, digest


def _default_output(label: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    safe_label = "".join(character if character.isalnum() or character in "-_" else "_" for character in label)
    return DEFAULT_OUTPUT_DIR / f"{timestamp}_{safe_label}.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=20)
    parser.add_argument("--frequency", type=float, default=10.0)
    parser.add_argument("--label", default="read_only_neutral_observation")
    parser.add_argument("--controller-display-observation")
    parser.add_argument("--startup-kind", choices=STARTUP_KINDS, default="not_a_startup_capture")
    parser.add_argument("--startup-index", type=int)
    parser.add_argument("--startup-age-seconds", type=float)
    parser.add_argument("--wake-animation-observed", choices=OBSERVATION_VALUES, default="unknown")
    parser.add_argument("--startup-app-observed", choices=OBSERVATION_VALUES, default="unknown")
    parser.add_argument("--controller-touched-since-start", choices=OBSERVATION_VALUES, default="unknown")
    parser.add_argument("--operator-notes")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    output = args.output or _default_output(args.label)
    client = ReadOnlyReachyState()
    try:
        record = capture_neutral_diagnostic(
            client,
            frame_count=args.frames,
            frequency_hz=args.frequency,
            label=args.label,
            controller_display_observation=args.controller_display_observation,
            startup_context={
                "startup_kind": args.startup_kind,
                "startup_index": args.startup_index,
                "startup_age_seconds": args.startup_age_seconds,
                "wake_animation_observed": args.wake_animation_observed,
                "startup_app_observed": args.startup_app_observed,
                "controller_touched_since_start": args.controller_touched_since_start,
                "operator_notes": args.operator_notes,
            },
        )
    except (requests.RequestException, TimeoutError, OSError) as exc:
        print(
            "Read-only diagnostic could not reach or finish reading Reachy; "
            f"no capture was written ({type(exc).__name__}: {exc}).",
            file=sys.stderr,
        )
        print("Robot commands sent: 0", file=sys.stderr)
        return 2
    path, checksum_path, digest = write_immutable_capture(record, output)
    summary = record["summary"]
    print(f"Read-only capture: {path}")
    print(f"SHA-256: {digest} ({checksum_path.name})")
    print(
        "Measured stream rotation from identity: "
        f"{summary['stream_rotation_from_identity_deg']['mean']:.6f} deg mean "
        f"({summary['stream_rotation_from_identity_deg']['minimum']:.6f}.."
        f"{summary['stream_rotation_from_identity_deg']['maximum']:.6f})"
    )
    print("Robot commands sent: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
