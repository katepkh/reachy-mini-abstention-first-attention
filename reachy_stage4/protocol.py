"""Frozen protocol definition for the first supervised physical-motion pilot."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .config import (
    DWELL_S,
    HORIZONTAL_FREEZE_PATH,
    MANIFEST_PATH,
    MOVE_ANGLE_DEG,
    MOVE_DURATION_S,
    OFFICIAL_PROTOCOL_VERSION,
    RESTORE_DURATION_S,
    RESTORE_SETTLE_S,
    TARGETED_FREEZE_PATH,
)


TARGETED_FREEZE_BUNDLE_SHA256 = (
    "033afdaf94117ca12c602b46bc28339ea45f8f3acfaa9508620bacaeb732e942"
)
HORIZONTAL_FREEZE_BUNDLE_SHA256 = (
    "d1bd3e7188761fc08cce93c56ecea09d168589d515f71b7e783d347f6f0b0fd8"
)
SUPERSEDED_V1_FINGERPRINT = (
    "3b334523f927c070ded6cfd582b5e675ce9f285897d80f449da902c6e7d909ea"
)
SUPERSEDED_V2_FINGERPRINT = (
    "a88aa5aa2c55933eff6f61718c19ed9d54ea39e80b46094c107d86b6cfa5de2f"
)
SUPERSEDED_V3_FINGERPRINT = (
    "0f9b1e8d076cf3ce6a3d4ca138aa8f07a691fae98543e9ad02db545c021f52af"
)
V3_DIAGNOSTIC_BUNDLE_SHA256 = (
    "be9385727be410964907ac2104b472ebfe34a6574dea5dd0c7b1693c86866693"
)
OFFICIAL_WS_CLIENT_SHA256 = (
    "6cff59fe8c8bf8ff0706ade571906b24852eb85cfb44d8da268615827bc986b6"
)
OFFICIAL_PROTOCOL_SHA256 = (
    "067ee2fe64b2445edaa48f6027a890e559c61d76f896eced0868d81df00011f7"
)
OFFICIAL_LOOK_AT_SHA256 = (
    "c1a59933b498324c7619217d0d16f3bd6fea1f65a946297947f680b29aad7cfa"
)
OFFICIAL_ROBOT_BACKEND_SHA256 = (
    "39031aaf2278d10a7c85079bd03e5a7e5a8c4b055383cae30d28373d2d71128a"
)
OFFICIAL_DAEMON_SHA256 = (
    "24af8189b83eb07a56a1753a9a9f76e31061026a1bf691368498059a7896d156"
)


@dataclass(frozen=True, slots=True)
class PilotStep:
    index: int
    direction: str
    title: str
    instruction: str


PILOT_STEPS = (
    PilotStep(1, "UP", "Head-only 3° up and automatic return", "Stand clear and observe one slow upward movement followed by return to the captured start pose."),
    PilotStep(2, "DOWN", "Head-only 3° down and automatic return", "Stand clear and observe one slow downward movement followed by return to the captured start pose."),
    PilotStep(3, "LEFT", "Head-only 3° left and automatic return", "Stand clear and observe one slow leftward movement followed by return to the captured start pose."),
    PilotStep(4, "RIGHT", "Head-only 3° right and automatic return", "Stand clear and observe one slow rightward movement followed by return to the captured start pose."),
)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def protocol_payload() -> dict[str, Any]:
    core = {
        "schema": "reachy-stage4a-supervised-motion-pilot-protocol-v4",
        "status": "FROZEN_BEFORE_FIRST_V4_ACTUATION",
        "purpose": "Verify four physical direction mappings and exact-pose restoration before any live attention policy is connected.",
        "source_evidence": {
            "targeted_vertical_cue_freeze": TARGETED_FREEZE_PATH.name,
            "targeted_vertical_cue_bundle_sha256": TARGETED_FREEZE_BUNDLE_SHA256,
            "horizontal_v3_freeze": HORIZONTAL_FREEZE_PATH.name,
            "horizontal_v3_bundle_sha256": HORIZONTAL_FREEZE_BUNDLE_SHA256,
            "failed_stage4a_v3_diagnostic_freeze": "stage4a_supervised_motion_pilot_v3_diagnostic_freeze.json",
            "failed_stage4a_v3_diagnostic_bundle_sha256": V3_DIAGNOSTIC_BUNDLE_SHA256,
        },
        "supersedes": {
            "manifest": "stage4a_supervised_motion_pilot_v3.json",
            "fingerprint": SUPERSEDED_V3_FINGERPRINT,
            "prior_v2_fingerprint": SUPERSEDED_V2_FINGERPRINT,
            "prior_v1_fingerprint": SUPERSEDED_V1_FINGERPRINT,
            "reason": "V3 exposed three measurement/geometry defects without weakening any acceptance threshold: it sampled before settling, compared slightly non-orthonormal FK matrices without SO(3) projection, and used an absolute-neutral target instead of a captured-baseline-relative increment. The failed result is frozen byte-for-byte.",
            "read_only_preflight_attempts_before_supersession": 4,
            "physical_motion_trials_before_supersession": 1,
            "zero_command_execution_blocks_before_supersession": 1,
            "head_only_actuation_commands_before_supersession": 2,
            "body_yaw_actuation_commands_before_supersession": 0,
            "antenna_actuation_commands_before_supersession": 0,
            "failed_result_deleted_or_relabelled": False,
        },
        "transport": {
            "official_protocol_version": OFFICIAL_PROTOCOL_VERSION,
            "matches_observed_daemon_version": True,
            "route": "ws://<audited-private-ip>:8000/ws/sdk",
            "task_type": "task/GotoTaskRequest",
            "interpolation": "minjerk",
            "implementation": "minimal audited protocol-compatible client on the already-trusted runtime",
            "official_source_hashes": {
                "reachy_mini/io/ws_client.py": OFFICIAL_WS_CLIENT_SHA256,
                "reachy_mini/io/protocol.py": OFFICIAL_PROTOCOL_SHA256,
                "reachy_mini/vision/look_at.py": OFFICIAL_LOOK_AT_SHA256,
                "reachy_mini/daemon/backend/robot/backend.py": OFFICIAL_ROBOT_BACKEND_SHA256,
                "reachy_mini/daemon/daemon.py": OFFICIAL_DAEMON_SHA256,
            },
        },
        "motion_envelope": {
            "head_only": True,
            "captured_baseline_relative_increment_deg": MOVE_ANGLE_DEG,
            "world_axis_direction_mapping": True,
            "command_poses_projected_to_nearest_rigid_transform": True,
            "minimum_jerk_duration_s": MOVE_DURATION_S,
            "target_settle_before_measurement_s": DWELL_S,
            "restore_duration_s": RESTORE_DURATION_S,
            "restore_settle_before_measurement_s": RESTORE_SETTLE_S,
            "automatic_return_to_captured_pose": True,
            "maximum_one_target_per_preflight_session": True,
        },
        "prohibited": {
            "continuous_control": True,
            "automatic_tracking": True,
            "body_yaw_command": True,
            "antenna_command": True,
            "torque_or_motor_mode_change": True,
            "gravity_compensation_change": True,
            "wobbling_or_head_tracking_change": True,
            "camera_or_microphone_access": True,
            "cloud_request": True,
            "robot_install_or_update": True,
        },
        "acceptance": {
            "daemon_running": True,
            "daemon_version_exactly_1_9_0": True,
            "motor_control_mode_enabled": True,
            "fresh_head_pose_and_status_max_age_s": 2.0,
            "control_loop_frequency_hz_inclusive": [40.0, 60.0],
            "control_loop_max_interval_s": 0.1,
            "control_loop_error_count": 0,
            "serialized_backend_ready_excluded_due_to_frozen_1_9_0_defect": True,
            "rotation_error_metric": "nearest-SO(3) geodesic angle via SVD projection",
            "baseline_neutral_error_max_deg": 1.0,
            "start_pose_near_neutral": True,
            "target_pose_within_frozen_3_degree_envelope": True,
            "measured_target_error_max_deg": 1.5,
            "measured_restore_error_max_deg": 1.0,
            "thresholds_weakened_after_v3_failure": False,
            "operator_observed_correct_direction": True,
            "operator_observed_smooth_motion": True,
            "operator_observed_no_abnormal_noise_or_heat": True,
            "operator_observed_return_to_start": True,
        },
        "steps": [asdict(step) for step in PILOT_STEPS],
        "scientific_boundary": {
            "manual_mechanical_mapping_only": True,
            "does_not_validate_autonomous_tracking": True,
            "does_not_connect_live_policy_evidence_to_motors": True,
            "later_live_pilot_requires_a_separate_frozen_protocol": True,
        },
    }
    return {**core, "fingerprint": hashlib.sha256(_canonical(core)).hexdigest()}


def write_protocol_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    destination = path.resolve()
    if destination.exists():
        raise FileExistsError(f"Stage 4A protocol is already frozen: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = protocol_payload()
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def verify_protocol_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    observed = json.loads(path.read_text(encoding="utf-8"))
    expected = protocol_payload()
    if observed != expected:
        raise ValueError("The frozen Stage 4A protocol manifest has changed.")
    return {
        "verified": True,
        "fingerprint": observed["fingerprint"],
        "steps": len(observed["steps"]),
    }
