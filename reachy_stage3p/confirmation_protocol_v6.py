"""Fresh passive confirmation protocol for the frozen V6 association repair."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from reachy_stage2a.config import PROJECT_ROOT

from .confirmation_protocol_v5 import CONFIRMATION_V5_STEPS, SUCCESS_CRITERIA as V5_SUCCESS_CRITERIA


SOURCE_POLICY_FINGERPRINT = (
    "cc6fc9731d2149a2e273989e6e0dea4caacca5859aee45ccf16d82d1f53b6da1"
)
SOURCE_POLICY_FREEZE_BUNDLE_SHA256 = (
    "464fbe6c038d12a41685d40c7a4d29e7e893ca0f1ad9bf5869ce4054f2bb1caf"
)
SOURCE_FAILED_V5_RESULT_BUNDLE_SHA256 = (
    "73609896e7b1e2667dd5d42a17282fcbf04a076e3e5df65f48b758cf1901433f"
)


CONFIRMATION_V6_STEPS = tuple(
    replace(
        step,
        condition_id=step.condition_id.replace("heldout-v5-", "heldout-v6-"),
        title=step.title.replace("Fresh V5 relative-servo", "Fresh V6 association-repair"),
    )
    for step in CONFIRMATION_V5_STEPS
)

SUCCESS_CRITERIA = copy.deepcopy(V5_SUCCESS_CRITERIA)
MANIFEST_PATH = (
    PROJECT_ROOT / "data/manifests/stage3p_confirmation_protocol_v6.json"
).resolve()


def protocol_payload() -> dict[str, Any]:
    core = {
        "schema": "reachy-stage3p-held-out-association-repair-confirmation-v6",
        "status": "FROZEN_FRESH_HELD_OUT_PASSIVE_PROTOCOL_NOT_AUTHORISED_FOR_ACTUATION",
        "frozen_at": "2026-08-31T00:10:39+01:00",
        "source_policy_fingerprint": SOURCE_POLICY_FINGERPRINT,
        "source_policy_freeze_bundle_sha256": SOURCE_POLICY_FREEZE_BUNDLE_SHA256,
        "source_failed_v5_result_bundle_sha256": SOURCE_FAILED_V5_RESULT_BUNDLE_SHA256,
        "policy_was_frozen_before_collection": True,
        "v5_result_was_frozen_before_v6_development": True,
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
            "association_geometry_error_deg": 13.0,
            "association_consensus_hits": 2,
            "repeated_speech_onset_window_ms": 2500.0,
        },
        "steps": [asdict(step) for step in CONFIRMATION_V6_STEPS],
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
        raise ValueError("Stage 3P V6 held-out manifest must remain in data/manifests.")
    payload = protocol_payload()
    if destination.exists():
        existing = json.loads(destination.read_text(encoding="utf-8"))
        if existing != payload:
            raise ValueError("A different Stage 3P V6 held-out manifest already exists.")
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return destination


def validate_protocol() -> None:
    if len(CONFIRMATION_V6_STEPS) != 18:
        raise ValueError("Fresh held-out Stage 3P V6 must contain exactly 18 trials.")
    roles = {
        role: sum(step.role == role for step in CONFIRMATION_V6_STEPS)
        for role in {step.role for step in CONFIRMATION_V6_STEPS}
    }
    if roles != {"matching_acquisition": 6, "maintenance_transition": 6, "hard_negative": 6}:
        raise ValueError(f"Unexpected Stage 3P V6 role matrix: {roles}")
    maintenance = [
        step for step in CONFIRMATION_V6_STEPS if step.role == "maintenance_transition"
    ]
    if any(step.transition_at_s != 7.0 or step.duration_s != 15 for step in maintenance):
        raise ValueError("Every Stage 3P V6 maintenance trial must reserve seven seconds for association.")
    if any("full-screen MOVE cue behind Reachy" not in step.instruction for step in maintenance):
        raise ValueError("Every V6 maintenance instruction must prevent gaze diversion at MOVE.")


validate_protocol()
