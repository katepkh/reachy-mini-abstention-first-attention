"""Frozen held-out confirmation protocol for the revised Stage 3V policy."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .config import PROJECT_ROOT
from .protocol import VALIDATION_STEPS
from .revised_policy import FROZEN_REVISED_POLICY


CONFIRMATION_STEPS = VALIDATION_STEPS
CONFIRMATION_MANIFEST_PATH = (
    PROJECT_ROOT / "data" / "manifests" / "stage3v_confirmation_protocol_v1.json"
).resolve()
CONFIRMATION_SUCCESS_CRITERIA = {
    "instrumentation_quality": {
        "minimum_samples": 48,
        "nominal_samples": 60,
        "minimum_valid_pct": 80.0,
        "minimum_single_face_pct": 60.0,
        "maximum_face_age_ms": 1500.0,
        "minimum_fresh_single_face_pct": 80.0,
        "minimum_speech_positive_matching": 3,
        "minimum_speech_positive_mismatch": 3,
    },
    "procedural_quality": {
        "operator_attestation_required": True,
        "audit_review_required_when_audit_mode_selected": True,
        "noncompliant_attempt_is_saved_but_not_accepted": True,
    },
    "shadow_safety": {"maximum_hard_negative_would_move_rows": 0},
    "shadow_direction": {
        "minimum_positive_trials_with_move_per_heading": 2,
        "repetitions_per_heading": 3,
        "maximum_target_error_deg": 8.0,
        "maximum_wrong_sign_moves": 0,
    },
}


def confirmation_protocol_payload() -> dict[str, Any]:
    core = {
        "schema": "reachy-stage3v-held-out-confirmation-protocol-v1",
        "status": "FROZEN_AWAITING_NEW_HELD_OUT_COLLECTION",
        "development_dataset_reuse_forbidden": True,
        "coordinate_frame": (
            "front=0; diagram-left=negative; diagram-right=positive; stored camera-right "
            "bearings are multiplied by -1 before fusion"
        ),
        "steps": [asdict(step) for step in CONFIRMATION_STEPS],
        "policy": FROZEN_REVISED_POLICY.payload(),
        "success_criteria": CONFIRMATION_SUCCESS_CRITERIA,
        "data_modes": {
            "privacy_validation": {
                "main_dataset_contains_media": False,
                "operator_attestation_required": True,
            },
            "development_audit": {
                "main_dataset_contains_media": False,
                "separate_encrypted_local_media_sidecar": True,
                "cloud_transfer": False,
                "retention_is_bounded": True,
                "review_before_acceptance": True,
            },
        },
        "actuation_commands": 0,
        "cloud_requests": 0,
    }
    encoded = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**core, "fingerprint": hashlib.sha256(encoded).hexdigest()}


def validate_confirmation_protocol() -> None:
    if len(CONFIRMATION_STEPS) != 18:
        raise ValueError("Held-out Stage 3V confirmation must contain 18 trials.")
    if CONFIRMATION_SUCCESS_CRITERIA["instrumentation_quality"]["minimum_samples"] < 48:
        raise ValueError("Held-out confirmation must retain at least 80% of nominal 5 Hz samples.")


validate_confirmation_protocol()


def write_confirmation_manifest(path: Path = CONFIRMATION_MANIFEST_PATH) -> dict[str, Any]:
    payload = confirmation_protocol_payload()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload
