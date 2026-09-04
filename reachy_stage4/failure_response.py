"""Pure, non-executing failure-response classification for successor review."""

from __future__ import annotations

from typing import Any


SCHEMA_VERSION = "reachy-stage4a-failure-response-matrix-v1"
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
    torque_expected_disabled: bool,
) -> dict[str, Any]:
    """Select a review response; never invoke the selected action."""

    phase = str(phase).strip().upper()
    failure_kind = str(failure_kind).strip().upper()
    if phase not in PHASES:
        raise ValueError(f"Unknown phase: {phase}")
    if failure_kind not in FAILURE_KINDS:
        raise ValueError(f"Unknown failure kind: {failure_kind}")

    if phase == "OBSERVATION_ONLY" and torque_expected_disabled:
        response = "STOP_TEMPORARY_DAEMON_PRESERVE_EVIDENCE_REVIEW_ROLLBACK"
        rationale = "The phase authorizes no motion and depends on torque remaining disabled."
    elif daemon_responsive and telemetry_fresh:
        response = "PREAPPROVED_SUPPORTED_STOP_OR_DISABLE_NO_RETURN"
        rationale = "Known fresh state permits only the separately reviewed stop/disable path."
    elif not daemon_responsive:
        response = "STAY_CLEAR_OWNER_APPROVED_PHYSICAL_DEENERGIZATION_NO_SOFTWARE_RETURN"
        rationale = "An unresponsive daemon cannot be trusted to execute a return trajectory."
    else:
        response = "STAY_CLEAR_NO_COMMAND_PRESERVE_EVIDENCE_ESCALATE"
        rationale = "Stale or ambiguous state cannot justify another software trajectory."

    return {
        "schema": SCHEMA_VERSION,
        "status": "DESIGN_ONLY_NO_COMMAND_AUTHORITY",
        "phase": phase,
        "failure_kind": failure_kind,
        "response": response,
        "rationale": rationale,
        "automatic_return": False,
        "normal_daemon_shutdown_assumed_safe": False,
        "hard_power_removal_assumed_safe": False,
        "requires_preapproved_unit_specific_procedure": True,
        "robot_connections": 0,
        "robot_commands_authorized": 0,
        "robot_commands_sent": 0,
    }
