"""Pure state machine for separately reviewed target and return legs.

This module produces design decisions only.  It has no transport, executor,
timer, file write, or robot command surface.  A return is never entered from a
target failure and cannot reuse the target authorization identifier.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Mapping

from .safety import validate_direction


SCHEMA_VERSION = "reachy-stage4a-split-target-return-design-v1"
STATUS_DESIGN_ONLY = "DESIGN_ONLY_NO_COMMAND_AUTHORITY"
TARGET_ARM_PHRASE = "AUTHORIZE REACHY TARGET 3 DEGREES"
RETURN_ARM_PHRASE = "AUTHORIZE REACHY RETURN TO CAPTURED BASELINE"
TERMINAL_STATES = {"COMPLETE", "ABORT_POWER_DOWN"}
FAILURE_EVENTS = {"HEALTH_FAILURE", "TIMEOUT", "UNEXPECTED_MOTION"}
TRANSITIONS = {
    ("EXTERNAL_APPROVALS_REQUIRED", "RECORD_EXTERNAL_APPROVALS"): "TARGET_PREFLIGHT_REQUIRED",
    ("TARGET_PREFLIGHT_REQUIRED", "TARGET_PREFLIGHT_PASS"): "TARGET_AUTHORIZATION_REQUIRED",
    ("TARGET_AUTHORIZATION_REQUIRED", "AUTHORIZE_TARGET"): "TARGET_AUTHORIZED",
    ("TARGET_AUTHORIZED", "TARGET_STARTED"): "TARGET_IN_PROGRESS",
    ("TARGET_IN_PROGRESS", "TARGET_OBSERVED_SUCCESS"): "RETURN_PREFLIGHT_REQUIRED",
    ("TARGET_IN_PROGRESS", "TARGET_OBSERVED_FAILURE"): "ABORT_POWER_DOWN",
    ("RETURN_PREFLIGHT_REQUIRED", "RETURN_PREFLIGHT_PASS"): "RETURN_AUTHORIZATION_REQUIRED",
    ("RETURN_AUTHORIZATION_REQUIRED", "AUTHORIZE_RETURN"): "RETURN_AUTHORIZED",
    ("RETURN_AUTHORIZED", "RETURN_STARTED"): "RETURN_IN_PROGRESS",
    ("RETURN_IN_PROGRESS", "RETURN_OBSERVED_SUCCESS"): "COMPLETE",
    ("RETURN_IN_PROGRESS", "RETURN_OBSERVED_FAILURE"): "ABORT_POWER_DOWN",
}


def _require_text(record: Mapping[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing structured evidence field: {field}")
    return value.strip()


def _validate_artifact_record(record: object, *, decision: str) -> dict[str, str]:
    if not isinstance(record, Mapping):
        raise ValueError("A structured artifact record is required.")
    result = {
        "artifact_reference": _require_text(record, "artifact_reference"),
        "artifact_sha256": _require_text(record, "artifact_sha256").lower(),
        "recorded_by": _require_text(record, "recorded_by"),
        "recorded_at_utc": _require_text(record, "recorded_at_utc"),
        "decision": _require_text(record, "decision"),
    }
    if not re.fullmatch(r"[0-9a-f]{64}", result["artifact_sha256"]):
        raise ValueError("artifact_sha256 must contain 64 lowercase hex characters.")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", result["recorded_at_utc"]):
        raise ValueError("recorded_at_utc must be a whole-second UTC timestamp.")
    if result["decision"] != decision:
        raise ValueError(f"Expected decision {decision}.")
    return result


def _validate_trace_record(record: object, *, decision: str) -> dict[str, str]:
    return _validate_artifact_record(record, decision=decision)


def _validate_authorization(
    record: object,
    *,
    phrase: str,
    previous_identifier: str | None = None,
) -> dict[str, str]:
    if not isinstance(record, Mapping):
        raise ValueError("A structured authorization record is required.")
    result = {
        "authorization_id": _require_text(record, "authorization_id"),
        "authorized_by": _require_text(record, "authorized_by"),
        "authorized_at_utc": _require_text(record, "authorized_at_utc"),
        "phrase": _require_text(record, "phrase"),
    }
    if result["phrase"] != phrase:
        raise ValueError("Authorization phrase does not match this leg.")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", result["authorized_at_utc"]):
        raise ValueError("authorized_at_utc must be a whole-second UTC timestamp.")
    if previous_identifier is not None and result["authorization_id"] == previous_identifier:
        raise ValueError("Return authorization must have a fresh identifier.")
    return result


def create_split_motion_design(
    direction: str,
    *,
    operator_identifier: str,
) -> dict[str, Any]:
    operator = str(operator_identifier).strip()
    if not operator:
        raise ValueError("A stable operator identifier is required.")
    return {
        "schema": SCHEMA_VERSION,
        "status": STATUS_DESIGN_ONLY,
        "direction": validate_direction(direction),
        "operator_identifier": operator,
        "state": "EXTERNAL_APPROVALS_REQUIRED",
        "records": {},
        "history": [],
        "next_requirement": "owner scope confirmation and independent robotics review",
        "automatic_return": False,
        "robot_connections": 0,
        "robot_commands_authorized": 0,
        "robot_commands_sent": 0,
    }


def apply_design_event(
    session: Mapping[str, Any],
    event: str,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply one review event without performing or authorizing its action."""

    result = copy.deepcopy(dict(session))
    if result.get("schema") != SCHEMA_VERSION or result.get("status") != STATUS_DESIGN_ONLY:
        raise ValueError("Unknown or command-capable session schema.")
    state = str(result.get("state"))
    name = str(event).strip().upper()
    supplied = dict(evidence or {})
    if state in TERMINAL_STATES:
        raise ValueError(f"Terminal state {state} cannot transition.")

    if name in FAILURE_EVENTS:
        next_state = "ABORT_POWER_DOWN"
        validated: Any = {"reason": _require_text(supplied, "reason")}
    else:
        try:
            next_state = TRANSITIONS[(state, name)]
        except KeyError as exc:
            raise ValueError(f"Event {name} is invalid from {state}.") from exc

        if name == "RECORD_EXTERNAL_APPROVALS":
            owner = _validate_artifact_record(
                supplied.get("owner_scope"), decision="SCOPE_CONFIRMED"
            )
            reviewer = _validate_artifact_record(
                supplied.get("independent_review"), decision="PROTOCOL_APPROVED"
            )
            if owner["recorded_by"].casefold() == reviewer["recorded_by"].casefold():
                raise ValueError("Owner and independent reviewer records must identify different people.")
            if reviewer["recorded_by"].casefold() == str(
                result["operator_identifier"]
            ).casefold():
                raise ValueError("Independent reviewer and operator must identify different people.")
            validated = {"owner_scope": owner, "independent_review": reviewer}
        elif name == "TARGET_PREFLIGHT_PASS":
            validated = _validate_trace_record(
                supplied, decision="TARGET_PREFLIGHT_PASS"
            )
        elif name == "AUTHORIZE_TARGET":
            validated = _validate_authorization(supplied, phrase=TARGET_ARM_PHRASE)
            result["records"]["target_authorization_id"] = validated["authorization_id"]
        elif name == "TARGET_STARTED":
            validated = {"executor_receipt": _require_text(supplied, "executor_receipt")}
        elif name == "TARGET_OBSERVED_SUCCESS":
            validated = _validate_trace_record(
                supplied, decision="TARGET_OBSERVED_SUCCESS"
            )
        elif name == "TARGET_OBSERVED_FAILURE":
            validated = {"reason": _require_text(supplied, "reason")}
        elif name == "RETURN_PREFLIGHT_PASS":
            validated = _validate_trace_record(
                supplied, decision="RETURN_PREFLIGHT_PASS"
            )
            target_hash = next(
                (
                    item["evidence"].get("artifact_sha256")
                    for item in reversed(result["history"])
                    if item["event"] == "TARGET_OBSERVED_SUCCESS"
                ),
                None,
            )
            if validated["artifact_sha256"] == target_hash:
                raise ValueError("Return preflight requires a fresh observation artifact.")
        elif name == "AUTHORIZE_RETURN":
            validated = _validate_authorization(
                supplied,
                phrase=RETURN_ARM_PHRASE,
                previous_identifier=result["records"].get("target_authorization_id"),
            )
        elif name == "RETURN_STARTED":
            validated = {"executor_receipt": _require_text(supplied, "executor_receipt")}
        elif name == "RETURN_OBSERVED_SUCCESS":
            validated = _validate_trace_record(
                supplied, decision="RETURN_OBSERVED_SUCCESS"
            )
        elif name == "RETURN_OBSERVED_FAILURE":
            validated = {"reason": _require_text(supplied, "reason")}
        else:
            raise AssertionError(f"Unvalidated event: {name}")

    result["history"].append(
        {"from": state, "event": name, "to": next_state, "evidence": validated}
    )
    result["state"] = next_state
    requirements = {
        "TARGET_PREFLIGHT_REQUIRED": "fresh receive-only target preflight",
        "TARGET_AUTHORIZATION_REQUIRED": TARGET_ARM_PHRASE,
        "TARGET_AUTHORIZED": "separate executor may start target leg",
        "TARGET_IN_PROGRESS": "observe target leg; no return is authorized",
        "RETURN_PREFLIGHT_REQUIRED": "fresh receive-only return preflight",
        "RETURN_AUTHORIZATION_REQUIRED": RETURN_ARM_PHRASE,
        "RETURN_AUTHORIZED": "separate executor may start return leg",
        "RETURN_IN_PROGRESS": "observe return leg",
        "COMPLETE": "none",
        "ABORT_POWER_DOWN": "normal power-down; return is not authorized",
    }
    result["next_requirement"] = requirements[next_state]
    # These counters describe this pure design evaluator, not a future executor.
    result["robot_connections"] = 0
    result["robot_commands_authorized"] = 0
    result["robot_commands_sent"] = 0
    return result
