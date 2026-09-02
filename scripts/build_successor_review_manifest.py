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
    "docs/SUCCESSOR_TRAJECTORY_REVIEW.md",
    "docs/SPLIT_TARGET_RETURN_PROTOCOL.md",
    "docs/RETURN_TO_BORROWED_CONDITION.md",
    "docs/OWNER_SCOPE_REQUEST.md",
    "docs/INDEPENDENT_PROTOCOL_REVIEW.md",
    "patches/reachy-mini-v1.9.0-target-state-observability.patch",
    "reachy_stage4/successor_review.py",
    "reachy_stage4/successor_trace.py",
    "reachy_stage4/trajectory_review.py",
    "reachy_stage4/split_authorization.py",
    "reachy_stage4/external_records.py",
    "scripts/build_successor_review_manifest.py",
    "scripts/capture_successor_present_target_trace.py",
    "scripts/validate_successor_trajectory_v190.py",
    "tests/test_stage4a_successor_review.py",
    "tests/test_stage4a_successor_trace.py",
    "tests/test_stage4a_trajectory_review.py",
    "tests/test_stage4a_trajectory_validator.py",
    "tests/test_stage4a_split_authorization.py",
    "tests/test_stage4a_external_records.py",
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
        "schema": "reachy-stage4a-successor-review-manifest-v1",
        "status": "DESIGN_ONLY_NO_COMMAND_AUTHORITY",
        "file_count": len(files),
        "files": files,
        "known_blockers": [
            "NO_OWNER_SCOPE_CONFIRMATION_RECORDED",
            "NO_INDEPENDENT_HUMAN_ROBOTICS_VERDICT_RECORDED",
            "TARGET_STATE_PATCH_NOT_INSTALLED",
            "NO_LIVE_PRESENT_TARGET_TRACE",
            "NO_SUCCESSOR_EXECUTOR",
            "NO_COLLISION_LOAD_TRACKING_OR_PHYSICAL_SAFETY_VALIDATION",
            "NO_APPROVED_RETURN_TO_BORROWED_CONDITION_PROCEDURE",
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
