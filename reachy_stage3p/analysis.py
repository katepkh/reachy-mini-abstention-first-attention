"""Offline evaluation helpers for future Stage 3P numeric datasets."""

from __future__ import annotations

import math
from collections import Counter
from statistics import median
from typing import Any

from .policy import CANDIDATE_POLICY_V1, Stage3PReplayPolicy
from .shadow import CoupledMotionShadow


def _number(row: dict[str, Any], key: str) -> float:
    try:
        return float(row.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def evaluate_vertical_trial(step: Any, rows: list[dict[str, Any]]) -> dict[str, Any]:
    policy = Stage3PReplayPolicy(CANDIDATE_POLICY_V1)
    shadow = CoupledMotionShadow()
    reasons: Counter[str] = Counter()
    targets: list[float] = []
    wrong_sign = 0
    # CSV elapsed_ms is relative to the long-running passive session.  The
    # protocol's transition_at_s is relative to the start of this trial.
    # Anchor the cue to the first accepted row so pre-cue centre evidence is
    # never mistaken for post-cue maintenance evidence.
    trial_start_ms = _number(rows[0], "elapsed_ms") if rows else 0.0
    transition_ms = (
        None
        if step.transition_at_s is None
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
            if elapsed < transition_ms:
                continue
            # Silent maintenance can only be evaluated if the speaking face
            # was actually associated before the MOVE cue.  A late acoustic
            # confirmation after the cue is a new acquisition, not maintenance.
            if not associated_before_transition:
                continue
        target = float(decision.target_pitch_deg)
        targets.append(target)
        if step.target_pitch_deg not in (None, 0.0) and math.copysign(1.0, target) != math.copysign(
            1.0, float(step.target_pitch_deg)
        ):
            wrong_sign += 1
    errors = (
        [abs(target - float(step.target_pitch_deg)) for target in targets]
        if step.target_pitch_deg is not None
        else []
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
        "maintenance_evaluable": (
            True if transition_ms is None else associated_before_transition
        ),
        "reason_counts": dict(sorted(reasons.items())),
    }


def aggregate_vertical_trials(trials: list[dict[str, Any]]) -> dict[str, Any]:
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
            evaluable = [trial for trial in group if trial.get("maintenance_evaluable", True)]
            errors = [
                float(trial["maximum_target_error_deg"])
                for trial in moving if trial["maximum_target_error_deg"] is not None
            ]
            summaries.append({
                "role": role,
                "pitch_deg": pitch,
                "trials": len(group),
                "evaluable_trials": len(evaluable),
                "not_evaluable_trials": len(group) - len(evaluable),
                "trials_with_adjustment": len(moving),
                "coverage_passed": len(moving) >= 2,
                "maximum_target_error_deg": max(errors) if errors else None,
                "accuracy_passed": bool(errors) and max(errors) <= 6.0,
                "wrong_sign_adjustments": sum(int(trial["wrong_sign_adjustments"]) for trial in group),
            })
    return {
        "hard_negative_safety_passed": unsafe == 0,
        "vertical_direction_passed": all(item["wrong_sign_adjustments"] == 0 for item in summaries),
        "coverage_passed": all(item["coverage_passed"] for item in summaries),
        "accuracy_passed": all(item["accuracy_passed"] for item in summaries),
        "hard_negative_would_adjust_rows": unsafe,
        "pitch_summary": summaries,
        "status": "DEVELOPMENT_REPLAY_ONLY_NOT_HELD_OUT_NOT_AUTHORISED_FOR_ACTUATION",
    }
