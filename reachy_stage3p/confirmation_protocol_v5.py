"""Fresh passive confirmation protocol for the frozen V5 relative visual servo."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from reachy_stage2a.config import PROJECT_ROOT

from .confirmation_protocol_v3 import CONFIRMATION_V3_STEPS


SOURCE_POLICY_FINGERPRINT = (
    "a78f9a71e4be351e07dbc1725130dc5ad4537df708609d3940ca07e90023ca07"
)
SOURCE_POLICY_FREEZE_BUNDLE_SHA256 = (
    "37da1575cd5ec2417e20cc118fa50b1a850ed8ecf8f53701f78f2af5c16950a7"
)


def _v5_instruction(instruction: str) -> str:
    return (
        instruction
        .replace("fresh vertical tracking test", "held-out relative centering test")
        .replace("the full-screen MOVE cue", "the full-screen MOVE cue behind Reachy")
    )


CONFIRMATION_V5_STEPS = tuple(
    replace(
        step,
        condition_id=step.condition_id.replace("heldout-v3-", "heldout-v5-"),
        title=step.title.replace("Fresh V3", "Fresh V5 relative-servo"),
        instruction=_v5_instruction(step.instruction),
    )
    for step in CONFIRMATION_V3_STEPS
)

SUCCESS_CRITERIA = {
    "instrumentation_quality": {
        "minimum_samples_12_second_trial": 48,
        "minimum_samples_15_second_trial": 60,
        "minimum_valid_doa_pct": 80.0,
        "minimum_fresh_single_face_pct_when_face_expected": 80.0,
        "minimum_eye_landmark_pct_when_face_expected": 80.0,
        "minimum_speech_positive_when_speech_expected": 3,
        "maximum_visible_face_pct_in_no_face_control": 20.0,
    },
    "procedural_audit": {
        "encrypted_local_clip_required_for_every_accepted_trial": True,
        "compliant_audit_verdict_required": True,
        "policy_never_receives_media": True,
    },
    "hard_negative_safety": {"maximum_would_adjust_rows": 0},
    "vertical_direction": {"maximum_wrong_sign_adjustments": 0},
    "bounded_increment": {"maximum_abs_increment_deg": 3.0},
    "static_relative_correction": {
        "required_trials_with_adjustment_per_pitch": 3,
        "repetitions_per_pitch": 3,
    },
    "silent_maintenance": {
        "required_pretransition_associations_per_pitch": 3,
        "maximum_pretransition_adjustment_rows": 0,
        "required_trials_with_adjustment_per_pitch": 3,
        "repetitions_per_pitch": 3,
        "repositioning_interval_after_move_ms": 4000.0,
    },
}
MANIFEST_PATH = (
    PROJECT_ROOT / "data/manifests/stage3p_confirmation_protocol_v5.json"
).resolve()


def protocol_payload() -> dict[str, Any]:
    core = {
        "schema": "reachy-stage3p-held-out-relative-servo-confirmation-v5",
        "status": "FROZEN_FRESH_HELD_OUT_PASSIVE_PROTOCOL_NOT_AUTHORISED_FOR_ACTUATION",
        "frozen_at": "2026-08-29T23:10:00+01:00",
        "source_policy_fingerprint": SOURCE_POLICY_FINGERPRINT,
        "source_policy_freeze_bundle_sha256": SOURCE_POLICY_FREEZE_BUNDLE_SHA256,
        "policy_was_frozen_before_collection": True,
        "prior_stage3p_confirmations_excluded_from_validation": True,
        "prior_failed_results_used_only_for_disclosed_offline_development": True,
        "outcomes_cannot_change_acceptance_or_policy": True,
        "encrypted_procedural_audit_required": True,
        "operator_cue_boundary": {
            "move_cue_at_recording_second": 7.0,
            "screen_should_be_directly_behind_reachy": True,
            "audible_environmental_cue_prohibited": True,
            "reason": "Avoid gaze diversion and avoid contaminating the acoustic/silent phase.",
        },
        "coordinate_frame": {
            "yaw": "front 0 degrees; diagram-left negative; diagram-right positive",
            "pitch": "camera optical axis 0 degrees; up positive; down negative",
            "distance": "1 metre horizontal radius from Reachy camera axis",
        },
        "scoring_boundary": {
            "absolute_pitch_accuracy_is_not_a_gate": True,
            "relative_increment_sign_coverage_and_bounds_are_gates": True,
            "neutral_raw_eye_pitch_deg": 7.5,
            "relative_eye_deadband_deg": 2.5,
            "maximum_abs_increment_deg": 3.0,
            "maintenance_scoring_after_move_ms": 4000.0,
            "pretransition_centre_must_hold": True,
        },
        "steps": [asdict(step) for step in CONFIRMATION_V5_STEPS],
        "success_criteria": copy.deepcopy(SUCCESS_CRITERIA),
        "contains_pixels": False,
        "contains_audio": False,
        "contains_transcript": False,
        "separate_encrypted_audit_sidecar": True,
        "robot_requests": 0,
        "cloud_requests": 0,
        "actuation_commands": 0,
    }
    encoded = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**core, "fingerprint": hashlib.sha256(encoded).hexdigest()}


def write_manifest(path: Path = MANIFEST_PATH) -> Path:
    destination = path.resolve()
    if destination.parent != (PROJECT_ROOT / "data/manifests").resolve():
        raise ValueError("Stage 3P V5 held-out manifest must remain in data/manifests.")
    payload = protocol_payload()
    if destination.exists():
        existing = json.loads(destination.read_text(encoding="utf-8"))
        if existing != payload:
            raise ValueError("A different Stage 3P V5 held-out manifest already exists.")
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return destination


def validate_protocol() -> None:
    if len(CONFIRMATION_V5_STEPS) != 18:
        raise ValueError("Fresh held-out Stage 3P V5 must contain exactly 18 trials.")
    roles = {
        role: sum(step.role == role for step in CONFIRMATION_V5_STEPS)
        for role in {step.role for step in CONFIRMATION_V5_STEPS}
    }
    if roles != {"matching_acquisition": 6, "maintenance_transition": 6, "hard_negative": 6}:
        raise ValueError(f"Unexpected Stage 3P V5 role matrix: {roles}")
    maintenance = [
        step for step in CONFIRMATION_V5_STEPS if step.role == "maintenance_transition"
    ]
    if any(step.transition_at_s != 7.0 or step.duration_s != 15 for step in maintenance):
        raise ValueError("Every Stage 3P V5 maintenance trial must reserve seven seconds for association.")
    if any("full-screen MOVE cue behind Reachy" not in step.instruction for step in maintenance):
        raise ValueError("Every maintenance instruction must prevent gaze diversion at MOVE.")


validate_protocol()
