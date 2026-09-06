"""Versioned development protocol for passive vertical face tracking.

This is a development design, not held-out confirmation and not permission to
move Reachy. Its output is numeric evidence for offline policy selection.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from reachy_stage2a.config import PROJECT_ROOT

from .calibration import vertical_offset_cm


@dataclass(frozen=True, slots=True)
class VerticalValidationStep:
    index: int
    condition_id: str
    role: str
    repetition: int
    initial_pitch_deg: float | None
    target_pitch_deg: float | None
    face_yaw_deg: float | None
    sound_yaw_deg: float | None
    transition_at_s: float | None
    title: str
    instruction: str
    countdown_s: int = 5
    duration_s: int = 12

    def run_id(self, date_prefix: str) -> str:
        return (
            f"{date_prefix}_stage3p-vertical_{self.index:02d}-of-18_"
            f"{self.condition_id}_take{self.repetition:02d}"
        )


def _pitch_slug(pitch: int) -> str:
    return f"up{pitch}" if pitch > 0 else f"down{abs(pitch)}"


def _yaw_slug(yaw: int) -> str:
    return f"plus{yaw}" if yaw >= 0 else f"minus{abs(yaw)}"


def _height_instruction(pitch: int) -> str:
    direction = "above" if pitch > 0 else "below"
    offset = abs(vertical_offset_cm(pitch))
    return f"your eye line {offset:.1f} cm {direction} the camera optical-centre mark"


def build_vertical_steps() -> tuple[VerticalValidationStep, ...]:
    steps: list[VerticalValidationStep] = []
    index = 1
    for repetition in range(1, 4):
        for pitch in (-10, 10):
            steps.append(
                VerticalValidationStep(
                    index=index,
                    condition_id=f"acquire-{_pitch_slug(pitch)}deg",
                    role="matching_acquisition",
                    repetition=repetition,
                    initial_pitch_deg=float(pitch),
                    target_pitch_deg=float(pitch),
                    face_yaw_deg=0.0,
                    sound_yaw_deg=0.0,
                    transition_at_s=None,
                    title=f"Acquire speaking face at pitch {pitch:+d}°",
                    instruction=(
                        "Stay at the front 0° mark, 1 m horizontally from Reachy, with "
                        f"{_height_instruction(pitch)}. Keep your whole face visible. During "
                        "RECORDING, say ‘Reachy, this is a vertical tracking test.’ naturally "
                        "about every 2 seconds."
                    ),
                )
            )
            index += 1

    for repetition in range(1, 4):
        for pitch in (-10, 10):
            steps.append(
                VerticalValidationStep(
                    index=index,
                    condition_id=f"maintain-centre-to-{_pitch_slug(pitch)}deg",
                    role="maintenance_transition",
                    repetition=repetition,
                    initial_pitch_deg=0.0,
                    target_pitch_deg=float(pitch),
                    face_yaw_deg=0.0,
                    sound_yaw_deg=0.0,
                    transition_at_s=4.0,
                    title=f"Maintain face track from centre to pitch {pitch:+d}°",
                    instruction=(
                        "Start at front 0°, 1 m away, with your eye line on the camera optical-centre "
                        "mark. Speak the test phrase during the first 3 seconds only. At the visual "
                        f"MOVE cue, silently change to {_height_instruction(pitch)}; keep exactly one "
                        "full face visible for the rest of RECORDING."
                    ),
                )
            )
            index += 1

    for pitch in (-10, 10):
        steps.append(
            VerticalValidationStep(
                index=index,
                condition_id=f"silent-visible-{_pitch_slug(pitch)}deg",
                role="hard_negative",
                repetition=1,
                initial_pitch_deg=float(pitch),
                target_pitch_deg=float(pitch),
                face_yaw_deg=0.0,
                sound_yaw_deg=None,
                transition_at_s=None,
                title=f"Silent visible face at pitch {pitch:+d}°",
                instruction=(
                    f"Stay at front 0°, 1 m away, with {_height_instruction(pitch)}. Remain silent "
                    "and keep all playback stopped throughout RECORDING."
                ),
            )
        )
        index += 1

    for repetition in (1, 2):
        steps.append(
            VerticalValidationStep(
                index=index,
                condition_id="speech-with-no-face",
                role="hard_negative",
                repetition=repetition,
                initial_pitch_deg=None,
                target_pitch_deg=None,
                face_yaw_deg=None,
                sound_yaw_deg=0.0,
                transition_at_s=None,
                title="Front speech with no visible face",
                instruction=(
                    "Keep every person completely outside Reachy’s camera view. Place the phone at "
                    "front 0°, 1 m away and play the standard speech clip during RECORDING."
                ),
            )
        )
        index += 1

    mismatch = ((-10, -20, 20), (10, 20, -20))
    for pitch, face_yaw, sound_yaw in mismatch:
        face_side = "diagram-left" if face_yaw < 0 else "diagram-right"
        sound_side = "diagram-left" if sound_yaw < 0 else "diagram-right"
        steps.append(
            VerticalValidationStep(
                index=index,
                condition_id=(
                    f"mismatch-face-{_yaw_slug(face_yaw)}-{_pitch_slug(pitch)}-"
                    f"sound-{_yaw_slug(sound_yaw)}"
                ),
                role="hard_negative",
                repetition=1,
                initial_pitch_deg=float(pitch),
                target_pitch_deg=float(pitch),
                face_yaw_deg=float(face_yaw),
                sound_yaw_deg=float(sound_yaw),
                transition_at_s=None,
                title=f"Visible face {face_yaw:+d}°/{pitch:+d}° and opposite phone speech",
                instruction=(
                    f"Stand silently at {face_yaw:+d}° {face_side}, 1 m away, with "
                    f"{_height_instruction(pitch)}. Put the phone at {sound_yaw:+d}° {sound_side}, "
                    "1 m away, and play the standard speech clip during RECORDING."
                ),
            )
        )
        index += 1
    return tuple(steps)


VERTICAL_STEPS = build_vertical_steps()
STAGE3P_DATA_DIR = (PROJECT_ROOT / "data" / "stage3p_development").resolve()
STAGE3P_MANIFEST_PATH = (
    PROJECT_ROOT / "data" / "manifests" / "stage3p_vertical_design_v1.json"
).resolve()

SUCCESS_CRITERIA = {
    "instrumentation_quality": {
        "minimum_samples": 48,
        "minimum_valid_doa_pct": 80.0,
        "minimum_fresh_single_face_pct_when_face_expected": 80.0,
        "maximum_face_age_ms": 1500.0,
        "minimum_speech_positive_when_speech_expected": 3,
    },
    "shadow_safety": {"maximum_hard_negative_would_adjust_rows": 0},
    "vertical_direction": {"maximum_wrong_sign_adjustments": 0},
    "static_acquisition": {
        "minimum_trials_with_adjustment_per_pitch": 2,
        "repetitions_per_pitch": 3,
        "maximum_target_error_deg": 6.0,
    },
    "silent_maintenance": {
        "minimum_trials_with_adjustment_per_pitch": 2,
        "repetitions_per_pitch": 3,
        "maximum_target_error_deg": 6.0,
    },
}


def protocol_payload() -> dict[str, Any]:
    core = {
        "schema": "reachy-stage3p-passive-vertical-design-v1",
        "status": "FROZEN_DEVELOPMENT_PROTOCOL_NOT_HELD_OUT_NOT_AUTHORISED_FOR_ACTUATION",
        "frozen_at": "2026-08-27T22:52:36+01:00",
        "review": {
            "scientific_matrix_reviewed": True,
            "acceptance_is_instrumentation_and_procedure_only": True,
            "candidate_policy_outcome_cannot_change_acceptance": True,
            "development_and_future_held_out_directories_are_separate": True,
            "face_expected_and_no_face_readiness_are_condition_specific": True,
            "safety_boundary_reviewed": True,
            "operator_instructions_reviewed": True,
        },
        "purpose": "Validate up/down acquisition and silent maintenance while Reachy is stationary.",
        "coordinate_frame": {
            "yaw": "front=0; diagram-left=negative; diagram-right=positive; reuse frozen V3 calibration",
            "pitch": "camera optical axis=0; up=positive; down=negative; normalized image y grows downward",
            "distance": "face eye line is positioned at 1 m horizontal distance from the camera",
            "ground_truth_pitch_deg": [-10.0, 10.0],
            "ground_truth_height_offsets_cm_at_1m": {
                "down_10": vertical_offset_cm(-10.0),
                "up_10": vertical_offset_cm(10.0),
            },
        },
        "known_observability_limit": (
            "The current DoA endpoint supplies horizontal bearing only. If no face is visible, "
            "Stage 3P must HOLD; it cannot infer whether a speaker is above or below the camera."
        ),
        "steps": [asdict(step) for step in VERTICAL_STEPS],
        "success_criteria": SUCCESS_CRITERIA,
        "raw_numeric_columns_reused": [
            "elapsed_ms", "speech_detected", "http_status", "acoustic_state",
            "acoustic_confidence", "hypothesis_a_deg", "hypothesis_b_deg",
            "face_detected", "face_count", "face_center_x_norm", "face_center_y_norm",
            "face_heading_deg", "face_confidence", "face_age_ms",
        ],
        "offline_derived_columns": [
            "face_pitch_deg", "candidate_target_yaw_deg", "candidate_target_pitch_deg",
            "association_phase", "stage3p_reason", "shadow_action",
        ],
        "development_sequence": [
            "collect isolated Stage 3P development data",
            "replay and compare candidate policies offline",
            "freeze exactly one revised coupled yaw/pitch policy",
            "collect a new held-out Stage 3P confirmation set",
            "run an offline coupled motion shadow",
        ],
        "policy_selection_boundary": (
            "This protocol and its quality gates are frozen. Candidate policy thresholds may be "
            "compared only by offline replay of this development set. Exactly one selected policy "
            "must be frozen before a separate held-out collection."
        ),
        "privacy": {
            "numeric_mode_contains_pixels": False,
            "numeric_mode_contains_audio": False,
            "numeric_mode_contains_transcript": False,
            "optional_audit_media_is_separate_encrypted_local_and_bounded": True,
        },
        "actuation_commands": 0,
        "cloud_requests": 0,
    }
    encoded = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**core, "fingerprint": hashlib.sha256(encoded).hexdigest()}


def validate_protocol() -> None:
    if len(VERTICAL_STEPS) != 18:
        raise ValueError("Stage 3P development design must contain exactly 18 steps.")
    if [step.index for step in VERTICAL_STEPS] != list(range(1, 19)):
        raise ValueError("Stage 3P indexes must be contiguous.")
    roles = {role: sum(step.role == role for step in VERTICAL_STEPS) for role in {
        "matching_acquisition", "maintenance_transition", "hard_negative"
    }}
    if roles != {"matching_acquisition": 6, "maintenance_transition": 6, "hard_negative": 6}:
        raise ValueError(f"Unexpected Stage 3P role matrix: {roles}")
    if any(step.duration_s != 12 or step.countdown_s != 5 for step in VERTICAL_STEPS):
        raise ValueError("Stage 3P timing changed from the predeclared design.")


def write_design_manifest(path: Path = STAGE3P_MANIFEST_PATH) -> dict[str, Any]:
    validate_protocol()
    payload = protocol_payload()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


validate_protocol()
