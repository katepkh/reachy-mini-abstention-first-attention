"""Disclosed post-V5 offline diagnosis and association-repair tournament."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from reachy_stage2a.config import PROJECT_ROOT
from reachy_stage3v.analysis import load_rows

from .analysis_v5 import _candidate_result as _prior_candidate_result
from .confirmation_protocol_v5 import CONFIRMATION_V5_STEPS
from .confirmation_v5 import (
    aggregate_confirmation_v5_trials,
    evaluate_confirmation_v5_trial,
    frozen_selected_spec,
)
from .policy_v6 import Stage3PVisualServoV6Spec, candidate_v6_spec
from .result_freeze_v5 import verify_result_freeze as verify_v5_result_freeze


V5_DIR = (PROJECT_ROOT / "data/stage3p_confirmation_v5").resolve()
V5_RESULT_PATH = (
    PROJECT_ROOT / "data/analysis/stage3p_confirmation_validation_v5.json"
).resolve()
TOURNAMENT_PATH = (
    PROJECT_ROOT / "data/analysis/stage3p_candidate_v6_association_repair_tournament.json"
).resolve()
DIAGNOSIS_PATH = (
    PROJECT_ROOT / "data/analysis/stage3p_v5_failure_offline_diagnosis_v6.json"
).resolve()
REPORT_PATH = (
    PROJECT_ROOT / "data/analysis/stage3p_v5_failure_offline_diagnosis_v6.md"
).resolve()
SELECTED_POLICY_PATH = (
    PROJECT_ROOT / "data/manifests/stage3p_selected_policy_v6.json"
).resolve()


def _accepted_v5_files() -> list[str]:
    progress = json.loads((V5_DIR / "progress.json").read_text(encoding="utf-8"))
    files = list(progress.get("accepted_csv_files") or [])
    if (
        progress.get("accepted_steps") != 18
        or progress.get("total_steps") != 18
        or progress.get("status") != "COLLECTION_COMPLETE"
        or len(files) != 18
    ):
        raise ValueError("The frozen V5 dataset is not a complete 18-trial collection.")
    return files


def _replay_v5(spec: Stage3PVisualServoV6Spec) -> dict[str, Any]:
    trials = [
        evaluate_confirmation_v5_trial(step, load_rows(V5_DIR / filename), spec)
        for step, filename in zip(CONFIRMATION_V5_STEPS, _accepted_v5_files())
    ]
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
                "scored_adjustment_rows": trial["scored_adjustment_rows"],
                "wrong_sign_adjustments": trial["wrong_sign_adjustments"],
                "reason_counts": trial["reason_counts"],
            }
            for trial in trials
            if trial["role"] == "maintenance_transition"
        ],
    }


def _candidate_result(spec: Stage3PVisualServoV6Spec) -> dict[str, Any]:
    prior = _prior_candidate_result(spec)
    v5 = _replay_v5(spec)
    gates = {
        **{f"prior_{name}": value for name, value in prior["gates"].items()},
        **{f"v5_{name}": value for name, value in v5["gates"].items()},
        "v5_zero_hard_negative_adjustments": v5["hard_negative_would_adjust_rows"] == 0,
        "v5_all_maintenance_trials_recovered": (
            not v5["failed_pretransition_steps"] and not v5["failed_maintenance_steps"]
        ),
        "v5_control_law_unchanged": (
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
        "silent_vad_adjustments": prior["silent_vad_adjustments"],
        "face_fault_adjustments": prior["face_fault_adjustments"],
        "prior_replay": {
            "heldout_v1_development_replay": prior["heldout_v1_development_replay"],
            "heldout_v3_development_replay": prior["heldout_v3_development_replay"],
            "original_development_replay": prior["original_development_replay"],
        },
        "v5_disclosed_development_replay": {
            key: value for key, value in v5.items() if key != "maintenance_trial_summary"
        },
    }


def run_tournament() -> dict[str, Any]:
    frozen_v5 = verify_v5_result_freeze()
    base = frozen_selected_spec()
    candidates = [
        _candidate_result(
            candidate_v6_spec(
                base,
                failed_v5_result_bundle_sha256=frozen_v5["bundle_sha256"],
                fallback_geometry_error_deg=geometry,
                fallback_speech_onset_window_ms=speech_window,
                association_consensus_hits=hits,
            )
        )
        for geometry in (10.0, 11.0, 12.0, 13.0, 14.0, 15.0)
        for speech_window in (2500.0, 3000.0, 3500.0, 4000.0)
        for hits in (2, 3)
    ]
    passing = [candidate for candidate in candidates if candidate["all_gates_passed"]]
    passing.sort(
        key=lambda item: (
            item["spec"]["fallback_geometry_error_deg"],
            -item["spec"]["association_consensus_hits"],
            item["spec"]["fallback_speech_onset_window_ms"],
            item["spec"]["fingerprint"],
        )
    )
    selected = passing[0] if passing else None
    return {
        "schema": "reachy-stage3p-v6-association-repair-tournament-v1",
        "status": "DISCLOSED_OFFLINE_DEVELOPMENT_REPLAY_NOT_HELD_OUT_NOT_AUTHORISED_FOR_ACTUATION",
        "source_failed_v5_result_bundle_sha256": frozen_v5["bundle_sha256"],
        "candidate_count": len(candidates),
        "passing_candidate_count": len(passing),
        "preregistered_grid": {
            "fallback_geometry_error_deg": [10.0, 11.0, 12.0, 13.0, 14.0, 15.0],
            "fallback_speech_onset_window_ms": [2500.0, 3000.0, 3500.0, 4000.0],
            "association_consensus_hits": [2, 3],
            "fixed_v5_control_law": True,
        },
        "selection_rule": (
            "All prior, V5, hard-negative, silent-VAD, face-fault, direction and bound "
            "gates must pass; then prefer the narrowest geometry envelope, the higher "
            "consensus-hit count, and the shortest repeated-speech window."
        ),
        "selected_policy_fingerprint": (
            None if selected is None else selected["spec"]["fingerprint"]
        ),
        "selected_candidate": selected,
        "candidates": candidates,
        "scientific_boundary": {
            "v5_was_frozen_before_this_analysis": True,
            "v5_is_now_label_disclosed_development_evidence": True,
            "candidate_was_selected_after_observing_v5": True,
            "fresh_held_out_v6_confirmation_required": True,
            "physical_movement_authorised": False,
        },
        "robot_requests": 0,
        "actuation_commands": 0,
        "cloud_requests": 0,
    }


def _diagnosis(payload: dict[str, Any]) -> dict[str, Any]:
    result = json.loads(V5_RESULT_PATH.read_text(encoding="utf-8"))
    by_step = {int(trial["step"]): trial for trial in result["trials"]}
    selected = payload.get("selected_candidate")
    return {
        "schema": "reachy-stage3p-v5-failure-offline-diagnosis-v6",
        "status": "DISCLOSED_OFFLINE_DIAGNOSIS_NOT_HELD_OUT_NOT_AUTHORISED_FOR_ACTUATION",
        "frozen_v5_result_bundle_sha256": payload["source_failed_v5_result_bundle_sha256"],
        "v5_data_quality": {
            "accepted_trials": 18,
            "procedurally_compliant_trials": 18,
            "hard_negative_would_adjust_rows": result["hard_negative_would_adjust_rows"],
            "direction_passed": result["gates"]["vertical_direction"],
            "bounded_increment_passed": result["gates"]["bounded_increment"],
            "static_coverage_passed": result["gates"][
                "static_relative_correction_coverage"
            ],
        },
        "failed_trials": [
            {
                "step": step,
                "condition": by_step[step]["condition"],
                "fresh_single_face_pct": by_step[step]["fresh_single_face_pct"],
                "eye_midpoint_pct": by_step[step]["eye_midpoint_pct"],
                "speech_positive": by_step[step]["speech_positive"],
                "pretransition_association_confirmed": by_step[step][
                    "pretransition_association_confirmed"
                ],
                "scored_adjustment_rows": by_step[step]["scored_adjustment_rows"],
                "reason_counts": by_step[step]["reason_counts"],
            }
            for step in (7, 12)
        ],
        "root_cause": (
            "The V5 repeated-speech acoustic/visual association fallback was too brittle "
            "for observed front-speech DoA transients: the combination of its 10-degree "
            "geometry envelope and three-hit requirement did not latch before MOVE "
            "in Steps 7 and 12. Face/eye instrumentation, procedure, correction direction, "
            "pitch bounds and hard-negative withholding all remained valid."
        ),
        "unsafe_shortcut_rejected": (
            "A geometry-only widening sufficient to recover both failures generated "
            "hard-negative corrections on prior disclosed datasets."
        ),
        "selected_repair": None if selected is None else selected["spec"],
        "selected_repair_all_known_gates_passed": bool(
            selected and selected["all_gates_passed"]
        ),
        "fresh_held_out_v6_confirmation_required": True,
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
    selected = payload.get("selected_candidate")
    if selected is None:
        raise ValueError("No V6 association-repair candidate passed every known-data gate.")
    policy = {
        **selected["spec"],
        "status": (
            "SELECTED_OFFLINE_DEVELOPMENT_POLICY_REQUIRES_FRESH_HELD_OUT_"
            "STAGE3P_V6_CONFIRMATION_NOT_AUTHORISED_FOR_ACTUATION"
        ),
        "selection_evidence": {
            "tournament": TOURNAMENT_PATH.relative_to(PROJECT_ROOT).as_posix(),
            "frozen_failed_v5_result_bundle_sha256": payload[
                "source_failed_v5_result_bundle_sha256"
            ],
            "all_known_data_gates": selected["gates"],
            "fresh_held_out_v6_required": True,
        },
        "robot_requests": 0,
        "actuation_commands": 0,
        "cloud_requests": 0,
    }
    SELECTED_POLICY_PATH.write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")
    spec = selected["spec"]
    lines = [
        "# Frozen V5 result: offline failure diagnosis and V6 decision",
        "",
        f"Frozen V5 result bundle: `{payload['source_failed_v5_result_bundle_sha256']}`",
        "",
        "## Finding",
        "",
        diagnosis["root_cause"],
        "",
        "The operator procedure and numeric data quality passed. Steps 7 and 12 failed "
        "because association was not established before MOVE; their failed outcomes are "
        "preserved and were not repeated away.",
        "",
        "## Rejected shortcut",
        "",
        diagnosis["unsafe_shortcut_rejected"],
        "",
        "## Selected offline V6 candidate",
        "",
        f"- Geometry envelope: {spec['fallback_geometry_error_deg']} degrees",
        f"- Repeated-speech onset window: {spec['fallback_speech_onset_window_ms']} ms",
        f"- Association consensus hits: {spec['association_consensus_hits']}",
        "- Relative eye-error control, 2.5-degree deadband and 3-degree increment bound: unchanged",
        f"- Tournament: {payload['passing_candidate_count']} of {payload['candidate_count']} candidates passed every known-data gate",
        "",
        "This is a disclosed development selection, not held-out validation. A fresh V6 "
        "held-out passive confirmation is required before any movement can be considered.",
        "Physical movement remains unauthorized.",
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
