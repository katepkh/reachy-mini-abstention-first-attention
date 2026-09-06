"""Frozen design for a future passive audio–mouth synchrony falsification study."""

from __future__ import annotations

import hashlib
import json
import random
from itertools import product
from typing import Any


ROOMS = ("room_a", "room_b", "room_c")
HEADINGS_DEG = (-20, 0, 20)
CONDITIONS = (
    {
        "id": "live_visible_continuous",
        "role": "matching_positive",
        "description": "Visible operator speaks naturally from the marked heading.",
    },
    {
        "id": "live_visible_interrupted",
        "role": "matching_positive",
        "description": "Visible operator alternates short speech and natural pauses from the marked heading.",
    },
    {
        "id": "silent_face_colocated_playback",
        "role": "hard_negative",
        "description": "Visible operator remains silent while a fixed playback source beside the face emits speech.",
    },
    {
        "id": "silent_mouthing_shifted_playback",
        "role": "hard_negative",
        "description": "Visible operator mouths silently while a deliberately time-shifted fixed playback source beside the face emits speech.",
    },
    {
        "id": "silent_face_opposite_playback",
        "role": "hard_negative",
        "description": "Visible operator remains silent while playback is emitted from the opposite marked heading.",
    },
    {
        "id": "live_speech_plus_opposite_playback",
        "role": "hard_negative",
        "description": "Visible operator speaks while an independent recording plays from the opposite heading; the intended response is abstention under source overlap.",
    },
)
RANDOMIZATION_SEED = 730114


def confirmation_trials() -> list[dict[str, Any]]:
    trials: list[dict[str, Any]] = []
    for index, (room, heading, condition) in enumerate(product(ROOMS, HEADINGS_DEG, CONDITIONS), 1):
        trials.append(
            {
                "trial_id": f"avsync-confirm-{index:02d}",
                "room": room,
                "heading_deg": heading,
                "condition_id": condition["id"],
                "role": condition["role"],
            }
        )
    return trials


def randomized_confirmation_trials() -> list[dict[str, Any]]:
    """Return the exact frozen within-room schedule."""

    canonical = confirmation_trials()
    ordered: list[dict[str, Any]] = []
    for room_index, room in enumerate(ROOMS):
        room_trials = [dict(trial) for trial in canonical if trial["room"] == room]
        random.Random(RANDOMIZATION_SEED + room_index).shuffle(room_trials)
        ordered.extend(room_trials)
    return ordered


def protocol_payload() -> dict[str, Any]:
    core = {
        "schema": "reachy-av-synchrony-falsification-protocol-v1",
        "status": "DESIGN_FROZEN_BEFORE_PROTOCOL_DATA_COLLECTION_REQUIRES_POST_PILOT_THRESHOLD_FREEZE",
        "research_question": (
            "When acoustic direction and face position agree, can derived audio–mouth synchrony reduce false visible-speaker proposals without unacceptable loss of matching-trial coverage?"
        ),
        "claims_excluded": [
            "speaker identity",
            "consent or authorization",
            "intent",
            "general active-speaker detection performance",
            "mechanical safety",
        ],
        "experimental_unit": "accepted trial",
        "development_block": {
            "minimum_trials": 12,
            "separate_from_confirmation": True,
            "purpose": "select synchrony thresholds and verify instrumentation only",
            "rule": "Freeze selected numeric thresholds and code hash in a new manifest before opening confirmation outcomes.",
        },
        "confirmation_design": {
            "rooms": list(ROOMS),
            "room_requirement": "three acoustically distinct physical spaces or configurations, documented before analysis",
            "headings_deg": list(HEADINGS_DEG),
            "conditions": list(CONDITIONS),
            "trials": confirmation_trials(),
            "total_trials": 54,
            "matching_positive_trials": 18,
            "hard_negative_trials": 36,
            "randomization_seed": RANDOMIZATION_SEED,
            "randomization_rule": "Within each room, shuffle the 18 room-specific trial IDs once with Python random.Random(seed + zero_based_room_index).shuffle; do not reorder after outcomes are visible.",
            "randomized_schedule": randomized_confirmation_trials(),
            "voice_stimuli": "Use at least two consented recorded voices; recordings are stimuli, not participant counts.",
        },
        "comparators": [
            "frozen Stage 3V V3 spatial compatibility policy",
            "visual-only temporal baseline",
            "audio-only front-hypothesis baseline",
            "spatial policy plus newly frozen synchrony gate",
        ],
        "primary_endpoints": [
            "matching-positive trial coverage",
            "hard-negative trial false-proposal rate",
            "paired hard-negative outcome difference versus frozen spatial policy",
        ],
        "secondary_endpoints": [
            "first-proposal latency",
            "observed abstention duration",
            "wrong-sign proposals",
            "maximum target-heading error",
            "abstention reason distribution",
        ],
        "confirmation_success_rule": {
            "synchrony_hard_negative_false_proposals": "0 of 36",
            "synchrony_matching_positive_coverage": "at least 15 of 18",
            "wrong_sign_proposals": 0,
            "maximum_target_error_deg": 8.0,
            "comparative_requirement": "strictly fewer hard-negative trial proposals than the frozen spatial comparator",
            "all_conditions_required": True,
        },
        "analysis": {
            "interval": "two-sided Wilson score interval at nominal 95%, computed over trials",
            "paired_test": "two-sided exact McNemar test on hard-negative trial proposal/no-proposal outcomes",
            "rows_are_independent": False,
            "report_all_attempts": True,
            "report_by_room_condition_and_heading": True,
            "no_adaptive_stopping": True,
        },
        "outcome_blind_quality_exclusions": [
            "capture did not complete the predeclared duration",
            "audio or video numeric stream was missing or nonfinite",
            "clock drift or sample gap exceeded the newly frozen instrumentation limits",
            "the required face configuration was not present for the predeclared minimum fraction",
            "the physical room/heading/condition setup deviated from the randomized schedule",
        ],
        "privacy": {
            "public_artifacts": "derived numeric energy, mouth-motion, geometry, timing, policy outputs, and hashes only",
            "public_raw_audio": False,
            "public_pixels": False,
            "public_transcripts": False,
            "consent_required_for_recorded_voice": True,
        },
        "robot_scope": {
            "passive_sensing_only": True,
            "actuation_commands": 0,
            "torque_or_calibration_changes": 0,
            "current_offline_prototype_robot_connections": 0,
        },
    }
    encoded = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**core, "fingerprint": hashlib.sha256(encoded).hexdigest()}


def validate_protocol() -> None:
    trials = confirmation_trials()
    if len(trials) != 54 or len({trial["trial_id"] for trial in trials}) != 54:
        raise ValueError("The confirmation design must contain 54 unique trials.")
    positives = [trial for trial in trials if trial["role"] == "matching_positive"]
    negatives = [trial for trial in trials if trial["role"] == "hard_negative"]
    if len(positives) != 18 or len(negatives) != 36:
        raise ValueError("The design must contain 18 positives and 36 hard negatives.")
    randomized = randomized_confirmation_trials()
    if sorted(trial["trial_id"] for trial in randomized) != sorted(
        trial["trial_id"] for trial in trials
    ):
        raise ValueError("The frozen randomized schedule must contain every trial exactly once.")


validate_protocol()
