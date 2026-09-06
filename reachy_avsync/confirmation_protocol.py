"""Frozen acquisition and analysis design for AV-synchrony confirmation.

This module is declarative and offline.  It creates a content-addressed trial
schedule and never opens a camera, microphone, network, or robot transport.
"""

from __future__ import annotations

import hashlib
import json
import random
from typing import Any


SCHEMA = "reachy-av-synchrony-confirmation-protocol-v1"
RANDOMIZATION_SEED = 730114
TRIAL_DURATION_S = 10
PILOT_PROTOCOL_FINGERPRINT = (
    "afb6794ec5a94a6d6739142dd69e873c1aec2f6df307a8bf4b9b4cf6612e8754"
)
PILOT_CANDIDATE_FINGERPRINT = (
    "586882b1a72b6eff64baebc98556e988a047d2290f4f484178a0aeb07db52e46"
)
PILOT_CANDIDATE_FILE_SHA256 = (
    "b113d15f0384cb9e9cd3dd6b9a5a928978c1d221dba919fa6552b1b27f919590"
)

ROOMS = (
    {
        "id": "room_a",
        "eligibility": "distinct enclosed physical room not used for the V2 pilot",
    },
    {
        "id": "room_b",
        "eligibility": "distinct enclosed physical room not used for the V2 pilot or room_a",
    },
    {
        "id": "room_c",
        "eligibility": "distinct enclosed physical room not used for the V2 pilot, room_a, or room_b",
    },
)

HEADINGS_DEG = (-20, 0, 20)

CONDITIONS = (
    {
        "id": "live_visible_continuous",
        "role": "matching_positive",
        "playback": False,
        "description": "Visible operator speaks naturally from the marked heading.",
    },
    {
        "id": "live_visible_interrupted",
        "role": "matching_positive",
        "playback": False,
        "description": "Visible operator alternates about one second of speech with one second of silence.",
    },
    {
        "id": "silent_face_colocated_playback",
        "role": "hard_negative",
        "playback": True,
        "playback_geometry": "colocated",
        "description": "Visible operator remains silent while consented speech plays beside the face.",
    },
    {
        "id": "silent_mouthing_shifted_playback",
        "role": "hard_negative",
        "playback": True,
        "playback_geometry": "colocated",
        "description": "Visible operator mouths silently out of time while consented speech plays beside the face.",
    },
    {
        "id": "silent_face_opposite_playback",
        "role": "hard_negative",
        "playback": True,
        "playback_geometry": "opposite",
        "description": "Visible operator remains silent while consented speech plays from the opposite mark.",
    },
    {
        "id": "live_speech_plus_opposite_playback",
        "role": "hard_negative",
        "playback": True,
        "playback_geometry": "opposite",
        "description": "Visible operator speaks while an independent consented recording plays from the opposite mark.",
    },
)


def _opposite_heading(visible_heading: int, *, room_index: int, condition_index: int) -> int:
    if visible_heading < 0:
        return 20
    if visible_heading > 0:
        return -20
    # There is no geometric opposite of 0 degrees in the three-heading design.
    # Counterbalance left/right across the two opposite-playback conditions and rooms.
    return -20 if (room_index + condition_index) % 2 == 0 else 20


def canonical_trials() -> list[dict[str, Any]]:
    trials: list[dict[str, Any]] = []
    for room_index, room in enumerate(ROOMS):
        hard_negative_index = 0
        for heading_index, heading in enumerate(HEADINGS_DEG):
            for condition_index, condition in enumerate(CONDITIONS):
                trial: dict[str, Any] = {
                    "trial_id": f"avsync-confirm-{len(trials) + 1:02d}",
                    "room": room["id"],
                    "visible_heading_deg": heading,
                    "condition_id": condition["id"],
                    "role": condition["role"],
                    "duration_s": TRIAL_DURATION_S,
                    "playback_voice_id": None,
                    "playback_heading_deg": None,
                }
                if condition["playback"]:
                    trial["playback_voice_id"] = (
                        "voice_a"
                        if (room_index + heading_index + hard_negative_index) % 2 == 0
                        else "voice_b"
                    )
                    if condition["playback_geometry"] == "colocated":
                        trial["playback_heading_deg"] = heading
                    else:
                        trial["playback_heading_deg"] = _opposite_heading(
                            heading,
                            room_index=room_index,
                            condition_index=condition_index,
                        )
                    hard_negative_index += 1
                trials.append(trial)
    return trials


