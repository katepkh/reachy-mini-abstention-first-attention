"""Cross-dataset offline tournament for the Stage 3P V5 visual servo."""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from statistics import median
from typing import Any

from reachy_stage2a.config import PROJECT_ROOT
from reachy_stage3v.analysis import load_rows

from .calibration import face_center_to_pitch
from .calibration_pilot import CALIBRATION_STEPS
from .confirmation_protocol import CONFIRMATION_STEPS
from .confirmation_protocol_v3 import CONFIRMATION_V3_STEPS
from .policy_v4 import Stage3PCandidateV4Spec
from .policy_v5 import (
    Stage3PVisualServoPolicyV5,
    Stage3PVisualServoV5Spec,
    candidate_v5_spec,
)
from .protocol import VERTICAL_STEPS
from .shadow import CoupledMotionShadow


V1_DIR = (PROJECT_ROOT / "data/stage3p_confirmation").resolve()
V3_DIR = (PROJECT_ROOT / "data/stage3p_confirmation_v3").resolve()
DEVELOPMENT_DIR = (PROJECT_ROOT / "data/stage3p_development").resolve()
CALIBRATION_DIR = (PROJECT_ROOT / "data/stage3p_calibration").resolve()
VAD_DIR = (PROJECT_ROOT / "data/stage3p_vad_diagnostic").resolve()
V4_HARDENING_PATH = (
    PROJECT_ROOT / "data/analysis/stage3p_candidate_v4_precollection_hardening.json"
).resolve()
V3_RESULT_FREEZE_PATH = (
    PROJECT_ROOT / "data/manifests/stage3p_confirmation_result_v3_freeze.json"
).resolve()
TOURNAMENT_PATH = (
    PROJECT_ROOT / "data/analysis/stage3p_candidate_v5_visual_servo_tournament.json"
).resolve()
DIAGNOSIS_PATH = (
    PROJECT_ROOT / "data/analysis/stage3p_visual_servo_v5_design_diagnosis.json"
).resolve()
SELECTED_POLICY_PATH = (
    PROJECT_ROOT / "data/manifests/stage3p_selected_policy_v5.json"
).resolve()


