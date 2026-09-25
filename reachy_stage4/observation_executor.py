"""Offline-only rehearsal of the receive-only observation lifecycle.

This module deliberately ships no process, socket, HTTP, serial, or Reachy
adapter.  It can call only an explicitly injected object that declares itself
offline-only.  The purpose is to exercise phase ordering, gates, failure
containment, and rollback decisions with mocks before a separate hardware
implementation is ever considered.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .daemon_lifecycle import plan_observation_shutdown
from .observation_health import evaluate_observation_health


SCHEMA_VERSION = "reachy-stage4a-offline-observation-rehearsal-v1"
TARGET_REQUIREMENTS = {
    "ALLOW_UNSET",
    "DEFINED_AT_LEAST_ONCE",
    "UNSET_TO_DEFINED",
}


def _result(
    *,
    status: str,
    phases: list[dict[str, Any]],
    blocked_phase: str | None = None,
    reasons: list[str] | None = None,
    rollback_completed: bool = False,
    physical_power_off_required: bool = False,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA_VERSION,
        "status": status,
        "phases": phases,
        "blocked_phase": blocked_phase,
        "reasons": list(reasons or []),
        "rollback_completed": bool(rollback_completed),
        "physical_power_off_required": bool(physical_power_off_required),
        "automatic_return": False,
        "hardware_execution_authorized": False,
        "replacement_started_after_ambiguous_state": False,
        "robot_connections": 0,
        "robot_commands_authorized": 0,
        "robot_commands_sent": 0,
    }


def _probe_health(
    probe: object,
    *,
    context: str,
    required_motor_mode: str | None,
) -> dict[str, Any]:
    if not isinstance(probe, Mapping):
        return {"accepted": False, "reasons": ["PROBE_NOT_A_MAPPING"]}
    required = {
        "status_before",
        "state_before",
        "status_after",
        "state_after",
        "app_lock",
        "current_app",
    }
    missing = sorted(required.difference(probe))
    if missing:
        return {
            "accepted": False,
            "reasons": [f"PROBE_FIELDS_ABSENT:{','.join(missing)}"],
        }
    return evaluate_observation_health(
        context=context,
        status_before=probe["status_before"],
        state_before=probe["state_before"],
        status_after=probe["status_after"],
        state_after=probe["state_after"],
        app_lock=probe["app_lock"],
        current_app=probe["current_app"],
        required_motor_mode=required_motor_mode,
    )


def _release_reasons(release: object) -> list[str]:
    if not isinstance(release, Mapping):
        return ["RELEASE_EVIDENCE_NOT_A_MAPPING"]
    reasons: list[str] = []
    if release.get("process_exited") is not True:
        reasons.append("PROCESS_EXIT_NOT_CONFIRMED")
    if release.get("serial_owner_count") != 0:
        reasons.append("SERIAL_RESOURCE_NOT_RELEASED")
    if release.get("listener_count") != 0:
        reasons.append("API_LISTENER_NOT_RELEASED")
    return reasons


def _capture_reasons(
    capture: Mapping[str, Any], target_requirement: str
) -> list[str]:
    reasons: list[str] = []
    transport = capture.get("transport") or {}
    if not isinstance(transport, Mapping):
        transport = {}
    if transport.get("client_application_messages_sent") != 0:
        reasons.append("TRACE_CLIENT_SENT_APPLICATION_MESSAGES")
    if transport.get("robot_commands_sent") != 0:
        reasons.append("TRACE_CLIENT_SENT_ROBOT_COMMANDS")
    if capture.get("target_inference_performed") is not False:
        reasons.append("TARGET_STATE_WAS_INFERRED")
    if capture.get("target_requirement") != target_requirement:
        reasons.append("TARGET_REQUIREMENT_MISMATCH")
    if not isinstance(capture.get("frame_count"), int) or capture.get("frame_count", 0) <= 0:
        reasons.append("NO_TRACE_FRAMES")
    return reasons


def _restore_stock(adapter: object, phases: list[dict[str, Any]]) -> list[str]:
    try:
        probe = adapter.restore_stock()
    except Exception as exc:
        phases.append(
            {
                "phase": "STOCK_RESTORED",
                "health": {
                    "accepted": False,
                    "reasons": ["STOCK_RESTORE_FAILED"],
                    "exception_type": type(exc).__name__,
                },
            }
        )
        return ["STOCK_RESTORE_FAILED"]
    health = _probe_health(
        probe,
        context="STOCK_RESTORED",
        required_motor_mode="disabled",
    )
    phases.append({"phase": "STOCK_RESTORED", "health": health})
    return list(health.get("reasons", []))


def _terminalize(
    adapter: object,
    phases: list[dict[str, Any]],
) -> tuple[list[str], bool, bool]:
    """Rehearse the terminal branch and return reasons/rollback/power-off."""

    try:
        terminal = adapter.terminal_state()
    except Exception as exc:
        phases.append(
            {
                "phase": "TERMINAL_BRANCH",
                "accepted": False,
                "reasons": ["TERMINAL_STATE_UNAVAILABLE"],
                "exception_type": type(exc).__name__,
            }
        )
        return ["TERMINAL_STATE_UNAVAILABLE"], False, True
    raw_mode = terminal.get("motor_mode")
    motor_mode = (
        str(raw_mode)
        if str(raw_mode).strip().upper() in {"DISABLED", "ENABLED"}
        else "UNKNOWN"
    )
    plan = plan_observation_shutdown(
        daemon_responsive=terminal.get("daemon_responsive") is True,
        telemetry_fresh=terminal.get("telemetry_fresh") is True,
        motor_mode=motor_mode,
    )
    phases.append({"phase": "TERMINAL_BRANCH", "plan": plan})
    if plan["branch"] == "PHYSICAL_POWER_OFF":
        return ["AMBIGUOUS_TERMINAL_STATE"], False, True

    if plan["branch"] == "SAFETY_DISABLE_THEN_STOP":
        try:
            adapter.safety_disable()
            verified = adapter.terminal_state()
        except Exception as exc:
            phases.append(
                {
                    "phase": "SAFETY_DISABLE_VERIFICATION",
                    "accepted": False,
                    "reasons": ["SAFETY_DISABLE_NOT_VERIFIED"],
                    "exception_type": type(exc).__name__,
                }
            )
            return ["SAFETY_DISABLE_NOT_VERIFIED"], False, True
        phases.append(
            {
                "phase": "SAFETY_DISABLE_VERIFICATION",
                "terminal_state": dict(verified),
            }
        )
        if not (
            verified.get("daemon_responsive") is True
            and verified.get("telemetry_fresh") is True
            and str(verified.get("motor_mode", "")).lower() == "disabled"
        ):
            return ["SAFETY_DISABLE_NOT_VERIFIED"], False, True

    try:
        release = adapter.stop_temporary()
    except Exception as exc:
        phases.append(
            {
                "phase": "TEMPORARY_RELEASE",
                "accepted": False,
                "reasons": ["TEMPORARY_STOP_FAILED"],
                "exception_type": type(exc).__name__,
            }
        )
        return ["TEMPORARY_STOP_FAILED"], False, True
    release_reasons = _release_reasons(release)
    phases.append(
        {
            "phase": "TEMPORARY_RELEASE",
            "accepted": not release_reasons,
            "reasons": release_reasons,
        }
    )
    if release_reasons:
        return release_reasons, False, False

    restore_reasons = _restore_stock(adapter, phases)
    return restore_reasons, not restore_reasons, False


def run_offline_observation_rehearsal(
    adapter: object,
    *,
    target_requirement: str = "ALLOW_UNSET",
) -> dict[str, Any]:
    """Run a mock lifecycle rehearsal with no hardware authority.

    The injected adapter must expose ``offline_only = True``.  No concrete
    adapter is provided by the project, making accidental hardware use
    unavailable by default.
    """

    requirement = str(target_requirement).strip().upper()
    if requirement not in TARGET_REQUIREMENTS:
        raise ValueError(f"Unknown target requirement: {target_requirement}")
    if getattr(adapter, "offline_only", False) is not True:
        raise PermissionError("OFFLINE_ONLY_ADAPTER_REQUIRED")

    phases: list[dict[str, Any]] = []
    try:
        baseline_probe = adapter.baseline_probe()
    except Exception as exc:
        return _result(
            status="BLOCKED_OFFLINE_MOCK_ONLY",
            phases=[
                {
                    "phase": "STOCK_BASELINE",
                    "health": {
                        "accepted": False,
                        "reasons": ["BASELINE_PROBE_FAILED"],
                        "exception_type": type(exc).__name__,
                    },
                }
            ],
            blocked_phase="STOCK_BASELINE",
            reasons=["BASELINE_PROBE_FAILED"],
        )
    baseline = _probe_health(
        baseline_probe,
        context="STOCK_BASELINE",
        required_motor_mode=None,
    )
    phases.append({"phase": "STOCK_BASELINE", "health": baseline})
    if not baseline.get("accepted"):
        return _result(
            status="BLOCKED_OFFLINE_MOCK_ONLY",
            phases=phases,
            blocked_phase="STOCK_BASELINE",
            reasons=list(baseline.get("reasons", [])),
        )

    try:
        stock_release = adapter.stop_stock()
    except Exception as exc:
        phases.append(
            {
                "phase": "STOCK_RELEASE",
                "accepted": False,
                "reasons": ["STOCK_STOP_FAILED"],
                "exception_type": type(exc).__name__,
            }
        )
        return _result(
            status="BLOCKED_OFFLINE_MOCK_ONLY",
            phases=phases,
            blocked_phase="STOCK_RELEASE",
            reasons=["STOCK_STOP_FAILED"],
        )
    release_reasons = _release_reasons(stock_release)
    phases.append(
        {
            "phase": "STOCK_RELEASE",
            "accepted": not release_reasons,
            "reasons": release_reasons,
        }
    )
    if release_reasons:
        return _result(
            status="BLOCKED_OFFLINE_MOCK_ONLY",
            phases=phases,
            blocked_phase="STOCK_RELEASE",
            reasons=release_reasons,
        )

    try:
        started = adapter.start_temporary()
    except Exception as exc:
        phases.append(
            {
                "phase": "TEMPORARY_START",
                "accepted": False,
                "reasons": ["TEMPORARY_START_FAILED_STATE_AMBIGUOUS"],
                "exception_type": type(exc).__name__,
            }
        )
        return _result(
            status="BLOCKED_OFFLINE_MOCK_ONLY",
            phases=phases,
            blocked_phase="TEMPORARY_START",
            reasons=["TEMPORARY_START_FAILED_STATE_AMBIGUOUS"],
            physical_power_off_required=True,
        )
    if not isinstance(started, Mapping):
        started = {}
    start_reasons: list[str] = []
    if started.get("bind_host") != "127.0.0.1":
        start_reasons.append("TEMPORARY_API_NOT_LOOPBACK_ONLY")
    if started.get("reflash_suppressed") is not True:
        start_reasons.append("REFLASH_NOT_SUPPRESSED")
    if started.get("pid_gain_writes_declared") is not True:
        start_reasons.append("CONTROLLER_PID_WRITES_NOT_DECLARED")
    if started.get("experimental_motion_requests") != 0:
        start_reasons.append("EXPERIMENTAL_MOTION_REQUESTED")
    if started.get("torque_enable_requests") != 0:
        start_reasons.append("TORQUE_ENABLE_REQUESTED")
    temp_health = _probe_health(
        started.get("probe") or {},
        context="TEMPORARY_OBSERVATION",
        required_motor_mode="disabled",
    )
    start_reasons.extend(temp_health.get("reasons", []))
    phases.append(
        {
            "phase": "TEMPORARY_START",
            "accepted": not start_reasons,
            "reasons": start_reasons,
            "health": temp_health,
        }
    )
    if start_reasons:
        terminal_reasons, rolled_back, power_off = _terminalize(adapter, phases)
        return _result(
            status="BLOCKED_OFFLINE_MOCK_ONLY",
            phases=phases,
            blocked_phase="TEMPORARY_START",
            reasons=start_reasons + terminal_reasons,
            rollback_completed=rolled_back,
            physical_power_off_required=power_off,
        )

    try:
        capture = adapter.capture(requirement)
        if not isinstance(capture, Mapping):
            raise TypeError("capture report is not a mapping")
        capture_reasons = _capture_reasons(capture, requirement)
    except Exception as exc:  # exercised with a mock fault; never hides the gate
        capture = {"exception_type": type(exc).__name__}
        capture_reasons = ["TRACE_CAPTURE_FAILED"]
    phases.append(
        {
            "phase": "TRACE_CAPTURE",
            "accepted": not capture_reasons,
            "reasons": capture_reasons,
            "report": dict(capture),
        }
    )

    terminal_reasons, rolled_back, power_off = _terminalize(adapter, phases)
    all_reasons = capture_reasons + terminal_reasons
    if all_reasons:
        return _result(
            status="BLOCKED_OFFLINE_MOCK_ONLY",
            phases=phases,
            blocked_phase="TRACE_CAPTURE" if capture_reasons else "TERMINAL_BRANCH",
            reasons=all_reasons,
            rollback_completed=rolled_back,
            physical_power_off_required=power_off,
        )

    return _result(
        status="PASS_OFFLINE_MOCK_ONLY",
        phases=phases,
        rollback_completed=True,
    )
