"""Evaluation for the frozen targeted association-gated cue confirmation."""

from __future__ import annotations

import csv
import json
import math
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

from reachy_stage3v.analysis import load_rows, summarise_rows
from reachy_stage3v.config import (
    ANALYSIS_DIR,
    DATA_DIR,
    REPORT_PATH,
    RESULT_CSV_PATH,
    RESULT_JSON_PATH,
)

from .association_gated_cue import AssociationGatedMoveCue
from .confirmation_v6 import frozen_selected_spec
from .cue_confirmation_protocol import (
    CUE_CONFIRMATION_STEPS,
    MAXIMUM_WAIT_MS,
    SUCCESS_CRITERIA,
    protocol_payload,
)
from .policy_v6 import Stage3PVisualServoPolicyV6
from .shadow import CoupledMotionShadow


def _number(row: dict[str, Any], key: str) -> float:
    try:
        return float(row.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def quality_issues(step: Any, summary: dict[str, Any]) -> tuple[str, ...]:
    limits = SUCCESS_CRITERIA["instrumentation_quality"]
    issues: list[str] = []
    samples = int(summary.get("samples", 0))
    minimum = 48 if step.role == "fail_closed_control" else 32
    if samples < minimum:
        issues.append(f"fewer than {minimum} numeric observations")
    if float(summary.get("valid_pct", 0.0)) < float(limits["minimum_valid_doa_pct"]):
        issues.append("fewer than 80% valid DoA responses")

    if step.face_yaw_deg is not None:
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
        step.role == "association_gated_transition"
        or step.condition_id in {
            "control-speaking-no-face",
            "control-speaking-visible-up10-not-centred",
        }
    )
    if speech_expected and int(summary.get("speech_positive", 0)) < int(
        limits["minimum_speech_positive_when_speech_expected"]
    ):
        issues.append("fewer than three speech-positive samples were observed")

    observed = summary.get("association_gate_observed_outcome")
    if observed and observed != step.expected_cue_outcome:
        issues.append(
            f"association gate produced {observed} instead of {step.expected_cue_outcome}"
        )
    if step.role == "association_gated_transition" and not observed:
        issues.append("association-gate outcome was not recorded")
    if step.role == "fail_closed_control" and not observed:
        issues.append("fail-closed timeout outcome was not recorded")
    return tuple(issues)