def _number(row: dict[str, Any], key: str) -> float:
    try:
        return float(row.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _accepted_files(directory: Path, expected: int) -> list[str]:
    payload = json.loads((directory / "progress.json").read_text(encoding="utf-8"))
    files = list(payload.get("accepted_csv_files") or [])
    if payload.get("accepted_steps") != expected or len(files) != expected:
        raise ValueError(f"Incomplete frozen dataset: {directory}")
    return files


def _selected_v4_spec() -> Stage3PCandidateV4Spec:
    source = json.loads(V4_HARDENING_PATH.read_text(encoding="utf-8"))["candidate"]["spec"]
    return Stage3PCandidateV4Spec(
        **{key: source[key] for key in Stage3PCandidateV4Spec.__dataclass_fields__}
    )


def evaluate_servo_trial(
    step: Any,
    rows: list[dict[str, Any]],
    spec: Stage3PVisualServoV5Spec,
    *,
    settling_after_move_ms: float,
) -> dict[str, Any]:
    policy = Stage3PVisualServoPolicyV5(spec)
    shadow = CoupledMotionShadow(
        maximum_abs_pitch_deg=spec.maximum_abs_increment_deg,
        pitch_deadband_deg=0.0,
        minimum_interval_ms=1000.0,
    )
    trial_start_ms = _number(rows[0], "elapsed_ms") if rows else 0.0
    transition_ms = (
        None
        if step.transition_at_s is None
        else trial_start_ms + 1000.0 * float(step.transition_at_s)
    )
    scoring_start_ms = (
        None if transition_ms is None else transition_ms + settling_after_move_ms
    )
    preassociated = transition_ms is None
    pretransition_adjustments = 0
    scored: list[float] = []
    all_adjustments: list[float] = []
    reasons: Counter[str] = Counter()
    for row in rows:
        elapsed = _number(row, "elapsed_ms")
        evidence = policy.process(row)
        reasons[evidence.reason] += 1
        if transition_ms is not None and elapsed < transition_ms and evidence.confirmed:
            preassociated = True
        decision = shadow.process(elapsed, evidence)
        if decision.action != "WOULD_ADJUST" or decision.target_pitch_deg is None:
            continue
        target = float(decision.target_pitch_deg)
        all_adjustments.append(target)
        if transition_ms is not None and elapsed < transition_ms:
            pretransition_adjustments += 1
            continue
        if transition_ms is not None and not preassociated:
            continue
        if scoring_start_ms is None or elapsed >= scoring_start_ms:
            scored.append(target)

    wrong_sign = 0
    if step.target_pitch_deg not in (None, 0.0):
        wrong_sign = sum(
            math.copysign(1.0, value) != math.copysign(1.0, float(step.target_pitch_deg))
            for value in scored
        )
    return {
        "step": int(step.index),
        "role": str(step.role),
        "target_pitch_deg": step.target_pitch_deg,
        "repetition": int(step.repetition),
        "adjustment_rows": len(all_adjustments),
        "scored_adjustment_rows": len(scored),
        "wrong_sign_adjustments": int(wrong_sign),
        "maximum_abs_increment_deg": max((abs(value) for value in all_adjustments), default=0.0),
        "median_scored_increment_deg": median(scored) if scored else None,
        "pretransition_association_confirmed": (
            None if transition_ms is None else preassociated
        ),
        "pretransition_adjustment_rows": (
            None if transition_ms is None else pretransition_adjustments
        ),
        "reason_counts": dict(sorted(reasons.items())),
    }


def _replay_dataset(
    directory: Path,
    steps: tuple[Any, ...],
    spec: Stage3PVisualServoV5Spec,
    *,
    settling_after_move_ms: float,
) -> dict[str, Any]:
    files = _accepted_files(directory, len(steps))
    trials = [
        evaluate_servo_trial(
            step,
            load_rows(directory / filename),
            spec,
            settling_after_move_ms=settling_after_move_ms,
        )
        for step, filename in zip(steps, files)
    ]
    groups: list[dict[str, Any]] = []
    for role in ("matching_acquisition", "maintenance_transition"):
        for pitch in (-10.0, 10.0):
            group = [
                trial for trial in trials
                if trial["role"] == role and trial["target_pitch_deg"] == pitch
            ]
            row: dict[str, Any] = {
                "role": role,
                "pitch_deg": pitch,
                "trials": len(group),
                "trials_with_adjustment": sum(
                    trial["scored_adjustment_rows"] > 0 for trial in group
                ),
                "wrong_sign_adjustments": sum(
                    int(trial["wrong_sign_adjustments"]) for trial in group
                ),
            }
            if role == "maintenance_transition":
                row["pretransition_associations"] = sum(
                    trial["pretransition_association_confirmed"] is True for trial in group
                )
                row["pretransition_adjustment_rows"] = sum(
                    int(trial["pretransition_adjustment_rows"] or 0) for trial in group
                )
            groups.append(row)
    hard_negative_adjustments = sum(
        int(trial["adjustment_rows"])
        for trial in trials
        if trial["role"] == "hard_negative"
    )
    return {
        "directory": directory.relative_to(PROJECT_ROOT).as_posix(),
        "trials": trials,
        "groups": groups,
        "hard_negative_adjustments": hard_negative_adjustments,
        "wrong_sign_adjustments": sum(
            int(trial["wrong_sign_adjustments"]) for trial in trials
        ),
        "maximum_abs_increment_deg": max(
            (float(trial["maximum_abs_increment_deg"]) for trial in trials), default=0.0
        ),
    }


def _calibration_gate(spec: Stage3PVisualServoV5Spec) -> dict[str, Any]:
    files = _accepted_files(CALIBRATION_DIR, len(CALIBRATION_STEPS))
    groups: dict[float, list[float]] = {-10.0: [], 0.0: [], 10.0: []}
    for step, filename in zip(CALIBRATION_STEPS, files):
        for row in load_rows(CALIBRATION_DIR / filename):
            if row.get("face_eye_midpoint_y_norm") in (None, ""):
                continue
            groups[float(step.target_pitch_deg)].append(
                face_center_to_pitch(float(row["face_eye_midpoint_y_norm"]))
                - spec.neutral_raw_eye_pitch_deg
            )
    deadband = spec.incremental_pitch_deadband_deg
    return {
        "center_rows": len(groups[0.0]),
        "down_rows": len(groups[-10.0]),
        "up_rows": len(groups[10.0]),
        "center_all_inside_deadband": all(abs(value) <= deadband for value in groups[0.0]),
        "down_all_correct_side": all(value < -deadband for value in groups[-10.0]),
        "up_all_correct_side": all(value > deadband for value in groups[10.0]),
        "center_error_min_deg": min(groups[0.0]),
        "center_error_max_deg": max(groups[0.0]),
    }


def _silent_vad_adjustments(spec: Stage3PVisualServoV5Spec) -> int:
    count = 0
    for filename in _accepted_files(VAD_DIR, 3):
        policy = Stage3PVisualServoPolicyV5(spec)
        shadow = CoupledMotionShadow(
            maximum_abs_pitch_deg=spec.maximum_abs_increment_deg,
            pitch_deadband_deg=0.0,
            minimum_interval_ms=1000.0,
        )
        for row in load_rows(VAD_DIR / filename):
            evidence = policy.process(row)
            count += int(
                shadow.process(_number(row, "elapsed_ms"), evidence).action
                == "WOULD_ADJUST"
            )
    return count


def _face_fault_adjustments(
    spec: Stage3PVisualServoV5Spec,
    seed_rows: list[dict[str, Any]],
) -> dict[str, int]:
    results: dict[str, int] = {}
    mutations = {
        "no_face": {"face_count": 0, "face_eye_midpoint_y_norm": None},
        "multiple_faces": {"face_count": 2},
        "stale_face": {"face_age_ms": spec.maximum_face_age_ms + 1.0},
        "low_confidence": {"face_confidence": spec.minimum_face_confidence - 0.01},
        "missing_eye_landmarks": {"face_eye_midpoint_y_norm": None},
    }
    for name, mutation in mutations.items():
        policy = Stage3PVisualServoPolicyV5(spec)
        shadow = CoupledMotionShadow(
            maximum_abs_pitch_deg=spec.maximum_abs_increment_deg,
            pitch_deadband_deg=0.0,
            minimum_interval_ms=1000.0,
        )
        adjustments = 0
        for source in seed_rows:
            row = {**source, **mutation}
            evidence = policy.process(row)
            adjustments += int(
                shadow.process(_number(row, "elapsed_ms"), evidence).action
                == "WOULD_ADJUST"
            )
        results[name] = adjustments
    return results


def _candidate_result(spec: Stage3PVisualServoV5Spec) -> dict[str, Any]:
    v1 = _replay_dataset(
        V1_DIR, CONFIRMATION_STEPS, spec, settling_after_move_ms=4000.0
    )
    v3 = _replay_dataset(
        V3_DIR, CONFIRMATION_V3_STEPS, spec, settling_after_move_ms=4000.0
    )
    development = _replay_dataset(
        DEVELOPMENT_DIR, VERTICAL_STEPS, spec, settling_after_move_ms=3000.0
    )
    calibration = _calibration_gate(spec)
    vad_adjustments = _silent_vad_adjustments(spec)
    seed_file = _accepted_files(V3_DIR, len(CONFIRMATION_V3_STEPS))[1]
    seed_rows = load_rows(V3_DIR / seed_file)
    face_faults = _face_fault_adjustments(spec, seed_rows)

    def complete(dataset: dict[str, Any], key: str) -> bool:
        return all(
            int(group.get(key, 0)) == 3
            for group in dataset["groups"]
        )

    gates = {
        "calibration_center_deadband": calibration["center_all_inside_deadband"],
        "calibration_signed_separation": (
            calibration["down_all_correct_side"] and calibration["up_all_correct_side"]
        ),
        "v1_static_and_maintenance_coverage": complete(v1, "trials_with_adjustment"),
        "v3_static_and_maintenance_coverage": complete(v3, "trials_with_adjustment"),
        "v1_pretransition_association": all(
            group.get("pretransition_associations") == 3
            for group in v1["groups"] if group["role"] == "maintenance_transition"
        ),
        "v3_pretransition_association": all(
            group.get("pretransition_associations") == 3
            for group in v3["groups"] if group["role"] == "maintenance_transition"
        ),
        "no_pretransition_pitch_adjustment": all(
            group.get("pretransition_adjustment_rows", 0) == 0
            for dataset in (v1, v3)
            for group in dataset["groups"] if group["role"] == "maintenance_transition"
        ),
        "correct_direction_all_replays": all(
            dataset["wrong_sign_adjustments"] == 0
            for dataset in (v1, v3, development)
        ),
        "hard_negative_safety_all_replays": all(
            dataset["hard_negative_adjustments"] == 0
            for dataset in (v1, v3, development)
        ),
        "silent_vad_safety": vad_adjustments == 0,
        "face_fault_safety": all(value == 0 for value in face_faults.values()),
        "bounded_increment": all(
            dataset["maximum_abs_increment_deg"] <= spec.maximum_abs_increment_deg
            for dataset in (v1, v3, development)
        ),
    }
    return {
        "spec": spec.payload(),
        "gates": gates,
        "all_gates_passed": all(gates.values()),
        "calibration": calibration,
        "silent_vad_adjustments": vad_adjustments,
        "face_fault_adjustments": face_faults,
        "heldout_v1_development_replay": {
            key: value for key, value in v1.items() if key != "trials"
        },
        "heldout_v3_development_replay": {
            key: value for key, value in v3.items() if key != "trials"
        },
        "original_development_replay": {
            key: value for key, value in development.items() if key != "trials"
        },
    }


def run_tournament() -> dict[str, Any]:
    base = _selected_v4_spec()
    candidates = [
        _candidate_result(
            candidate_v5_spec(
                base,
                association_geometry_error_deg=geometry,
                neutral_raw_eye_pitch_deg=neutral,
                incremental_pitch_deadband_deg=deadband,
                maximum_abs_increment_deg=maximum_step,
            )
        )
        for geometry in (8.0, 10.0, 12.0)
        for neutral in (7.5, 8.0, 8.5)
        for deadband in (1.5, 2.0, 2.5)
        for maximum_step in (3.0, 5.0)
    ]
    passing = [candidate for candidate in candidates if candidate["all_gates_passed"]]
    passing.sort(
        key=lambda item: (
            item["spec"]["fallback_geometry_error_deg"],
            -item["spec"]["incremental_pitch_deadband_deg"],
            item["spec"]["maximum_abs_increment_deg"],
            abs(item["spec"]["neutral_raw_eye_pitch_deg"] - 8.0),
            item["spec"]["fingerprint"],
        )
    )
    selected = passing[0] if passing else None
    failed_freeze = json.loads(V3_RESULT_FREEZE_PATH.read_text(encoding="utf-8"))
    payload = {
        "schema": "reachy-stage3p-v5-relative-visual-servo-tournament-v1",
        "status": "OFFLINE_DEVELOPMENT_REPLAY_NOT_HELD_OUT_NOT_AUTHORISED_FOR_ACTUATION",
        "source_failed_v3_result_bundle_sha256": failed_freeze["bundle_sha256"],
        "candidate_count": len(candidates),
        "passing_candidate_count": len(passing),
        "selection_rule": (
            "All gates must pass; then prefer the narrowest association envelope, largest safe "
            "deadband, smallest pitch increment, and neutral reference nearest 8 degrees."
        ),
        "selected_policy_fingerprint": (
            None if selected is None else selected["spec"]["fingerprint"]
        ),
        "selected_candidate": selected,
        "candidates": candidates,
        "scientific_boundary": {
            "failed_held_out_v1_and_v3_are_now_disclosed_development_evidence": True,
            "absolute_target_accuracy_is_not_relabelled": True,
            "relative_servo_gate_tests_direction_coverage_safety_and_bounded_increment_only": True,
            "fresh_held_out_confirmation_required": True,
            "physical_movement_authorised": False,
        },
        "actuation_commands": 0,
        "cloud_requests": 0,
    }
    return payload


def write_outputs() -> dict[str, Any]:
    payload = run_tournament()
    TOURNAMENT_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOURNAMENT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    diagnosis = {
        "schema": "reachy-stage3p-v5-design-diagnosis-v1",
        "status": "OFFLINE_DIAGNOSIS_NOT_AUTHORISED_FOR_ACTUATION",
        "conclusion": (
            "Treat vertical eye contact as bounded relative visual servoing after speaker "
            "association, not as a one-shot absolute pitch estimate."
        ),
        "selected_policy_fingerprint": payload["selected_policy_fingerprint"],
        "passing_candidate_count": payload["passing_candidate_count"],
        "fresh_held_out_confirmation_required": True,
        "physical_movement_authorised": False,
        "actuation_commands": 0,
        "cloud_requests": 0,
    }
    DIAGNOSIS_PATH.write_text(json.dumps(diagnosis, indent=2) + "\n", encoding="utf-8")
    selected = payload["selected_candidate"]
    if selected is not None:
        policy = {
            **selected["spec"],
            "status": "FROZEN_SELECTED_POLICY_REQUIRES_FRESH_HELD_OUT_STAGE3P_V5_VALIDATION",
            "selection_evidence": {
                "tournament": TOURNAMENT_PATH.relative_to(PROJECT_ROOT).as_posix(),
                "all_gates": selected["gates"],
                "fresh_held_out_required": True,
            },
            "actuation_commands": 0,
            "cloud_requests": 0,
        }
        SELECTED_POLICY_PATH.write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")
    return payload
