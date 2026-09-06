"""Frozen replacement pilot for face-normalized audio-mouth synchrony."""

from __future__ import annotations

import hashlib
import json
import random
from typing import Any


PILOT_V2_RANDOMIZATION_SEED = 40904
PILOT_V2_DURATION_S = 10
PILOT_V2_SAMPLE_PERIOD_MS = 40
PILOT_V2_INSTRUMENT_REVISION = 3
PILOT_V2_PREVIOUS_FINGERPRINT = (
    "82de81cfd631db26ce95c2f0f3a07374146b09896f640fe67111511a9c437326"
)
PILOT_V2_INITIAL_FINGERPRINT = (
    "2aa408a5eee83038b56660f96184c849bcbde41b5bab43d313c7a45650954231"
)
PILOT_V2_CONDITIONS = (
    {
        "id": "live_visible_continuous",
        "role": "matching_positive",
        "instruction": "Look toward the camera and speak naturally throughout the capture.",
    },
    {
        "id": "live_visible_interrupted",
        "role": "matching_positive",
        "instruction": "Alternate about one second of speech with one second of silence.",
    },
    {
        "id": "silent_face_colocated_playback",
        "role": "hard_negative",
        "instruction": "Remain silent and still while the fixed consented recording plays beside your face.",
    },
    {
        "id": "silent_mouthing_unrelated_playback",
        "role": "hard_negative",
        "instruction": "Mouth silently out of time with the fixed consented recording beside your face.",
    },
)


def canonical_pilot_v2_trials() -> list[dict[str, Any]]:
    trials: list[dict[str, Any]] = []
    for repetition in range(1, 4):
        split = "development" if repetition <= 2 else "internal_validation"
        for condition in PILOT_V2_CONDITIONS:
            trials.append(
                {
                    "trial_id": f"avsync-v2-pilot-{len(trials) + 1:02d}",
                    "condition_id": condition["id"],
                    "role": condition["role"],
                    "repetition": repetition,
                    "split": split,
                    "duration_s": PILOT_V2_DURATION_S,
                    "instruction": condition["instruction"],
                }
            )
    return trials


def randomized_pilot_v2_trials() -> list[dict[str, Any]]:
    trials = [dict(trial) for trial in canonical_pilot_v2_trials()]
    random.Random(PILOT_V2_RANDOMIZATION_SEED).shuffle(trials)
    return trials


