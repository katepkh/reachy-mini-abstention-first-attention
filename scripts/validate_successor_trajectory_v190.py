#!/usr/bin/env python3
"""Reconstruct the proposed successor path with exact Reachy Mini 1.9.0 code.

Run this only in an isolated Python environment containing the official 1.9.0
wheel and its exact Rust kinematics dependency.  The script opens no socket and
contains no robot command path.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any
import zipfile

import numpy as np
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from reachy_stage4.config import MOVE_DURATION_S
from reachy_stage4.successor_review import candidate_target_pose
from reachy_stage4.trajectory_review import (
    JOINT_NAMES,
    SCHEMA_VERSION,
    STATUS_OFFLINE,
    analyze_joint_margins,
    reconstruct_ideal_leg_v190,
)


EXPECTED_WHEEL_SHA256 = "9d3f8551c42bd12b43f47a1f3fe5e8c39ca0c2ff6d02c27b094ed0f5586c7655"
EXPECTED_REACHY_VERSION = "1.9.0"
EXPECTED_RUST_KINEMATICS_VERSION = "1.0.3"
SOURCE_MEMBERS = (
    "reachy_mini/utils/interpolation.py",
    "reachy_mini/motion/goto.py",
    "reachy_mini/kinematics/analytical_kinematics.py",
    "reachy_mini/daemon/backend/abstract.py",
    "reachy_mini/assets/config/hardware_config.yaml",
    "reachy_mini/assets/kinematics_data.json",
)
EXPECTED_RAW_STEWART_LIMITS = (
    (1502, 2958),
    (1138, 2844),
    (1502, 2958),
    (1138, 2594),
    (1252, 2958),
    (1138, 2594),
)
TICKS_PER_REVOLUTION = 4096.0
CENTRE_TICK = 2048.0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_sidecar(path: Path) -> str:
    sidecar = path.with_suffix(path.suffix + ".sha256")
    expected = sidecar.read_text(encoding="utf-8").split()[0].lower()
    observed = _sha256(path)
    if observed != expected:
        raise RuntimeError(f"Baseline SHA-256 mismatch: {observed} != {expected}")
    return observed


def _verify_exact_install(wheel: Path) -> tuple[dict[str, Any], Path]:
    wheel_hash = _sha256(wheel)
    if wheel_hash != EXPECTED_WHEEL_SHA256:
        raise RuntimeError(f"Unexpected Reachy wheel SHA-256: {wheel_hash}")
    reachy_version = importlib.metadata.version("reachy-mini")
    rust_version = importlib.metadata.version("reachy-mini-rust-kinematics")
    if reachy_version != EXPECTED_REACHY_VERSION:
        raise RuntimeError(f"Expected reachy-mini 1.9.0, found {reachy_version}")
    if rust_version != EXPECTED_RUST_KINEMATICS_VERSION:
        raise RuntimeError(
            f"Expected reachy-mini-rust-kinematics 1.0.3, found {rust_version}"
        )

    import reachy_mini

    installed_root = Path(reachy_mini.__file__).resolve().parent
    source_hashes: dict[str, Any] = {}
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        for member in SOURCE_MEMBERS:
            if member not in names:
                raise RuntimeError(f"Wheel member missing: {member}")
            wheel_bytes = archive.read(member)
            installed_bytes = (installed_root / member.removeprefix("reachy_mini/")).read_bytes()
            if wheel_bytes != installed_bytes:
                raise RuntimeError(f"Installed source differs byte-for-byte: {member}")
            source_hashes[member] = hashlib.sha256(wheel_bytes).hexdigest()

    return {
        "reachy_mini_version": reachy_version,
        "reachy_mini_rust_kinematics_version": rust_version,
        "numpy_version": importlib.metadata.version("numpy"),
        "scipy_version": importlib.metadata.version("scipy"),
        "wheel_filename": wheel.name,
        "wheel_sha256": wheel_hash,
        "installed_sources_byte_equal_to_wheel": True,
        "source_sha256": source_hashes,
    }, installed_root


def _joint_bounds(installed_root: Path) -> tuple[dict[str, tuple[float, float]], dict[str, Any]]:
    config_path = installed_root / "assets/config/hardware_config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    motors = config["motors"]
    raw_limits: list[tuple[int, int]] = []
    for index in range(1, 7):
        motor = motors[index][f"stewart_{index}"]
        raw_limits.append((int(motor["lower_limit"]), int(motor["upper_limit"])))
    if tuple(raw_limits) != EXPECTED_RAW_STEWART_LIMITS:
        raise RuntimeError(f"Unexpected configured Stewart limits: {raw_limits}")

    radians_per_tick = 2.0 * np.pi / TICKS_PER_REVOLUTION
    bounds: dict[str, tuple[float, float]] = {
        # This is the analytical IK safe bound, not the full raw body servo range.
        "body_yaw": (float(np.deg2rad(-160.0)), float(np.deg2rad(160.0)))
    }
    derived_deg: dict[str, list[float]] = {}
    for index, (lower_tick, upper_tick) in enumerate(raw_limits, start=1):
        lower = (lower_tick - CENTRE_TICK) * radians_per_tick
        upper = (upper_tick - CENTRE_TICK) * radians_per_tick
        name = f"stewart_{index}"
        bounds[name] = (float(lower), float(upper))
        derived_deg[name] = [float(np.degrees(lower)), float(np.degrees(upper))]
    return bounds, {
        "body_yaw_deg": [-160.0, 160.0],
        "body_yaw_source": "AnalyticalKinematics.inverse_kinematics_safe max_body_yaw",
        "stewart_raw_ticks": {f"stewart_{i + 1}": list(value) for i, value in enumerate(raw_limits)},
        "stewart_degrees_from_2048_at_4096_ticks_per_revolution": derived_deg,
        "stewart_source": "official 1.9.0 assets/config/hardware_config.yaml",
    }


def _json_ready(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def _write_immutable(path: Path, payload: dict[str, Any]) -> str:
    destination = path.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(_json_ready(payload), indent=2, sort_keys=True).encode("utf-8") + b"\n"
    digest = hashlib.sha256(encoded).hexdigest()
    sidecar = destination.with_suffix(destination.suffix + ".sha256")
    with destination.open("xb") as stream:
        stream.write(encoded)
    try:
        with sidecar.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(f"{digest}  {destination.name}\n")
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return digest


def reconstruct(wheel: Path, baseline_capture: Path) -> dict[str, Any]:
    environment, installed_root = _verify_exact_install(wheel.resolve())
    baseline_hash = _verify_sidecar(baseline_capture.resolve())
    capture = json.loads(baseline_capture.read_text(encoding="utf-8"))
    frame = capture["stream_frames"][-1]
    baseline = np.asarray(frame["head_pose"]["matrix_row_major"], dtype=np.float64).reshape(4, 4)
    # The proposed successor explicitly projects the measured FK matrix to SO(3).
    from reachy_stage4.safety import rigid_pose

    baseline = rigid_pose(baseline)
    body_yaw = float(frame["body_yaw_rad"])
    present_joints = np.asarray(frame["head_joints_rad"], dtype=np.float64)
    bounds, bounds_provenance = _joint_bounds(installed_root)

    from reachy_mini.kinematics.analytical_kinematics import AnalyticalKinematics
    from reachy_mini.motion.goto import GotoMove
    from reachy_mini.utils.interpolation import InterpolationTechnique

    kinematics = AnalyticalKinematics(automatic_body_yaw=True)

    def ik(pose: np.ndarray, requested_body_yaw: float) -> np.ndarray:
        return kinematics.ik(pose, body_yaw=requested_body_yaw, check_collision=False)

    directions: dict[str, Any] = {}
    maximum_crosscheck_error = 0.0
    for direction in ("UP", "DOWN", "LEFT", "RIGHT"):
        target = candidate_target_pose(baseline, direction)
        direction_legs: dict[str, Any] = {}
        for leg_name, start, end in (
            ("target", baseline, target),
            ("nominal_return", target, baseline),
        ):
            leg = reconstruct_ideal_leg_v190(
                start,
                end,
                start_body_yaw=body_yaw,
                target_body_yaw=body_yaw,
                duration_s=MOVE_DURATION_S,
                sample_hz=100.0,
            )
            official = GotoMove(
                start_head_pose=start,
                target_head_pose=end,
                start_antennas=np.zeros(2),
                target_antennas=None,
                start_body_yaw=body_yaw,
                target_body_yaw=None,
                duration=MOVE_DURATION_S,
                method=InterpolationTechnique.MIN_JERK,
            )
            official_poses = np.stack(
                [official.evaluate(float(t))[0] for t in leg["times_s"]]
            )
            crosscheck = float(np.max(np.abs(leg["poses"] - official_poses)))
            maximum_crosscheck_error = max(maximum_crosscheck_error, crosscheck)
            if crosscheck > 1e-12:
                raise RuntimeError(f"1.9.0 trajectory cross-check failed: {crosscheck}")
            margin = analyze_joint_margins(
                leg,
                inverse_kinematics=ik,
                joint_bounds_rad=bounds,
            )
            margin["joint_positions_rad"] = margin["joint_positions_rad"].tolist()
            direction_legs[leg_name] = {
                "official_goto_max_absolute_pose_element_difference": crosscheck,
                "trajectory": leg,
                "joint_margin_analysis": margin,
            }
        directions[direction] = {
            "candidate_target_pose": target,
            "legs": direction_legs,
        }

    exact_baseline_ik = ik(baseline, body_yaw)
    return {
        "schema": SCHEMA_VERSION,
        "status": STATUS_OFFLINE,
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "environment": environment,
        "baseline": {
            "capture_filename": baseline_capture.name,
            "capture_sha256": baseline_hash,
            "capture_schema": capture.get("schema"),
            "selected_stream_frame_index": int(frame["index"]),
            "pose_projected_to_nearest_so3": True,
            "pose": baseline,
            "body_yaw_rad": body_yaw,
            "recorded_present_joints_rad": present_joints,
            "exact_1_9_0_ik_joints_rad": exact_baseline_ik,
            "recorded_minus_exact_ik_joints_rad": present_joints - exact_baseline_ik,
        },
        "joint_bounds": bounds_provenance,
        "directions": directions,
        "crosscheck": {
            "maximum_absolute_pose_element_difference_vs_official_GotoMove": maximum_crosscheck_error,
            "tolerance": 1e-12,
            "all_samples_within_tolerance": True,
        },
        "scope": {
            "exact": (
                "continuous minimum-jerk/yaw-scalar pose law and analytical IK from the "
                "byte-verified official 1.9.0 install on the stated inclusive grid"
            ),
            "not_exact": (
                "live scheduler timestamps, endpoint write, tracking error, collision, load, "
                "thermal state, cable routing, and a return from a measured rather than nominal target"
            ),
            "nominal_return_requires_separate_authorization": True,
        },
        "transport_audit": {
            "network_connections": 0,
            "robot_connections": 0,
            "robot_commands_authorized": 0,
            "robot_commands_sent": 0,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--baseline-capture", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = reconstruct(args.wheel, args.baseline_capture)
    digest = _write_immutable(args.output, report)
    summary = {
        direction: {
            leg: details["joint_margin_analysis"]["minimum_margin_deg"]
            for leg, details in result["legs"].items()
        }
        for direction, result in report["directions"].items()
    }
    print(json.dumps({"output": str(args.output), "sha256": digest, "minimum_joint_margin_deg": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
