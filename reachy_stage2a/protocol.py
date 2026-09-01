"""Controlled, passive Stage 2A experiment matrix and row summaries."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Any


@dataclass(frozen=True)
class MatrixStep:
    index: int
    condition_id: str
    title: str
    repetition: int
    instruction: str
    expected_result: str
    countdown_s: int = 5
    duration_s: int = 20

    def run_id(self, date_prefix: str) -> str:
        return (
            f"{date_prefix}_stage2a-matrix_{self.index:02d}-of-15_"
            f"{self.condition_id}_take{self.repetition:02d}"
        )

    @property
    def condition_code(self) -> str:
        return f"stage2a-matrix-{self.condition_id}"


_CONDITIONS = (
    (
        "visible-silent-face",
        "Visible, silent face",
        "Stand 1 m directly in front of Reachy, face centred and visible. "
        "Remain silent and still throughout RECORDING.",
        "No acoustic target should be confirmed; any raw speech-positive samples are false-activation candidates.",
    ),
    (
        "speech-no-visible-face",
        "Speech with no visible face",
        "Stand 1 m directly behind Reachy so your face is outside its camera view. "
        "During RECORDING, say ‘Reachy, this is a sound-direction test.’ naturally about every 3 seconds.",
        "Acoustic evidence may track, but fusion should withhold because no face is visible.",
    ),
    (
        "matching-face-speech",
        "Matching face and speech",
        "Stand 1 m directly in front of Reachy, face centred and visible. "
        "During RECORDING, say ‘Reachy, this is a sound-direction test.’ naturally about every 3 seconds.",
        "The visible face should geometrically confirm the compatible acoustic hypothesis.",
    ),
    (
        "mismatched-face-phone-right",
        "Mismatched visible face and phone speech",
        "Place a phone 1 m at diagram-right, using the same podcast speech clip at about 35% volume. "
        "Stand front-centre, remain silent and keep your face visible while the phone plays during RECORDING.",
        "Fusion should withhold when the visible face and acoustic evidence disagree.",
    ),
    (
        "partial-edge-face-speech",
        "Partial edge face with speech",
        "Stand 1 m in front, but place your face at the camera-frame edge with roughly half visible. "
        "During RECORDING, say ‘Reachy, this is a sound-direction test.’ naturally about every 3 seconds.",
        "This probes detector dropout, duplicate boxes and safe withholding near the visual boundary.",
    ),
)


def build_matrix_steps() -> tuple[MatrixStep, ...]:
    steps: list[MatrixStep] = []
    index = 1
    for condition_id, title, instruction, expected_result in _CONDITIONS:
        for repetition in range(1, 4):
            steps.append(
                MatrixStep(
                    index=index,
                    condition_id=condition_id,
                    title=title,
                    repetition=repetition,
                    instruction=instruction,
                    expected_result=expected_result,
                )
            )
            index += 1
    return tuple(steps)


MATRIX_STEPS = build_matrix_steps()


def summarise_matrix_rows(rows: list[dict[str, Any]]) -> dict[str, float | int]:
    """Return transparent trial-level quality and outcome counts."""
    count = len(rows)
    valid_rows = [row for row in rows if row.get("http_status") == 200]
    latencies = [
        float(row["http_latency_ms"])
        for row in valid_rows
        if row.get("http_latency_ms") is not None
    ]
    return {
        "samples": count,
        "valid": len(valid_rows),
        "valid_pct": 100.0 * len(valid_rows) / count if count else 0.0,
        "speech_positive": sum(row.get("speech_detected") is True for row in rows),
        "no_face": sum((row.get("face_count") or 0) == 0 for row in rows),
        "single_face": sum(row.get("face_count") == 1 for row in rows),
        "multiple_faces": sum((row.get("face_count") or 0) > 1 for row in rows),
        "confirmed": sum(row.get("fusion_state") == "CONFIRMED" for row in rows),
        "withheld": sum(row.get("fusion_state") != "CONFIRMED" for row in rows),
        "median_latency_ms": median(latencies) if latencies else 0.0,
    }


def matrix_quality_issues(
    step: MatrixStep,
    summary: dict[str, float | int],
) -> tuple[str, ...]:
    """Check protocol observability, never whether the measured result was desirable."""
    issues: list[str] = []
    samples = int(summary.get("samples", 0))
    if samples < 20:
        issues.append("fewer than 20 numeric observations")
    if float(summary.get("valid_pct", 0.0)) < 80.0:
        issues.append("fewer than 80% valid DoA responses")

    visible_conditions = {
        "visible-silent-face",
        "matching-face-speech",
        "mismatched-face-phone-right",
    }
    if step.condition_id in visible_conditions and samples:
        if int(summary.get("single_face", 0)) / samples < 0.60:
            issues.append("one visible face was not detected in at least 60% of samples")
    if step.condition_id == "speech-no-visible-face" and samples:
        if int(summary.get("no_face", 0)) / samples < 0.80:
            issues.append("a face was visible in more than 20% of the no-face control")
    if step.condition_id in {
        "speech-no-visible-face",
        "matching-face-speech",
        "mismatched-face-phone-right",
        "partial-edge-face-speech",
    }:
        if int(summary.get("speech_positive", 0)) < 3:
            issues.append("fewer than three speech-positive samples were observed")
    return tuple(issues)
