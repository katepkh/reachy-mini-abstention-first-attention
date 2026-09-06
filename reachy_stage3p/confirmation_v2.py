"""Evaluation for the frozen fresh Stage 3P V2 held-out confirmation."""

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

from .confirmation_protocol_v2 import CONFIRMATION_V2_STEPS, SUCCESS_CRITERIA, protocol_payload
from .policy_v3 import Stage3PCandidateV3Spec, Stage3PReplayPolicyV3
from .policy_v3_freeze import POLICY_PATH, TOURNAMENT_PATH, verify_policy_v3_freeze
from .shadow import CoupledMotionShadow


def _number(row: dict[str, Any], key: str) -> float:
    try:
        return float(row.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def frozen_selected_spec() -> Stage3PCandidateV3Spec:
    verified = verify_policy_v3_freeze()
    selected = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    tournament = json.loads(TOURNAMENT_PATH.read_text(encoding="utf-8"))
    fingerprint = verified["policy_fingerprint"]
    candidates = [
        item["spec"]
        for item in tournament["candidates"]
        if item["spec"]["fingerprint"] == fingerprint
    ]
    if len(candidates) != 1 or selected.get("fingerprint") != fingerprint:
        raise ValueError("The frozen selected Stage 3P V3 policy cannot be resolved uniquely.")
    source = candidates[0]
    return Stage3PCandidateV3Spec(**{
        key: source[key] for key in Stage3PCandidateV3Spec.__dataclass_fields__
    })


def quality_issues(step: Any, summary: dict[str, float | int]) -> tuple[str, ...]:
    limits = SUCCESS_CRITERIA["instrumentation_quality"]
    issues: list[str] = []
    samples = int(summary.get("samples", 0))
    minimum = (
        int(limits["minimum_samples_15_second_trial"])
        if step.duration_s == 15
        else int(limits["minimum_samples_12_second_trial"])
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
        or step.condition_id.endswith("speech-with-no-face")
        or "-mismatch-" in step.condition_id
    )
    if speech_expected and int(summary.get("speech_positive", 0)) < int(
        limits["minimum_speech_positive_when_speech_expected"]
    ):
        issues.append("fewer than three speech-positive samples were observed")
    return tuple(issues)


def evaluate_confirmation_v2_trial(
    step: Any,
    rows: list[dict[str, Any]],
    spec: Stage3PCandidateV3Spec | None = None,
) -> dict[str, Any]:
    active_spec = spec or frozen_selected_spec()
    policy = Stage3PReplayPolicyV3(active_spec)
    shadow = CoupledMotionShadow(maximum_abs_pitch_deg=10.0)
    reasons: Counter[str] = Counter()
    post_move_targets: list[float] = []
    scored_targets: list[float] = []
    wrong_sign = 0
    trial_start_ms = _number(rows[0], "elapsed_ms") if rows else 0.0
    transition_ms = (
        None
        if step.transition_at_s is None
        else trial_start_ms + 1000.0 * float(step.transition_at_s)
    )
    settling_ms = float(
        SUCCESS_CRITERIA["silent_maintenance"]["repositioning_interval_after_move_ms"]
    )
    scoring_start_ms = None if transition_ms is None else transition_ms + settling_ms
    associated_before_transition = transition_ms is None
    confirmed_before_transition_rows = 0
    first_correct_sign_ms: float | None = None
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
        if transition_ms is not None and (
            elapsed < transition_ms or not associated_before_transition
        ):
            continue
        target = float(decision.target_pitch_deg)
        post_move_targets.append(target)
        if step.target_pitch_deg not in (None, 0.0):
            correct_sign = math.copysign(1.0, target) == math.copysign(
                1.0, float(step.target_pitch_deg)
            )
            if not correct_sign:
                wrong_sign += 1
            elif first_correct_sign_ms is None:
                first_correct_sign_ms = elapsed
        if scoring_start_ms is None or elapsed >= scoring_start_ms:
            scored_targets.append(target)

    errors = (
        [abs(target - float(step.target_pitch_deg)) for target in scored_targets]
        if step.target_pitch_deg is not None
        else []
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
        "would_adjust_rows": len(post_move_targets),
        "scored_adjustment_rows": len(scored_targets),
        "first_scored_target_pitch_deg": scored_targets[0] if scored_targets else None,
        "median_scored_target_pitch_deg": median(scored_targets) if scored_targets else None,
        "maximum_scored_target_error_deg": max(errors) if errors else None,
        "wrong_sign_adjustments": wrong_sign,
        "pretransition_association_confirmed": (
            None if transition_ms is None else associated_before_transition
        ),
        "pretransition_confirmed_rows": (
            None if transition_ms is None else confirmed_before_transition_rows
        ),
        "first_correct_sign_latency_after_move_ms": (
            None
            if transition_ms is None or first_correct_sign_ms is None
            else first_correct_sign_ms - transition_ms
        ),
        "reason_counts": dict(sorted(reasons.items())),
    }


def _role_pitch_summary(trials: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for role in ("matching_acquisition", "maintenance_transition"):
        for pitch in (-10.0, 10.0):
            group = [
                trial
                for trial in trials
                if trial["role"] == role and trial["target_pitch_deg"] == pitch
            ]
            moving = [trial for trial in group if trial["scored_adjustment_rows"] > 0]
            errors = [
                float(trial["maximum_scored_target_error_deg"])
                for trial in moving
                if trial["maximum_scored_target_error_deg"] is not None
            ]
            criteria = SUCCESS_CRITERIA[
                "static_acquisition" if role == "matching_acquisition" else "silent_maintenance"
            ]
            required = int(criteria["required_trials_with_adjustment_per_pitch"])
            error_limit = float(
                criteria.get("maximum_target_error_deg", criteria.get("maximum_settled_target_error_deg"))
            )
            summary = {
                "role": role,
                "pitch_deg": pitch,
                "trials": len(group),
                "trials_with_scored_adjustment": len(moving),
                "coverage_passed": len(moving) >= required,
                "maximum_scored_target_error_deg": max(errors) if errors else None,
                "accuracy_passed": bool(errors) and max(errors) <= error_limit,
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
                    criteria["required_pretransition_associations_per_pitch"]
                )
            summaries.append(summary)
    return summaries


def aggregate_confirmation_v2_trials(trials: list[dict[str, Any]]) -> dict[str, Any]:
    summaries = _role_pitch_summary(trials)
    negatives = [trial for trial in trials if trial["role"] == "hard_negative"]
    unsafe = sum(int(trial["would_adjust_rows"]) for trial in negatives)
    acquisition = [row for row in summaries if row["role"] == "matching_acquisition"]
    maintenance = [row for row in summaries if row["role"] == "maintenance_transition"]
    gates = {
        "hard_negative_safety": unsafe == 0,
        "vertical_direction": all(row["wrong_sign_adjustments"] == 0 for row in summaries),
        "static_acquisition_coverage": all(row["coverage_passed"] for row in acquisition),
        "static_acquisition_accuracy": all(row["accuracy_passed"] for row in acquisition),
        "pretransition_association": all(
            row["pretransition_association_passed"] for row in maintenance
        ),
        "silent_maintenance_coverage": all(row["coverage_passed"] for row in maintenance),
        "silent_maintenance_accuracy": all(row["accuracy_passed"] for row in maintenance),
    }
    return {
        "gates": gates,
        "overall_passed": all(gates.values()),
        "safety_passed": gates["hard_negative_safety"],
        "direction_passed": gates["vertical_direction"],
        "coverage_passed": (
            gates["static_acquisition_coverage"]
            and gates["pretransition_association"]
            and gates["silent_maintenance_coverage"]
        ),
        "accuracy_passed": (
            gates["static_acquisition_accuracy"]
            and gates["silent_maintenance_accuracy"]
        ),
        "hard_negative_would_adjust_rows": unsafe,
        "pitch_summary": summaries,
    }


def _compliance_path(csv_path: Path) -> Path:
    return csv_path.with_name(csv_path.stem + "_compliance.json")


def _metadata_path(csv_path: Path) -> Path:
    return csv_path.with_name(csv_path.stem + "_metadata.json")


def evaluate_saved_files(csv_files: list[str]) -> dict[str, Any]:
    if len(csv_files) != len(CONFIRMATION_V2_STEPS):
        raise ValueError("A complete fresh Stage 3P V2 confirmation requires 18 accepted files.")
    spec = frozen_selected_spec()
    fingerprint = protocol_payload()["fingerprint"]
    trials: list[dict[str, Any]] = []
    for step, filename in zip(CONFIRMATION_V2_STEPS, csv_files):
        path = (DATA_DIR / filename).resolve()
        if path.parent != DATA_DIR or not path.is_file():
            raise ValueError(f"Fresh held-out Stage 3P V2 file is missing: {filename}")
        rows = load_rows(path)
        issues = quality_issues(step, summarise_rows(rows))
        if issues:
            raise ValueError(f"Held-out V2 file fails quality: {filename}: {'; '.join(issues)}")
        metadata_path = _metadata_path(path)
        compliance_path = _compliance_path(path)
        if not metadata_path.is_file() or not compliance_path.is_file():
            raise ValueError(f"Held-out V2 sidecars are incomplete: {filename}")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        compliance = json.loads(compliance_path.read_text(encoding="utf-8"))
        if (
            metadata.get("protocol_fingerprint") != fingerprint
            or metadata.get("step_index") != step.index
            or metadata.get("actuation_commands") != 0
            or metadata.get("cloud_requests") != 0
        ):
            raise ValueError(f"Held-out V2 metadata integrity failed: {filename}")
        if (
            compliance.get("verdict") != "COMPLIANT"
            or compliance.get("protocol_fingerprint") != fingerprint
            or compliance.get("data_mode") != "development_audit"
            or not compliance.get("audit_clip_id")
            or compliance.get("audit_verdict") != "COMPLIANT"
        ):
            raise ValueError(f"Held-out V2 audit compliance is incomplete: {filename}")
        trials.append({**evaluate_confirmation_v2_trial(step, rows, spec), "file": filename})

    aggregate = aggregate_confirmation_v2_trials(trials)
    freeze = verify_policy_v3_freeze()
    return {
        "schema": "reachy-stage3p-held-out-vertical-confirmation-result-v2",
        "status": "FRESH_HELD_OUT_PASSIVE_RESULT_NOT_AUTHORISED_FOR_ACTUATION",
        "protocol_fingerprint": fingerprint,
        "frozen_policy_fingerprint": freeze["policy_fingerprint"],
        "frozen_policy_bundle_sha256": freeze["bundle_sha256"],
        "policy_integrity_verified": True,
        "prior_confirmation_files_used": 0,
        "development_files_used": 0,
        "outcomes_changed_policy": False,
        "outcomes_controlled_acceptance": False,
        "procedural_audit_required_for_all_trials": True,
        "maintenance_repositioning_interval_ms": 4000.0,
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
    rows = [
        {key: value for key, value in row.items() if key != "reason_counts"}
        for row in result["trials"]
    ]
    with RESULT_CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# Fresh held-out passive Stage 3P confirmation V2",
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
