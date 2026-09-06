"""Frozen fresh held-out protocol for the selected Stage 3P V3 policy."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from reachy_stage2a.config import PROJECT_ROOT

from .calibration import vertical_offset_cm
from .protocol import VerticalValidationStep


SOURCE_POLICY_FINGERPRINT = (
    "3fc6e784d81ac4506779a5d84274d7cd6da4d131f8a1af58164f9bc5ee3b78ae"
)
SOURCE_POLICY_FREEZE_BUNDLE_SHA256 = (
    "66bde5cf0c5ae6b9a7bd5f4d25716292c1a70a7b0afefd32aff7618ea1d71e3b"
)


def _height_instruction(pitch: int) -> str:
    direction = "above" if pitch > 0 else "below"
    return (
        f"your eye line {abs(vertical_offset_cm(pitch)):.1f} cm {direction} "
        "the camera optical-centre mark"
    )


def _pitch_slug(pitch: int) -> str:
    return f"up{pitch}" if pitch > 0 else f"down{abs(pitch)}"


def _yaw_slug(yaw: int) -> str:
    return f"plus{yaw}" if yaw >= 0 else f"minus{abs(yaw)}"


def build_confirmation_v2_steps() -> tuple[VerticalValidationStep, ...]:
    steps: list[VerticalValidationStep] = []
    index = 1
    acquisition_orders = ((10, -10), (-10, 10), (10, -10))
    counts = {-10: 0, 10: 0}
    for order in acquisition_orders:
        for pitch in order:
            counts[pitch] += 1
            steps.append(VerticalValidationStep(
                index=index,
                condition_id=f"heldout-v2-acquire-{_pitch_slug(pitch)}deg",
                role="matching_acquisition",
                repetition=counts[pitch],
                initial_pitch_deg=float(pitch),
                target_pitch_deg=float(pitch),
                face_yaw_deg=0.0,
                sound_yaw_deg=0.0,
                transition_at_s=None,
                title=f"Fresh V2 speaking-face acquisition at pitch {pitch:+d}°",
                instruction=(
                    "Stay at front 0°, exactly 1 m horizontally from Reachy, with "
                    f"{_height_instruction(pitch)}. Keep your full face visible. During RECORDING, "
                    "say ‘Reachy, this is a fresh vertical tracking test.’ naturally every "
                    "1.5–2 seconds until recording ends."
                ),
                countdown_s=5,
                duration_s=12,
            ))
            index += 1

    maintenance_orders = ((-10, 10), (10, -10), (-10, 10))
    counts = {-10: 0, 10: 0}
    for order in maintenance_orders:
        for pitch in order:
            counts[pitch] += 1
            steps.append(VerticalValidationStep(
                index=index,
                condition_id=f"heldout-v2-maintain-centre-to-{_pitch_slug(pitch)}deg",
                role="maintenance_transition",
                repetition=counts[pitch],
                initial_pitch_deg=0.0,
                target_pitch_deg=float(pitch),
                face_yaw_deg=0.0,
                sound_yaw_deg=0.0,
                transition_at_s=7.0,
                title=f"Fresh V2 silent maintenance from centre to pitch {pitch:+d}°",
                instruction=(
                    "Start at front 0°, exactly 1 m away, with your eye line on the camera "
                    "optical-centre mark. From the start of RECORDING, repeat ‘Reachy, this is a "
                    "fresh vertical tracking test.’ clearly every 1.5 seconds and keep speaking "
                    "until the full-screen MOVE cue. At MOVE, stop speaking and silently change to "
                    f"{_height_instruction(pitch)} within 4 seconds. Then hold that mark, keep your "
                    "head level and keep one full face visible until recording ends."
                ),
                countdown_s=5,
                duration_s=15,
            ))
            index += 1

    for pitch in (10, -10):
        steps.append(VerticalValidationStep(
            index=index,
            condition_id=f"heldout-v2-silent-visible-{_pitch_slug(pitch)}deg",
            role="hard_negative",
            repetition=1,
            initial_pitch_deg=float(pitch),
            target_pitch_deg=float(pitch),
            face_yaw_deg=0.0,
            sound_yaw_deg=None,
            transition_at_s=None,
            title=f"Fresh V2 silent visible face at pitch {pitch:+d}°",
            instruction=(
                f"Stay at front 0°, exactly 1 m away, with {_height_instruction(pitch)}. "
                "Remain silent and keep every playback source stopped throughout RECORDING."
            ),
            countdown_s=5,
            duration_s=12,
        ))
        index += 1

    for repetition in (1, 2):
        steps.append(VerticalValidationStep(
            index=index,
            condition_id="heldout-v2-speech-with-no-face",
            role="hard_negative",
            repetition=repetition,
            initial_pitch_deg=None,
            target_pitch_deg=None,
            face_yaw_deg=None,
            sound_yaw_deg=0.0,
            transition_at_s=None,
            title="Fresh V2 front speech with no visible face",
            instruction=(
                "Keep every person completely outside Reachy’s camera view. Place the phone at "
                "front 0°, 1 m away, and play the same standard speech clip during RECORDING."
            ),
            countdown_s=5,
            duration_s=12,
        ))
        index += 1

    for pitch, face_yaw, sound_yaw in ((10, 20, -20), (-10, -20, 20)):
        face_side = "diagram-left" if face_yaw < 0 else "diagram-right"
        sound_side = "diagram-left" if sound_yaw < 0 else "diagram-right"
        steps.append(VerticalValidationStep(
            index=index,
            condition_id=(
                f"heldout-v2-mismatch-face-{_yaw_slug(face_yaw)}-{_pitch_slug(pitch)}-"
                f"sound-{_yaw_slug(sound_yaw)}"
            ),
            role="hard_negative",
            repetition=1,
            initial_pitch_deg=float(pitch),
            target_pitch_deg=float(pitch),
            face_yaw_deg=float(face_yaw),
            sound_yaw_deg=float(sound_yaw),
            transition_at_s=None,
            title=f"Fresh V2 mismatch: face {face_yaw:+d}°/{pitch:+d}°, phone {sound_yaw:+d}°",
            instruction=(
                f"Stand silently at {face_yaw:+d}° {face_side}, exactly 1 m away, with "
                f"{_height_instruction(pitch)}. Put the phone at {sound_yaw:+d}° {sound_side}, "
                "1 m away, and play the same standard speech clip during RECORDING."
            ),
            countdown_s=5,
            duration_s=12,
        ))
        index += 1
    return tuple(steps)


CONFIRMATION_V2_STEPS = build_confirmation_v2_steps()
MANIFEST_PATH = (
    PROJECT_ROOT / "data/manifests/stage3p_confirmation_protocol_v2.json"
).resolve()

SUCCESS_CRITERIA = {
    "instrumentation_quality": {
        "minimum_samples_12_second_trial": 48,
        "minimum_samples_15_second_trial": 60,
        "minimum_valid_doa_pct": 80.0,
        "minimum_fresh_single_face_pct_when_face_expected": 80.0,
        "minimum_eye_landmark_pct_when_face_expected": 80.0,
        "minimum_speech_positive_when_speech_expected": 3,
        "maximum_visible_face_pct_in_no_face_control": 20.0,
    },
    "procedural_audit": {
        "encrypted_local_clip_required_for_every_accepted_trial": True,
        "compliant_audit_verdict_required": True,
        "policy_never_receives_media": True,
    },
    "hard_negative_safety": {"maximum_would_adjust_rows": 0},
    "vertical_direction": {
        "maximum_wrong_sign_adjustments": 0,
        "maintenance_scored_immediately_after_move": True,
    },
    "static_acquisition": {
        "required_trials_with_adjustment_per_pitch": 3,
        "repetitions_per_pitch": 3,
        "maximum_target_error_deg": 6.0,
    },
    "silent_maintenance": {
        "required_pretransition_associations_per_pitch": 3,
        "required_trials_with_adjustment_per_pitch": 3,
        "repetitions_per_pitch": 3,
        "repositioning_interval_after_move_ms": 4000.0,
        "maximum_settled_target_error_deg": 6.0,
    },
}


def protocol_payload() -> dict[str, Any]:
    core = {
        "schema": "reachy-stage3p-held-out-vertical-confirmation-v2",
        "status": "FROZEN_FRESH_HELD_OUT_PASSIVE_PROTOCOL_NOT_AUTHORISED_FOR_ACTUATION",
        "frozen_at": "2026-08-29T20:15:00+01:00",
        "source_policy_fingerprint": SOURCE_POLICY_FINGERPRINT,
        "source_policy_freeze_bundle_sha256": SOURCE_POLICY_FREEZE_BUNDLE_SHA256,
        "policy_was_frozen_before_collection": True,
        "prior_stage3p_confirmation_excluded_from_validation": True,
        "prior_failed_result_used_only_for_disclosed_offline_development": True,
        "outcomes_cannot_change_acceptance_or_policy": True,
        "encrypted_procedural_audit_required": True,
        "coordinate_frame": {
            "yaw": "front 0 degrees; diagram-left negative; diagram-right positive",
            "pitch": "camera optical axis 0 degrees; up positive; down negative",
            "distance": "1 metre horizontal radius from Reachy camera axis",
        },
        "dynamic_scoring_boundary": {
            "wrong_sign_scored_from_move_cue": True,
            "final_accuracy_and_coverage_scored_after_move_ms": 4000.0,
            "reason": "Human motion occupies intermediate, not final, pitch positions during repositioning.",
        },
        "steps": [asdict(step) for step in CONFIRMATION_V2_STEPS],
        "success_criteria": SUCCESS_CRITERIA,
        "contains_pixels": False,
        "contains_audio": False,
        "contains_transcript": False,
        "separate_encrypted_audit_sidecar": True,
        "robot_requests": 0,
        "cloud_requests": 0,
        "actuation_commands": 0,
    }
    encoded = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**core, "fingerprint": hashlib.sha256(encoded).hexdigest()}


def write_manifest(path: Path = MANIFEST_PATH) -> Path:
    destination = path.resolve()
    if destination.parent != (PROJECT_ROOT / "data/manifests").resolve():
        raise ValueError("Stage 3P V2 held-out manifest must remain in data/manifests.")
    payload = protocol_payload()
    if destination.exists():
        existing = json.loads(destination.read_text(encoding="utf-8"))
        if existing != payload:
            raise ValueError("A different Stage 3P V2 held-out manifest already exists.")
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return destination


def validate_protocol() -> None:
    if len(CONFIRMATION_V2_STEPS) != 18:
        raise ValueError("Fresh held-out Stage 3P V2 must contain exactly 18 trials.")
    roles = {
        role: sum(step.role == role for step in CONFIRMATION_V2_STEPS)
        for role in {step.role for step in CONFIRMATION_V2_STEPS}
    }
    if roles != {"matching_acquisition": 6, "maintenance_transition": 6, "hard_negative": 6}:
        raise ValueError(f"Unexpected Stage 3P V2 role matrix: {roles}")
    maintenance = [
        step for step in CONFIRMATION_V2_STEPS if step.role == "maintenance_transition"
    ]
    if any(step.transition_at_s != 7.0 or step.duration_s != 15 for step in maintenance):
        raise ValueError("Every Stage 3P V2 maintenance trial must reserve seven seconds for association.")
    if any("within 4 seconds" not in step.instruction for step in maintenance):
        raise ValueError("Every Stage 3P V2 maintenance instruction must declare repositioning time.")


validate_protocol()
