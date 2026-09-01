"""Frozen targeted confirmation for the association-gated visual MOVE cue.

This is a fresh passive protocol.  It confirms only the operator cue boundary
identified after the frozen V6 result; it cannot change V6 and it contains no
robot SDK, controller, media inference, or actuation capability.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from reachy_stage2a.config import PROJECT_ROOT

from .calibration import vertical_offset_cm


SOURCE_POLICY_FINGERPRINT = (
    "cc6fc9731d2149a2e273989e6e0dea4caacca5859aee45ccf16d82d1f53b6da1"
)
SOURCE_POLICY_FREEZE_BUNDLE_SHA256 = (
    "464fbe6c038d12a41685d40c7a4d29e7e893ca0f1ad9bf5869ce4054f2bb1caf"
)
SOURCE_V6_RESULT_BUNDLE_SHA256 = (
    "2a330cb7f65fc151306328fc95109da3ee61c4736cffd1bcd733aac4d9ca4db8"
)
DESIGN_FILE = "data/analysis/stage3p_association_gated_move_cue_design_v1.json"
MINIMUM_CONSECUTIVE_CENTER_ROWS = 3
MAXIMUM_WAIT_MS = 12000.0
POST_CUE_OBSERVATION_MS = 8000.0


@dataclass(frozen=True, slots=True)
class CueConfirmationStep:
    index: int
    condition_id: str
    role: str
    repetition: int
    initial_pitch_deg: float | None
    target_pitch_deg: float | None
    face_yaw_deg: float | None
    sound_yaw_deg: float | None
    transition_at_s: float | None
    expected_cue_outcome: str
    title: str
    instruction: str
    countdown_s: int = 5
    duration_s: int = 20

    def run_id(self, date_prefix: str) -> str:
        return (
            f"{date_prefix}_stage3p-cue-confirmation_{self.index:02d}-of-09_"
            f"{self.condition_id}_take{self.repetition:02d}"
        )


def _height_instruction(pitch: int) -> str:
    direction = "above" if pitch > 0 else "below"
    return (
        f"your eye line {abs(vertical_offset_cm(pitch)):.1f} cm {direction} "
        "the camera optical-centre mark"
    )


def build_steps() -> tuple[CueConfirmationStep, ...]:
    steps: list[CueConfirmationStep] = []
    # ABBAAB counterbalancing prevents a direction from being confounded with
    # collection order while retaining three independent trials per pitch.
    pitches = (-10, 10, 10, -10, -10, 10)
    repetitions = {-10: 0, 10: 0}
    for index, pitch in enumerate(pitches, start=1):
        repetitions[pitch] += 1
        direction = "UP" if pitch > 0 else "DOWN"
        steps.append(CueConfirmationStep(
            index=index,
            condition_id=f"association-gated-centre-to-{'up10' if pitch > 0 else 'down10'}",
            role="association_gated_transition",
            repetition=repetitions[pitch],
            initial_pitch_deg=0.0,
            target_pitch_deg=float(pitch),
            face_yaw_deg=0.0,
            sound_yaw_deg=0.0,
            transition_at_s=None,
            expected_cue_outcome="MOVE_CUE",
            title=f"Association-gated centre-to-{direction.lower()} transition",
            instruction=(
                "Start at front 0°, exactly 1 m away, with your eye line on the camera "
                "optical-centre mark. From RECORDING, repeat ‘Reachy, this is an "
                "association-gated tracking test.’ clearly about every 1.5 seconds. "
                f"Only if the full-screen MOVE {direction} cue appears, stop speaking, change to "
                f"{_height_instruction(pitch)}, and keep one full face visible until recording ends. "
                "If a red NO MOVE timeout appears, do not move."
            ),
        ))

    steps.extend((
        CueConfirmationStep(
            index=7,
            condition_id="control-silent-visible-centre",
            role="fail_closed_control",
            repetition=1,
            initial_pitch_deg=0.0,
            target_pitch_deg=0.0,
            face_yaw_deg=0.0,
            sound_yaw_deg=None,
            transition_at_s=None,
            expected_cue_outcome="TIMEOUT_NO_CUE",
            title="No-cue control: silent centred face",
            instruction=(
                "Stay at front 0°, exactly 1 m away, with your eye line on the camera "
                "optical-centre mark. Remain silent, keep one full face visible, and do not move. "
                "The correct result is a red NO MOVE timeout with no green MOVE cue."
            ),
            duration_s=12,
        ),
        CueConfirmationStep(
            index=8,
            condition_id="control-speaking-no-face",
            role="fail_closed_control",
            repetition=1,
            initial_pitch_deg=None,
            target_pitch_deg=None,
            face_yaw_deg=None,
            sound_yaw_deg=0.0,
            transition_at_s=None,
            expected_cue_outcome="TIMEOUT_NO_CUE",
            title="No-cue control: speech without a visible face",
            instruction=(
                "Keep every person completely outside Reachy’s camera view. From RECORDING, "
                "play or speak the association-gated test phrase from front 0° about every "
                "1.5 seconds. Do not enter view and do not move. The correct result is a red "
                "NO MOVE timeout with no green MOVE cue."
            ),
            duration_s=12,
        ),
        CueConfirmationStep(
            index=9,
            condition_id="control-speaking-visible-up10-not-centred",
            role="fail_closed_control",
            repetition=1,
            initial_pitch_deg=10.0,
            target_pitch_deg=10.0,
            face_yaw_deg=0.0,
            sound_yaw_deg=0.0,
            transition_at_s=None,
            expected_cue_outcome="TIMEOUT_NO_CUE",
            title="No-cue control: associated but not centred",
            instruction=(
                f"Stay at front 0°, exactly 1 m away, with {_height_instruction(10)}. From "
                "RECORDING, repeat the association-gated test phrase clearly about every "
                "1.5 seconds. Remain at that mark and do not move. The correct result is a red "
                "NO MOVE timeout because centred readiness was never established."
            ),
            duration_s=12,
        ),
    ))
    return tuple(steps)


CUE_CONFIRMATION_STEPS = build_steps()
MANIFEST_PATH = (
    PROJECT_ROOT / "data/manifests/stage3p_association_gated_cue_confirmation_v1.json"
).resolve()

SUCCESS_CRITERIA = {
    "instrumentation_quality": {
        "minimum_numeric_hz": 4.0,
        "minimum_valid_doa_pct": 80.0,
        "minimum_fresh_single_face_pct_when_face_expected": 80.0,
        "minimum_eye_landmark_pct_when_face_expected": 80.0,
        "maximum_visible_face_pct_in_no_face_control": 20.0,
        "minimum_speech_positive_when_speech_expected": 3,
    },
    "association_gated_move": {
        "required_transition_trials_per_pitch": 3,
        "maximum_wait_ms": MAXIMUM_WAIT_MS,
        "minimum_consecutive_confirmed_center_rows": MINIMUM_CONSECUTIVE_CENTER_ROWS,
        "maximum_cue_replay_lag_ms": 1500.0,
        "post_cue_scoring_delay_ms": 4000.0,
        "required_post_cue_correction_trials_per_pitch": 3,
        "maximum_abs_increment_deg": 3.0,
        "maximum_wrong_sign_adjustments": 0,
        "maximum_pre_cue_adjustments": 0,
    },
    "fail_closed_controls": {
        "required_no_cue_timeouts": 3,
        "maximum_unexpected_move_cues": 0,
        "maximum_shadow_adjustments": 0,
    },
    "procedural_audit": {
        "encrypted_local_clip_required_for_every_accepted_trial": True,
        "compliant_audit_verdict_required": True,
        "policy_never_receives_media": True,
    },
}


def protocol_payload() -> dict[str, Any]:
    core = {
        "schema": "reachy-stage3p-association-gated-cue-targeted-confirmation-v1",
        "status": "FROZEN_FRESH_TARGETED_PASSIVE_PROTOCOL_NOT_AUTHORISED_FOR_ACTUATION",
        "frozen_at": "2026-08-31T12:00:00+01:00",
        "source_policy_fingerprint": SOURCE_POLICY_FINGERPRINT,
        "source_policy_freeze_bundle_sha256": SOURCE_POLICY_FREEZE_BUNDLE_SHA256,
        "source_v6_result_bundle_sha256": SOURCE_V6_RESULT_BUNDLE_SHA256,
        "source_design_file": DESIGN_FILE,
        "policy_parameters_changed": False,
        "cue_gate_frozen_before_collection": True,
        "fresh_data_isolated_from_v6": True,
        "outcomes_cannot_change_policy_cue_gate_or_acceptance": True,
        "purpose": (
            "Independently confirm that a visual MOVE cue is issued only after stable centred "
            "speaker/face association, and otherwise times out without a movement instruction."
        ),
        "cue_rule": {
            "minimum_consecutive_confirmed_center_rows": MINIMUM_CONSECUTIVE_CENTER_ROWS,
            "center_pitch_tolerance_deg": 2.5,
            "maximum_wait_ms": MAXIMUM_WAIT_MS,
            "post_cue_silent_observation_ms": POST_CUE_OBSERVATION_MS,
            "cue_type": "FULL_SCREEN_VISUAL_ONLY",
            "on_timeout": "END_TRIAL_WITH_NO_MOVE_CUE",
            "unexpected_control_cue": "SUPPRESS_MOVE_INSTRUCTION_AND_FAIL_TRIAL",
            "face_or_instrument_fault": "RESET_READY_STREAK",
        },
        "coordinate_frame": {
            "yaw": "front 0 degrees; diagram-left negative; diagram-right positive",
            "pitch": "camera optical axis 0 degrees; up positive; down negative",
            "distance": "1 metre horizontal radius from Reachy camera axis",
        },
        "steps": [asdict(step) for step in CUE_CONFIRMATION_STEPS],
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
    expected_parent = (PROJECT_ROOT / "data/manifests").resolve()
    if destination.parent != expected_parent:
        raise ValueError("Cue-confirmation manifest must remain in data/manifests.")
    payload = protocol_payload()
    if destination.exists():
        existing = json.loads(destination.read_text(encoding="utf-8"))
        if existing != payload:
            raise ValueError("A different targeted cue-confirmation manifest already exists.")
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return destination


def validate_protocol() -> None:
    if len(CUE_CONFIRMATION_STEPS) != 9:
        raise ValueError("Targeted cue confirmation must contain exactly nine trials.")
    roles = {
        role: sum(step.role == role for step in CUE_CONFIRMATION_STEPS)
        for role in {step.role for step in CUE_CONFIRMATION_STEPS}
    }
    if roles != {"association_gated_transition": 6, "fail_closed_control": 3}:
        raise ValueError(f"Unexpected targeted cue-confirmation matrix: {roles}")
    transitions = [
        step for step in CUE_CONFIRMATION_STEPS
        if step.role == "association_gated_transition"
    ]
    if any(step.transition_at_s is not None for step in transitions):
        raise ValueError("Targeted transitions must never contain a clock-based MOVE time.")
    for pitch in (-10.0, 10.0):
        if sum(step.target_pitch_deg == pitch for step in transitions) != 3:
            raise ValueError("Targeted transitions require three trials per pitch.")
    if any(step.expected_cue_outcome != "TIMEOUT_NO_CUE" for step in CUE_CONFIRMATION_STEPS[6:]):
        raise ValueError("Every control must require a fail-closed no-cue timeout.")


validate_protocol()
