"""Predeclared Stage 3V trial metrics and final passive validation report."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from statistics import median
from typing import Any

from reachy_stage2a.models import STAGE2A_CSV_COLUMNS
from reachy_stage2a.tournament import replay_policy
from reachy_stage3a.controller import MotionShadowController
from reachy_stage3a.evaluation import STAGE3A_POLICY

from .camera_health import row_has_fresh_single_face
from .config import ANALYSIS_DIR, DATA_DIR, REPORT_PATH, RESULT_CSV_PATH, RESULT_JSON_PATH
from .protocol import SUCCESS_CRITERIA, VALIDATION_STEPS, ValidationStep, protocol_payload


def summarise_rows(rows: list[dict[str, Any]]) -> dict[str, float | int]:
    count = len(rows)
    valid = [row for row in rows if int(row.get("http_status") or 0) == 200]
    face_ages = []
    for row in rows:
        try:
            age_ms = float(row["face_age_ms"])
        except (KeyError, TypeError, ValueError):
            continue
        if age_ms >= 0.0:
            face_ages.append(age_ms)
    fresh_single_face = sum(row_has_fresh_single_face(row) for row in rows)
    eye_midpoint = sum(
        _as_int(row.get("face_count")) == 1
        and _number_or_none(row.get("face_eye_midpoint_y_norm")) is not None
        for row in rows
    )
    return {
        "samples": count,
        "valid_pct": 100.0 * len(valid) / count if count else 0.0,
        "speech_positive": sum(_as_bool(row.get("speech_detected")) for row in rows),
        "single_face": sum(_as_int(row.get("face_count")) == 1 for row in rows),
        "fresh_single_face": fresh_single_face,
        "fresh_single_face_pct": 100.0 * fresh_single_face / count if count else 0.0,
        "eye_midpoint": eye_midpoint,
        "eye_midpoint_pct": 100.0 * eye_midpoint / count if count else 0.0,
        "minimum_face_age_ms": min(face_ages) if face_ages else -1.0,
        "maximum_face_age_ms": max(face_ages) if face_ages else -1.0,
        "multiple_faces": sum(_as_int(row.get("face_count")) > 1 for row in rows),
        "tracking_rows": sum(row.get("acoustic_state") == "TRACKING_AXIS" for row in rows),
    }


def quality_issues(step: ValidationStep, summary: dict[str, float | int]) -> tuple[str, ...]:
    limits = SUCCESS_CRITERIA["protocol_quality"]
    issues: list[str] = []
    samples = int(summary.get("samples", 0))
    if samples < int(limits["minimum_samples"]):
        issues.append("fewer than 20 numeric observations")
    if float(summary.get("valid_pct", 0.0)) < float(limits["minimum_valid_pct"]):
        issues.append("fewer than 80% valid DoA responses")
    if samples and 100.0 * int(summary.get("single_face", 0)) / samples < float(
        limits["minimum_single_face_pct"]
    ):
        issues.append("one visible face was not detected in at least 60% of samples")
    if float(summary.get("fresh_single_face_pct", 0.0)) < float(
        limits["minimum_fresh_single_face_pct"]
    ):
        issues.append(
            "a fresh single-face camera observation was not present in at least 80% of samples"
        )
    if step.role == "matching_positive" and int(summary.get("speech_positive", 0)) < int(
        limits["minimum_speech_positive_matching"]
    ):
        issues.append("fewer than three speech-positive samples were observed")
    if step.condition_id.startswith("mismatch-") and int(summary.get("speech_positive", 0)) < int(
        limits["minimum_speech_positive_mismatch"]
    ):
        issues.append("phone speech produced fewer than three speech-positive samples")
    return tuple(issues)


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def _as_int(value: object) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _number_or_none(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _coerce_row(row: dict[str, Any]) -> dict[str, Any]:
    converted = dict(row)
    for key in (
        "elapsed_ms", "raw_angle_rad", "raw_angle_deg", "http_latency_ms",
        "acoustic_confidence", "hypothesis_a_deg", "hypothesis_b_deg",
        "face_heading_deg", "face_confidence", "face_age_ms",
        "face_center_x_norm", "face_center_y_norm",
        "face_eye_midpoint_x_norm", "face_eye_midpoint_y_norm",
        "confirmed_heading_deg", "agreement_error_deg",
    ):
        value = converted.get(key)
        if value in (None, ""):
            converted[key] = None
        else:
            try:
                converted[key] = float(value)
            except (TypeError, ValueError):
                converted[key] = None
    converted["http_status"] = _as_int(converted.get("http_status")) or None
    converted["face_count"] = _as_int(converted.get("face_count"))
    converted["camera_frame_width_px"] = _as_int(converted.get("camera_frame_width_px")) or None
    converted["camera_frame_height_px"] = _as_int(converted.get("camera_frame_height_px")) or None
    converted["speech_detected"] = _as_bool(converted.get("speech_detected"))
    return converted


def load_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [_coerce_row(row) for row in csv.DictReader(handle)]


def evaluate_trial(step: ValidationStep, rows: list[dict[str, Any]]) -> dict[str, Any]:
    evidence = replay_policy(STAGE3A_POLICY, rows)
    controller = MotionShadowController()
    targets: list[float] = []
    actions: list[str] = []
    source_confirmations = 0
    for row, source in zip(rows, evidence):
        source_confirmations += int(source.confirmed)
        decision = controller.process(float(row.get("elapsed_ms") or 0.0), source)
        actions.append(decision.action)
        if decision.action == "WOULD_MOVE" and decision.target_yaw_deg is not None:
            targets.append(float(decision.target_yaw_deg))

    errors = [abs(target - step.true_heading_deg) for target in targets]
    wrong_sign = sum(
        target != 0.0 and math.copysign(1.0, target) != math.copysign(1.0, step.true_heading_deg)
        for target in targets
    )
    summary = summarise_rows(rows)
    return {
        "step": step.index,
        "condition": step.condition_id,
        "role": step.role,
        "repetition": step.repetition,
        "true_heading_deg": step.true_heading_deg,
        "rows": len(rows),
        "valid_pct": summary["valid_pct"],
        "speech_positive": summary["speech_positive"],
        "single_face": summary["single_face"],
        "fresh_single_face": summary["fresh_single_face"],
        "fresh_single_face_pct": summary["fresh_single_face_pct"],
        "maximum_face_age_ms": summary["maximum_face_age_ms"],
        "tracking_rows": summary["tracking_rows"],
        "source_confirmed_rows": source_confirmations,
        "would_move_rows": sum(action == "WOULD_MOVE" for action in actions),
        "return_neutral_rows": sum(action == "RETURN_NEUTRAL" for action in actions),
        "first_target_yaw_deg": targets[0] if targets else None,
        "median_target_yaw_deg": median(targets) if targets else None,
        "median_target_error_deg": median(errors) if errors else None,
        "maximum_target_error_deg": max(errors) if errors else None,
        "wrong_sign_moves": wrong_sign,
    }


def evaluate_saved_trials(csv_files: list[str]) -> dict[str, Any]:
    if len(csv_files) != len(VALIDATION_STEPS):
        raise ValueError("A complete Stage 3V evaluation requires 18 accepted CSV files.")
    trials: list[dict[str, Any]] = []
    for step, filename in zip(VALIDATION_STEPS, csv_files):
        path = (DATA_DIR / filename).resolve()
        if path.parent != DATA_DIR or not path.is_file():
            raise ValueError(f"Accepted Stage 3V file is missing: {filename}")
        rows = load_rows(path)
        issues = quality_issues(step, summarise_rows(rows))
        if issues:
            raise ValueError(
                f"Accepted Stage 3V file fails the instrumentation gate: {filename}: "
                + "; ".join(issues)
            )
        trials.append({**evaluate_trial(step, rows), "file": filename})

    positives = [row for row in trials if row["role"] == "matching_positive"]
    negatives = [row for row in trials if row["role"] == "hard_negative"]
    heading_summary: list[dict[str, Any]] = []
    minimum_moves = int(
        SUCCESS_CRITERIA["shadow_direction"]["minimum_positive_trials_with_move_per_heading"]
    )
    max_error = float(SUCCESS_CRITERIA["shadow_direction"]["maximum_target_error_deg"])
    for heading in (-20.0, -10.0, 10.0, 20.0):
        group = [row for row in positives if row["true_heading_deg"] == heading]
        moving = [row for row in group if row["would_move_rows"] > 0]
        errors = [
            float(row["median_target_error_deg"])
            for row in moving if row["median_target_error_deg"] is not None
        ]
        heading_summary.append({
            "heading_deg": heading,
            "trials": len(group),
            "trials_with_move": len(moving),
            "coverage_passed": len(moving) >= minimum_moves,
            "median_target_error_deg": median(errors) if errors else None,
            "accuracy_passed": bool(errors) and max(errors) <= max_error,
            "wrong_sign_moves": sum(int(row["wrong_sign_moves"]) for row in group),
        })

    unsafe_negative_rows = sum(int(row["would_move_rows"]) for row in negatives)
    wrong_sign_moves = sum(int(row["wrong_sign_moves"]) for row in positives)
    result = {
        "schema": "reachy-stage3v-off-axis-validation-result-v1",
        "status": "PASSIVE_VALIDATION_ONLY_NOT_APPROVED_FOR_ACTUATION",
        "protocol_fingerprint": protocol_payload()["fingerprint"],
        "safety_passed": unsafe_negative_rows == 0,
        "direction_passed": wrong_sign_moves == 0,
        "coverage_passed": all(row["coverage_passed"] for row in heading_summary),
        "accuracy_passed": all(row["accuracy_passed"] for row in heading_summary),
        "hard_negative_would_move_rows": unsafe_negative_rows,
        "wrong_sign_moves": wrong_sign_moves,
        "heading_summary": heading_summary,
        "trials": trials,
        "contains_pixels": False,
        "contains_audio": False,
        "contains_transcript": False,
        "robot_requests": 0,
        "cloud_requests": 0,
        "actuation_commands": 0,
    }
    return result


def write_results(csv_files: list[str]) -> dict[str, Any]:
    result = evaluate_saved_trials(csv_files)
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_JSON_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    with RESULT_CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(result["trials"][0]))
        writer.writeheader()
        writer.writerows(result["trials"])
    lines = [
        "# Stage 3V predeclared off-axis validation",
        "",
        f"Protocol fingerprint: `{result['protocol_fingerprint']}`",
        "",
        f"- Hard-negative safety: **{'PASS' if result['safety_passed'] else 'FAIL'}**",
        f"- Turn direction: **{'PASS' if result['direction_passed'] else 'FAIL'}**",
        f"- Per-heading coverage: **{'PASS' if result['coverage_passed'] else 'FAIL'}**",
        f"- Target accuracy: **{'PASS' if result['accuracy_passed'] else 'FAIL'}**",
        "",
        "| True heading | Trials with shadow move | Median target error | Wrong-sign moves |",
        "|---:|---:|---:|---:|",
    ]
    for row in result["heading_summary"]:
        error = "—" if row["median_target_error_deg"] is None else f"{row['median_target_error_deg']:.2f}°"
        lines.append(
            f"| {row['heading_deg']:+.0f}° | {row['trials_with_move']}/{row['trials']} | "
            f"{error} | {row['wrong_sign_moves']} |"
        )
    lines.extend([
        "",
        "> This validation is passive and retrospective at the moment of analysis. It does not authorize or execute motion.",
    ])
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result
