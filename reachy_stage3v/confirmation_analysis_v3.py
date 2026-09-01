"""Held-out evaluation for the frozen Stage 3V V3 policy."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .analysis import load_rows, summarise_rows
from .config import ANALYSIS_DIR, DATA_DIR, REPORT_PATH, RESULT_CSV_PATH, RESULT_JSON_PATH
from .confirmation_protocol_v3 import (
    CONFIRMATION_V3_STEPS,
    CONFIRMATION_V3_SUCCESS_CRITERIA,
    confirmation_v3_protocol_payload,
)
from .revised_policy import aggregate_revised_trials
from .revised_policy_v3 import FROZEN_REVISED_POLICY_V3, evaluate_revised_trial_v3


def confirmation_v3_quality_issues(step: Any, summary: dict[str, float | int]) -> tuple[str, ...]:
    limits = CONFIRMATION_V3_SUCCESS_CRITERIA["instrumentation_quality"]
    issues: list[str] = []
    samples = int(summary.get("samples", 0))
    if samples < int(limits["minimum_samples"]):
        issues.append("fewer than 48 numeric observations")
    if float(summary.get("valid_pct", 0.0)) < float(limits["minimum_valid_pct"]):
        issues.append("fewer than 80% valid DoA responses")
    if samples and 100.0 * int(summary.get("single_face", 0)) / samples < float(
        limits["minimum_single_face_pct"]
    ):
        issues.append("one visible face was not detected in at least 60% of samples")
    if float(summary.get("fresh_single_face_pct", 0.0)) < float(
        limits["minimum_fresh_single_face_pct"]
    ):
        issues.append("fresh single-face evidence was not present in at least 80% of samples")
    minimum_speech = (
        int(limits["minimum_speech_positive_matching"])
        if step.role == "matching_positive"
        else int(limits["minimum_speech_positive_mismatch"])
        if step.condition_id.startswith("mismatch-")
        else 0
    )
    if int(summary.get("speech_positive", 0)) < minimum_speech:
        issues.append("fewer than three speech-positive samples were observed")
    return tuple(issues)


def evaluate_confirmation_v3_trial(step: Any, rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary = summarise_rows(rows)
    revised = evaluate_revised_trial_v3(step, rows, FROZEN_REVISED_POLICY_V3)
    return {
        **revised,
        "valid_pct": summary["valid_pct"],
        "single_face": summary["single_face"],
        "fresh_single_face": summary["fresh_single_face"],
        "fresh_single_face_pct": summary["fresh_single_face_pct"],
        "maximum_face_age_ms": summary["maximum_face_age_ms"],
        "tracking_rows": summary["tracking_rows"],
    }


def _compliance_path(csv_path: Path) -> Path:
    return csv_path.with_name(csv_path.stem + "_compliance.json")


def evaluate_confirmation_v3_files(csv_files: list[str]) -> dict[str, Any]:
    if len(csv_files) != len(CONFIRMATION_V3_STEPS):
        raise ValueError("A held-out Stage 3V V3 evaluation requires 18 accepted files.")
    trials: list[dict[str, Any]] = []
    modes: set[str] = set()
    for step, filename in zip(CONFIRMATION_V3_STEPS, csv_files):
        path = (DATA_DIR / filename).resolve()
        if path.parent != DATA_DIR or not path.is_file():
            raise ValueError(f"Held-out V3 file is missing: {filename}")
        rows = load_rows(path)
        issues = confirmation_v3_quality_issues(step, summarise_rows(rows))
        if issues:
            raise ValueError(f"Held-out V3 file fails instrumentation quality: {filename}: {'; '.join(issues)}")
        compliance_path = _compliance_path(path)
        if not compliance_path.is_file():
            raise ValueError(f"Held-out V3 file lacks procedural compliance review: {filename}")
        compliance = json.loads(compliance_path.read_text(encoding="utf-8"))
        if compliance.get("verdict") != "COMPLIANT":
            raise ValueError(f"Held-out V3 file is not procedurally compliant: {filename}")
        modes.add(str(compliance.get("data_mode") or "unknown"))
        trials.append({**evaluate_confirmation_v3_trial(step, rows), "file": filename})

    aggregate = aggregate_revised_trials(trials)
    return {
        "schema": "reachy-stage3v-held-out-confirmation-result-v3",
        "status": "PASSIVE_V3_HELD_OUT_VALIDATION_ONLY_NOT_APPROVED_FOR_ACTUATION",
        "protocol_fingerprint": confirmation_v3_protocol_payload()["fingerprint"],
        "policy_fingerprint": FROZEN_REVISED_POLICY_V3.payload()["fingerprint"],
        **aggregate,
        "trials": trials,
        "data_modes_used": sorted(modes),
        "main_dataset_contains_pixels": False,
        "main_dataset_contains_audio": False,
        "main_dataset_contains_transcript": False,
        "robot_requests": 0,
        "cloud_requests": 0,
        "actuation_commands": 0,
    }


def write_confirmation_v3_results(csv_files: list[str]) -> dict[str, Any]:
    result = evaluate_confirmation_v3_files(csv_files)
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_JSON_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    with RESULT_CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        rows = [{key: value for key, value in row.items() if key != "reason_counts"} for row in result["trials"]]
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# Stage 3V V3 held-out confirmation",
        "",
        f"Protocol fingerprint: `{result['protocol_fingerprint']}`",
        f"Policy fingerprint: `{result['policy_fingerprint']}`",
        "",
        f"- Hard-negative safety: **{'PASS' if result['safety_passed'] else 'FAIL'}**",
        f"- Turn direction: **{'PASS' if result['direction_passed'] else 'FAIL'}**",
        f"- Per-heading coverage: **{'PASS' if result['coverage_passed'] else 'FAIL'}**",
        f"- Target accuracy: **{'PASS' if result['accuracy_passed'] else 'FAIL'}**",
        "",
        "| Heading | Trials with shadow move | Maximum target error | Wrong-sign moves |",
        "|---:|---:|---:|---:|",
    ]
    for row in result["heading_summary"]:
        error = "—" if row["maximum_target_error_deg"] is None else f"{row['maximum_target_error_deg']:.2f}°"
        lines.append(
            f"| {row['heading_deg']:+.0f}° | {row['trials_with_move']}/{row['trials']} | "
            f"{error} | {row['wrong_sign_moves']} |"
        )
    lines.extend(["", "> Passive confirmation does not authorize physical movement."])
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result
