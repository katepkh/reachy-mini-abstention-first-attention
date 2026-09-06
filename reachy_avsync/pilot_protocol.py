"""Frozen twelve-trial, off-robot development pilot for synchrony instrumentation."""

from __future__ import annotations

import hashlib
import json
import random
from typing import Any


PILOT_RANDOMIZATION_SEED = 91207
PILOT_DURATION_S = 8
PILOT_SAMPLE_PERIOD_MS = 40
PILOT_CONDITIONS = (
    {
        "id": "live_visible_continuous",
        "role": "matching_positive",
        "instruction": "Look toward the laptop camera and speak naturally throughout the capture.",
    },
    {
        "id": "live_visible_interrupted",
        "role": "matching_positive",
        "instruction": "Look toward the laptop camera and alternate about one second of speech with one second of silence.",
    },
    {
        "id": "silent_face_colocated_playback",
        "role": "hard_negative",
        "instruction": "Remain silent and still while a consented speech recording plays from a fixed speaker beside your face.",
    },
    {
        "id": "silent_mouthing_shifted_playback",
        "role": "hard_negative",
        "instruction": "Mouth silently while a deliberately unrelated or time-shifted consented speech recording plays beside your face.",
    },
)


def canonical_pilot_trials() -> list[dict[str, Any]]:
    trials: list[dict[str, Any]] = []
    for repetition in range(1, 4):
        for condition in PILOT_CONDITIONS:
            trials.append(
                {
                    "trial_id": f"avsync-pilot-{len(trials) + 1:02d}",
                    "condition_id": condition["id"],
                    "role": condition["role"],
                    "repetition": repetition,
                    "duration_s": PILOT_DURATION_S,
                    "instruction": condition["instruction"],
                }
            )
    return trials


def randomized_pilot_trials() -> list[dict[str, Any]]:
    trials = [dict(trial) for trial in canonical_pilot_trials()]
    random.Random(PILOT_RANDOMIZATION_SEED).shuffle(trials)
    return trials


def pilot_protocol_payload() -> dict[str, Any]:
    core = {
        "schema": "reachy-av-synchrony-off-robot-pilot-v1",
        "status": "DEVELOPMENT_ONLY_NO_CONFIRMATION_DATA_NO_ROBOT",
        "purpose": "verify local numeric instrumentation and select candidate synchrony thresholds before a separate confirmation freeze",
        "experimental_unit": "one eight-second laptop-only trial",
        "conditions": list(PILOT_CONDITIONS),
        "canonical_trials": canonical_pilot_trials(),
        "randomized_schedule": randomized_pilot_trials(),
        "randomization_seed": PILOT_RANDOMIZATION_SEED,
        "sample_period_ms": PILOT_SAMPLE_PERIOD_MS,
        "required_columns": ["timestamp_ms", "audio_energy", "mouth_motion"],
        "expected_files": [f"{trial['trial_id']}.csv" for trial in canonical_pilot_trials()],
        "threshold_grid": {
            "min_correlation": [0.35, 0.45, 0.55, 0.65, 0.75],
            "max_abs_lag_ms": [120.0, 240.0, 360.0],
            "min_audio_std": [0.005, 0.01, 0.02, 0.05],
            "min_mouth_std": [0.001, 0.0025, 0.005, 0.01],
        },
        "selection_rule": [
            "require zero hard-negative trial candidates",
            "require at least four of six matching-positive trial candidates",
            "maximize matching-positive trial coverage",
            "then prefer higher correlation threshold",
            "then prefer narrower lag window",
            "then prefer higher audio and mouth dynamic-range thresholds",
        ],
        "privacy": {
            "recorder_uploads_data": False,
            "recorder_saves_raw_audio": False,
            "recorder_saves_video_or_pixels": False,
            "numeric_csv_only": True,
            "consent_required_for_playback_voice": True,
        },
        "scope": {
            "reachy_power_required": False,
            "robot_connections": 0,
            "actuation_commands": 0,
            "result_may_be_called_confirmation": False,
            "selected_thresholds_are_automatically_frozen": False,
        },
    }
    encoded = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**core, "fingerprint": hashlib.sha256(encoded).hexdigest()}


def validate_pilot_protocol() -> None:
    canonical = canonical_pilot_trials()
    randomized = randomized_pilot_trials()
    if len(canonical) != 12 or len({trial["trial_id"] for trial in canonical}) != 12:
        raise ValueError("The pilot must contain twelve unique trials.")
    if sum(trial["role"] == "matching_positive" for trial in canonical) != 6:
        raise ValueError("The pilot must contain six matching-positive trials.")
    if sum(trial["role"] == "hard_negative" for trial in canonical) != 6:
        raise ValueError("The pilot must contain six hard-negative trials.")
    if sorted(trial["trial_id"] for trial in canonical) != sorted(
        trial["trial_id"] for trial in randomized
    ):
        raise ValueError("The randomized pilot schedule must contain every trial exactly once.")


validate_pilot_protocol()

