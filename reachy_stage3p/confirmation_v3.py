"""Evaluation for the final fresh Stage 3P V3 held-out confirmation."""

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

from .confirmation_protocol_v3 import CONFIRMATION_V3_STEPS, protocol_payload
from .confirmation_v2 import (
    aggregate_confirmation_v2_trials,
    quality_issues,
)
from .policy_v4 import Stage3PCandidateV4Spec, Stage3PReplayPolicyV4
from .policy_v4_freeze import POLICY_PATH, verify_policy_v4_freeze
from .shadow import CoupledMotionShadow


def _number(row: dict[str, Any], key: str) -> float:
    try:
        return float(row.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def frozen_selected_spec() -> Stage3PCandidateV4Spec:
    verified = verify_policy_v4_freeze()
    selected = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    source = json.loads(
        (ANALYSIS_DIR / "stage3p_candidate_v4_precollection_hardening.json").read_text(
            encoding="utf-8"
        )
    )["candidate"]["spec"]
    if selected.get("fingerprint") != verified["policy_fingerprint"]:
        raise ValueError("The frozen selected Stage 3P V4 policy cannot be resolved.")
    return Stage3PCandidateV4Spec(**{
        key: source[key] for key in Stage3PCandidateV4Spec.__dataclass_fields__
    })


def evaluate_confirmation_v3_trial(
    step: Any,
    rows: list[dict[str, Any]],
    spec: Stage3PCandidateV4Spec | None = None,
) -> dict[str, Any]:
    active_spec = spec or frozen_selected_spec()
    policy = Stage3PReplayPolicyV4(active_spec)
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
        protocol_payload()["success_criteria"]["silent_maintenance"][
            "repositioning_interval_after_move_ms"
        ]
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


def _sidecar(csv_path: Path, suffix: str) -> Path:
    return csv_path.with_name(csv_path.stem + suffix)


def evaluate_saved_files(csv_files: list[str]) -> dict[str, Any]:
    if len(csv_files) != len(CONFIRMATION_V3_STEPS):
        raise ValueError("A complete fresh Stage 3P V3 confirmation requires 18 accepted files.")
    spec = frozen_selected_spec()
    fingerprint = protocol_payload()["fingerprint"]
    trials: list[dict[str, Any]] = []
    for step, filename in zip(CONFIRMATION_V3_STEPS, csv_files):
        path = (DATA_DIR / filename).resolve()
        if path.parent != DATA_DIR or not path.is_file():
            raise ValueError(f"Fresh held-out Stage 3P V3 file is missing: {filename}")
        rows = load_rows(path)
        issues = quality_issues(step, summarise_rows(rows))
        if issues:
            raise ValueError(f"Held-out V3 file fails quality: {filename}: {'; '.join(issues)}")
        metadata_path = _sidecar(path, "_metadata.json")
        compliance_path = _sidecar(path, "_compliance.json")
        if not metadata_path.is_file() or not compliance_path.is_file():
            raise ValueError(f"Held-out V3 sidecars are incomplete: {filename}")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        compliance = json.loads(compliance_path.read_text(encoding="utf-8"))
        if (
            metadata.get("protocol_fingerprint") != fingerprint
            or metadata.get("step_index") != step.index
            or metadata.get("actuation_commands") != 0
            or metadata.get("cloud_requests") != 0
        ):
            raise ValueError(f"Held-out V3 metadata integrity failed: {filename}")
        if (
            compliance.get("verdict") != "COMPLIANT"
            or compliance.get("protocol_fingerprint") != fingerprint
            or compliance.get("data_mode") != "development_audit"
            or not compliance.get("audit_clip_id")
            or compliance.get("audit_verdict") != "COMPLIANT"
        ):
            raise ValueError(f"Held-out V3 audit compliance is incomplete: {filename}")
        trials.append({**evaluate_confirmation_v3_trial(step, rows, spec), "file": filename})

    aggregate = aggregate_confirmation_v2_trials(trials)
    freeze = verify_policy_v4_freeze()
    return {
        "schema": "reachy-stage3p-held-out-vertical-confirmation-result-v3",
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
        "# Fresh held-out passive Stage 3P confirmation V3",
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
