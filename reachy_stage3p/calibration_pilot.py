"""Isolated passive eye-line calibration pilot for Stage 3P V2 design.

The pilot records numeric YuNet face-box and eye-midpoint coordinates only.
It does not select a movement policy and contains no robot-control path.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from typing import Any

from reachy_stage2a.config import PROJECT_ROOT
from reachy_stage3v.analysis import load_rows, summarise_rows
from reachy_stage3v.config import (
    ANALYSIS_DIR,
    DATA_DIR,
    REPORT_PATH,
    RESULT_CSV_PATH,
    RESULT_JSON_PATH,
)

from .calibration import face_center_to_pitch, vertical_offset_cm


@dataclass(frozen=True, slots=True)
class CalibrationPilotStep:
    index: int
    condition_id: str
    role: str
    repetition: int
    initial_pitch_deg: float
    target_pitch_deg: float
    face_yaw_deg: float
    sound_yaw_deg: float | None
    transition_at_s: float | None
    title: str
    instruction: str
    countdown_s: int = 5
    duration_s: int = 8

    def run_id(self, date_prefix: str) -> str:
        return (
            f"{date_prefix}_stage3p-calibration_{self.index:02d}-of-09_"
            f"{self.condition_id}_take{self.repetition:02d}"
        )


def _instruction(pitch: int) -> str:
    if pitch == 0:
        position = "your eye line exactly on the camera optical-centre mark"
    else:
        direction = "above" if pitch > 0 else "below"
        position = f"your eye line 17.6 cm {direction} the camera optical-centre mark"
    return (
        f"Stay at the front 0° mark, exactly 1 m horizontally from Reachy, with {position}. "
        "Remain silent, keep your head level and keep one complete face visible. Do not lean "
        "toward or away from Reachy during RECORDING."
    )


def build_calibration_steps() -> tuple[CalibrationPilotStep, ...]:
    # Counterbalanced order limits drift, fatigue and learning from becoming a
    # position-specific bias. Each physical target is collected three times.
    orders = ((0, -10, 10), (10, 0, -10), (-10, 10, 0))
    counts = {-10: 0, 0: 0, 10: 0}
    steps: list[CalibrationPilotStep] = []
    for pitch in (item for order in orders for item in order):
        counts[pitch] += 1
        label = "centre" if pitch == 0 else "up10" if pitch > 0 else "down10"
        steps.append(CalibrationPilotStep(
            index=len(steps) + 1,
            condition_id=f"eye-line-{label}",
            role="geometry_calibration",
            repetition=counts[pitch],
            initial_pitch_deg=float(pitch),
            target_pitch_deg=float(pitch),
            face_yaw_deg=0.0,
            sound_yaw_deg=None,
            transition_at_s=None,
            title=f"Eye-line calibration at {pitch:+d}°",
            instruction=_instruction(pitch),
        ))
    return tuple(steps)


CALIBRATION_STEPS = build_calibration_steps()

SUCCESS_CRITERIA = {
    "instrumentation_quality": {
        "minimum_samples": 32,
        "minimum_valid_doa_pct": 80.0,
        "minimum_fresh_single_face_pct": 90.0,
        "minimum_eye_midpoint_pct": 90.0,
    },
    "pilot_geometry": {
        "maximum_within_trial_eye_pitch_iqr_deg": 2.0,
        "required_repetitions_per_position": 3,
        "required_positions_deg": [-10.0, 0.0, 10.0],
    },
}


def protocol_payload() -> dict[str, Any]:
    core = {
        "schema": "reachy-stage3p-eye-line-calibration-pilot-v1",
        "status": "FROZEN_CALIBRATION_PILOT_NOT_HELD_OUT_NOT_AUTHORISED_FOR_ACTUATION",
        "purpose": (
            "Measure the relationship between physical eye-line marks, YuNet eye midpoint and "
            "the legacy face-box centre before designing Stage 3P V2."
        ),
        "parent_stage3p_d1_protocol_fingerprint": (
            "de264f940166e3018512b1946d5f8a0b271d97956c537506b8e0349c9b0d6d2a"
        ),
        "counterbalanced_sequence": [step.target_pitch_deg for step in CALIBRATION_STEPS],
        "steps": [asdict(step) for step in CALIBRATION_STEPS],
        "success_criteria": SUCCESS_CRITERIA,
        "required_data_mode": "development_audit",
        "privacy": {
            "numeric_dataset_contains_pixels": False,
            "numeric_dataset_contains_audio": False,
            "numeric_dataset_contains_transcript": False,
            "audit_clip_is_separate_encrypted_local_and_bounded": True,
        },
        "actuation_commands": 0,
        "cloud_requests": 0,
    }
    encoded = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**core, "fingerprint": hashlib.sha256(encoded).hexdigest()}


def _number(row: dict[str, Any], key: str) -> float | None:
    try:
        value = row.get(key)
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    weight = index - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _pitch_values(rows: list[dict[str, Any]], column: str) -> list[float]:
    result: list[float] = []
    for row in rows:
        value = _number(row, column)
        if value is not None and 0.0 <= value <= 1.0 and int(float(row.get("face_count") or 0)) == 1:
            result.append(face_center_to_pitch(value))
    return result


def quality_issues(_step: CalibrationPilotStep, summary: dict[str, float | int]) -> tuple[str, ...]:
    limits = SUCCESS_CRITERIA["instrumentation_quality"]
    issues: list[str] = []
    if int(summary.get("samples", 0)) < int(limits["minimum_samples"]):
        issues.append("fewer than 32 numeric observations")
    if float(summary.get("valid_pct", 0.0)) < float(limits["minimum_valid_doa_pct"]):
        issues.append("fewer than 80% valid DoA responses")
    if float(summary.get("fresh_single_face_pct", 0.0)) < float(
        limits["minimum_fresh_single_face_pct"]
    ):
        issues.append("a fresh single face was not present in at least 90% of samples")
    if float(summary.get("eye_midpoint_pct", 0.0)) < float(limits["minimum_eye_midpoint_pct"]):
        issues.append("numeric eye landmarks were not present in at least 90% of samples")
    return tuple(issues)


def evaluate_calibration_trial(step: CalibrationPilotStep, rows: list[dict[str, Any]]) -> dict[str, Any]:
    eye = _pitch_values(rows, "face_eye_midpoint_y_norm")
    box = _pitch_values(rows, "face_center_y_norm")
    q1 = _percentile(eye, 0.25)
    q3 = _percentile(eye, 0.75)
    eye_iqr = None if q1 is None or q3 is None else q3 - q1
    return {
        "step": step.index,
        "condition": step.condition_id,
        "role": step.role,
        "repetition": step.repetition,
        "target_pitch_deg": step.target_pitch_deg,
        "rows": len(rows),
        "eye_rows": len(eye),
        "eye_midpoint_pitch_median_deg": median(eye) if eye else None,
        "eye_midpoint_pitch_iqr_deg": eye_iqr,
        "face_box_pitch_median_deg": median(box) if box else None,
        # Compatibility fields used by the shared passive conductor UI. No
        # movement shadow is evaluated in this geometry-only pilot.
        "would_adjust_rows": 0,
        "first_target_pitch_deg": median(eye) if eye else None,
        "wrong_sign_adjustments": 0,
    }


def _linear_fit(points: list[tuple[float, float]]) -> dict[str, float | None]:
    if len(points) < 2:
        return {"slope": None, "intercept_deg": None, "rmse_deg": None}
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    denominator = sum((x - mx) ** 2 for x in xs)
    if denominator <= 0.0:
        return {"slope": None, "intercept_deg": None, "rmse_deg": None}
    slope = sum((x - mx) * (y - my) for x, y in points) / denominator
    intercept = my - slope * mx
    residuals = [(slope * x + intercept) - y for x, y in points]
    rmse = math.sqrt(sum(value * value for value in residuals) / len(residuals))
    return {"slope": slope, "intercept_deg": intercept, "rmse_deg": rmse}


def evaluate_saved_files(csv_files: list[str]) -> dict[str, Any]:
    if len(csv_files) != len(CALIBRATION_STEPS):
        raise ValueError("A complete Stage 3P calibration pilot requires nine accepted files.")
    trials: list[dict[str, Any]] = []
    for step, filename in zip(CALIBRATION_STEPS, csv_files):
        path = (DATA_DIR / filename).resolve()
        if path.parent != DATA_DIR or not path.is_file():
            raise ValueError(f"Calibration pilot file is missing: {filename}")
        rows = load_rows(path)
        issues = quality_issues(step, summarise_rows(rows))
        if issues:
            raise ValueError(f"Calibration pilot file fails quality: {filename}: {'; '.join(issues)}")
        compliance = path.with_name(path.stem + "_compliance.json")
        if not compliance.is_file() or json.loads(compliance.read_text(encoding="utf-8")).get(
            "verdict"
        ) != "COMPLIANT":
            raise ValueError(f"Calibration pilot file lacks a compliant audit: {filename}")
        trials.append({**evaluate_calibration_trial(step, rows), "file": filename})

    summaries: list[dict[str, Any]] = []
    points: list[tuple[float, float]] = []
    iqr_limit = float(
        SUCCESS_CRITERIA["pilot_geometry"]["maximum_within_trial_eye_pitch_iqr_deg"]
    )
    for target in (-10.0, 0.0, 10.0):
        group = [trial for trial in trials if trial["target_pitch_deg"] == target]
        observed = [
            float(trial["eye_midpoint_pitch_median_deg"])
            for trial in group
            if trial["eye_midpoint_pitch_median_deg"] is not None
        ]
        points.extend((value, target) for value in observed)
        summaries.append({
            "target_pitch_deg": target,
            "trials": len(group),
            "median_eye_pitch_deg": median(observed) if observed else None,
            "minimum_eye_pitch_deg": min(observed) if observed else None,
            "maximum_eye_pitch_deg": max(observed) if observed else None,
            "stable_trials": sum(
                trial["eye_midpoint_pitch_iqr_deg"] is not None
                and float(trial["eye_midpoint_pitch_iqr_deg"]) <= iqr_limit
                for trial in group
            ),
        })
    mapping = _linear_fit(points)
    return {
        "schema": "reachy-stage3p-eye-line-calibration-pilot-result-v1",
        "status": "CALIBRATION_PILOT_ONLY_NOT_HELD_OUT_NOT_AUTHORISED_FOR_ACTUATION",
        "protocol_fingerprint": protocol_payload()["fingerprint"],
        "collection_complete": True,
        "all_positions_covered": all(row["trials"] == 3 for row in summaries),
        "stability_passed": all(row["stable_trials"] == 3 for row in summaries),
        "mapping_ready_for_offline_review": mapping["rmse_deg"] is not None,
        "position_summary": summaries,
        "linear_eye_pitch_mapping": mapping,
        "trials": trials,
        "contains_pixels": False,
        "contains_audio": False,
        "contains_transcript": False,
        "robot_requests": 0,
        "cloud_requests": 0,
        "actuation_commands": 0,
    }


def write_results(csv_files: list[str]) -> dict[str, Any]:
    result = evaluate_saved_files(csv_files)
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_JSON_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    with RESULT_CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(result["trials"][0]))
        writer.writeheader()
        writer.writerows(result["trials"])
    REPORT_PATH.write_text(
        "\n".join([
            "# Stage 3P eye-line calibration pilot",
            "",
            f"Protocol fingerprint: `{result['protocol_fingerprint']}`",
            "",
            f"- Collection complete: **{'YES' if result['collection_complete'] else 'NO'}**",
            f"- All positions covered: **{'YES' if result['all_positions_covered'] else 'NO'}**",
            f"- Stability gate: **{'PASS' if result['stability_passed'] else 'FAIL'}**",
            "",
            "> Passive geometry calibration only. No policy was selected and no movement was authorized.",
        ]) + "\n",
        encoding="utf-8",
    )
    return result


def write_manifest(path: Path | None = None) -> dict[str, Any]:
    destination = path or (PROJECT_ROOT / "data/manifests/stage3p_calibration_pilot_v1.json")
    payload = protocol_payload()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


if len(CALIBRATION_STEPS) != 9:
    raise ValueError("Stage 3P calibration pilot must contain exactly nine steps.")
