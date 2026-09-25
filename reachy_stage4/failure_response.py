"""Pure, non-executing failure-response classification for successor review."""

from __future__ import annotations

from typing import Any


SCHEMA_VERSION = "reachy-stage4a-failure-response-matrix-v2"
FAILURE_KINDS = {
    "HEALTH_FAILURE",
    "TIMEOUT",
    "UNEXPECTED_MOTION",
    "TARGET_TRACKING_FAILURE",
    "RETURN_TRACKING_FAILURE",
}
PHASES = {"OBSERVATION_ONLY", "TARGET", "RETURN"}


def classify_failure(
    phase: str,
    failure_kind: str,
    *,
    daemon_responsive: bool,
    telemetry_fresh: bool,
    motor_mode_confirmed_disabled: bool,
) -> dict[str, Any]:
    """Select a review response; never invoke the selected action."""

    phase = str(phase).strip().upper()
    failure_kind = str(failure_kind).strip().upper()
    if phase not in PHASES:
        raise ValueError(f"Unknown phase: {phase}")
    if failure_kind not in FAILURE_KINDS:
        raise ValueError(f"Unknown failure kind: {failure_kind}")

    if not daemon_responsive or not telemetry_fresh:
        response = (
            "STAY_CLEAR_USE_PREAPPROVED_PHYSICAL_POWER_OFF_"
            "EXPECT_PASSIVE_PLATFORM_DROP_NO_SOFTWARE_RETURN"
        )
        rationale = (
            "Unresponsive or stale control state cannot justify a software disable, "
            "replacement daemon, or return trajectory."
        )
        safety_disable_actions_planned = 0
        physical_power_off_planned = True
    elif motor_mode_confirmed_disabled:
        response = "STOP_TEMPORARY_DAEMON_VERIFY_EXIT_AND_SERIAL_RELEASE_NO_RETURN"
        rationale = (
            "Fresh telemetry confirms disabled motor control; stopping still requires "
            "process-exit and serial-release evidence."
        )
        safety_disable_actions_planned = 0
        physical_power_off_planned = False
    else:
        response = "ISSUE_ONE_SAFETY_DISABLE_VERIFY_DISABLED_THEN_STOP_NO_RETURN"
        rationale = (
            "Fresh responsive state permits only the predeclared safety-disable action, "
            "never an experimental trajectory."
        )
        safety_disable_actions_planned = 1
        physical_power_off_planned = False

    return {
        "schema": SCHEMA_VERSION,
        "status": "DESIGN_ONLY_NO_COMMAND_AUTHORITY",
        "phase": phase,
        "failure_kind": failure_kind,
        "response": response,
        "rationale": rationale,
        "automatic_return": False,
        "replacement_daemon_before_terminal_verification": False,
        "motor_mode_confirmed_disabled": bool(motor_mode_confirmed_disabled),
        "safety_disable_actions_planned": safety_disable_actions_planned,
        "physical_power_off_planned": physical_power_off_planned,
        "platform_drop_zone_required": physical_power_off_planned,
        "experimental_commands_planned": 0,
        "normal_daemon_shutdown_assumed_safe": False,
        "hard_power_removal_assumed_safe": False,
        "requires_preapproved_unit_specific_procedure": True,
        "robot_connections": 0,
        "robot_commands_authorized": 0,
        "robot_commands_sent": 0,
    }
