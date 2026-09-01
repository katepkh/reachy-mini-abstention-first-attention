"""Quality gates and result writer for the frozen Stage 3P development set."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from reachy_stage3v.analysis import load_rows, summarise_rows
from reachy_stage3v.config import ANALYSIS_DIR, DATA_DIR, REPORT_PATH, RESULT_CSV_PATH, RESULT_JSON_PATH

from .analysis import aggregate_vertical_trials, evaluate_vertical_trial
from .protocol import SUCCESS_CRITERIA, VERTICAL_STEPS, protocol_payload


def quality_issues(step: Any, summary: dict[str, float | int]) -> tuple[str, ...]:
    limits = SUCCESS_CRITERIA["instrumentation_quality"]
    issues: list[str] = []
    samples = int(summary.get("samples", 0))
    if samples < int(limits["minimum_samples"]):
        issues.append("fewer than 48 numeric observations")
    if float(summary.get("valid_pct", 0.0)) < float(limits["minimum_valid_doa_pct"]):
        issues.append("fewer than 80% valid DoA responses")

    face_expected = step.face_yaw_deg is not None
    if face_expected and float(summary.get("fresh_single_face_pct", 0.0)) < float(
        limits["minimum_fresh_single_face_pct_when_face_expected"]
    ):
        issues.append("a fresh single face was not present in at least 80% of samples")
    if not face_expected and samples:
        no_face_pct = 100.0 * (samples - int(summary.get("single_face", 0))) / samples
        if no_face_pct < 80.0 or int(summary.get("multiple_faces", 0)) > 0:
            issues.append("the no-face control contained visible-face contamination")

    speech_expected = (
        step.role in {"matching_acquisition", "maintenance_transition"}
        or step.condition_id == "speech-with-no-face"
        or step.condition_id.startswith("mismatch-")
    )
    if speech_expected and int(summary.get("speech_positive", 0)) < int(
        limits["minimum_speech_positive_when_speech_expected"]
    ):
        issues.append("fewer than three speech-positive samples were observed")
    return tuple(issues)


def _compliance_path(csv_path: Path) -> Path:
    return csv_path.with_name(csv_path.stem + "_compliance.json")


def evaluate_saved_files(csv_files: list[str]) -> dict[str, Any]:
    if len(csv_files) != len(VERTICAL_STEPS):
        raise ValueError("A complete Stage 3P development evaluation requires 18 accepted files.")
    trials: list[dict[str, Any]] = []
    modes: set[str] = set()
    for step, filename in zip(VERTICAL_STEPS, csv_files):
        path = (DATA_DIR / filename).resolve()
        if path.parent != DATA_DIR or not path.is_file():
            raise ValueError(f"Stage 3P file is missing: {filename}")
        rows = load_rows(path)
        issues = quality_issues(step, summarise_rows(rows))
        if issues:
            raise ValueError(f"Stage 3P file fails quality: {filename}: {'; '.join(issues)}")
        compliance_path = _compliance_path(path)
        if not compliance_path.is_file():
            raise ValueError(f"Stage 3P file lacks compliance review: {filename}")
        compliance = json.loads(compliance_path.read_text(encoding="utf-8"))
        if compliance.get("verdict") != "COMPLIANT":
            raise ValueError(f"Stage 3P file is noncompliant: {filename}")
        modes.add(str(compliance.get("data_mode") or "unknown"))
        trials.append({**evaluate_vertical_trial(step, rows), "file": filename})

    aggregate = aggregate_vertical_trials(trials)
    return {
        "schema": "reachy-stage3p-development-result-v1",
        "status": "DEVELOPMENT_ONLY_NOT_HELD_OUT_NOT_AUTHORISED_FOR_ACTUATION",
        "protocol_fingerprint": protocol_payload()["fingerprint"],
        "candidate_policy_outcome_did_not_control_acceptance": True,
        **aggregate,
        "safety_passed": aggregate["hard_negative_safety_passed"],
        "direction_passed": aggregate["vertical_direction_passed"],
        "trials": trials,
        "data_modes_used": sorted(modes),
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
    rows = [{key: value for key, value in row.items() if key != "reason_counts"} for row in result["trials"]]
    with RESULT_CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# Stage 3P passive vertical development result",
        "",
        f"Protocol fingerprint: `{result['protocol_fingerprint']}`",
        "",
        f"- Hard-negative safety: **{'PASS' if result['safety_passed'] else 'FAIL'}**",
        f"- Vertical direction: **{'PASS' if result['direction_passed'] else 'FAIL'}**",
        f"- Acquisition/maintenance coverage: **{'PASS' if result['coverage_passed'] else 'FAIL'}**",
        f"- Pitch target accuracy: **{'PASS' if result['accuracy_passed'] else 'FAIL'}**",
        "",
        "> Development evidence only. The candidate policy may be revised offline; this is not held-out validation or actuation authority.",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result
