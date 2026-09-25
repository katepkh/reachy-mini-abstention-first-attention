"""Pure health gate for stock and temporary Reachy Mini 1.9.0 daemons.

The released robot backend updates an internal ready event and ``last_alive``
clock but never copies either value into the serialized ``RobotBackendStatus``.
For exact v1.9.0, this gate therefore uses two advancing full-state samples and
the published control-loop statistics.  It opens no transport and sends no
command.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
import math
from typing import Any


SCHEMA_VERSION = "reachy-stage4a-observation-health-v1"
EXACT_DAEMON_VERSION = "1.9.0"
CONTEXTS = {
    "STOCK_BASELINE",
    "TEMPORARY_OBSERVATION",
    "STOCK_RESTORED",
}
MIN_CONTROL_LOOP_HZ = 40.0
MAX_CONTROL_LOOP_HZ = 60.0
MAX_CONTROL_LOOP_INTERVAL_S = 0.1


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _finite_number(value: object) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _finite_sequence(value: object, length: int) -> bool:
    return (
        isinstance(value, Sequence)
        and not isinstance(value, (str, bytes, bytearray))
        and len(value) == length
        and all(_finite_number(item) for item in value)
    )


def _pose_is_finite(value: object) -> bool:
    if isinstance(value, Mapping):
        value = value.get("m")
    if _finite_sequence(value, 16):
        return True
    return (
        isinstance(value, Sequence)
        and not isinstance(value, (str, bytes, bytearray))
        and len(value) == 4
        and all(_finite_sequence(row, 4) for row in value)
    )


def evaluate_observation_health(
    *,
    context: str,
    status_before: Mapping[str, Any],
    state_before: Mapping[str, Any],
    status_after: Mapping[str, Any],
    state_after: Mapping[str, Any],
    app_lock: Mapping[str, Any],
    current_app: object,
    required_motor_mode: str | None,
) -> dict[str, Any]:
    """Evaluate two read-only samples and return stable fail-closed reasons."""

    context = str(context).strip().upper()
    if context not in CONTEXTS:
        raise ValueError(f"Unknown observation health context: {context}")
    required_mode = (
        None if required_motor_mode is None else str(required_motor_mode).strip().lower()
    )
    if required_mode not in {None, "enabled", "disabled"}:
        raise ValueError(f"Unknown required motor mode: {required_motor_mode}")

    reasons: list[str] = []
    backend_before = status_before.get("backend_status") or {}
    backend_after = status_after.get("backend_status") or {}
    if not isinstance(backend_before, Mapping) or not isinstance(backend_after, Mapping):
        reasons.append("BACKEND_STATUS_UNAVAILABLE")
        backend_before = {}
        backend_after = {}

    version = status_after.get("version")
    if version != EXACT_DAEMON_VERSION:
        reasons.append("DAEMON_VERSION_MISMATCH")
    if status_before.get("version") != version:
        reasons.append("DAEMON_VERSION_CHANGED_DURING_PROBE")
    if status_after.get("state") != "running":
        reasons.append("DAEMON_NOT_RUNNING")
    if status_after.get("error") is not None:
        reasons.append("DAEMON_ERROR_PRESENT")
    if backend_after.get("error") is not None:
        reasons.append("BACKEND_ERROR_PRESENT")

    expected_wireless = context != "TEMPORARY_OBSERVATION"
    expected_no_media = context == "TEMPORARY_OBSERVATION"
    if status_after.get("wireless_version") is not expected_wireless:
        reasons.append("WIRELESS_MODE_MISMATCH")
    if status_after.get("no_media") is not expected_no_media:
        reasons.append("MEDIA_MODE_MISMATCH")

    before_time = _timestamp(state_before.get("timestamp"))
    after_time = _timestamp(state_after.get("timestamp"))
    if before_time is None or after_time is None:
        reasons.append("STATE_TIMESTAMP_INVALID")
    elif after_time <= before_time:
        reasons.append("STATE_TIMESTAMP_NOT_ADVANCING")

    control_mode = state_after.get("control_mode")
    backend_mode = backend_after.get("motor_control_mode")
    if control_mode not in {"enabled", "disabled"}:
        reasons.append("STATE_MOTOR_MODE_UNKNOWN")
    if backend_mode not in {"enabled", "disabled"}:
        reasons.append("BACKEND_MOTOR_MODE_UNKNOWN")
    if control_mode != backend_mode:
        reasons.append("MOTOR_MODE_DISAGREEMENT")
    if required_mode is not None and control_mode != required_mode:
        reasons.append("REQUIRED_MOTOR_MODE_NOT_MET")

    if not _pose_is_finite(state_after.get("head_pose")):
        reasons.append("HEAD_POSE_INVALID")
    if not _finite_sequence(state_after.get("head_joints"), 7):
        reasons.append("HEAD_JOINTS_INVALID")
    if not _finite_number(state_after.get("body_yaw")):
        reasons.append("BODY_YAW_INVALID")

    stats = backend_after.get("control_loop_stats") or {}
    if not isinstance(stats, Mapping):
        stats = {}
    frequency = stats.get("mean_control_loop_frequency")
    maximum_interval = stats.get("max_control_loop_interval")
    error_count = stats.get("nb_error")
    if not _finite_number(frequency) or not (
        MIN_CONTROL_LOOP_HZ <= float(frequency) <= MAX_CONTROL_LOOP_HZ
    ):
        reasons.append("CONTROL_LOOP_FREQUENCY_OUT_OF_RANGE")
    if not _finite_number(maximum_interval) or float(maximum_interval) > MAX_CONTROL_LOOP_INTERVAL_S:
        reasons.append("CONTROL_LOOP_INTERVAL_TOO_LARGE")
    if isinstance(error_count, bool) or not isinstance(error_count, int) or error_count != 0:
        reasons.append("CONTROL_LOOP_ERRORS_PRESENT")

    if app_lock.get("state") != "free" or app_lock.get("holder_name") is not None:
        reasons.append("ROBOT_APP_LOCK_NOT_FREE")
    if current_app is not None:
        reasons.append("APPLICATION_ACTIVE")

    return {
        "schema": SCHEMA_VERSION,
        "context": context,
        "accepted": not reasons,
        "reasons": reasons,
        "evidence": {
            "daemon_version": version,
            "daemon_state": status_after.get("state"),
            "wireless_version": status_after.get("wireless_version"),
            "no_media": status_after.get("no_media"),
            "state_timestamp_before": state_before.get("timestamp"),
            "state_timestamp_after": state_after.get("timestamp"),
            "state_timestamp_advanced": (
                before_time is not None
                and after_time is not None
                and after_time > before_time
            ),
            "state_motor_mode": control_mode,
            "backend_motor_mode": backend_mode,
            "control_loop_frequency_hz": frequency,
            "control_loop_max_interval_s": maximum_interval,
            "control_loop_error_count": error_count,
            "serialized_backend_ready_observed": backend_after.get("ready"),
            "serialized_last_alive_observed": backend_after.get("last_alive"),
            "serialized_ready_and_last_alive_excluded_for_exact_v1_9_0": True,
            "robot_app_lock_state": app_lock.get("state"),
            "current_app": current_app,
        },
        "robot_connections": 0,
        "robot_commands_authorized": 0,
        "robot_commands_sent": 0,
    }