def evaluate_cue_confirmation_trial(
    step: Any,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    spec = frozen_selected_spec()
    policy = Stage3PVisualServoPolicyV6(spec)
    gate = AssociationGatedMoveCue()
    shadow = CoupledMotionShadow(
        maximum_abs_pitch_deg=spec.maximum_abs_increment_deg,
        pitch_deadband_deg=0.0,
        minimum_interval_ms=1000.0,
    )
    start_ms = _number(rows[0], "elapsed_ms") if rows else 0.0
    observed_cue_ms = (
        None
        if step.transition_at_s is None
        else 1000.0 * float(step.transition_at_s)
    )
    replay_cue_ms: float | None = None
    ready_streak = 0
    reasons: Counter[str] = Counter()
    raw_adjustments: list[tuple[float, float]] = []

    for row in rows:
        relative_ms = _number(row, "elapsed_ms") - start_ms
        evidence = policy.process(row)
        reasons[evidence.reason] += 1
        decision = gate.process(relative_ms, evidence)
        ready_streak = max(ready_streak, decision.ready_streak)
        if decision.action == "MOVE_CUE" and replay_cue_ms is None:
            replay_cue_ms = relative_ms
        shadow_decision = shadow.process(_number(row, "elapsed_ms"), evidence)
        if (
            shadow_decision.action == "WOULD_ADJUST"
            and shadow_decision.target_pitch_deg is not None
        ):
            raw_adjustments.append((relative_ms, float(shadow_decision.target_pitch_deg)))

    pre_cue = (
        []
        if observed_cue_ms is None
        else [value for elapsed, value in raw_adjustments if elapsed < observed_cue_ms]
    )
    scoring_delay = float(
        SUCCESS_CRITERIA["association_gated_move"]["post_cue_scoring_delay_ms"]
    )
    scored = (
        []
        if observed_cue_ms is None
        else [
            value for elapsed, value in raw_adjustments
            if elapsed >= observed_cue_ms + scoring_delay
        ]
    )
    target = step.target_pitch_deg
    wrong_sign = 0
    if step.role == "association_gated_transition" and target not in (None, 0.0):
        wrong_sign = sum(
            math.copysign(1.0, value) != math.copysign(1.0, float(target))
            for value in scored
        )
    observed_outcome = (
        "MOVE_CUE" if observed_cue_ms is not None
        else "TIMEOUT_NO_CUE"
    )
    replay_lag_ms = (
        None
        if observed_cue_ms is None or replay_cue_ms is None
        else observed_cue_ms - replay_cue_ms
    )
    summary = summarise_rows(rows)
    return {
        "step": int(step.index),
        "condition": str(step.condition_id),
        "role": str(step.role),
        "repetition": int(step.repetition),
        "target_pitch_deg": target,
        "rows": len(rows),
        "valid_pct": summary["valid_pct"],
        "fresh_single_face_pct": summary["fresh_single_face_pct"],
        "eye_midpoint_pct": summary["eye_midpoint_pct"],
        "speech_positive": summary["speech_positive"],
        "expected_cue_outcome": str(step.expected_cue_outcome),
        "observed_cue_outcome": observed_outcome,
        "observed_cue_ms": observed_cue_ms,
        "replay_cue_ms": replay_cue_ms,
        "cue_replay_lag_ms": replay_lag_ms,
        "maximum_ready_streak": ready_streak,
        "raw_policy_adjustment_rows": len(raw_adjustments),
        "pre_cue_adjustment_rows": len(pre_cue),
        "scored_adjustment_rows": len(scored),
        "would_adjust_rows": len(scored),
        "first_target_pitch_deg": scored[0] if scored else None,
        "maximum_abs_increment_deg": max((abs(value) for value in scored), default=0.0),
        "wrong_sign_adjustments": int(wrong_sign),
        "reason_counts": dict(sorted(reasons.items())),
    }


def _sidecar(csv_path: Path, suffix: str) -> Path:
    return csv_path.with_name(csv_path.stem + suffix)


def _step_with_observed_cue(step: Any, metadata: dict[str, Any]) -> Any:
    observed = metadata.get("association_gate_observed_outcome")
    cue_at = metadata.get("association_gate_cue_at_s")
    transition = float(cue_at) if observed == "MOVE_CUE" and cue_at is not None else None
    return replace(step, transition_at_s=transition)


def aggregate_trials(trials: list[dict[str, Any]]) -> dict[str, Any]:
    transitions = [trial for trial in trials if trial["role"] == "association_gated_transition"]
    controls = [trial for trial in trials if trial["role"] == "fail_closed_control"]
    lag_limit = float(
        SUCCESS_CRITERIA["association_gated_move"]["maximum_cue_replay_lag_ms"]
    )
    bound = float(SUCCESS_CRITERIA["association_gated_move"]["maximum_abs_increment_deg"])
    pitch_summary: list[dict[str, Any]] = []
    for pitch in (-10.0, 10.0):
        group = [trial for trial in transitions if trial["target_pitch_deg"] == pitch]
        pitch_summary.append({
            "pitch_deg": pitch,
            "trials": len(group),
            "move_cues_after_stable_association": sum(
                trial["observed_cue_outcome"] == "MOVE_CUE"
                and trial["replay_cue_ms"] is not None
                for trial in group
            ),
            "move_cues_within_12s_deadline": sum(
                trial["observed_cue_ms"] is not None
                and 0.0 <= float(trial["observed_cue_ms"]) <= MAXIMUM_WAIT_MS
                for trial in group
            ),
            "cue_replay_consistent": sum(
                trial["cue_replay_lag_ms"] is not None
                and 0.0 <= float(trial["cue_replay_lag_ms"]) <= lag_limit
                for trial in group
            ),
            "trials_with_post_cue_correction": sum(
                int(trial["scored_adjustment_rows"]) > 0 for trial in group
            ),
            "pre_cue_adjustment_rows": sum(
                int(trial["pre_cue_adjustment_rows"]) for trial in group
            ),
            "wrong_sign_adjustments": sum(
                int(trial["wrong_sign_adjustments"]) for trial in group
            ),
            "maximum_abs_increment_deg": max(
                (float(trial["maximum_abs_increment_deg"]) for trial in group),
                default=0.0,
            ),
        })
    control_summary = [{
        "condition": trial["condition"],
        "observed_outcome": trial["observed_cue_outcome"],
        "replay_move_cue": trial["replay_cue_ms"] is not None,
        "gate_authorised_adjustments": trial["scored_adjustment_rows"],
        "raw_policy_adjustment_rows": trial["raw_policy_adjustment_rows"],
    } for trial in controls]
    gates = {
        "transition_cue_coverage": all(
            row["trials"] == 3
            and row["move_cues_after_stable_association"] == 3
            and row["move_cues_within_12s_deadline"] == 3
            for row in pitch_summary
        ),
        "cue_evidence_integrity": all(
            row["cue_replay_consistent"] == 3 for row in pitch_summary
        ),
        "fail_closed_controls": (
            len(controls) == 3
            and all(trial["observed_cue_outcome"] == "TIMEOUT_NO_CUE" for trial in controls)
            and all(trial["replay_cue_ms"] is None for trial in controls)
        ),
        "pre_cue_hold": all(row["pre_cue_adjustment_rows"] == 0 for row in pitch_summary),
        "vertical_direction": all(row["wrong_sign_adjustments"] == 0 for row in pitch_summary),
        "bounded_increment": all(row["maximum_abs_increment_deg"] <= bound for row in pitch_summary),
        "post_cue_correction_coverage": all(
            row["trials_with_post_cue_correction"] == 3 for row in pitch_summary
        ),
    }
    return {
        "gates": gates,
        "overall_passed": all(gates.values()),
        "pitch_summary": pitch_summary,
        "control_summary": control_summary,
    }


def evaluate_saved_files(csv_files: list[str]) -> dict[str, Any]:
    if len(csv_files) != len(CUE_CONFIRMATION_STEPS):
        raise ValueError("A complete targeted cue confirmation requires nine accepted files.")
    fingerprint = protocol_payload()["fingerprint"]
    trials: list[dict[str, Any]] = []
    for frozen_step, filename in zip(CUE_CONFIRMATION_STEPS, csv_files):
        path = (DATA_DIR / filename).resolve()
        if path.parent != DATA_DIR or not path.is_file():
            raise ValueError(f"Targeted cue-confirmation file is missing: {filename}")
        metadata_path = _sidecar(path, "_metadata.json")
        compliance_path = _sidecar(path, "_compliance.json")
        if not metadata_path.is_file() or not compliance_path.is_file():
            raise ValueError(f"Targeted cue-confirmation sidecars are incomplete: {filename}")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        compliance = json.loads(compliance_path.read_text(encoding="utf-8"))
        if (
            metadata.get("protocol_fingerprint") != fingerprint
            or metadata.get("step_index") != frozen_step.index
            or metadata.get("association_gate_expected_outcome")
            != frozen_step.expected_cue_outcome
            or metadata.get("actuation_commands") != 0
            or metadata.get("cloud_requests") != 0
        ):
            raise ValueError(f"Targeted cue-confirmation metadata integrity failed: {filename}")
        observed = metadata.get("association_gate_observed_outcome")
        if observed != frozen_step.expected_cue_outcome:
            raise ValueError(f"Targeted cue outcome is not acceptable: {filename}: {observed}")
        if (
            compliance.get("verdict") != "COMPLIANT"
            or compliance.get("protocol_fingerprint") != fingerprint
            or compliance.get("data_mode") != "development_audit"
            or not compliance.get("audit_clip_id")
            or compliance.get("audit_verdict") != "COMPLIANT"
        ):
            raise ValueError(f"Targeted cue-confirmation audit is incomplete: {filename}")
        step = _step_with_observed_cue(frozen_step, metadata)
        rows = load_rows(path)
        summary = summarise_rows(rows)
        summary["association_gate_observed_outcome"] = observed
        issues = quality_issues(step, summary)
        if issues:
            raise ValueError(f"Targeted cue-confirmation quality failed: {filename}: {'; '.join(issues)}")
        trials.append({**evaluate_cue_confirmation_trial(step, rows), "file": filename})

    aggregate = aggregate_trials(trials)
    return {
        "schema": "reachy-stage3p-association-gated-cue-targeted-result-v1",
        "status": "FRESH_TARGETED_PASSIVE_RESULT_NOT_AUTHORISED_FOR_ACTUATION",
        "protocol_fingerprint": fingerprint,
        "frozen_policy_fingerprint": protocol_payload()["source_policy_fingerprint"],
        "frozen_policy_bundle_sha256": protocol_payload()["source_policy_freeze_bundle_sha256"],
        "source_v6_result_bundle_sha256": protocol_payload()["source_v6_result_bundle_sha256"],
        "policy_parameters_changed": False,
        "prior_v6_files_used": 0,
        "development_files_used": 0,
        "outcomes_changed_policy_or_gate": False,
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
        {key: value for key, value in trial.items() if key != "reason_counts"}
        for trial in result["trials"]
    ]
    with RESULT_CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# Targeted Stage 3P association-gated cue confirmation",
        "",
        f"Protocol fingerprint: `{result['protocol_fingerprint']}`",
        f"Frozen V6 policy fingerprint: `{result['frozen_policy_fingerprint']}`",
        "",
        *[
            f"- {name.replace('_', ' ').title()}: **{'PASS' if passed else 'FAIL'}**"
            for name, passed in result["gates"].items()
        ],
        "",
        f"Overall targeted passive result: **{'PASS' if result['overall_passed'] else 'FAIL'}**",
        "",
        "> This confirms only the association-gated operator cue and bounded passive shadow.",
        "> It does not revise V6 or authorize physical movement.",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result