def randomized_schedule() -> list[dict[str, Any]]:
    randomized: list[dict[str, Any]] = []
    canonical = canonical_trials()
    for room_index, room in enumerate(ROOMS):
        room_trials = [dict(item) for item in canonical if item["room"] == room["id"]]
        random.Random(RANDOMIZATION_SEED + room_index).shuffle(room_trials)
        randomized.extend(room_trials)
    return randomized


def _fingerprint(core: dict[str, Any]) -> str:
    encoded = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def confirmation_protocol_payload() -> dict[str, Any]:
    core: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "FROZEN_BEFORE_CONFIRMATION_DATA_COLLECTION",
        "research_question": (
            "When spatial evidence agrees, can the frozen V2 audio-mouth synchrony "
            "candidate reduce false visible-speaker proposals without unacceptable "
            "loss of matching-trial coverage?"
        ),
        "experimental_unit": "one ten-second trial",
        "predecessor_design_fingerprint": (
            "c61ed6fa70029f5016c567bcb6c6952d6e8dc5f5e1742ad06a2aa731ae165572"
        ),
        "frozen_candidate": {
            "pilot_protocol_fingerprint": PILOT_PROTOCOL_FINGERPRINT,
            "candidate_fingerprint": PILOT_CANDIDATE_FINGERPRINT,
            "candidate_file_sha256": PILOT_CANDIDATE_FILE_SHA256,
            "min_correlation": 0.25,
            "max_abs_lag_ms": 120.0,
            "moving_average_samples": 3,
            "required_stable_windows": 3,
            "max_consensus_gap_ms": 800.0,
            "selection_or_retuning_during_confirmation": "PROHIBITED",
        },
        "rooms": list(ROOMS),
        "room_binding": {
            "deadline": "before the first confirmation preview or capture",
            "private_record_required": True,
            "required_fields": [
                "opaque_room_id",
                "confirmation_not_v2_pilot_room",
                "approximate_dimensions_m",
                "dominant_surface_and_furnishing_description",
                "background_audio_dbfs_10s",
                "camera_mark",
                "microphone_mark",
                "visible_person_marks",
                "playback_marks",
                "room_record_sha256",
            ],
            "failure_rule": "do not collect until all three room records are complete and hashed",
        },
        "voice_binding": {
            "voice_ids": ["voice_a", "voice_b"],
            "allocation": "18 hard-negative trials per voice; two trials per voice in every room-heading block",
            "private_record_required": True,
            "required_fields": [
                "opaque_voice_id",
                "consent_basis",
                "recording_sha256",
                "clip_duration_s",
                "spoken_language",
                "playback_device_make_model",
                "fixed_volume_setting",
            ],
            "stimulus_boundary": "recorded voices are stimuli, not participants",
        },
        "device_binding": {
            "deadline": "before the first confirmation preview or capture",
            "required_fields": [
                "computer_os_and_build",
                "browser_and_version",
                "camera_make_model",
                "microphone_make_model",
                "audio_input_selected",
                "media_device_settings",
                "recorder_sha256",
                "model_and_runtime_hashes",
            ],
            "fixed_rule": (
                "use the same fixed camera and microphone configuration in all rooms; "
                "a headset microphone must be mounted at a fixed mark and must not be worn"
            ),
        },
        "conditions": list(CONDITIONS),
        "headings_deg": list(HEADINGS_DEG),
        "trial_counts": {
            "total": 54,
            "matching_positive": 18,
            "hard_negative": 36,
            "per_room": 18,
            "per_room_heading": 6,
        },
        "canonical_trials": canonical_trials(),
        "randomization": {
            "seed": RANDOMIZATION_SEED,
            "rule": (
                "shuffle the 18 canonical trials within each room once using Python "
                "random.Random(seed + zero_based_room_index).shuffle; never reorder "
                "after preview, quality, or outcome data are visible"
            ),
            "schedule": randomized_schedule(),
        },
        "quality_gates": {
            "minimum_samples": 160,
            "minimum_span_ms": 7000.0,
            "maximum_sample_gap_ms": 160.0,
            "minimum_single_face_fraction": 0.95,
            "multiple_face_rows_allowed": 0,
            "minimum_median_face_scale": 0.16,
            "minimum_audio_dbfs_std": 0.5,
            "minimum_lip_aperture_std_when_motion_required": 0.002,
            "motion_required_conditions": [
                "live_visible_continuous",
                "live_visible_interrupted",
                "silent_mouthing_shifted_playback",
            ],
            "provenance": "unchanged from the successful V2 pilot",
        },
        "exclusions": {
            "decision_timing": "before any candidate or comparator outcome is computed",
            "allowed": [
                "capture did not complete the scheduled duration",
                "required numeric stream is missing or nonfinite",
                "timestamp order, span, sample-count, or sample-gap quality gate failed",
                "single-face fraction, multiple-face, face-scale, or valid-face-gap quality gate failed",
                "predeclared audio or lip dynamic-range quality gate failed",
                "room, device, voice, heading, playback, or condition setup deviated from the frozen card",
                "consent was withdrawn or equipment safety required stopping",
            ],
            "repeat_rule": (
                "retain the failed attempt; correct only the recorded objective issue; "
                "repeat the same scheduled trial; never substitute another condition"
            ),
            "all_attempts_retained": True,
            "condition_removal": "PROHIBITED",
        },
        "analysis": {
            "primary_endpoints": [
                "matching-positive trial coverage",
                "hard-negative trial false-proposal rate",
                "paired hard-negative proposal difference versus frozen Stage 3V spatial policy",
            ],
            "secondary_endpoints": [
                "first-proposal latency",
                "observed abstention duration",
                "wrong-sign proposals",
                "maximum target-heading error",
                "abstention reason distribution",
            ],
            "interval": "two-sided Wilson score interval at nominal 95% over trials",
            "paired_test": "two-sided exact McNemar test over paired hard-negative trials",
            "stratification": "report every endpoint by room, condition, heading, and playback voice",
            "rows_are_independent": False,
            "no_adaptive_stopping": True,
            "no_confirmation_retuning": True,
        },
        "confirmation_rule": {
            "hard_negative_false_proposals": "0 of 36",
            "matching_positive_coverage": "at least 15 of 18",
            "wrong_sign_proposals": 0,
            "maximum_target_error_deg": 8.0,
            "comparative_requirement": (
                "strictly fewer hard-negative trial proposals than the frozen spatial comparator"
            ),
            "all_conditions_required": True,
        },
        "scope": {
            "passive_sensing_only": True,
            "robot_motion_commands": 0,
            "torque_calibration_or_motor_mode_commands": 0,
            "identity_intent_consent_or_authorization_claims": False,
            "physical_safety_claims": False,
        },
        "opening_gate": [
            "three private room bindings complete and hashed",
            "two consented voice-stimulus records complete and hashed",
            "camera, microphone, browser, and recorder versions bound",
            "frozen candidate and acquisition implementation hashes agree",
            "empty confirmation output directory and complete attempt ledger initialized",
            "operator confirms no pilot attempt will be reused",
        ],
    }
    return {**core, "fingerprint": _fingerprint(core)}


__all__ = [
    "CONDITIONS",
    "HEADINGS_DEG",
    "ROOMS",
    "SCHEMA",
    "canonical_trials",
    "confirmation_protocol_payload",
    "randomized_schedule",
]
