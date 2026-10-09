"""Separately frozen Reachy-camera / external-microphone no-motion pilot."""

from __future__ import annotations

import hashlib
import json
import random
from copy import deepcopy

from .joint_pilot_protocol import joint_pilot_protocol_payload
from .robot_camera_commissioning import ROBOT_CAMERA_COMMISSIONING_SPEC_V1


def fingerprint(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def protocol() -> dict:
    """No sensors, file writes or authority. Historical v2 is not modified."""
    previous = joint_pilot_protocol_payload()
    conditions = deepcopy(previous["conditions"])
    for condition in conditions:
        if condition["id"] == "live_visible_interrupted":
            condition["instruction"] = (
                "Face Reachy. Speak naturally for seconds 0–3, stay silent for 3–5, "
                "then speak for 5–10. Keep the phone silent."
            )
        elif condition["id"] == "live_visible_continuous":
            condition["instruction"] = (
                "Face Reachy's camera at the fixed front mark and speak naturally "
                "for all ten seconds. Keep the phone silent."
            )
        elif condition["id"] == "visible_silence":
            condition["instruction"] = "Keep one face visible to Reachy. Stay silent; no phone playback."
        elif condition["id"] == "spatial_conflict":
            condition["instruction"] = (
                "Stay silent with your face visible at the front mark. Play the fixed "
                "recording on the single iPhone at the 60-degree mark to Reachy's right."
            )
        condition["instruction"] += " Playback conditions: restart the same recording immediately before Record, at the sealed volume, and let it play throughout."
    rng = random.Random(20261001)
    schedule = []
    for block in (1, 2, 3):
        cards = deepcopy(conditions)
        rng.shuffle(cards)
        for card in cards:
            index = len(schedule) + 1
            schedule.append({"trial_id": f"reachy-camera-pilot-v1-{index:02d}",
                             "schedule_index": index, "condition_id": card["id"],
                             "role": card["role"], "instruction": card["instruction"],
                             "repetition": block, "duration_s": 10,
                             "split": "development" if block < 3 else "internal_validation"})
    quality = deepcopy(previous["quality_gates"])
    quality.update({"minimum_robot_transport_fps": 15.0,
                    "minimum_unique_analyzed_fps": 15.0,
                    "maximum_p95_robot_frame_age_ms": 350.0,
                    "maximum_duplicate_row_fraction": 0.5,
                    "maximum_median_landmark_inference_ms": 60.0})
    core = {
        "schema": "reachy-camera-no-motion-pilot-v1",
        "status": "DESIGN_FROZEN_EXECUTION_AND_PRIVATE_SEAL_REQUIRED",
        "instrument_fingerprint": ROBOT_CAMERA_COMMISSIONING_SPEC_V1.payload()["fingerprint"],
        "sensors": {"camera": "Reachy Mini Wireless receive-only WebRTC",
                    "direction": "Reachy GET-only DoA",
                    "audio": "external laptop microphone; not fully robot-native audiovisual sensing"},
        "experimental_unit": "one ten-second trial, not telemetry rows or camera frames",
        "conditions": conditions, "schedule": schedule, "randomization_seed": 20261001,
        "quality_gates": quality,
        "threshold_basis": "Retain v2 acquisition gates plus the original robot-camera transport/timing gates; no thresholds selected from pilot outcomes.",
        "candidate_grid": deepcopy(previous["candidate_grid"]),
        "development_selection_rule": deepcopy(previous["development_selection_rule"]),
        "internal_validation_rule": deepcopy(previous["internal_validation_rule"]),
        "baselines": deepcopy(previous["baselines"]),
        "timing_analysis": {
            "mouth": "one observation per distinct frame, timestamp = row time minus corrected local frame age",
            "audio": "every 40-ms telemetry sample; timestamp = row time minus half the 2048-sample RMS window",
            "resampling": "common support only, 40-ms grid, linear interpolation; reject gaps over 160 ms before interpolation",
            "smoothing": "apply candidate smoothing on the common 40-ms grid, not on duplicated camera rows",
            "scope": "lag includes unmeasured exposure/robot/network/decode delays; not sensor-exposure synchrony or liveness",
            "boundary_lag": "report boundary hits; a selected boundary-lag result requires a new timing investigation, not a wider post-hoc grid",
        },
        "attempt_rule": "Store every attempted pair immutably; accept first quality-passing attempt in schedule order. No outcome-based retries. At most two attempts per trial, then stop for repair/new version.",
        "validation_lock": "Do not open block 3 until all 14 development trials are accepted and their selected setting and source hashes are frozen. Evaluate block 3 once without reselection.",
        "excluded": "all commissioning captures and every laptop v1/v2 attempt; never import as pilot trials",
        "opening_gate": "matching execution manifest, private setup seal, verified microphone settings and next scheduled card; first trial remains closed until all pass",
        "authority": {"motion_commands": 0, "response_commands": 0, "robot_mutating_requests": 0},
        "privacy": {"raw_media_saved": False, "raw_media_uploaded": False},
        "claim_boundary": "Single-setup engineering pilot. No confirmation, liveness, safe motion, attention hold, response or end-to-end validation. Laptop audio remains external.",
    }
    return {**core, "fingerprint": fingerprint(core)}
