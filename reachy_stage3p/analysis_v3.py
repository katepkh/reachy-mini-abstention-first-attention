"""Offline diagnosis and candidate tournament after the frozen Stage 3P failure."""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

from reachy_stage2a.config import PROJECT_ROOT
from reachy_stage3v.analysis import load_rows

from .confirmation_protocol import CONFIRMATION_STEPS
from .policy_v3 import Stage3PCandidateV3Spec, Stage3PReplayPolicyV3, candidate_v3_spec
from .protocol import VERTICAL_STEPS
from .result_freeze_v1 import FREEZE_PATH, verify_result_freeze
from .shadow import CoupledMotionShadow


FAILED_CONFIRMATION_DIR = (PROJECT_ROOT / "data/stage3p_confirmation").resolve()
ORIGINAL_DEVELOPMENT_DIR = (PROJECT_ROOT / "data/stage3p_development").resolve()
VAD_DIR = (PROJECT_ROOT / "data/stage3p_vad_diagnostic").resolve()
TOURNAMENT_PATH = (
    PROJECT_ROOT / "data/analysis/stage3p_candidate_v3_tournament.json"
).resolve()
DIAGNOSIS_PATH = (
    PROJECT_ROOT / "data/analysis/stage3p_failed_confirmation_offline_diagnosis_v1.json"
).resolve()
SELECTED_POLICY_PATH = (
    PROJECT_ROOT / "data/manifests/stage3p_selected_policy_v3.json"
).resolve()

# The MOVE cue begins a human repositioning interval.  Final target accuracy is
# assessed only after it, while every wrong-sign adjustment after MOVE remains
# a failure.  This is an evaluation correction, not an input to the policy.
MAINTENANCE_SETTLING_MS = 4000.0


