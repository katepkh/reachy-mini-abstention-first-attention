"""Compare verified post-wake captures with Reachy Mini 1.9.0's identity reference.

This module is deliberately offline. It reads checksum-verified diagnostic
captures, performs arithmetic, and writes an immutable private report. It has
no network, robot transport, or actuation surface.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .config import OFFICIAL_PROTOCOL_VERSION, PROJECT_ROOT
from .startup_characterization import (
    load_verified_capture,
    summarize_startup_captures,
    write_report,
)


SCHEMA_VERSION = "reachy-stage4-post-wake-reference-audit-v1"
DEFAULT_REPORT = (
    PROJECT_ROOT / "data/private/stage4a_post_wake_reference_audit_v1/report.json"
)

# Reachy Mini 1.9.0 defines AbstractBackend.INIT_HEAD_POSE as np.eye(4), and
# wake_up() ends by requesting that pose. The corresponding analytical IK
# solution was evaluated from the released 1.9.0 wheel and is intentionally
# rounded here: this audit characterizes degree-scale residuals, not calibration.
IDENTITY_POSE_ROW_MAJOR = (
    1.0,
    0.0,
    0.0,
    0.0,
    0.0,
    1.0,
    0.0,
    0.0,
    0.0,
    0.0,
    1.0,
    0.0,
    0.0,
    0.0,
    0.0,
    1.0,
)
IDENTITY_IK_JOINTS_DEG = (0.0, 35.899, -35.898, 35.898, -35.898, 35.898, -35.898)
JOINT_NAMES = (
    "body_yaw",
    "stewart_1",
    "stewart_2",
    "stewart_3",
    "stewart_4",
    "stewart_5",
    "stewart_6",
)
SOURCE_URLS = {
    "wake_definition": (
        "https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/"
        "src/reachy_mini/daemon/backend/abstract.py"
    ),
    "daemon_start": (
        "https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/"
        "src/reachy_mini/daemon/daemon.py"
    ),
    "physical_backend": (
        "https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/"
        "src/reachy_mini/daemon/backend/robot/backend.py"
    ),
    "analytical_kinematics": (
        "https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/"
        "src/reachy_mini/kinematics/analytical_kinematics.py"
    ),
}


def _mean(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("Cannot average an empty sequence.")
    return sum(values) / len(values)


def _joint_means_deg(record: Mapping[str, Any]) -> list[float]:
    frames = record.get("stream_frames")
    if not isinstance(frames, list) or not frames:
        raise ValueError("Capture has no state-stream frames.")
    columns: list[list[float]] = [[] for _ in JOINT_NAMES]
    for frame in frames:
        if not isinstance(frame, Mapping):
            raise ValueError("State-stream frame must be an object.")
        joints = frame.get("head_joints_rad")
        if not isinstance(joints, list) or len(joints) != len(JOINT_NAMES):
            raise ValueError("Each frame requires seven head_joints_rad values.")
        for index, value in enumerate(joints):
            if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise ValueError("Joint values must be finite numbers.")
            columns[index].append(math.degrees(float(value)))
    return [_mean(column) for column in columns]


def audit_post_wake_reference(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Return a source-pinned, zero-authority joint and pose reference audit."""

    materialized = list(records)
    startup_report = summarize_startup_captures(materialized)
    indexed = {}
    for record in materialized:
        context = record["operator_annotation"]["startup_context"]
        indexed[int(context["startup_index"])] = record

    rows: list[dict[str, Any]] = []
    joint_means_by_start: list[list[float]] = []
    for startup_row in startup_report["captures"]:
        index = int(startup_row["startup_index"])
        means = _joint_means_deg(indexed[index])
        deltas = [
            observed - nominal
            for observed, nominal in zip(means, IDENTITY_IK_JOINTS_DEG, strict=True)
        ]
        joint_means_by_start.append(means)
        rows.append(
            {
                "startup_index": index,
                "capture_file": startup_row["capture_file"],
                "capture_sha256": startup_row["capture_sha256"],
                "pose_rotation_mean_deg": startup_row["rotation_mean_deg"],
                "mean_joints_deg": dict(zip(JOINT_NAMES, means, strict=True)),
                "delta_from_rounded_identity_ik_deg": dict(
                    zip(JOINT_NAMES, deltas, strict=True)
                ),
                "maximum_absolute_joint_delta_deg": max(abs(value) for value in deltas),
            }
        )

    per_joint = {}
    for joint_index, joint_name in enumerate(JOINT_NAMES):
        observed = [means[joint_index] for means in joint_means_by_start]
        nominal = IDENTITY_IK_JOINTS_DEG[joint_index]
        per_joint[joint_name] = {
            "rounded_identity_ik_deg": nominal,
            "observed_mean_deg": _mean(observed),
            "observed_minimum_deg": min(observed),
            "observed_maximum_deg": max(observed),
            "between_start_range_deg": max(observed) - min(observed),
            "mean_delta_from_rounded_identity_ik_deg": _mean(observed) - nominal,
        }

    return {
        "schema": SCHEMA_VERSION,
        "daemon_version": OFFICIAL_PROTOCOL_VERSION,
        "source_defined_wake_endpoint": "4x4 identity pose",
        "source_reference_pose_row_major": list(IDENTITY_POSE_ROW_MAJOR),
        "rounded_identity_ik_joint_order": list(JOINT_NAMES),
        "rounded_identity_ik_joints_deg": list(IDENTITY_IK_JOINTS_DEG),
        "identity_ik_precision_note": (
            "The released-wheel analytical IK values are rounded to 0.001 degree; "
            "they are a source reference, not unit calibration."
        ),
        "source_urls": SOURCE_URLS,
        "capture_count": len(rows),
        "captures": rows,
        "per_joint_summary": per_joint,
        "startup_characterization_status": startup_report["diagnostic_status"],
        "reference_finding": (
            "The project's identity reference matches the daemon 1.9.0 wake endpoint. "
            "The captured post-wake pose and joint states remain non-identity."
        ),
        "unresolved_observability": (
            "Daemon 1.9.0 did not expose the retained live target in these captures, "
            "so the audit cannot classify the residual as target error, calibration "
            "error, mechanical deflection, or another cause."
        ),
        "claim_boundary": (
            "This is a within-unit source-reference comparison, not a vendor tolerance, "
            "calibration, repair diagnosis, or motion authorization."
        ),
        "robot_commands_authorized": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    records = [load_verified_capture(path) for path in args.capture]
    report = audit_post_wake_reference(records)
    path, _, digest = write_report(report, args.output)
    print(f"Post-wake reference audit: {path}")
    print(f"SHA-256: {digest}")
    print(f"Finding: {report['reference_finding']}")
    print("Robot commands authorized: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
