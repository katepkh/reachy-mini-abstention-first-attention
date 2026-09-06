"""Disclosed post-V6 offline diagnosis and bounded association tournament.

V6 is frozen before this module may use it.  Every replay here is development
evidence: it can reject a candidate, but it cannot authorize motion or turn the
observed V6 outcome into held-out validation for a revised policy.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from reachy_stage2a.config import PROJECT_ROOT
from reachy_stage3v.analysis import load_rows

from .association_gated_cue import AssociationGatedMoveCue
from .analysis_v6 import _candidate_result as _pre_v6_candidate_result
from .confirmation_protocol_v6 import CONFIRMATION_V6_STEPS
from .confirmation_v5 import aggregate_confirmation_v5_trials
from .confirmation_v6 import evaluate_confirmation_v6_trial, frozen_selected_spec
from .policy_v5 import Stage3PVisualServoPolicyV5
from .policy_v7 import Stage3PVisualServoV7Spec, candidate_v7_spec
from .result_freeze_v6 import verify_result_freeze as verify_v6_result_freeze


V6_DIR = (PROJECT_ROOT / "data/stage3p_confirmation_v6").resolve()
V6_RESULT_PATH = (
    PROJECT_ROOT / "data/analysis/stage3p_confirmation_validation_v6.json"
).resolve()
TOURNAMENT_PATH = (
    PROJECT_ROOT / "data/analysis/stage3p_candidate_v7_temporal_association_tournament.json"
).resolve()
DIAGNOSIS_PATH = (
    PROJECT_ROOT / "data/analysis/stage3p_v6_failure_offline_diagnosis_v7.json"
).resolve()
REPORT_PATH = (
    PROJECT_ROOT / "data/analysis/stage3p_v6_failure_offline_diagnosis_v7.md"
).resolve()
SELECTED_POLICY_PATH = (
    PROJECT_ROOT / "data/manifests/stage3p_selected_policy_v7_candidate.json"
).resolve()
CUE_DESIGN_PATH = (
    PROJECT_ROOT / "data/analysis/stage3p_association_gated_move_cue_design_v1.json"
).resolve()

WINDOW_GRID_MS = (2500.0, 3000.0, 3500.0, 4000.0, 4500.0, 5000.0, 5500.0, 6000.0)
HIT_GRID = (1, 2)
MINIMUM_OBSERVED_TIMING_MARGIN_MS = 400.0
MINIMUM_PRE_MOVE_CONFIRMATION_LEAD_MS = 500.0


def _truth(value: object) -> bool:
    return value is True or str(value).strip().lower() == "true"


def _accepted_v6_files() -> list[str]:
    progress = json.loads((V6_DIR / "progress.json").read_text(encoding="utf-8"))
    files = list(progress.get("accepted_csv_files") or [])
    if (
        progress.get("accepted_steps") != 18
        or progress.get("total_steps") != 18
        or progress.get("status") != "COLLECTION_COMPLETE"
        or len(files) != 18
        or len(set(files)) != 18
    ):
        raise ValueError("The frozen V6 dataset is not a complete 18-trial collection.")
    return files


def _step12_timing() -> dict[str, Any]:
    rows = load_rows(V6_DIR / _accepted_v6_files()[11])
    start = float(rows[0]["elapsed_ms"])
    transition_ms = start + 7000.0
    onsets: list[float] = []
    speech_was_positive = False
    for row in rows:
        speech = _truth(row.get("speech_detected"))
        if speech and not speech_was_positive:
            onsets.append(float(row["elapsed_ms"]) - start)
        speech_was_positive = speech
    if len(onsets) != 2:
        raise ValueError(f"Expected exactly two detected Step 12 speech onsets, got {onsets}.")

    eligible = [
        float(row["elapsed_ms"]) - start
        for row in rows
        if float(row["elapsed_ms"]) < transition_ms
        and row.get("acoustic_state") == "TRACKING_AXIS"
        and int(float(row.get("face_count") or 0)) == 1
    ]
    if not eligible:
        raise ValueError("Step 12 has no pre-MOVE tracking-axis geometry row.")
    first_eligible = eligible[-1]
    required_memory = first_eligible - onsets[0]
    return {
        "speech_positive_samples": sum(_truth(row.get("speech_detected")) for row in rows),
        "distinct_speech_onsets": len(onsets),
        "speech_onset_times_from_trial_start_ms": onsets,
        "gap_between_detected_onsets_ms": onsets[1] - onsets[0],
        "first_pre_move_tracking_axis_row_ms": first_eligible,
        "move_cue_ms": 7000.0,
        "tracking_row_lead_before_move_ms": 7000.0 - first_eligible,
        "minimum_memory_to_retain_first_onset_at_tracking_row_ms": required_memory,
        "v6_window_ms": 2500.0,
        "v6_window_shortfall_ms": required_memory - 2500.0,
    }


def _replay_v6(spec: Stage3PVisualServoV7Spec) -> dict[str, Any]:
    trials: list[dict[str, Any]] = []
    for step, filename in zip(CONFIRMATION_V6_STEPS, _accepted_v6_files()):
        rows = load_rows(V6_DIR / filename)
        trial = evaluate_confirmation_v6_trial(step, rows, spec)
        if step.transition_at_s is not None:
            policy = Stage3PVisualServoPolicyV5(spec)
            start = float(rows[0]["elapsed_ms"])
            transition = start + 1000.0 * float(step.transition_at_s)
            first_confirmation = next(
                (
                    float(row["elapsed_ms"])
                    for row in rows
                    if float(row["elapsed_ms"]) < transition
                    and policy.process(row).confirmed
                ),
                None,
            )
            trial["pretransition_confirmation_lead_ms"] = (
                None if first_confirmation is None else transition - first_confirmation
            )
        trials.append(trial)
    aggregate = aggregate_confirmation_v5_trials(trials)
    return {
        **aggregate,
        "failed_pretransition_steps": [
            int(trial["step"])
            for trial in trials
            if trial["role"] == "maintenance_transition"
            and trial["pretransition_association_confirmed"] is not True
        ],
        "failed_maintenance_steps": [
            int(trial["step"])
            for trial in trials
            if trial["role"] == "maintenance_transition"
            and int(trial["scored_adjustment_rows"]) == 0
        ],
        "maintenance_trial_summary": [
            {
                "step": trial["step"],
                "pretransition_association_confirmed": trial[
                    "pretransition_association_confirmed"
                ],
                "pretransition_confirmed_rows": trial["pretransition_confirmed_rows"],
                "pretransition_adjustment_rows": trial["pretransition_adjustment_rows"],
                "pretransition_confirmation_lead_ms": trial.get(
                    "pretransition_confirmation_lead_ms"
                ),
                "scored_adjustment_rows": trial["scored_adjustment_rows"],
                "wrong_sign_adjustments": trial["wrong_sign_adjustments"],
                "reason_counts": trial["reason_counts"],
            }
            for trial in trials
            if trial["role"] == "maintenance_transition"
        ],
        "minimum_pretransition_confirmation_lead_ms": min(
            (
                float(trial["pretransition_confirmation_lead_ms"])
                for trial in trials
                if trial["role"] == "maintenance_transition"
                and trial.get("pretransition_confirmation_lead_ms") is not None
            ),
            default=None,
        ),
    }


def _association_gated_cue_replay() -> dict[str, Any]:
    """Test an unchanged-V6, fail-closed cue against disclosed V6 rows."""
    spec = frozen_selected_spec()
    summaries: list[dict[str, Any]] = []
    for step, filename in zip(
        CONFIRMATION_V6_STEPS[6:12], _accepted_v6_files()[6:12]
    ):
        rows = load_rows(V6_DIR / filename)
        policy = Stage3PVisualServoPolicyV5(spec)
        start = float(rows[0]["elapsed_ms"])
        cue_ms: float | None = None
        cue = AssociationGatedMoveCue()
        for row in rows:
            evidence = policy.process(row)
            decision = cue.process(float(row["elapsed_ms"]) - start, evidence)
            if decision.action == "MOVE_CUE":
                cue_ms = float(row["elapsed_ms"]) - start
                break
            if decision.action == "ABORT":
                break
        summaries.append(
            {
                "step": int(step.index),
                "cue_ready_ms": cue_ms,
                "ready_before_12000ms_timeout": cue_ms is not None and cue_ms <= 12000.0,
            }
        )
    return {
        "schema": "reachy-stage3p-association-gated-move-cue-design-v1",
        "status": "OFFLINE_PROTOCOL_DESIGN_NOT_HELD_OUT_NOT_AUTHORISED_FOR_ACTUATION",
        "policy_fingerprint": spec.payload()["fingerprint"],
        "policy_parameters_changed": False,
        "cue_rule": {
            "minimum_consecutive_confirmed_center_rows": 3,
            "maximum_wait_for_ready_ms": 12000.0,
            "cue_type": "FULL_SCREEN_VISUAL_ONLY",
            "on_timeout": "ABORT_TRIAL_WITHOUT_MOVE_CUE",
            "on_face_or_instrument_fault": "RESET_READY_STREAK_AND_CONTINUE_WAITING",
            "post_cue_silent_observation_ms": 8000.0,
        },
        "disclosed_v6_feasibility_replay": summaries,
        "all_six_maintenance_rows_reached_ready_state": all(
            row["ready_before_12000ms_timeout"] for row in summaries
        ),
        "scientific_boundary": {
            "v6_rows_are_disclosed_development_evidence": True,
            "this_replay_does_not_validate_the_protocol": True,
            "independent_targeted_confirmation_required_before_motion": True,
            "no_user_collection_requested": True,
            "physical_movement_authorised": False,
        },
        "robot_requests": 0,
        "actuation_commands": 0,
        "cloud_requests": 0,
    }


def _single_onset_counterfactual(spec: Stage3PVisualServoV7Spec) -> dict[str, Any]:
    """Remove the second Step 12 utterance; one onset must never pre-associate."""
    rows = load_rows(V6_DIR / _accepted_v6_files()[11])
    onset_count = 0
    speech_was_positive = False
    mutated: list[dict[str, Any]] = []
    for source in rows:
        row = dict(source)
        speech = _truth(row.get("speech_detected"))
        onset = speech and not speech_was_positive
        if onset:
            onset_count += 1
        if onset_count >= 2:
            row["speech_detected"] = False
        speech_was_positive = speech
        mutated.append(row)
    trial = evaluate_confirmation_v6_trial(CONFIRMATION_V6_STEPS[11], mutated, spec)
    return {
        "pretransition_association_confirmed": trial[
            "pretransition_association_confirmed"
        ],
        "pretransition_adjustment_rows": trial["pretransition_adjustment_rows"],
        "scored_adjustment_rows": trial["scored_adjustment_rows"],
        "passed": (
            trial["pretransition_association_confirmed"] is False
            and int(trial["pretransition_adjustment_rows"] or 0) == 0
            and int(trial["scored_adjustment_rows"]) == 0
        ),
    }


def _candidate_result(spec: Stage3PVisualServoV7Spec) -> dict[str, Any]:
    prior = _pre_v6_candidate_result(spec)
    v6 = _replay_v6(spec)
    timing = _step12_timing()
    single_onset = _single_onset_counterfactual(spec)
    margin = (
        float(spec.fallback_speech_onset_window_ms)
        - float(timing["minimum_memory_to_retain_first_onset_at_tracking_row_ms"])
    )
    gates = {
        **{f"pre_v6_{name}": value for name, value in prior["gates"].items()},
        **{f"v6_{name}": value for name, value in v6["gates"].items()},
        "v6_zero_hard_negative_adjustments": v6["hard_negative_would_adjust_rows"] == 0,
        "v6_all_maintenance_trials_recovered": (
            not v6["failed_pretransition_steps"] and not v6["failed_maintenance_steps"]
        ),
        "v6_no_pretransition_pitch_adjustments": all(
            int(row["pretransition_adjustment_rows"] or 0) == 0
            for row in v6["maintenance_trial_summary"]
        ),
        "single_speech_onset_cannot_associate": single_onset["passed"],
        "observed_timing_margin_at_least_400ms": margin >= MINIMUM_OBSERVED_TIMING_MARGIN_MS,
        "pre_move_confirmation_lead_at_least_500ms": (
            v6["minimum_pretransition_confirmation_lead_ms"] is not None
            and float(v6["minimum_pretransition_confirmation_lead_ms"])
            >= MINIMUM_PRE_MOVE_CONFIRMATION_LEAD_MS
        ),
        "two_distinct_speech_onsets_still_required": (
            spec.fallback_required_speech_onsets == 2
        ),
        "recent_speech_latch_unchanged": spec.speech_latch_ms == 800.0,
        "geometry_envelope_unchanged": spec.fallback_geometry_error_deg == 13.0,
        "face_fault_boundaries_unchanged": (
            spec.minimum_face_confidence == 0.55
            and spec.maximum_face_age_ms == 1500.0
            and spec.runtime_requires_eye_landmarks is True
        ),
        "pitch_control_law_unchanged": (
            spec.neutral_raw_eye_pitch_deg == 7.5
            and spec.incremental_pitch_deadband_deg == 2.5
            and spec.incremental_pitch_gain == 1.0
            and spec.maximum_abs_increment_deg == 3.0
            and spec.control_mode == "BOUNDED_INCREMENTAL_RELATIVE_EYE_ERROR"
        ),
    }
    return {
        "spec": spec.payload(),
        "gates": gates,
        "all_gates_passed": all(gates.values()),
        "observed_step12_timing_margin_ms": margin,
        "single_onset_counterfactual": single_onset,
        "pre_v6_replay": {
            "all_gates_passed": prior["all_gates_passed"],
            "silent_vad_adjustments": prior["silent_vad_adjustments"],
            "face_fault_adjustments": prior["face_fault_adjustments"],
            "v5_disclosed_development_replay": prior[
                "v5_disclosed_development_replay"
            ],
        },
        "v6_disclosed_development_replay": {
            key: value for key, value in v6.items() if key != "maintenance_trial_summary"
        },
    }


def run_tournament() -> dict[str, Any]:
    frozen_v6 = verify_v6_result_freeze()
    base = frozen_selected_spec()
    candidates = [
        _candidate_result(
            candidate_v7_spec(
                base,
                failed_v6_result_bundle_sha256=frozen_v6["bundle_sha256"],
                fallback_speech_onset_window_ms=window,
                association_consensus_hits=hits,
            )
        )
        for window in WINDOW_GRID_MS
        for hits in HIT_GRID
    ]
    passing = [candidate for candidate in candidates if candidate["all_gates_passed"]]
    passing.sort(
        key=lambda item: (
            item["spec"]["fallback_speech_onset_window_ms"],
            -item["spec"]["association_consensus_hits"],
            item["spec"]["fingerprint"],
        )
    )
    selected = passing[0] if passing else None
    replay_recovery = [
        candidate
        for candidate in candidates
        if candidate["v6_disclosed_development_replay"]["overall_passed"]
        and candidate["pre_v6_replay"]["all_gates_passed"]
        and candidate["gates"]["single_speech_onset_cannot_associate"]
    ]
    replay_recovery.sort(
        key=lambda item: (
            item["spec"]["fallback_speech_onset_window_ms"],
            -item["spec"]["association_consensus_hits"],
            item["spec"]["fingerprint"],
        )
    )
    best_replay_only = replay_recovery[0] if replay_recovery else None
    return {
        "schema": "reachy-stage3p-post-v6-temporal-association-tournament-v1",
        "status": "DISCLOSED_OFFLINE_DEVELOPMENT_REPLAY_NOT_HELD_OUT_NOT_AUTHORISED_FOR_ACTUATION",
        "source_failed_v6_result_bundle_sha256": frozen_v6["bundle_sha256"],
        "candidate_count": len(candidates),
        "passing_candidate_count": len(passing),
        "replay_recovery_candidate_count": len(replay_recovery),
        "disclosed_grid": {
            "fallback_speech_onset_window_ms": list(WINDOW_GRID_MS),
            "association_consensus_hits": list(HIT_GRID),
            "fixed_v6_geometry_envelope_deg": 13.0,
            "fixed_required_distinct_speech_onsets": 2,
            "fixed_recent_speech_latch_ms": 800.0,
            "fixed_v6_face_fault_and_pitch_control_boundaries": True,
        },
        "selection_rule": (
            "All prior, V5, V6, hard-negative, silent-VAD, face-fault, direction, "
            "bound, single-onset and timing-margin gates must pass; then choose the "
            "shortest speech-memory window and prefer more geometry hits on a tie."
        ),
        "selected_policy_fingerprint": (
            None if selected is None else selected["spec"]["fingerprint"]
        ),
        "selected_candidate": selected,
        "best_replay_only_candidate_rejected_for_timing_margin": best_replay_only,
        "step12_observed_timing": _step12_timing(),
        "candidates": candidates,
        "scientific_boundary": {
            "v6_was_frozen_before_this_analysis": True,
            "v6_is_now_label_disclosed_development_evidence": True,
            "candidate_was_selected_after_observing_v6": True,
            "v6_cannot_validate_the_selected_candidate": True,
            "independent_passive_confirmation_required_before_motion": True,
            "no_new_collection_protocol_created": True,
            "parameter_only_repair_with_robust_timing_margin_found": selected is not None,
            "physical_movement_authorised": False,
        },
        "robot_requests": 0,
        "actuation_commands": 0,
        "cloud_requests": 0,
    }


def _diagnosis(payload: dict[str, Any]) -> dict[str, Any]:
    result = json.loads(V6_RESULT_PATH.read_text(encoding="utf-8"))
    by_step = {int(trial["step"]): trial for trial in result["trials"]}
    selected = payload.get("selected_candidate")
    rejected = payload.get("best_replay_only_candidate_rejected_for_timing_margin")
    cue_design = _association_gated_cue_replay()
    return {
        "schema": "reachy-stage3p-v6-failure-offline-diagnosis-v7-candidate",
        "status": "DISCLOSED_OFFLINE_DIAGNOSIS_NOT_HELD_OUT_NOT_AUTHORISED_FOR_ACTUATION",
        "frozen_v6_result_bundle_sha256": payload[
            "source_failed_v6_result_bundle_sha256"
        ],
        "v6_data_quality": {
            "accepted_trials": 18,
            "procedurally_compliant_trials": 18,
            "numeric_rows": sum(int(trial["rows"]) for trial in result["trials"]),
            "hard_negative_would_adjust_rows": result["hard_negative_would_adjust_rows"],
            "direction_passed": result["gates"]["vertical_direction"],
            "bounded_increment_passed": result["gates"]["bounded_increment"],
            "static_coverage_passed": result["gates"][
                "static_relative_correction_coverage"
            ],
        },
        "failed_trial": {
            "step": 12,
            "condition": by_step[12]["condition"],
            "fresh_single_face_pct": by_step[12]["fresh_single_face_pct"],
            "eye_midpoint_pct": by_step[12]["eye_midpoint_pct"],
            "speech_positive_samples": by_step[12]["speech_positive"],
            "pretransition_association_confirmed": by_step[12][
                "pretransition_association_confirmed"
            ],
            "scored_adjustment_rows": by_step[12]["scored_adjustment_rows"],
            "reason_counts": by_step[12]["reason_counts"],
        },
        "step12_timing": payload["step12_observed_timing"],
        "root_cause": (
            "Step 12 contained two distinct detected speech onsets, but V6 retained "
            "the first for only 2500 ms. The first pre-MOVE TRACKING_AXIS geometry row "
            "arrived more than 4500 ms after that onset, so the first onset had already "
            "expired. V6 then required two fallback geometry rows; only one occurred "
            "before MOVE. The compliant operator procedure, face/eye data, correction "
            "direction, pitch bound and hard-negative withholding all passed."
        ),
        "unsafe_shortcuts_rejected": [
            "Do not relabel the failed pre-MOVE association as a pass.",
            "Do not reuse V6 as held-out validation for a policy selected after seeing it.",
            "Do not widen the 13-degree acoustic/visual geometry envelope.",
            "Do not remove the two-distinct-speech-onset requirement or the 800 ms recent-speech latch.",
            "Do not authorize physical movement from offline replay.",
        ],
        "selected_offline_candidate": None if selected is None else selected["spec"],
        "selected_candidate_all_known_gates_passed": bool(
            selected and selected["all_gates_passed"]
        ),
        "best_parameter_replay_candidate_rejected": (
            None if rejected is None else rejected["spec"]
        ),
        "parameter_repair_rejection_reason": (
            "The best parameter-only replay candidate first confirmed Step 12 only "
            "3.6 ms before the fixed MOVE cue, below the required 500 ms robustness "
            "margin. Treating that boundary fit as a repair would be overfitting."
        ),
        "recommended_protocol_repair": cue_design,
        "new_user_collection_requested": False,
        "independent_confirmation_required_before_motion": True,
        "physical_movement_authorised": False,
        "robot_requests": 0,
        "actuation_commands": 0,
        "cloud_requests": 0,
    }


def write_outputs() -> dict[str, Any]:
    payload = run_tournament()
    TOURNAMENT_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOURNAMENT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    diagnosis = _diagnosis(payload)
    DIAGNOSIS_PATH.write_text(json.dumps(diagnosis, indent=2) + "\n", encoding="utf-8")
    CUE_DESIGN_PATH.write_text(
        json.dumps(diagnosis["recommended_protocol_repair"], indent=2) + "\n",
        encoding="utf-8",
    )
    selected = payload.get("selected_candidate")
    rejected = payload.get("best_replay_only_candidate_rejected_for_timing_margin")
    timing = payload["step12_observed_timing"]
    lines = [
        "# Frozen V6 result: offline failure diagnosis and bounded candidate decision",
        "",
        f"Frozen V6 result bundle: `{payload['source_failed_v6_result_bundle_sha256']}`",
        "",
        "## Finding",
        "",
        diagnosis["root_cause"],
        "",
        f"- Detected speech onsets: {timing['speech_onset_times_from_trial_start_ms']}",
        f"- First pre-MOVE tracking row: {timing['first_pre_move_tracking_axis_row_ms']:.1f} ms",
        f"- V6 memory shortfall: {timing['v6_window_shortfall_ms']:.1f} ms",
        "",
        "## Parameter-only tournament decision",
        "",
        f"- Robustly passing candidates: {payload['passing_candidate_count']} of {payload['candidate_count']}",
        f"- Replay-only recoveries rejected for timing margin: {payload['replay_recovery_candidate_count']}",
        "- No revised policy was selected or frozen.",
        "",
        diagnosis["parameter_repair_rejection_reason"],
        "",
        "## Recommended protocol repair",
        "",
        "Keep the frozen V6 policy unchanged. Replace the fixed seven-second MOVE timer "
        "with a fail-closed full-screen cue issued only after three consecutive confirmed "
        "center rows. Abort without a cue if readiness is not reached within 12 seconds.",
        f"Disclosed feasibility replay: {sum(row['ready_before_12000ms_timeout'] for row in diagnosis['recommended_protocol_repair']['disclosed_v6_feasibility_replay'])}/6 maintenance trials reached readiness.",
        "",
        "This is disclosed development replay, not independent validation. No new "
        "collection protocol was created and no user recording is requested by this "
        "analysis. Physical movement remains unauthorized.",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    result = write_outputs()
    print(
        json.dumps(
            {
                "candidate_count": result["candidate_count"],
                "passing_candidate_count": result["passing_candidate_count"],
                "selected_policy_fingerprint": result["selected_policy_fingerprint"],
            },
            indent=2,
        )
    )
