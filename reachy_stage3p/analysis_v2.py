"""Offline replay and selection helpers for Stage 3P candidate V2."""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

from reachy_stage2a.config import PROJECT_ROOT
from reachy_stage3v.analysis import load_rows

from .policy_v2 import CANDIDATE_V2_SPECS, Stage3PCandidateV2Spec, Stage3PReplayPolicyV2
from .protocol import VERTICAL_STEPS
from .shadow import CoupledMotionShadow


DEVELOPMENT_DIR = (PROJECT_ROOT / "data/stage3p_development").resolve()
VAD_DIR = (PROJECT_ROOT / "data/stage3p_vad_diagnostic").resolve()
TOURNAMENT_PATH = (PROJECT_ROOT / "data/analysis/stage3p_candidate_v2_tournament.json").resolve()
SELECTED_POLICY_PATH = (PROJECT_ROOT / "data/manifests/stage3p_selected_policy_v2.json").resolve()


def _number(row: dict[str, Any], key: str) -> float:
    try:
        return float(row.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def evaluate_vertical_trial_v2(
    step: Any, rows: list[dict[str, Any]], spec: Stage3PCandidateV2Spec
) -> dict[str, Any]:
    # The accepted development collection predates eye-landmark columns.  Use
    # the audited calibration bridge for association/state-machine development
    # only; the dedicated VAD safety set and all future held-out data require
    # actual eye landmarks.
    policy = Stage3PReplayPolicyV2(spec, allow_legacy_box_bridge=True)
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
    for row in rows:
        elapsed = _number(row, "elapsed_ms")
        evidence = policy.process(row)
        decision = shadow.process(elapsed, evidence)
        reasons[evidence.reason] += 1
        if transition_ms is not None and elapsed < transition_ms and evidence.confirmed:
            associated_before_transition = True
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
    return {
        "step": int(step.index),
        "condition": str(step.condition_id),
        "role": str(step.role),
        "repetition": int(step.repetition),
        "target_pitch_deg": step.target_pitch_deg,
        "rows": len(rows),
        "would_adjust_rows": len(targets),
        "first_target_pitch_deg": targets[0] if targets else None,
        "median_target_pitch_deg": median(targets) if targets else None,
        "maximum_target_error_deg": max(errors) if errors else None,
        "wrong_sign_adjustments": wrong_sign,
        "pretransition_association_confirmed": (
            None if transition_ms is None else associated_before_transition
        ),
        "maintenance_evaluable": True if transition_ms is None else associated_before_transition,
        "reason_counts": dict(sorted(reasons.items())),
        "vertical_measurement_source": "AUDITED_LEGACY_BOX_BRIDGE_FOR_OFFLINE_DEVELOPMENT_ONLY",
    }


def _aggregate(trials: list[dict[str, Any]]) -> dict[str, Any]:
    negatives = [trial for trial in trials if trial["role"] == "hard_negative"]
    unsafe = sum(int(trial["would_adjust_rows"]) for trial in negatives)
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
            summaries.append({
                "role": role,
                "pitch_deg": pitch,
                "trials": len(group),
                "trials_with_adjustment": len(moving),
                "coverage_passed": len(moving) >= 2,
                "maximum_target_error_deg": max(errors) if errors else None,
                "accuracy_passed": bool(errors) and max(errors) <= 6.0,
                "wrong_sign_adjustments": sum(
                    int(trial["wrong_sign_adjustments"]) for trial in group
                ),
            })
    acquisition = [row for row in summaries if row["role"] == "matching_acquisition"]
    maintenance = [row for row in summaries if row["role"] == "maintenance_transition"]
    maintenance_evaluable_trials = sum(
        bool(trial["maintenance_evaluable"])
        for trial in trials if trial["role"] == "maintenance_transition"
    )
    return {
        "hard_negative_safety_passed": unsafe == 0,
        "vertical_direction_passed": all(
            row["wrong_sign_adjustments"] == 0 for row in summaries
        ),
        "coverage_passed": all(row["coverage_passed"] for row in summaries),
        "accuracy_passed": all(row["accuracy_passed"] for row in summaries),
        "static_acquisition_coverage_passed": all(
            row["coverage_passed"] for row in acquisition
        ),
        "static_acquisition_accuracy_passed": all(
            row["accuracy_passed"] for row in acquisition
        ),
        "maintenance_evaluable_trials": maintenance_evaluable_trials,
        "maintenance_development_status": (
            "EVALUABLE" if maintenance_evaluable_trials else
            "UNEVALUABLE_NO_PRETRANSITION_ASSOCIATION"
        ),
        "maintenance_coverage_passed": bool(maintenance) and all(
            row["coverage_passed"] for row in maintenance
        ),
        "maintenance_accuracy_passed": bool(maintenance) and all(
            row["accuracy_passed"] for row in maintenance
        ),
        "hard_negative_would_adjust_rows": unsafe,
        "pitch_summary": summaries,
    }


def _accepted_files(directory: Path, expected: int) -> list[str]:
    progress = json.loads((directory / "progress.json").read_text(encoding="utf-8"))
    files = list(progress.get("accepted_csv_files") or [])
    if progress.get("accepted_steps") != expected or len(files) != expected:
        raise ValueError(f"Incomplete accepted collection: {directory}")
    return files


def evaluate_candidate(spec: Stage3PCandidateV2Spec) -> dict[str, Any]:
    development_files = _accepted_files(DEVELOPMENT_DIR, len(VERTICAL_STEPS))
    trials = [
        evaluate_vertical_trial_v2(step, load_rows(DEVELOPMENT_DIR / filename), spec)
        for step, filename in zip(VERTICAL_STEPS, development_files)
    ]
    vad_files = _accepted_files(VAD_DIR, 3)
    vad_false_targets = 0
    vad_confirmed_rows = 0
    for filename in vad_files:
        policy = Stage3PReplayPolicyV2(spec)
        shadow = CoupledMotionShadow()
        for row in load_rows(VAD_DIR / filename):
            evidence = policy.process(row)
            vad_confirmed_rows += int(evidence.confirmed)
            vad_false_targets += int(
                shadow.process(_number(row, "elapsed_ms"), evidence).action == "WOULD_ADJUST"
            )
    aggregate = _aggregate(trials)
    gates = {
        "development_hard_negative_safety": aggregate["hard_negative_safety_passed"],
        "silent_vad_safety": vad_false_targets == 0 and vad_confirmed_rows == 0,
        "vertical_direction": aggregate["vertical_direction_passed"],
        "static_acquisition_coverage": aggregate["static_acquisition_coverage_passed"],
        "static_acquisition_accuracy": aggregate["static_acquisition_accuracy_passed"],
    }
    return {
        "spec": spec.payload(),
        "gates": gates,
        "all_selection_gates_passed": all(gates.values()),
        "vad_confirmed_rows": vad_confirmed_rows,
        "vad_false_targets": vad_false_targets,
        **aggregate,
        "trials": trials,
    }


def run_candidate_tournament() -> dict[str, Any]:
    candidates = [evaluate_candidate(spec) for spec in CANDIDATE_V2_SPECS]
    passing = [item for item in candidates if item["all_selection_gates_passed"]]
    # Safety and all declared scientific gates are mandatory. Among passing
    # candidates prefer the shorter weak-evidence window, then the widest
    # strong-evidence gate for responsiveness.
    selected = min(
        passing,
        key=lambda item: (
            float(item["spec"]["speech_burst_window_ms"]),
            -float(item["spec"]["strong_geometry_error_deg"]),
        ),
    ) if passing else None
    payload = {
        "schema": "reachy-stage3p-candidate-v2-offline-tournament-v1",
        "status": "DEVELOPMENT_REPLAY_ONLY_NOT_HELD_OUT_NOT_AUTHORISED_FOR_ACTUATION",
        "candidate_count": len(candidates),
        "selection_rule": (
            "Require development hard-negative safety, dedicated silent-VAD safety, direction, "
            "and static-acquisition coverage and accuracy. The legacy maintenance trials are "
            "explicitly not selection evidence because none established association before the "
            "MOVE cue. Among candidates passing the valid gates, prefer the shortest weak-evidence "
            "burst window and widest passing strong-geometry gate."
        ),
        "development_replay_limitation": (
            "The 18-trial development files predate eye-landmark capture. Their pitch values are "
            "bridged from face-box centre using the nine accepted audited calibration trials. "
            "The selected runtime policy still requires eye landmarks and must pass a fresh "
            "held-out Stage 3P collection."
        ),
        "selected_policy_fingerprint": (
            selected["spec"]["fingerprint"] if selected is not None else None
        ),
        "candidates": candidates,
        "actuation_commands": 0,
        "cloud_requests": 0,
    }
    TOURNAMENT_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOURNAMENT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if selected is not None:
        frozen = {
            **selected["spec"],
            "status": "FROZEN_SELECTED_POLICY_REQUIRES_FRESH_HELD_OUT_STAGE3P_VALIDATION",
            "selection_evidence": {
                "tournament": TOURNAMENT_PATH.relative_to(PROJECT_ROOT).as_posix(),
                "gates": selected["gates"],
                "vad_confirmed_rows": selected["vad_confirmed_rows"],
                "vad_false_targets": selected["vad_false_targets"],
                "pitch_summary": selected["pitch_summary"],
                "maintenance_development_status": selected["maintenance_development_status"],
                "maintenance_evaluable_trials": selected["maintenance_evaluable_trials"],
                "mandatory_held_out_gates": [
                    "hard_negative_safety",
                    "vertical_direction",
                    "static_acquisition_coverage_and_accuracy",
                    "pretransition_association_success",
                    "silent_visual_maintenance_coverage_and_accuracy",
                ],
            },
            "actuation_commands": 0,
            "cloud_requests": 0,
        }
        SELECTED_POLICY_PATH.parent.mkdir(parents=True, exist_ok=True)
        SELECTED_POLICY_PATH.write_text(json.dumps(frozen, indent=2) + "\n", encoding="utf-8")
    return payload
