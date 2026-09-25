#!/usr/bin/env python3
"""Build or check the content-addressed Stage 4A successor review packet."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = PROJECT_ROOT / "docs/SUCCESSOR_REVIEW_MANIFEST.json"
REVIEW_FILES = (
    "README.md",
    "SAFETY.md",
    "pyproject.toml",
    "docs/EXTERNAL_REVIEW.md",
    "docs/FAILURE_LEDGER.md",
    "docs/LIMITATIONS.md",
    "docs/THRESHOLD_PROVENANCE.md",
    "docs/CENTERING_REVIEW.md",
    "docs/MAINTENANCE_TRIAGE.md",
    "docs/TARGET_STATE_OBSERVABILITY.md",
    "docs/STARTUP_CHARACTERIZATION.md",
    "docs/BASELINE_RELATIVE_SUCCESSOR.md",
    "docs/RECEIVE_ONLY_SUCCESSOR_TRACE.md",
    "docs/TEMPORARY_DAEMON_LIFECYCLE.md",
    "docs/OFFLINE_FAILURE_REHEARSAL.md",
    "docs/SUCCESSOR_TRAJECTORY_REVIEW.md",
    "docs/SPLIT_TARGET_RETURN_PROTOCOL.md",
    "docs/RETURN_TO_BORROWED_CONDITION.md",
    "patches/reachy-mini-v1.9.0-target-state-observability.patch",
    "patches/reachy-mini-v1.9.0-observation-lifecycle.patch",
    "reachy_stage4/daemon_lifecycle.py",
    "reachy_stage4/observation_health.py",
    "reachy_stage4/observation_executor.py",
    "reachy_stage4/failure_response.py",
    "reachy_stage4/rollback_inventory.py",
    "reachy_stage4/offline_fault_rehearsal.py",
    "reachy_stage4/successor_review.py",
    "reachy_stage4/successor_trace.py",
    "reachy_stage4/trajectory_review.py",
    "reachy_stage4/split_authorization.py",
    "reachy_stage4/external_records.py",
    "scripts/build_successor_review_manifest.py",
    "scripts/validate_daemon_lifecycle_patch.py",
    "scripts/run_offline_fault_rehearsal.py",
    "scripts/capture_successor_present_target_trace.py",
    "scripts/validate_target_schema_endpoints.py",
    "scripts/validate_target_schema_daemon.py",
    "scripts/validate_successor_trajectory_v190.py",
    "tests/test_stage4a_successor_review.py",
    "tests/test_stage4a_successor_trace.py",
    "tests/test_stage4a_trajectory_review.py",
    "tests/test_stage4a_trajectory_validator.py",
    "tests/test_stage4a_split_authorization.py",
    "tests/test_stage4a_external_records.py",
    "tests/test_stage4a_daemon_lifecycle.py",
    "tests/test_stage4a_observation_health.py",
    "tests/test_stage4a_observation_executor.py",
    "tests/test_stage4a_target_schema_endpoint_validator.py",
    "tests/test_stage4a_target_schema_daemon_validator.py",
    "tests/test_stage4a_failure_response.py",
    "tests/test_stage4a_rollback_inventory.py",
    "tests/test_stage4a_offline_fault_rehearsal.py",
    "evidence/analysis/stage4a_offline_fault_rehearsal_v1.json",
    "evidence/analysis/stage4a_offline_fault_rehearsal_v1.json.sha256",
)


def build_payload() -> dict:
    files = []
    for relative in REVIEW_FILES:
        path = PROJECT_ROOT / relative
        content = path.read_bytes()
        files.append(
            {
                "path": relative,
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    return {
        "schema": "reachy-stage4a-successor-review-manifest-v3",
        "status": "DESIGN_ONLY_NO_COMMAND_AUTHORITY",
        "external_authorization_status": "OUTSIDE_REPOSITORY_NO_CORRESPONDENCE_RETAINED",
        "file_count": len(files),
        "files": files,
        "known_blockers": [
            "OBSERVATION_PATCHES_NOT_PERSISTENTLY_INSTALLED",
            "NO_LIVE_PRESENT_TARGET_TRACE",
            "NULL_TO_DEFINED_TARGET_TRANSITION_NOT_PHYSICALLY_OBSERVED",
            "CONTROLLER_STARTUP_WRITES_PID_GAINS",
            "NO_HARDWARE_LIFECYCLE_EXECUTOR",
            "NO_COLLISION_LOAD_TRACKING_OR_PHYSICAL_SAFETY_VALIDATION",
            "NO_APPROVED_RETURN_TO_BORROWED_CONDITION_PROCEDURE",
            "NO_VERIFIED_TORQUE_REMOVAL_AFTER_DAEMON_FAILURE",
            "PHYSICAL_POWER_OFF_BRANCH_NOT_HARDWARE_VALIDATED",
            "NO_MOVEMENT_SPECIFIC_ABORT_OR_CLEARANCE_VALIDATION",
        ],
        "robot_connections": 0,
        "robot_commands_authorized": 0,
        "robot_commands_sent": 0,
    }


def render() -> bytes:
    return json.dumps(build_payload(), indent=2, sort_keys=True).encode("utf-8") + b"\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = render()
    if args.write:
        OUTPUT.write_bytes(expected)
        print(f"Wrote {OUTPUT.relative_to(PROJECT_ROOT)} with {len(REVIEW_FILES)} files.")
        return 0
    if not OUTPUT.is_file() or OUTPUT.read_bytes() != expected:
        print("FAIL: successor review manifest is missing or stale.")
        return 1
    print(f"PASS: successor review manifest matches {len(REVIEW_FILES)} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
