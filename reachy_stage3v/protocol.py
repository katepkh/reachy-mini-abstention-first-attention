"""Frozen physical protocol for passive off-axis motion-shadow validation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ValidationStep:
    index: int
    condition_id: str
    role: str
    repetition: int
    true_heading_deg: float
    face_heading_deg: float
    sound_heading_deg: float | None
    title: str
    instruction: str
    countdown_s: int = 5
    duration_s: int = 12

    @property
    def condition_code(self) -> str:
        return f"stage3v-{self.condition_id}"

    def run_id(self, date_prefix: str) -> str:
        return (
            f"{date_prefix}_stage3v-off-axis_{self.index:02d}-of-18_"
            f"{self.condition_id}_take{self.repetition:02d}"
        )


def _heading_slug(heading: int) -> str:
    return f"plus{heading}" if heading >= 0 else f"minus{abs(heading)}"


def _matching_step(index: int, heading: int, repetition: int) -> ValidationStep:
    side = "diagram-left" if heading < 0 else "diagram-right"
    magnitude = abs(heading)
    return ValidationStep(
        index=index,
        condition_id=f"matching-{_heading_slug(heading)}deg",
        role="matching_positive",
        repetition=repetition,
        true_heading_deg=float(heading),
        face_heading_deg=float(heading),
        sound_heading_deg=float(heading),
        title=f"Matching face + live speech at {heading:+d}°",
        instruction=(
            f"Stand on the {heading:+d}° floor mark: {magnitude}° toward {side} from front-centre, "
            "at 1 m radius. Face Reachy. During RECORDING, say ‘Reachy, this is a "
            "sound-direction test.’ naturally about every 2 seconds. Keep your feet on the mark."
        ),
    )


def build_validation_steps() -> tuple[ValidationStep, ...]:
    steps: list[ValidationStep] = []
    index = 1
    # Blocked sweeps prevent every angle from being tied to one moment in the session.
    for repetition in range(1, 4):
        for heading in (-20, -10, 10, 20):
            steps.append(_matching_step(index, heading, repetition))
            index += 1

    for heading in (-20, 20):
        side = "diagram-left" if heading < 0 else "diagram-right"
        steps.append(
            ValidationStep(
                index=index,
                condition_id=f"silent-face-{_heading_slug(heading)}deg",
                role="hard_negative",
                repetition=1,
                true_heading_deg=float(heading),
                face_heading_deg=float(heading),
                sound_heading_deg=None,
                title=f"Silent visible face at {heading:+d}°",
                instruction=(
                    f"Stand at the {heading:+d}° {side} mark, 1 m from Reachy. Face Reachy, "
                    "remain silent and still, and keep all playback stopped during RECORDING."
                ),
            )
        )
        index += 1

    mismatch_pairs = ((-20, 20), (20, -20))
    for repetition in range(1, 3):
        for face_heading, phone_heading in mismatch_pairs:
            face_side = "diagram-left" if face_heading < 0 else "diagram-right"
            phone_side = "diagram-left" if phone_heading < 0 else "diagram-right"
            steps.append(
                ValidationStep(
                    index=index,
                    condition_id=(
                        f"mismatch-face-{_heading_slug(face_heading)}-"
                        f"phone-{_heading_slug(phone_heading)}"
                    ),
                    role="hard_negative",
                    repetition=repetition,
                    true_heading_deg=float(face_heading),
                    face_heading_deg=float(face_heading),
                    sound_heading_deg=float(phone_heading),
                    title=(
                        f"Silent face {face_heading:+d}° + phone speech {phone_heading:+d}°"
                    ),
                    instruction=(
                        f"Stand silently on the {face_heading:+d}° {face_side} mark, facing Reachy. "
                        f"Place the phone on the {phone_heading:+d}° {phone_side} mark at 1 m. "
                        "During RECORDING play the same podcast-speech clip at about 35% volume. "
                        "Keep your face visible and do not speak."
                    ),
                )
            )
            index += 1
    return tuple(steps)


VALIDATION_STEPS = build_validation_steps()


SUCCESS_CRITERIA = {
    "protocol_quality": {
        "minimum_samples": 20,
        "minimum_valid_pct": 80.0,
        "minimum_single_face_pct": 60.0,
        "maximum_face_age_ms": 1500.0,
        "minimum_fresh_single_face_pct": 80.0,
        "minimum_speech_positive_matching": 3,
        "minimum_speech_positive_mismatch": 3,
        "camera_analysis_max_width_px": 640,
        "camera_detector": "opencv_yunet_2023mar_score_0.90",
        "camera_model_sha256": "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
        "camera_zero_face_numeric_bridge_bounded": True,
        "camera_frame_timeout_seconds": 2.5,
        "camera_proxy_unavailability_is_explicit": True,
    },
    "shadow_safety": {"maximum_hard_negative_would_move_rows": 0},
    "shadow_direction": {
        "minimum_positive_trials_with_move_per_heading": 2,
        "repetitions_per_heading": 3,
        "maximum_target_error_deg": 8.0,
        "maximum_wrong_sign_moves": 0,
    },
}


def protocol_payload() -> dict[str, Any]:
    core = {
        "schema": "reachy-stage3v-off-axis-protocol-v3",
        "status": "PREDECLARED_RERUN_AFTER_CAMERA_TRANSPORT_WATCHDOG_AMENDMENT",
        "coordinate_frame": (
            "front=0; diagram-left=negative; diagram-right=positive; positions are measured "
            "on a 1 m radius while Reachy remains fixed"
        ),
        "steps": [asdict(step) for step in VALIDATION_STEPS],
        "success_criteria": SUCCESS_CRITERIA,
        "privacy": {
            "contains_pixels": False,
            "contains_audio": False,
            "contains_transcript": False,
            "contains_identity_embedding": False,
        },
        "actuation_commands": 0,
        "cloud_requests": 0,
    }
    encoded = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**core, "fingerprint": hashlib.sha256(encoded).hexdigest()}


def validate_protocol() -> None:
    if len(VALIDATION_STEPS) != 18:
        raise ValueError("Stage 3V protocol must contain exactly 18 trials.")
    if [step.index for step in VALIDATION_STEPS] != list(range(1, 19)):
        raise ValueError("Stage 3V step indexes must be contiguous.")
    positives = [step for step in VALIDATION_STEPS if step.role == "matching_positive"]
    negatives = [step for step in VALIDATION_STEPS if step.role == "hard_negative"]
    if len(positives) != 12 or len(negatives) != 6:
        raise ValueError("Stage 3V must contain 12 positives and 6 hard negatives.")
    for heading in (-20.0, -10.0, 10.0, 20.0):
        repetitions = [step.repetition for step in positives if step.true_heading_deg == heading]
        if repetitions != [1, 2, 3]:
            raise ValueError(f"Heading {heading} does not have three frozen repetitions.")


validate_protocol()
