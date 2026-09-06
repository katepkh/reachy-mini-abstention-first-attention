"""Evaluation for the frozen, passive, held-out Stage 3P confirmation."""

from __future__ import annotations

import csv
import json
import math
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

from reachy_stage3v.analysis import load_rows, summarise_rows
from reachy_stage3v.config import ANALYSIS_DIR, DATA_DIR, REPORT_PATH, RESULT_CSV_PATH, RESULT_JSON_PATH

from .confirmation_protocol import CONFIRMATION_STEPS, SUCCESS_CRITERIA, protocol_payload
from .policy_v2 import Stage3PCandidateV2Spec, Stage3PReplayPolicyV2
from .policy_v2_freeze import POLICY_PATH, TOURNAMENT_PATH, verify_policy_v2_freeze
from .shadow import CoupledMotionShadow


def _number(row: dict[str, Any], key: str) -> float:
    try:
        return float(row.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def frozen_selected_spec() -> Stage3PCandidateV2Spec:
    verified = verify_policy_v2_freeze()
    selected = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    tournament = json.loads(TOURNAMENT_PATH.read_text(encoding="utf-8"))
    fingerprint = verified["policy_fingerprint"]
    candidates = [
        item["spec"] for item in tournament["candidates"]
        if item["spec"]["fingerprint"] == fingerprint
    ]
    if len(candidates) != 1 or selected.get("fingerprint") != fingerprint:
        raise ValueError("The frozen selected Stage 3P policy cannot be resolved uniquely.")
    source = candidates[0]
    return Stage3PCandidateV2Spec(**{
        key: source[key]
        for key in Stage3PCandidateV2Spec.__dataclass_fields__
    })


def quality_issues(step: Any, summary: dict[str, float | int]) -> tuple[str, ...]:
    limits = SUCCESS_CRITERIA["instrumentation_quality"]
    issues: list[str] = []
    samples = int(summary.get("samples", 0))
    minimum = (
        int(limits["minimum_samples_15_second_trial"])
        if step.duration_s == 15 else int(limits["minimum_samples_12_second_trial"])
    )
    if samples < minimum:
        issues.append(f"fewer than {minimum} numeric observations")
    if float(summary.get("valid_pct", 0.0)) < float(limits["minimum_valid_doa_pct"]):
        issues.append("fewer than 80% valid DoA responses")

    face_expected = step.face_yaw_deg is not None
    if face_expected:
        if float(summary.get("fresh_single_face_pct", 0.0)) < float(
            limits["minimum_fresh_single_face_pct_when_face_expected"]
        ):
            issues.append("a fresh single face was not present in at least 80% of samples")
        if float(summary.get("eye_midpoint_pct", 0.0)) < float(
            limits["minimum_eye_landmark_pct_when_face_expected"]
        ):
            issues.append("fresh eye landmarks were not present in at least 80% of samples")
    elif samples:
        visible_pct = 100.0 * int(summary.get("single_face", 0)) / samples
        if visible_pct > float(limits["maximum_visible_face_pct_in_no_face_control"]):
            issues.append("the no-face control contained visible-face contamination")
        if int(summary.get("multiple_faces", 0)) > 0:
            issues.append("the no-face control contained multiple-face contamination")

    speech_expected = (
        step.role in {"matching_acquisition", "maintenance_transition"}
        or step.condition_id == "heldout-speech-with-no-face"
        or step.condition_id.startswith("heldout-mismatch-")
    )
    if speech_expected and int(summary.get("speech_positive", 0)) < int(
        limits["minimum_speech_positive_when_speech_expected"]
    ):
        issues.append("fewer than three speech-positive samples were observed")
    return tuple(issues)


def evaluate_confirmation_trial(
    step: Any, rows: list[dict[str, Any]], spec: Stage3PCandidateV2Spec | None = None
) -> dict[str, Any]:
    active_spec = spec or frozen_selected_spec()
    policy = Stage3PReplayPolicyV2(active_spec)
    shadow = CoupledMotionShadow()
    reasons: Counter[str] = Counter()
    targets: list[float] = []
    wrong_sign = 0
    trial_start_ms = _number(rows[0], "elapsed_ms") if rows else 0.0
    transition_ms = (
        None if step.transition_at_s is None
        else trial_start_ms + 1000.0 * float(step.transition_at_s)
    )
    associated_before_transition = transition_ms is None
    confirmed_before_transition_rows = 0
    for row in rows:
        elapsed = _number(row, "elapsed_ms")
        evidence = policy.process(row)
        reasons[evidence.reason] += 1
        if transition_ms is not None and elapsed < transition_ms and evidence.confirmed:
            associated_before_transition = True
            confirmed_before_transition_rows += 1
        decision = shadow.process(elapsed, evidence)
        if decision.action != "WOULD_ADJUST" or decision.target_pitch_deg is None:
            continue
        if transition_ms is not None:
            if elapsed < transition_ms or not associated_before_transition:
                continue
        target = float(decision.target_pitch_deg)
        targets.append(target)
        if step.target_pitch_deg not in (None, 0.0) and math.copysign(1.0, target) != math.copysign(
            1.0, float(step.target_pitch_deg)
        ):
            wrong_sign += 1
    errors = (
        [abs(target - float(step.target_pitch_deg)) for target in targets]
        if step.target_pitch_deg is not None else []
    )
    summary = summarise_rows(rows)
    return {
        "step": int(step.index),
        "condition": str(step.condition_id),
        "role": str(step.role),
        "repetition": int(step.repetition),
        "target_pitch_deg": step.target_pitch_deg,
        "rows": len(rows),
        "valid_pct": summary["valid_pct"],
        "fresh_single_face_pct": summary["fresh_single_face_pct"],
        "eye_midpoint_pct": summary["eye_midpoint_pct"],
        "speech_positive": summary["speech_positive"],
        "would_adjust_rows": len(targets),
        "first_target_pitch_deg": targets[0] if targets else None,
        "median_target_pitch_deg": median(targets) if targets else None,
        "maximum_target_error_deg": max(errors) if errors else None,
        "wrong_sign_adjustments": wrong_sign,
        "pretransition_association_confirmed": (
            None if transition_ms is None else associated_before_transition
        ),
        "pretransition_confirmed_rows": (
            None if transition_ms is None else confirmed_before_transition_rows
        ),
        "maintenance_evaluable": True if transition_ms is None else associated_before_transition,
        "reason_counts": dict(sorted(reasons.items())),
    }


def _role_pitch_summary(trials: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for role in ("matching_acquisition", "maintenance_transition"):
        for pitch in (-10.0, 10.0):
            group = [
                trial for trial in trials
                if trial["role"] == role and trial["target_pitch_deg"] == pitch
            ]
            moving = [trial for trial in group if trial["would_adjust_rows"] > 0]
            errors = [
                float(trial["maximum_target_error_deg"])
                for trial in moving if trial["maximum_target_error_deg"] is not None
            ]
            required = int(
                SUCCESS_CRITERIA[
                    "static_acquisition" if role == "matching_acquisition" else "silent_maintenance"
                ]["required_trials_with_adjustment_per_pitch"]
            )
            summary = {
                "role": role,
                "pitch_deg": pitch,
                "trials": len(group),
                "trials_with_adjustment": len(moving),
                "coverage_passed": len(moving) >= required,
                "maximum_target_error_deg": max(errors) if errors else None,
                "accuracy_passed": bool(errors) and max(errors) <= 6.0,
                "wrong_sign_adjustments": sum(
                    int(trial["wrong_sign_adjustments"]) for trial in group
                ),
            }
            if role == "maintenance_transition":
                preassociated = sum(
                    trial["pretransition_association_confirmed"] is True for trial in group
                )
                summary["pretransition_associations"] = preassociated
                summary["pretransition_association_passed"] = preassociated >= int(
                    SUCCESS_CRITERIA["silent_maintenance"][
                        "required_pretransition_associations_per_pitch"
                    ]
                )
            summaries.append(summary)
    return summaries


def aggregate_confirmation_trials(trials: list[dict[str, Any]]) -> dict[str, Any]:
    summaries = _role_pitch_summary(trials)
    negatives = [trial for trial in trials if trial["role"] == "hard_negative"]
    unsafe = sum(int(trial["would_adjust_rows"]) for trial in negatives)
    acquisition = [row for row in summaries if row["role"] == "matching_acquisition"]
    maintenance = [row for row in summaries if row["role"] == "maintenance_transition"]
    safety = unsafe == 0
    direction = all(row["wrong_sign_adjustments"] == 0 for row in summaries)
    acquisition_coverage = all(row["coverage_passed"] for row in acquisition)
    acquisition_accuracy = all(row["accuracy_passed"] for row in acquisition)
    preassociation = all(row["pretransition_association_passed"] for row in maintenance)
    maintenance_coverage = all(row["coverage_passed"] for row in maintenance)
    maintenance_accuracy = all(row["accuracy_passed"] for row in maintenance)
    gates = {
        "hard_negative_safety": safety,
        "vertical_direction": direction,
        "static_acquisition_coverage": acquisition_coverage,
        "static_acquisition_accuracy": acquisition_accuracy,
        "pretransition_association": preassociation,
        "silent_maintenance_coverage": maintenance_coverage,
        "silent_maintenance_accuracy": maintenance_accuracy,
    }
    return {
        "gates": gates,
        "overall_passed": all(gates.values()),
        "safety_passed": safety,
        "direction_passed": direction,
        "coverage_passed": acquisition_coverage and maintenance_coverage and preassociation,
        "accuracy_passed": acquisition_accuracy and maintenance_accuracy,
        "hard_negative_would_adjust_rows": unsafe,
        "pitch_summary": summaries,
    }


def _compliance_path(csv_path: Path) -> Path:
    return csv_path.with_name(csv_path.stem + "_compliance.json")


def evaluate_saved_files(csv_files: list[str]) -> dict[str, Any]:
    if len(csv_files) != len(CONFIRMATION_STEPS):
        raise ValueError("A complete held-out Stage 3P confirmation requires 18 accepted files.")
    spec = frozen_selected_spec()
    trials: list[dict[str, Any]] = []
    for step, filename in zip(CONFIRMATION_STEPS, csv_files):
        path = (DATA_DIR / filename).resolve()
        if path.parent != DATA_DIR or not path.is_file():
            raise ValueError(f"Held-out Stage 3P file is missing: {filename}")
        rows = load_rows(path)
        issues = quality_issues(step, summarise_rows(rows))
        if issues:
            raise ValueError(f"Held-out file fails quality: {filename}: {'; '.join(issues)}")
        compliance_path = _compliance_path(path)
        if not compliance_path.is_file():
            raise ValueError(f"Held-out file lacks audit compliance review: {filename}")
        compliance = json.loads(compliance_path.read_text(encoding="utf-8"))
        if (
            compliance.get("verdict") != "COMPLIANT"
            or compliance.get("data_mode") != "development_audit"
            or not compliance.get("audit_clip_id")
            or compliance.get("audit_verdict") != "COMPLIANT"
        ):
            raise ValueError(f"Held-out audit compliance is incomplete: {filename}")
        trials.append({**evaluate_confirmation_trial(step, rows, spec), "file": filename})

    aggregate = aggregate_confirmation_trials(trials)
    freeze = verify_policy_v2_freeze()
    return {
        "schema": "reachy-stage3p-held-out-vertical-confirmation-result-v1",
        "status": "HELD_OUT_PASSIVE_RESULT_NOT_AUTHORISED_FOR_ACTUATION",
        "protocol_fingerprint": protocol_payload()["fingerprint"],
        "frozen_policy_fingerprint": freeze["policy_fingerprint"],
        "frozen_policy_bundle_sha256": freeze["bundle_sha256"],
        "policy_integrity_verified": True,
        "development_files_used": 0,
        "outcomes_changed_policy": False,
        "outcomes_controlled_acceptance": False,
        "procedural_audit_required_for_all_trials": True,
        **aggregate,
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
    rows = [{key: value for key, value in row.items() if key != "reason_counts"} for row in result["trials"]]
    with RESULT_CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# Held-out passive Stage 3P confirmation",
        "",
        f"Protocol fingerprint: `{result['protocol_fingerprint']}`",
        f"Frozen policy fingerprint: `{result['frozen_policy_fingerprint']}`",
        "",
        *[
            f"- {name.replace('_', ' ').title()}: **{'PASS' if passed else 'FAIL'}**"
            for name, passed in result["gates"].items()
        ],
        "",
        f"Overall passive held-out result: **{'PASS' if result['overall_passed'] else 'FAIL'}**",
        "",
        "> This result cannot revise the frozen policy and does not authorize physical movement.",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result