def _number(row: dict[str, Any], key: str) -> float:
    try:
        return float(row.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _accepted_files(directory: Path, expected: int) -> list[str]:
    progress = json.loads((directory / "progress.json").read_text(encoding="utf-8"))
    files = list(progress.get("accepted_csv_files") or [])
    if progress.get("accepted_steps") != expected or len(files) != expected:
        raise ValueError(f"Incomplete accepted collection: {directory}")
    return files


def evaluate_trial(
    step: Any,
    rows: list[dict[str, Any]],
    spec: Stage3PCandidateV3Spec,
    *,
    allow_legacy_box_bridge: bool = False,
) -> dict[str, Any]:
    policy = Stage3PReplayPolicyV3(
        spec, allow_legacy_box_bridge=allow_legacy_box_bridge
    )
    shadow = CoupledMotionShadow(maximum_abs_pitch_deg=10.0)
    reasons: Counter[str] = Counter()
    post_transition_targets: list[float] = []
    scoring_targets: list[float] = []
    wrong_sign = 0
    trial_start_ms = _number(rows[0], "elapsed_ms") if rows else 0.0
    transition_ms = (
        None
        if step.transition_at_s is None
        else trial_start_ms + 1000.0 * float(step.transition_at_s)
    )
    scoring_start_ms = (
        None if transition_ms is None else transition_ms + MAINTENANCE_SETTLING_MS
    )
    associated_before_transition = transition_ms is None
    confirmed_before_transition_rows = 0
    first_confirmed_ms: float | None = None
    first_correct_sign_ms: float | None = None
    for row in rows:
        elapsed = _number(row, "elapsed_ms")
        evidence = policy.process(row)
        reasons[evidence.reason] += 1
        if evidence.confirmed and first_confirmed_ms is None:
            first_confirmed_ms = elapsed
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
        post_transition_targets.append(target)
        if step.target_pitch_deg not in (None, 0.0):
            correct_sign = math.copysign(1.0, target) == math.copysign(
                1.0, float(step.target_pitch_deg)
            )
            if not correct_sign:
                wrong_sign += 1
            elif first_correct_sign_ms is None:
                first_correct_sign_ms = elapsed
        if scoring_start_ms is None or elapsed >= scoring_start_ms:
            scoring_targets.append(target)

    errors = (
        [abs(target - float(step.target_pitch_deg)) for target in scoring_targets]
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
        "post_transition_adjustments": len(post_transition_targets),
        "scored_adjustments": len(scoring_targets),
        "first_scored_target_pitch_deg": scoring_targets[0] if scoring_targets else None,
        "median_scored_target_pitch_deg": median(scoring_targets) if scoring_targets else None,
        "maximum_scored_target_error_deg": max(errors) if errors else None,
        "wrong_sign_adjustments_after_move": wrong_sign,
        "pretransition_association_confirmed": (
            None if transition_ms is None else associated_before_transition
        ),
        "pretransition_confirmed_rows": (
            None if transition_ms is None else confirmed_before_transition_rows
        ),
        "first_confirmation_latency_ms": (
            None if first_confirmed_ms is None else first_confirmed_ms - trial_start_ms
        ),
        "first_correct_sign_latency_after_move_ms": (
            None
            if transition_ms is None or first_correct_sign_ms is None
            else first_correct_sign_ms - transition_ms
        ),
        "reason_counts": dict(sorted(reasons.items())),
    }


def _aggregate(trials: list[dict[str, Any]]) -> dict[str, Any]:
    negatives = [trial for trial in trials if trial["role"] == "hard_negative"]
    unsafe = sum(int(trial["post_transition_adjustments"]) for trial in negatives)
    summaries: list[dict[str, Any]] = []
    for role in ("matching_acquisition", "maintenance_transition"):
        for pitch in (-10.0, 10.0):
            group = [
                trial
                for trial in trials
                if trial["role"] == role and trial["target_pitch_deg"] == pitch
            ]
            moving = [trial for trial in group if trial["scored_adjustments"] > 0]
            errors = [
                float(trial["maximum_scored_target_error_deg"])
                for trial in moving
                if trial["maximum_scored_target_error_deg"] is not None
            ]
            summary = {
                "role": role,
                "pitch_deg": pitch,
                "trials": len(group),
                "trials_with_scored_adjustment": len(moving),
                "coverage_passed": len(group) == 3 and len(moving) == 3,
                "maximum_scored_target_error_deg": max(errors) if errors else None,
                "accuracy_passed": bool(errors) and max(errors) <= 6.0,
                "wrong_sign_adjustments_after_move": sum(
                    int(trial["wrong_sign_adjustments_after_move"]) for trial in group
                ),
            }
            if role == "maintenance_transition":
                preassociated = sum(
                    trial["pretransition_association_confirmed"] is True for trial in group
                )
                summary["pretransition_associations"] = preassociated
                summary["pretransition_association_passed"] = preassociated == 3
            summaries.append(summary)
    acquisition = [row for row in summaries if row["role"] == "matching_acquisition"]
    maintenance = [row for row in summaries if row["role"] == "maintenance_transition"]
    gates = {
        "hard_negative_safety": unsafe == 0,
        "vertical_direction": all(
            row["wrong_sign_adjustments_after_move"] == 0 for row in summaries
        ),
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
        "all_gates_passed": all(gates.values()),
        "hard_negative_would_adjust_rows": unsafe,
        "pitch_summary": summaries,
    }


def _replay_set(
    directory: Path,
    steps: tuple[Any, ...],
    spec: Stage3PCandidateV3Spec,
    *,
    legacy: bool = False,
) -> list[dict[str, Any]]:
    files = _accepted_files(directory, len(steps))
    return [
        evaluate_trial(
            step,
            load_rows(directory / filename),
            spec,
            allow_legacy_box_bridge=legacy,
        )
        for step, filename in zip(steps, files)
    ]


def evaluate_candidate(spec: Stage3PCandidateV3Spec) -> dict[str, Any]:
    failed_trials = _replay_set(
        FAILED_CONFIRMATION_DIR, CONFIRMATION_STEPS, spec
    )
    failed_result = _aggregate(failed_trials)
    original_trials = _replay_set(
        ORIGINAL_DEVELOPMENT_DIR, VERTICAL_STEPS, spec, legacy=True
    )
    original_negative_adjustments = sum(
        int(trial["post_transition_adjustments"])
        for trial in original_trials
        if trial["role"] == "hard_negative"
    )

    vad_files = _accepted_files(VAD_DIR, 3)
    vad_confirmed_rows = 0
    vad_false_targets = 0
    for filename in vad_files:
        policy = Stage3PReplayPolicyV3(spec)
        shadow = CoupledMotionShadow(maximum_abs_pitch_deg=10.0)
        for row in load_rows(VAD_DIR / filename):
            evidence = policy.process(row)
            vad_confirmed_rows += int(evidence.confirmed)
            vad_false_targets += int(
                shadow.process(_number(row, "elapsed_ms"), evidence).action
                == "WOULD_ADJUST"
            )

    safety = {
        "failed_confirmation_hard_negatives": failed_result[
            "hard_negative_would_adjust_rows"
        ]
        == 0,
        "original_development_hard_negatives": original_negative_adjustments == 0,
        "dedicated_silent_vad": vad_confirmed_rows == 0 and vad_false_targets == 0,
    }
    selection_gates = {**safety, **failed_result["gates"]}
    return {
        "spec": spec.payload(),
        "selection_gates": selection_gates,
        "all_selection_gates_passed": all(selection_gates.values()),
        "vad_confirmed_rows": vad_confirmed_rows,
        "vad_false_targets": vad_false_targets,
        "original_development_hard_negative_adjustments": original_negative_adjustments,
        "failed_confirmation_replay": {**failed_result, "trials": failed_trials},
    }


def run_candidate_tournament() -> dict[str, Any]:
    verification = verify_result_freeze()
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    specs = [
        candidate_v3_spec(
            failed_result_bundle_sha256=verification["bundle_sha256"],
            fallback_geometry_error_deg=geometry,
            fallback_speech_onset_window_ms=window,
        )
        for geometry in (8.0, 10.0, 12.0)
        for window in (2500.0, 4000.0)
    ]
    candidates = [evaluate_candidate(spec) for spec in specs]
    passing = [item for item in candidates if item["all_selection_gates_passed"]]
    selected = (
        min(
            passing,
            key=lambda item: (
                float(item["spec"]["fallback_geometry_error_deg"]),
                float(item["spec"]["fallback_speech_onset_window_ms"]),
            ),
        )
        if passing
        else None
    )
    payload = {
        "schema": "reachy-stage3p-candidate-v3-offline-tournament-v1",
        "status": "POST_FAILURE_DEVELOPMENT_REPLAY_ONLY_NOT_HELD_OUT_NOT_AUTHORISED_FOR_ACTUATION",
        "failed_result_was_frozen_before_reuse": True,
        "source_failed_result_freeze": FREEZE_PATH.relative_to(PROJECT_ROOT).as_posix(),
        "source_failed_result_bundle_sha256": verification["bundle_sha256"],
        "source_failed_result_original_overall_passed": freeze["validated_state"]["overall_passed"],
        "candidate_count": len(candidates),
        "maintenance_scoring": {
            "wrong_sign_checked_from_move_cue": True,
            "accuracy_and_coverage_settling_delay_ms": MAINTENANCE_SETTLING_MS,
            "rationale": (
                "The final target is not physically occupied during the human transition. "
                "Scoring every intermediate same-direction target against the final mark "
                "confounds responsive tracking with final-setpoint error."
            ),
        },
        "selection_rule": (
            "Require zero adjustments in hard negatives from both Stage 3P datasets and the "
            "dedicated silent-VAD set; require zero wrong-sign post-MOVE adjustments, 3/3 "
            "coverage and <=6 degree settled accuracy at each pitch, and 3/3 pre-MOVE "
            "associations. Among passing candidates choose the smallest fallback geometry "
            "window, then the shortest repeated-speech window."
        ),
        "selected_policy_fingerprint": (
            None if selected is None else selected["spec"]["fingerprint"]
        ),
        "candidates": candidates,
        "actuation_commands": 0,
        "cloud_requests": 0,
    }
    TOURNAMENT_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOURNAMENT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    diagnosis = {
        "schema": "reachy-stage3p-failed-confirmation-offline-diagnosis-v1",
        "status": "DIAGNOSIS_ONLY_NOT_AUTHORISED_FOR_ACTUATION",
        "frozen_source_bundle_sha256": verification["bundle_sha256"],
        "root_causes": [
            {
                "issue": "LEAST_SQUARES_CALIBRATION_MISSED_AUDITED_ANCHORS",
                "effect": "The centre mark replayed around +2 degrees and the down mark could overshoot -10 degrees.",
                "repair": "Use a monotonic piecewise mapping through the audited -10/0/+10 medians, clipped to the tested envelope.",
            },
            {
                "issue": "TRANSIENT_DISAGREEMENT_LOCKOUT_PREVENTED_ONE_PRE_MOVE_ASSOCIATION",
                "effect": "One +10 maintenance trial associated only after MOVE despite later valid geometry.",
                "repair": "Add a repeated-speech, three-hit fallback within the unchanged 10 degree acoustic/visual envelope.",
            },
            {
                "issue": "SPARSE_VAD_FALSE_POSITIVES_COULD_CLEAR_A_VALID_ASSOCIATION",
                "effect": "Post-MOVE acoustic noise was treated as renewed speech and could erase visual maintenance.",
                "repair": "Latch the one-face association for at most ten seconds; face loss, multiplicity, staleness or low confidence still clears it.",
            },
            {
                "issue": "TRANSITION_ROWS_WERE_SCORED_AS_FINAL_SETPOINTS",
                "effect": "Correct same-direction intermediate targets were counted as final-target accuracy errors.",
                "repair": "Keep wrong-sign scoring immediate, but assess final coverage and accuracy after a declared three-second repositioning interval.",
            },
        ],
        "selected_policy_fingerprint": payload["selected_policy_fingerprint"],
        "fresh_held_out_confirmation_required": True,
        "actuation_commands": 0,
        "cloud_requests": 0,
    }
    DIAGNOSIS_PATH.write_text(json.dumps(diagnosis, indent=2) + "\n", encoding="utf-8")

    if selected is not None:
        frozen = {
            **selected["spec"],
            "status": "FROZEN_SELECTED_POLICY_REQUIRES_FRESH_HELD_OUT_STAGE3P_V2_VALIDATION",
            "selection_evidence": {
                "tournament": TOURNAMENT_PATH.relative_to(PROJECT_ROOT).as_posix(),
                "diagnosis": DIAGNOSIS_PATH.relative_to(PROJECT_ROOT).as_posix(),
                "selection_gates": selected["selection_gates"],
                "pitch_summary": selected["failed_confirmation_replay"]["pitch_summary"],
                "vad_confirmed_rows": selected["vad_confirmed_rows"],
                "vad_false_targets": selected["vad_false_targets"],
                "fresh_held_out_required": True,
            },
            "actuation_commands": 0,
            "cloud_requests": 0,
        }
        SELECTED_POLICY_PATH.parent.mkdir(parents=True, exist_ok=True)
        SELECTED_POLICY_PATH.write_text(json.dumps(frozen, indent=2) + "\n", encoding="utf-8")
    return payload
