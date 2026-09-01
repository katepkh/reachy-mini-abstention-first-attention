"""One-shot preflight, execution and operator review for Stage 4A."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import numpy as np

from reachy_stage3p.result_freeze_cue_v1 import verify_result_freeze
from reachy_stage3v.result_freeze_v3 import verify_v3_result_freeze

from .config import (
    ARM_PHRASE,
    BASELINE_NEUTRAL_LIMIT_DEG,
    BASELINE_RECHECK_LIMIT_DEG,
    DATA_DIR,
    DWELL_S,
    MOVE_DURATION_S,
    MAX_CONTROL_LOOP_HZ,
    MAX_CONTROL_LOOP_INTERVAL_S,
    MAX_TELEMETRY_AGE_S,
    MIN_CONTROL_LOOP_HZ,
    OFFICIAL_PROTOCOL_VERSION,
    PROGRESS_PATH,
    REACHY_HOST,
    RESTORE_DURATION_S,
    RESTORE_SETTLE_S,
    RESTORE_ERROR_LIMIT_DEG,
    SESSIONS_DIR,
    SESSION_MAX_AGE_S,
    TARGET_ERROR_LIMIT_DEG,
    TRANSLATION_LIMIT_MM,
)
from .protocol import PILOT_STEPS, verify_protocol_manifest
from .runtime import ReachySdkAdapter
from .safety import (
    as_pose,
    neutral_point,
    relative_target_pose,
    rigid_pose,
    rotation_distance_deg,
    translation_distance_mm,
    validate_direction,
    validate_host,
)


AdapterFactory = Callable[[str], Any]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _integrity(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(payload)).hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _signed(payload: dict[str, Any]) -> dict[str, Any]:
    return {**payload, "integrity_sha256": _integrity(payload)}


def _verify_signed(payload: dict[str, Any]) -> dict[str, Any]:
    expected = str(payload.get("integrity_sha256") or "")
    body = {key: value for key, value in payload.items() if key != "integrity_sha256"}
    if not expected or _integrity(body) != expected:
        raise ValueError("The Stage 4A session record failed its integrity check.")
    return body


def load_progress() -> dict[str, Any]:
    if not PROGRESS_PATH.is_file():
        return {
            "schema": "reachy-stage4a-supervised-motion-progress-v2",
            "accepted_steps": 0,
            "total_steps": len(PILOT_STEPS),
            "accepted_result_files": [],
            "status": "NOT_STARTED",
        }
    return json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))


def expected_step() -> Any | None:
    accepted = int(load_progress().get("accepted_steps") or 0)
    return None if accepted >= len(PILOT_STEPS) else PILOT_STEPS[accepted]


def verify_prerequisites() -> dict[str, Any]:
    from .result_freeze_v3 import verify_result_freeze as verify_v3_diagnostic

    horizontal = verify_v3_result_freeze()
    targeted = verify_result_freeze()
    v3_diagnostic = verify_v3_diagnostic()
    protocol = verify_protocol_manifest()
    return {
        "horizontal_freeze": horizontal,
        "targeted_freeze": targeted,
        "v3_diagnostic_freeze": v3_diagnostic,
        "pilot_protocol": protocol,
    }


def _status_ready(status: dict[str, Any]) -> bool:
    try:
        frequency = float(status["control_loop_frequency_hz"])
        maximum_interval = float(status["control_loop_max_interval_s"])
        error_count = int(status["control_loop_error_count"])
        head_pose_age = float(status["head_pose_age_s"])
        daemon_status_age = float(status["daemon_status_age_s"])
    except (KeyError, TypeError, ValueError):
        return False
    return (
        status.get("state") == "running"
        and status.get("motor_control_mode") == "enabled"
        and status.get("daemon_version") == OFFICIAL_PROTOCOL_VERSION
        and not status.get("error")
        and status.get("simulation_enabled") is not True
        and status.get("mockup_sim_enabled") is not True
        and MIN_CONTROL_LOOP_HZ <= frequency <= MAX_CONTROL_LOOP_HZ
        and 0.0 < maximum_interval <= MAX_CONTROL_LOOP_INTERVAL_S
        and error_count == 0
        and bool(status.get("motor_controller_status"))
        and 0.0 <= head_pose_age <= MAX_TELEMETRY_AGE_S
        and 0.0 <= daemon_status_age <= MAX_TELEMETRY_AGE_S
    )


def run_preflight(
    host: str = REACHY_HOST,
    *,
    adapter_factory: AdapterFactory = ReachySdkAdapter,
) -> dict[str, Any]:
    host = validate_host(host)
    prerequisites = verify_prerequisites()
    step = expected_step()
    if step is None:
        raise ValueError("All four Stage 4A directions are already accepted.")
    adapter = adapter_factory(host)
    try:
        status = adapter.status()
        if not _status_ready(status):
            raise RuntimeError(f"Reachy is not ready for the pilot: {status}")
        baseline = as_pose(adapter.current_pose())
        neutral = as_pose(adapter.target_pose(neutral_point()))
        neutral_error = rotation_distance_deg(baseline, neutral)
        neutral_translation = translation_distance_mm(baseline, neutral)
        if neutral_error > BASELINE_NEUTRAL_LIMIT_DEG:
            raise RuntimeError(
                f"Reachy's head is {neutral_error:.2f}° from neutral; centre it in Reachy Mini Control first."
            )
        if neutral_translation > TRANSLATION_LIMIT_MM:
            raise RuntimeError(
                f"Reachy's start pose translation differs from neutral by {neutral_translation:.2f} mm."
            )
    finally:
        adapter.disconnect()

    session_id = uuid4().hex
    body = {
        "schema": "reachy-stage4a-preflight-session-v2",
        "session_id": session_id,
        "created_time_iso": _utc_now(),
        "created_unix_s": time.time(),
        "host": host,
        "step_index": step.index,
        "direction": step.direction,
        "baseline_pose": baseline.tolist(),
        "baseline_neutral_error_deg": neutral_error,
        "baseline_neutral_translation_mm": neutral_translation,
        "status": status,
        "prerequisites": prerequisites,
        "protocol_fingerprint": prerequisites["pilot_protocol"]["fingerprint"],
        "robot_commands": 0,
        "media_access": 0,
        "cloud_requests": 0,
    }
    session_path = SESSIONS_DIR / f"{session_id}_preflight.json"
    _write_json(session_path, _signed(body))
    return {**body, "session_file": session_path.name}


def _load_session(session_id: str) -> tuple[dict[str, Any], Path]:
    if not session_id or any(character not in "0123456789abcdef" for character in session_id):
        raise ValueError("Invalid Stage 4A session identifier.")
    path = (SESSIONS_DIR / f"{session_id}_preflight.json").resolve()
    if path.parent != SESSIONS_DIR or not path.is_file():
        raise ValueError("The Stage 4A preflight session does not exist.")
    return _verify_signed(json.loads(path.read_text(encoding="utf-8"))), path


def execute_trial(
    session_id: str,
    direction: str,
    arm_phrase: str,
    *,
    adapter_factory: AdapterFactory = ReachySdkAdapter,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    verify_prerequisites()
    direction = validate_direction(direction)
    if arm_phrase != ARM_PHRASE:
        raise ValueError("The exact Stage 4A arming phrase is required.")
    session, _ = _load_session(session_id)
    step = expected_step()
    if step is None or session["step_index"] != step.index or direction != step.direction:
        raise ValueError("This preflight does not match the next frozen Stage 4A step.")
    if time.time() - float(session["created_unix_s"]) > SESSION_MAX_AGE_S:
        raise ValueError("The preflight expired; capture a fresh starting pose.")
    validate_host(session["host"])

    lock = (SESSIONS_DIR / f"{session_id}.consumed").resolve()
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        with lock.open("x", encoding="utf-8") as handle:
            handle.write(_utc_now() + "\n")
    except FileExistsError as exc:
        raise ValueError("This preflight has already been consumed and cannot be replayed.") from exc

    baseline = as_pose(session["baseline_pose"])
    restore_target = rigid_pose(baseline)
    adapter = None
    command_count = 0
    target_measured: np.ndarray | None = None
    restored_measured: np.ndarray | None = None
    target_error = None
    restore_error = None
    restore_translation = None
    failure = None
    target_attempted = False
    started = _utc_now()
    try:
        adapter = adapter_factory(session["host"])
        status = adapter.status()
        if not _status_ready(status):
            raise RuntimeError(f"Reachy is no longer ready: {status}")
        current = as_pose(adapter.current_pose())
        recheck_error = rotation_distance_deg(current, baseline)
        recheck_translation = translation_distance_mm(current, baseline)
        if (
            recheck_error > BASELINE_RECHECK_LIMIT_DEG
            or recheck_translation > TRANSLATION_LIMIT_MM
        ):
            raise RuntimeError(
                f"Reachy moved after preflight ({recheck_error:.2f}°, {recheck_translation:.2f} mm)."
            )
        target = relative_target_pose(baseline, direction)
        commanded_delta = rotation_distance_deg(baseline, target)
        if not 2.0 <= commanded_delta <= 4.0:
            raise RuntimeError(f"Computed target escaped the 3° envelope: {commanded_delta:.2f}°.")

        target_attempted = True
        adapter.goto_head_only(target, MOVE_DURATION_S)
        command_count += 1
        sleep(DWELL_S)
        target_measured = as_pose(adapter.current_pose())
        target_error = rotation_distance_deg(target_measured, target)
    except Exception as exc:
        failure = f"{type(exc).__name__}: {exc}"
    finally:
        if adapter is not None and target_attempted:
            try:
                adapter.goto_head_only(restore_target, RESTORE_DURATION_S)
                command_count += 1
                sleep(RESTORE_SETTLE_S)
                restored_measured = as_pose(adapter.current_pose())
                restore_error = rotation_distance_deg(restored_measured, baseline)
                restore_translation = translation_distance_mm(restored_measured, baseline)
            except Exception as restore_exc:
                detail = f"RESTORE_{type(restore_exc).__name__}: {restore_exc}"
                failure = detail if failure is None else f"{failure}; {detail}"
            finally:
                adapter.disconnect()
        elif adapter is not None:
            adapter.disconnect()

    mechanical_pass = (
        failure is None
        and command_count == 2
        and target_error is not None
        and target_error <= TARGET_ERROR_LIMIT_DEG
        and restore_error is not None
        and restore_error <= RESTORE_ERROR_LIMIT_DEG
        and restore_translation is not None
        and restore_translation <= TRANSLATION_LIMIT_MM
    )
    result = {
        "schema": "reachy-stage4a-supervised-motion-trial-v2",
        "session_id": session_id,
        "step_index": step.index,
        "direction": direction,
        "started_time_iso": started,
        "finished_time_iso": _utc_now(),
        "mechanical_gate_passed": mechanical_pass,
        "failure": failure,
        "target_error_deg": target_error,
        "commanded_increment_deg": None if not target_attempted else commanded_delta,
        "restore_error_deg": restore_error,
        "restore_translation_mm": restore_translation,
        "target_measured_pose": None if target_measured is None else target_measured.tolist(),
        "restored_measured_pose": None if restored_measured is None else restored_measured.tolist(),
        "target_command_pose": None if not target_attempted else target.tolist(),
        "restore_command_pose": restore_target.tolist(),
        "target_settle_s": DWELL_S,
        "restore_settle_s": RESTORE_SETTLE_S,
        "actuation_commands": command_count,
        "head_only_commands": command_count,
        "body_yaw_commands": 0,
        "antenna_commands": 0,
        "torque_or_motor_mode_commands": 0,
        "media_access": 0,
        "cloud_requests": 0,
        "operator_review": "PENDING" if mechanical_pass else "NOT_ELIGIBLE",
    }
    result_path = SESSIONS_DIR / f"{session_id}_result.json"
    _write_json(result_path, _signed(result))
    return {**result, "result_file": result_path.name}


def accept_trial(session_id: str, observations: dict[str, bool]) -> dict[str, Any]:
    session, _ = _load_session(session_id)
    result_path = (SESSIONS_DIR / f"{session_id}_result.json").resolve()
    if result_path.parent != SESSIONS_DIR or not result_path.is_file():
        raise ValueError("No Stage 4A motion result exists for this session.")
    result = _verify_signed(json.loads(result_path.read_text(encoding="utf-8")))
    if not result.get("mechanical_gate_passed"):
        raise ValueError("A failed mechanical trial cannot be accepted.")
    required = {
        "correct_direction",
        "smooth_motion",
        "no_abnormal_noise_or_heat",
        "returned_to_start",
    }
    if set(observations) != required or not all(observations.values()):
        raise ValueError("All four direct operator observations are required.")
    step = expected_step()
    if step is None or step.index != session["step_index"]:
        raise ValueError("This trial is not the next frozen Stage 4A step.")

    accepted = {
        **result,
        "operator_review": "COMPLIANT",
        "operator_observations": observations,
        "accepted_time_iso": _utc_now(),
    }
    _write_json(result_path, _signed(accepted))
    progress = load_progress()
    files = list(progress.get("accepted_result_files") or [])
    files.append(result_path.name)
    completed = int(progress.get("accepted_steps") or 0) + 1
    updated = {
        "schema": "reachy-stage4a-supervised-motion-progress-v2",
        "accepted_steps": completed,
        "total_steps": len(PILOT_STEPS),
        "accepted_result_files": files,
        "status": "COMPLETE" if completed == len(PILOT_STEPS) else "IN_PROGRESS",
        "updated_time_iso": _utc_now(),
    }
    _write_json(PROGRESS_PATH, updated)
    return updated


def reject_trial(session_id: str, observations: dict[str, bool]) -> dict[str, Any]:
    _load_session(session_id)
    result_path = (SESSIONS_DIR / f"{session_id}_result.json").resolve()
    if result_path.parent != SESSIONS_DIR or not result_path.is_file():
        raise ValueError("No Stage 4A motion result exists for this session.")
    result = _verify_signed(json.loads(result_path.read_text(encoding="utf-8")))
    if result.get("operator_review") == "COMPLIANT":
        raise ValueError("An already accepted Stage 4A result cannot be relabelled.")
    reviewed = {
        **result,
        "operator_review": "NONCOMPLIANT",
        "operator_observations": observations,
        "reviewed_time_iso": _utc_now(),
    }
    _write_json(result_path, _signed(reviewed))
    return reviewed