def pilot_v2_protocol_payload() -> dict[str, Any]:
    core = {
        "schema": "reachy-av-synchrony-off-robot-pilot-v2",
        "status": "FROZEN_DEVELOPMENT_ONLY_NO_DATA_NO_ROBOT",
        "predecessor": {
            "protocol": "reachy-av-synchrony-off-robot-pilot-v1",
            "disposition": "INSTRUMENT_REJECTED_ZERO_OF_240_SETTINGS_ELIGIBLE",
        },
        "instrument_revision": PILOT_V2_INSTRUMENT_REVISION,
        "instrument_revision_history": {
            "previous_protocol_fingerprint": PILOT_V2_PREVIOUS_FINGERPRINT,
            "initial_protocol_fingerprint": PILOT_V2_INITIAL_FINGERPRINT,
            "commissioning_attempt_sample_counts": [90, 86, 86, 142, 146, 138],
            "revision_1_attempt_sample_counts": [90, 86, 86],
            "revision_2_attempt_sample_counts": [142, 146, 138],
            "commissioning_failed_gate": "INSUFFICIENT_SAMPLES",
            "canonical_trials_accepted_before_revision": 0,
            "reason": (
                "revision 1 added a 40 ms delay after synchronous landmark inference; "
                "revision 2 removed that delay but this laptop still sustained only "
                "138-146 samples per eight seconds; revision 3 uniformly extends every "
                "trial to ten seconds while preserving every quality and selection threshold"
            ),
            "quality_or_selection_threshold_changed": False,
        },
        "purpose": (
            "test a tracked face-normalized lip-aperture instrument before any "
            "multi-room confirmation study"
        ),
        "experimental_unit": "one ten-second laptop-only trial",
        "conditions": list(PILOT_V2_CONDITIONS),
        "canonical_trials": canonical_pilot_v2_trials(),
        "randomized_schedule": randomized_pilot_v2_trials(),
        "randomization_seed": PILOT_V2_RANDOMIZATION_SEED,
        "sample_period_ms": PILOT_V2_SAMPLE_PERIOD_MS,
        "required_columns": [
            "timestamp_ms",
            "audio_dbfs",
            "lip_aperture",
            "face_scale",
            "face_count",
        ],
        "expected_files": [
            f"{trial['trial_id']}.csv" for trial in canonical_pilot_v2_trials()
        ],
        "instrument": {
            "runtime": "@mediapipe/tasks-vision",
            "runtime_version": "1.0.1",
            "runtime_tarball_url": (
                "https://registry.npmjs.org/@mediapipe/tasks-vision/-/"
                "tasks-vision-1.0.1.tgz"
            ),
            "runtime_tarball_sha256": (
                "ee318eaa3d42230aa10910d114faf2a488c577c4e4d33c7cb04126924aca505f"
            ),
            "model_url": (
                "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
                "face_landmarker/float16/1/face_landmarker.task"
            ),
            "model_sha256": (
                "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"
            ),
            "running_mode": "VIDEO",
            "delegate": "GPU",
            "capture_width": 320,
            "capture_height": 240,
            "scheduler": (
                "deadline-anchored 40 ms cadence; inference time is not added to the "
                "next deadline"
            ),
            "maximum_faces": 2,
            "lip_landmarks": [13, 14],
            "scale_landmarks": [33, 263],
            "lip_aperture_definition": (
                "Euclidean distance between landmarks 13 and 14 divided by the "
                "distance between landmarks 33 and 263"
            ),
            "audio_definition": "20*log10(max(local microphone RMS, 1e-6))",
        },
        "instrument_preflight": {
            "preview_measurements": 25,
            "maximum_median_landmark_inference_ms": 45.0,
            "failure_rule": (
                "do not open a canonical capture when the local inference benchmark "
                "is too slow"
            ),
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
                "silent_mouthing_unrelated_playback",
            ],
            "failed_capture_rule": (
                "retain the failed attempt, do not advance, and repeat only the "
                "same scheduled trial after correcting the objective quality issue"
            ),
        },
        "preprocessing": {
            "resample_period_ms": 40.0,
            "moving_average_samples": [1, 3, 5],
            "correlation_inputs": "audio_dbfs versus normalized lip_aperture",
            "maximum_clock_drift_fraction": 0.03,
            "minimum_overlap_ms": 1200.0,
        },
        "threshold_grid": {
            "min_correlation": [0.15, 0.25, 0.35, 0.45, 0.55],
            "max_abs_lag_ms": [120.0, 240.0, 360.0],
            "moving_average_samples": [1, 3, 5],
        },
        "development_selection_rule": [
            "use only repetitions one and two",
            "require every development trial to pass objective quality gates",
            "require zero of four hard-negative trial candidates",
            "require at least three of four matching-positive trial candidates",
            "maximize matching-positive coverage",
            "then prefer higher correlation threshold",
            "then prefer narrower lag window",
            "then prefer less temporal smoothing",
        ],
        "internal_validation_rule": [
            "evaluate repetition three once with the development-selected setting",
            "require every validation trial to pass objective quality gates",
            "require two of two matching-positive trial candidates",
            "require zero of two hard-negative trial candidates",
        ],
        "privacy": {
            "recorder_uploads_data": False,
            "recorder_saves_raw_audio": False,
            "recorder_saves_video_or_pixels": False,
            "recorder_saves_face_embeddings": False,
            "numeric_csv_only": True,
            "consent_required_for_playback_voice": True,
            "runtime_and_model_served_from_localhost": True,
        },
        "scope": {
            "reachy_power_required": False,
            "robot_connections": 0,
            "actuation_commands": 0,
            "result_may_be_called_confirmation": False,
            "successful_result_requires_a_separate_code_threshold_freeze": True,
        },
    }
    encoded = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**core, "fingerprint": hashlib.sha256(encoded).hexdigest()}


def validate_pilot_v2_protocol() -> None:
    canonical = canonical_pilot_v2_trials()
    randomized = randomized_pilot_v2_trials()
    if len(canonical) != 12 or len({trial["trial_id"] for trial in canonical}) != 12:
        raise ValueError("The V2 pilot must contain twelve unique trials.")
    if sum(trial["split"] == "development" for trial in canonical) != 8:
        raise ValueError("The V2 pilot must contain eight development trials.")
    if sum(trial["split"] == "internal_validation" for trial in canonical) != 4:
        raise ValueError("The V2 pilot must contain four validation trials.")
    for split, expected in (("development", 4), ("internal_validation", 2)):
        subset = [trial for trial in canonical if trial["split"] == split]
        if sum(trial["role"] == "matching_positive" for trial in subset) != expected:
            raise ValueError(f"Unexpected positive count in {split} split.")
        if sum(trial["role"] == "hard_negative" for trial in subset) != expected:
            raise ValueError(f"Unexpected negative count in {split} split.")
    if sorted(trial["trial_id"] for trial in canonical) != sorted(
        trial["trial_id"] for trial in randomized
    ):
        raise ValueError("The randomized V2 schedule must contain every trial exactly once.")


validate_pilot_v2_protocol()
