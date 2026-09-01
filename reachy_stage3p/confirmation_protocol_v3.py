"""Final pre-collection frozen protocol for the hardened Stage 3P V4 policy."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from reachy_stage2a.config import PROJECT_ROOT

from .confirmation_protocol_v2 import CONFIRMATION_V2_STEPS, SUCCESS_CRITERIA as V2_CRITERIA


SOURCE_POLICY_FINGERPRINT = (
    "3a89386709b96b7fd979fddb34a7d09cebaabafc6608ade9a27da8adb91b5ce8"
)
SOURCE_POLICY_FREEZE_BUNDLE_SHA256 = (
    "4b43fa93cb851839d30a9c9b29d215854d455f2d5735c3a6c2ebda1ba6b4a40a"
)


CONFIRMATION_V3_STEPS = tuple(
    replace(
        step,
        condition_id=step.condition_id.replace("heldout-v2-", "heldout-v3-"),
        title=step.title.replace("Fresh V2", "Fresh V3"),
    )
    for step in CONFIRMATION_V2_STEPS
)
SUCCESS_CRITERIA = copy.deepcopy(V2_CRITERIA)
MANIFEST_PATH = (
    PROJECT_ROOT / "data/manifests/stage3p_confirmation_protocol_v3.json"
).resolve()


def protocol_payload() -> dict[str, Any]:
    core = {
        "schema": "reachy-stage3p-held-out-vertical-confirmation-v3",
        "status": "FROZEN_FRESH_HELD_OUT_PASSIVE_PROTOCOL_NOT_AUTHORISED_FOR_ACTUATION",
        "frozen_at": "2026-08-29T20:40:00+01:00",
        "source_policy_fingerprint": SOURCE_POLICY_FINGERPRINT,
        "source_policy_freeze_bundle_sha256": SOURCE_POLICY_FREEZE_BUNDLE_SHA256,
        "policy_was_frozen_before_collection": True,
        "supersedes_uncollected_protocol": "data/manifests/stage3p_confirmation_protocol_v2.json",
        "superseded_protocol_human_trials": 0,
        "prior_stage3p_confirmations_excluded_from_validation": True,
        "prior_failed_result_used_only_for_disclosed_offline_development": True,
        "outcomes_cannot_change_acceptance_or_policy": True,
        "encrypted_procedural_audit_required": True,
        "coordinate_frame": {
            "yaw": "front 0 degrees; diagram-left negative; diagram-right positive",
            "pitch": "camera optical axis 0 degrees; up positive; down negative",
            "distance": "1 metre horizontal radius from Reachy camera axis",
        },
        "dynamic_scoring_boundary": {
            "wrong_sign_scored_from_move_cue": True,
            "final_accuracy_and_coverage_scored_after_move_ms": 4000.0,
            "reason": "Human motion occupies intermediate, not final, pitch positions during repositioning.",
        },
        "maintenance_lease_boundary": {
            "duration_after_last_valid_matching_reconfirmation_ms": 10000.0,
            "face_fault_clears_immediately": True,
            "acoustic_conflict_after_association_does_not_refresh_lease": True,
        },
        "steps": [asdict(step) for step in CONFIRMATION_V3_STEPS],
        "success_criteria": SUCCESS_CRITERIA,
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
        raise ValueError("Stage 3P V3 held-out manifest must remain in data/manifests.")
    payload = protocol_payload()
    if destination.exists():
        existing = json.loads(destination.read_text(encoding="utf-8"))
        if existing != payload:
            raise ValueError("A different Stage 3P V3 held-out manifest already exists.")
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return destination


def validate_protocol() -> None:
    if len(CONFIRMATION_V3_STEPS) != 18:
        raise ValueError("Fresh held-out Stage 3P V3 must contain exactly 18 trials.")
    roles = {
        role: sum(step.role == role for step in CONFIRMATION_V3_STEPS)
        for role in {step.role for step in CONFIRMATION_V3_STEPS}
    }
    if roles != {"matching_acquisition": 6, "maintenance_transition": 6, "hard_negative": 6}:
        raise ValueError(f"Unexpected Stage 3P V3 role matrix: {roles}")
    maintenance = [
        step for step in CONFIRMATION_V3_STEPS if step.role == "maintenance_transition"
    ]
    if any(step.transition_at_s != 7.0 or step.duration_s != 15 for step in maintenance):
        raise ValueError("Every Stage 3P V3 maintenance trial must reserve seven seconds for association.")
    if any("within 4 seconds" not in step.instruction for step in maintenance):
        raise ValueError("Every Stage 3P V3 maintenance instruction must declare repositioning time.")


validate_protocol()
