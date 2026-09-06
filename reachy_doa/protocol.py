"""Deterministic, read-only experiment plans for the guided conductor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .angles import physical_heading_to_expected_doa


@dataclass(slots=True, frozen=True)
class TrialStep:
    plan_id: str
    index: int
    total: int
    label: str
    true_position_deg: float | None
    distance_m: float | None
    condition: str
    repetition: int
    duration_seconds: float
    operator_instruction: str
    prompt_text: str | None = "Reachy, this is a sound-direction test."

    @property
    def expected_doa_deg(self) -> float | None:
        if self.true_position_deg is None:
            return None
        return physical_heading_to_expected_doa(self.true_position_deg)

    @property
    def run_id(self) -> str:
        stamp = date.today().isoformat()
        return (
            f"{stamp}_{self.plan_id}_{self.index:02d}-of-{self.total:02d}_"
            f"{self.label}_take{self.repetition:02d}"
        )


@dataclass(slots=True, frozen=True)
class ExperimentPlan:
    plan_id: str
    title: str
    purpose: str
    setup: str
    steps: tuple[TrialStep, ...]


HEADINGS = (
    (0.0, "front"),
    (45.0, "front-right"),
    (90.0, "right"),
    (135.0, "back-right"),
    (180.0, "back"),
    (-135.0, "back-left"),
    (-90.0, "left"),
    (-45.0, "front-left"),
)


def _number_steps(plan_id: str, drafts: list[dict[str, object]]) -> tuple[TrialStep, ...]:
    total = len(drafts)
    return tuple(
        TrialStep(plan_id=plan_id, index=index, total=total, **draft)
        for index, draft in enumerate(drafts, start=1)
    )


def _speech_instruction(position: str, distance: float, style: str) -> str:
    return (
        f"Stand {distance:g} m from Reachy at {position}. Face the robot. "
        f"When RECORDING appears, say the displayed standard phrase once in {style}. "
        "Then remain still and quiet until the trial completes."
    )


def _continuous_speech_instruction(position: str, distance: float) -> str:
    return (
        f"Stand {distance:g} m from Reachy at {position}. Face the robot. "
        "When RECORDING appears, repeat the displayed standard phrase continuously "
        "in a comfortable normal voice until the recording ends."
    )


def build_plans() -> dict[str, ExperimentPlan]:
    plans: dict[str, ExperimentPlan] = {}

    silence = [
        {
            "label": "silence",
            "true_position_deg": None,
            "distance_m": None,
            "condition": "Silence",
            "repetition": repetition,
            "duration_seconds": 15.0,
            "operator_instruction": (
                "Leave the room as quiet as practical. Do not speak or touch the table. "
                "Note any motor, street, household, or ventilation noise after the trial."
            ),
            "prompt_text": None,
        }
        for repetition in range(1, 4)
    ]
    plans["silence-baseline"] = ExperimentPlan(
        "silence-baseline",
        "0 · Controlled silence baseline",
        "Measure invalid responses and unexpected speech-positive detections before calibration.",
        "Reachy stationary; all robot applications stopped; Motor Backend up and ready.",
        _number_steps("silence-baseline", silence),
    )

    calibration: list[dict[str, object]] = []
    for heading, label in HEADINGS:
        for repetition in range(1, 6):
            calibration.append(
                {
                    "label": label,
                    "true_position_deg": heading,
                    "distance_m": 1.0,
                    "condition": "Normal speech",
                    "repetition": repetition,
                    "duration_seconds": 6.0,
                    "operator_instruction": _speech_instruction(label, 1.0, "a normal voice"),
                }
            )
    plans["direction-calibration"] = ExperimentPlan(
        "direction-calibration",
        "1 · Eight-position directional calibration",
        "Forty controlled speech trials: eight physical headings with five repetitions each.",
        "Mark a 1 m radius around Reachy. Keep robot orientation, room and voice constant.",
        _number_steps("direction-calibration", calibration),
    )

    endfire: list[dict[str, object]] = []
    for heading, label in (HEADINGS[2], HEADINGS[6]):
        for repetition in range(1, 4):
            endfire.append(
                {
                    "label": f"{label}-continuous",
                    "true_position_deg": heading,
                    "distance_m": 1.0,
                    "condition": "Continuous speech · end-fire diagnostic",
                    "repetition": repetition,
                    "duration_seconds": 10.0,
                    "operator_instruction": _continuous_speech_instruction(label, 1.0),
                }
            )
    plans["endfire-diagnostic"] = ExperimentPlan(
        "endfire-diagnostic",
        "1B · Left/right continuous-speech diagnostic",
        "Determine whether sparse speech sampling or microphone-array end-fire geometry caused the weak exact-side estimates.",
        "Keep Reachy fixed. Use diagram-right then diagram-left at 1 m, with three repetitions each.",
        _number_steps("endfire-diagnostic", endfire),
    )

    orientation_swap: list[dict[str, object]] = []
    swapped_positions = (
        (
            -90.0,
            "original-right-after-180-rotation",
            "Stand at the original diagram-right (+90°) floor mark. With Reachy's whole base rotated 180° from calibration, this room position should now map to sensor DoA 180°. ",
        ),
        (
            90.0,
            "original-left-after-180-rotation",
            "Stand at the original diagram-left (−90°) floor mark. With Reachy's whole base rotated 180° from calibration, this room position should now map to sensor DoA 0°. ",
        ),
    )
    for heading, label, position_instruction in swapped_positions:
        for repetition in range(1, 4):
            orientation_swap.append(
                {
                    "label": label,
                    "true_position_deg": heading,
                    "distance_m": 1.0,
                    "condition": "Continuous speech · 180-degree orientation swap",
                    "repetition": repetition,
                    "duration_seconds": 10.0,
                    "operator_instruction": (
                        position_instruction
                        + "Face Reachy. When RECORDING appears, repeat the displayed standard phrase continuously "
                        "in a comfortable normal voice until the recording ends."
                    ),
                }
            )
    plans["orientation-swap-control"] = ExperimentPlan(
        "orientation-swap-control",
        "1C · 180° orientation-swap control",
        "Distinguish a robot-frame end-fire bias from a room-position/reflection effect by swapping the sensor orientation while reusing the same two floor marks.",
        "Before loading: mark the base outline and front direction, put Motor Backend to sleep, rotate the whole base exactly 180° without twisting the head, then re-enable Motor Backend. Keep all Reachy applications stopped.",
        _number_steps("orientation-swap-control", orientation_swap),
    )

    ranges: list[dict[str, object]] = []
    for distance in (0.5, 1.0, 2.0, 4.0):
        for heading, label in (HEADINGS[0], HEADINGS[2], HEADINGS[6]):
            for repetition in range(1, 4):
                ranges.append(
                    {
                        "label": f"{label}-{distance:g}m",
                        "true_position_deg": heading,
                        "distance_m": distance,
                        "condition": "Range limit · normal speech",
                        "repetition": repetition,
                        "duration_seconds": 6.0,
                        "operator_instruction": _speech_instruction(label, distance, "a normal voice"),
                    }
                )
    plans["range-limits"] = ExperimentPlan(
        "range-limits",
        "2 · Range limits",
        "Compare detection and directional error across four distances and three lateral positions.",
        "Use the same room and phrase. If 4 m is impossible, use the greatest measured distance and note it.",
        _number_steps("range-limits", ranges),
    )

    styles = (
        ("normal", "Normal speech", "a normal voice", 6.0),
        ("quiet", "Quiet speech", "a quiet voice", 6.0),
        ("whisper", "Whisper", "a whisper", 6.0),
        ("loud", "Loud speech", "a loud but comfortable voice", 6.0),
        ("short-word", "Short word", "one short word", 4.0),
        ("continuous", "Continuous speech", "continuous speech", 10.0),
    )
    speech_limits: list[dict[str, object]] = []
    for label, condition, instruction_style, duration in styles:
        for repetition in range(1, 4):
            speech_limits.append(
                {
                    "label": label,
                    "true_position_deg": 0.0,
                    "distance_m": 1.0,
                    "condition": condition,
                    "repetition": repetition,
                    "duration_seconds": duration,
                    "operator_instruction": _speech_instruction("front", 1.0, instruction_style),
                    "prompt_text": "Hello." if label == "short-word" else "Reachy, this is a sound-direction test.",
                }
            )
    plans["speech-limits"] = ExperimentPlan(
        "speech-limits",
        "3 · Speech limits",
        "Measure sensitivity to voice level, duration and speaking style.",
        "One speaker, 1 m in front, constant room. Do not strain or shout.",
        _number_steps("speech-limits", speech_limits),
    )

    sound_types = (
        ("clap", "Clap", "Clap once at chest height"),
        ("keys", "Keys", "Jingle keys for two seconds"),
        ("music", "Music", "Play five seconds of music from your phone"),
        ("television", "Television", "Play five seconds of television dialogue from your phone"),
        ("tone", "Phone playback", "Play a steady non-speech tone from your phone"),
        ("mechanical", "Mechanical sound", "Create a safe, repeatable mechanical sound"),
    )
    non_speech: list[dict[str, object]] = []
    for label, condition, action in sound_types:
        for repetition in range(1, 4):
            non_speech.append(
                {
                    "label": label,
                    "true_position_deg": 0.0,
                    "distance_m": 1.0,
                    "condition": condition,
                    "repetition": repetition,
                    "duration_seconds": 8.0,
                    "operator_instruction": (
                        f"Place the sound source 1 m in front of Reachy. When RECORDING appears, {action}. "
                        "Do not speak. Stop the sound and remain still until completion."
                    ),
                    "prompt_text": None,
                }
            )
    plans["non-speech-confusion"] = ExperimentPlan(
        "non-speech-confusion",
        "4 · Non-speech confusion",
        "Test whether the speech flag responds to non-speech and media sounds.",
        "Keep playback volume moderate and fixed. The laptop stores only DoA metadata, never audio.",
        _number_steps("non-speech-confusion", non_speech),
    )

    environments = (
        ("open-room", "Open room"),
        ("near-wall", "Near wall"),
        ("doorway", "Doorway"),
        ("reflective-corner", "Reflective corner"),
        ("background-noise", "Background noise"),
    )
    adversity: list[dict[str, object]] = []
    for label, condition in environments:
        for repetition in range(1, 4):
            adversity.append(
                {
                    "label": label,
                    "true_position_deg": 0.0,
                    "distance_m": 1.0,
                    "condition": condition,
                    "repetition": repetition,
                    "duration_seconds": 6.0,
                    "operator_instruction": (
                        f"Use the {condition.lower()} setup. Stand 1 m in front. "
                        "Say the standard phrase once in a normal voice, then remain quiet."
                    ),
                }
            )
    plans["acoustic-adversity"] = ExperimentPlan(
        "acoustic-adversity",
        "5 · Acoustic adversity",
        "Quantify room-placement and background-noise effects.",
        "Change only the named environmental factor; keep distance, heading and phrase constant.",
        _number_steps("acoustic-adversity", adversity),
    )

    conflicts = (
        ("alternating", "Two speakers · alternating", "Alternate one phrase each without overlap"),
        ("rapid-switch", "Two speakers · rapid switching", "Rapidly alternate short words"),
        ("overlap", "Two simultaneous speakers", "Speak the phrase at the same time"),
        ("masking", "Two speakers · louder masking", "Speak simultaneously; right speaker moderately louder"),
    )
    two_speaker: list[dict[str, object]] = []
    for label, condition, action in conflicts:
        for repetition in range(1, 4):
            two_speaker.append(
                {
                    "label": label,
                    "true_position_deg": None,
                    "distance_m": 1.0,
                    "condition": condition,
                    "repetition": repetition,
                    "duration_seconds": 10.0,
                    "operator_instruction": (
                        "Place one speaker 1 m left and one 1 m right of Reachy. "
                        f"When RECORDING appears, {action}. Stop when the timer ends."
                    ),
                    "prompt_text": "Hello." if label == "rapid-switch" else "Reachy, this is a sound-direction test.",
                }
            )
    plans["two-speaker-conflict"] = ExperimentPlan(
        "two-speaker-conflict",
        "6 · Two-speaker conflict",
        "Challenge a single DoA estimate with alternation, overlap and masking.",
        "Requires two people at equal measured distances. No robot application is started.",
        _number_steps("two-speaker-conflict", two_speaker),
    )

    front_back: list[dict[str, object]] = []
    for heading, label in ((0.0, "front-only-continuous"), (180.0, "back-only-continuous")):
        position = "diagram-front" if heading == 0.0 else "diagram-back"
        silent_position = "diagram-back" if heading == 0.0 else "diagram-front"
        for repetition in range(1, 4):
            front_back.append(
                {
                    "label": label,
                    "true_position_deg": heading,
                    "distance_m": 1.0,
                    "condition": f"Front/back ambiguity · {position} only",
                    "repetition": repetition,
                    "duration_seconds": 10.0,
                    "operator_instruction": (
                        f"The active speaker stands 1 m at {position}; the other person remains silent at "
                        f"{silent_position}. When RECORDING appears, the active speaker repeats the displayed "
                        "phrase continuously in a comfortable normal voice until the recording ends."
                    ),
                }
            )

    for mode, condition in (("alternating", "Front/back ambiguity · alternating phrases"),
                            ("rapid-switch", "Front/back ambiguity · rapid switching")):
        for repetition in range(1, 4):
            starter = "diagram-front" if repetition in (1, 3) else "diagram-back"
            if mode == "alternating":
                action = (
                    f"Start with the {starter} speaker, then alternate one complete displayed phrase at a time "
                    "without overlap until recording ends."
                )
                prompt = "Reachy, this is a sound-direction test."
            else:
                action = (
                    f"Start with the {starter} speaker, then alternate the displayed short word about twice per "
                    "second without overlap until recording ends."
                )
                prompt = "Hello."
            front_back.append(
                {
                    "label": f"front-back-{mode}",
                    "true_position_deg": None,
                    "distance_m": 1.0,
                    "condition": condition,
                    "repetition": repetition,
                    "duration_seconds": 10.0,
                    "operator_instruction": (
                        "Place one speaker 1 m at diagram-front and one 1 m at diagram-back. " + action
                    ),
                    "prompt_text": prompt,
                }
            )

    plans["front-back-ambiguity"] = ExperimentPlan(
        "front-back-ambiguity",
        "6B · Front/back ambiguity",
        "Test whether repeated DoA distributions or temporal behavior contain usable front/back information despite the nominal 90-degree fold.",
        "Requires two people at the fixed 1 m diagram-front and diagram-back marks. Keep Reachy in its original orientation; all robot applications remain stopped.",
        _number_steps("front-back-ambiguity", front_back),
    )

    return plans


PLANS = build_plans()
