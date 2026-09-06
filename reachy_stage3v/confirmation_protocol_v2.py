"""Frozen independent confirmation protocol for the Stage 3V V2 policy."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .config import PROJECT_ROOT
from .protocol import VALIDATION_STEPS
from .revised_policy_v2 import FROZEN_REVISED_POLICY_V2


CONFIRMATION_V2_STEPS = VALIDATION_STEPS
CONFIRMATION_V2_MANIFEST_PATH = (
    PROJECT_ROOT / "data" / "manifests" / "stage3v_confirmation_protocol_v2.json"
).resolve()
CONFIRMATION_V2_SUCCESS_CRITERIA = {
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


def confirmation_v2_protocol_payload() -> dict[str, Any]:
    core = {
        "schema": "reachy-stage3v-held-out-confirmation-protocol-v2",
        "status": "FROZEN_AWAITING_NEW_INDEPENDENT_V2_COLLECTION",
        "prior_dataset_reuse_forbidden": ["data/stage3v", "data/stage3v_confirmation"],
        "new_data_directory": "data/stage3v_confirmation_v2",
        "coordinate_frame": (
            "front=0; diagram-left=negative; diagram-right=positive; stored camera-right "
            "bearings are multiplied by -1 before fusion"
        ),
        "steps": [asdict(step) for step in CONFIRMATION_V2_STEPS],
        "policy": FROZEN_REVISED_POLICY_V2.payload(),
        "success_criteria": CONFIRMATION_V2_SUCCESS_CRITERIA,
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


def validate_confirmation_v2_protocol() -> None:
    if len(CONFIRMATION_V2_STEPS) != 18:
        raise ValueError("Held-out Stage 3V V2 confirmation must contain 18 trials.")
    if CONFIRMATION_V2_SUCCESS_CRITERIA["instrumentation_quality"]["minimum_samples"] < 48:
        raise ValueError("V2 confirmation must retain at least 80% of nominal 5 Hz samples.")
    if FROZEN_REVISED_POLICY_V2.speech_latch_ms != 800.0:
        raise ValueError("The predeclared V2 speech latch changed.")


validate_confirmation_v2_protocol()


def write_confirmation_v2_manifest(
    path: Path = CONFIRMATION_V2_MANIFEST_PATH,
) -> dict[str, Any]:
    payload = confirmation_v2_protocol_payload()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload
