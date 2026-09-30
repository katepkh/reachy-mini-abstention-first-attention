"""Frozen v2 no-motion pilot for the commissioned joint shadow instrument.

This module defines trial order and analysis selection boundaries only.  It
opens no sensors or network connections, writes no files, and grants no motion
or response authority.
"""

from __future__ import annotations

import hashlib
import json
import random
from typing import Any

from .joint_instrument import JOINT_CONDITIONS, JOINT_INSTRUMENT_SPEC_V1


JOINT_PILOT_RANDOMIZATION_SEED = 20260930
JOINT_PILOT_DURATION_S = 10
JOINT_PILOT_REPETITIONS = 3
JOINT_PILOT_CONDITION_IDS = (
    "live_visible_continuous",
    "live_visible_interrupted",
    "silent_face_phone_playback",
    "silent_mouthing_unrelated_playback",
    "visible_silence",
    "speech_without_usable_face",
    "spatial_conflict",
)
JOINT_PILOT_INSTRUCTION_OVERRIDES = {
    "silent_face_phone_playback": (
        "Remain silent with one face visible while the fixed phone recording plays "
        "from the colocated mark within 10 degrees of the face heading."
    ),
    "silent_mouthing_unrelated_playback": (
        "Mouth silently and deliberately out of time with the fixed phone recording; "
        "keep the phone on the colocated mark within 10 degrees of the face heading."
    ),
    "speech_without_usable_face": (
        "Speak live while keeping every face outside the camera view; do not use playback."
    ),
    "spatial_conflict": (
        "Remain silent with one face visible while the fixed phone recording plays from "
        "the conflict mark at least 45 degrees away from the face heading."
    ),
}


def _conditions_by_id() -> dict[str, dict[str, str]]:
    conditions = {str(item["id"]): dict(item) for item in JOINT_CONDITIONS}
    for condition_id, instruction in JOINT_PILOT_INSTRUCTION_OVERRIDES.items():
        conditions[condition_id]["instruction"] = instruction
    return conditions


def canonical_joint_pilot_trials() -> list[dict[str, Any]]:
    conditions = _conditions_by_id()
    trials: list[dict[str, Any]] = []
    for repetition in range(1, JOINT_PILOT_REPETITIONS + 1):
        split = "development" if repetition <= 2 else "internal_validation"
        for condition_id in JOINT_PILOT_CONDITION_IDS:
            condition = conditions[condition_id]
            trials.append(
                {
                    "trial_id": f"joint-shadow-pilot-v2-{len(trials) + 1:02d}",
                    "condition_id": condition_id,
                    "role": condition["role"],
                    "repetition": repetition,
                    "split": split,
                    "duration_s": JOINT_PILOT_DURATION_S,
                    "instruction": condition["instruction"],
                }
            )
    return trials


def randomized_joint_pilot_trials() -> list[dict[str, Any]]:
    """Return a frozen block-randomized order with every condition per block."""

    canonical = canonical_joint_pilot_trials()
    rng = random.Random(JOINT_PILOT_RANDOMIZATION_SEED)
    schedule: list[dict[str, Any]] = []
    for repetition in range(1, JOINT_PILOT_REPETITIONS + 1):
        block = [dict(item) for item in canonical if item["repetition"] == repetition]
        rng.shuffle(block)
        schedule.extend(block)
    return [
        {**trial, "schedule_index": index}
        for index, trial in enumerate(schedule, start=1)
    ]


def joint_pilot_protocol_payload() -> dict[str, Any]:
    core: dict[str, Any] = {
        "schema": "reachy-joint-shadow-no-motion-pilot-v2",
        "status": "V2_STRUCTURE_AND_ANALYSIS_FROZEN_PRIVATE_BINDINGS_REQUIRED",
        "purpose": (
            "Determine whether spatial agreement plus audio-mouth synchrony can retain "
            "visible live speech while rejecting phone playback and conflicting cues."
        ),
        "experimental_unit": "one ten-second command-free joint numeric capture",
        "instrument_fingerprint": JOINT_INSTRUMENT_SPEC_V1.payload()["fingerprint"],
        "commissioning_boundary": (
            "The passing commissioning capture establishes observability only and is "
            "excluded from pilot fitting and internal validation."
        ),
        "revision_from_v1": {
            "v1_status": "INVALID_PROTOCOL_GEOMETRY_EXCLUDED_FROM_ANALYSIS",
            "v1_trial_ids_reusable": False,
            "v1_attempts_reusable": False,
            "unchanged_design": (
                "seven conditions, three balanced blocks, development repetitions 1-2, "
                "one-shot internal validation repetition 3, candidate grid, baselines, and "
                "zero-motion/zero-response boundary"
            ),
            "changed_design": (
                "new trial IDs and randomization seed; face-scale acquisition threshold "
                "corrected from 0.16 to 0.06; recorder reports the same condition-specific "
                "quality gate as the offline analyzer"
            ),
            "independent_threshold_basis": (
                "At the fixed one-metre geometry and approximately 60-degree horizontal "
                "camera field of view, a roughly 63 mm inter-eye distance projects to about "
                "0.06 of image width. Two pre-pilot commissioning captures had median "
                "normalized inter-eye scales 0.1344 and 0.0687. Pilot-v1 outcomes were not "
                "used to select the v2 threshold."
            ),
        },
        "conditions": [
            _conditions_by_id()[condition_id]
            for condition_id in JOINT_PILOT_CONDITION_IDS
        ],
        "canonical_trials": canonical_joint_pilot_trials(),
        "randomized_schedule": randomized_joint_pilot_trials(),
        "randomization": {
            "seed": JOINT_PILOT_RANDOMIZATION_SEED,
            "method": (
                "three consecutive blocks; each condition appears once per block; "
                "order shuffled deterministically within each block"
            ),
        },
        "splits": {
            "development": "repetitions 1 and 2 only",
            "internal_validation": (
                "repetition 3; evaluated once after the development setting is frozen"
            ),
        },
        "quality_gates": {
            "minimum_samples": 160,
            "minimum_span_ms": 7000.0,
            "maximum_sample_gap_ms": 160.0,
            "minimum_single_face_fraction_when_required": 0.95,
            "multiple_face_rows_allowed": 0,
            "minimum_doa_valid_fraction": 0.80,
            "maximum_p95_doa_age_ms": 650.0,
            "minimum_median_face_scale_when_required": 0.06,
            "minimum_audio_dbfs_std_when_speech_required": 0.5,
            "minimum_lip_aperture_std_when_motion_required": 0.002,
            "minimum_doa_speech_fraction_when_speech_required": 0.25,
            "maximum_doa_speech_fraction_for_visible_silence": 0.10,
            "maximum_usable_face_fraction_for_unavailable_face_control": 0.05,
            "minimum_spatial_conflict_deg": 40.0,
            "failed_capture_rule": (
                "retain the failed attempt privately, correct only the objective issue, "
                "and repeat the same scheduled trial before advancing"
            ),
        },
        "candidate_grid": {
            "minimum_synchrony_correlation": [0.15, 0.20, 0.25, 0.30, 0.35],
            "maximum_absolute_lag_ms": [120.0, 240.0, 360.0, 480.0, 600.0],
            "moving_average_samples": [1, 3, 5],
            "maximum_median_spatial_error_deg": [10.0, 15.0, 20.0, 30.0],
            "note": (
                "The wider lag grid is an instrument-transfer diagnostic. A wider lag "
                "is not accepted unless every development hard negative still abstains."
            ),
        },
        "development_selection_rule": [
            "use only repetitions 1 and 2",
            "require every development capture to pass its objective quality gates",
            "require zero proposals for every development hard-negative/control trial",
            "require at least three proposals across the four development positives",
            "maximize positive coverage",
            "then prefer higher correlation threshold",
            "then prefer tighter spatial threshold",
            "then prefer narrower lag window",
            "then prefer less smoothing",
            "if no setting qualifies, conclude pilot failure without relaxing a gate",
        ],
        "internal_validation_rule": [
            "freeze the development-selected setting before opening repetition 3",
            "evaluate repetition 3 exactly once",
            "require both matching-positive trials to propose",
            "require every hard-negative/control trial to abstain",
            "otherwise stop and revise the method in a new protocol version",
        ],
        "baselines": {
            "acoustic_only": "proposal from DoA speech activity without face synchrony",
            "visual_activity_only": "proposal from lip activity without audio synchrony",
            "speech_plus_mouth_activity": (
                "proposal from simultaneous speech and mouth activity without temporal synchrony"
            ),
            "spatial_only": "proposal from face-DoA agreement without synchrony",
            "synchrony_only": "proposal from audio-mouth synchrony without spatial agreement",
            "non_abstaining_visible_face": "proposal whenever one usable face is visible",
            "fused_abstaining": "proposal only when speech, spatial and synchrony gates pass",
        },
        "capture_constraints": {
            "fixed_laptop_and_reachy_marks": True,
            "fixed_phone_playback_mark_and_volume": True,
            "one_face_maximum_except_unavailable_face_control": True,
            "no_robot_application": True,
            "motion_commands": 0,
            "response_commands": 0,
            "raw_media_saved": False,
            "raw_media_uploaded": False,
        },
        "opening_gate": {
            "analysis_code": "IMPLEMENTED_AND_CONTENT_ADDRESSED",
            "playback_stimulus_sha256": "REQUIRED_VIA_PRIVATE_BINDING",
            "phone_make_model_volume_and_two_marks": "REQUIRED_VIA_PRIVATE_BINDING",
            "room_laptop_reachy_camera_and_operator_marks": "REQUIRED_VIA_PRIVATE_BINDING",
            "pilot_fingerprint_in_every_trial": "ENFORCED_BY_RECORDER",
            "private_binding_manifest": "REQUIRED_AND_VERIFIED_BY_COLLECTION_GATE",
            "note": (
                "These bindings are required before trial 1. Their values may remain "
                "private, but they must be fixed and checked across all 21 captures."
            ),
        },
        "claim_boundary": (
            "This is an engineering pilot, not a confirmation study. It cannot establish "
            "generalization, publication-level accuracy, safe motion, attention hold, "
            "audible response, or end-to-end robot behaviour."
        ),
    }
    encoded = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**core, "fingerprint": hashlib.sha256(encoded).hexdigest()}


def validate_joint_pilot_protocol() -> None:
    conditions = _conditions_by_id()
    if not set(JOINT_PILOT_CONDITION_IDS).issubset(conditions):
        raise ValueError("The joint pilot references an unknown condition.")
    canonical = canonical_joint_pilot_trials()
    schedule = randomized_joint_pilot_trials()
    if len(canonical) != 21 or len({item["trial_id"] for item in canonical}) != 21:
        raise ValueError("The joint pilot must contain twenty-one unique trials.")
    if [item["schedule_index"] for item in schedule] != list(range(1, 22)):
        raise ValueError("Schedule indices must be consecutive.")
    if {item["trial_id"] for item in schedule} != {item["trial_id"] for item in canonical}:
        raise ValueError("The randomized schedule must contain every canonical trial once.")
    for repetition in range(1, JOINT_PILOT_REPETITIONS + 1):
        block = [item for item in schedule if item["repetition"] == repetition]
        if {item["condition_id"] for item in block} != set(JOINT_PILOT_CONDITION_IDS):
            raise ValueError("Every randomized block must contain each condition exactly once.")
    payload = joint_pilot_protocol_payload()
    constraints = payload["capture_constraints"]
    if constraints["motion_commands"] or constraints["response_commands"]:
        raise ValueError("The joint pilot must remain command-free.")


validate_joint_pilot_protocol()
