"""Offline pre-collection hardening for the renewable Stage 3P V4 lease."""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

from reachy_stage2a.config import PROJECT_ROOT
from reachy_stage3v.analysis import load_rows

from .analysis_v3 import (
    FAILED_CONFIRMATION_DIR,
    MAINTENANCE_SETTLING_MS,
    ORIGINAL_DEVELOPMENT_DIR,
    VAD_DIR,
    _accepted_files,
    _aggregate,
    _number,
)
from .calibration import pitch_to_center_y_norm
from .confirmation_protocol import CONFIRMATION_STEPS
from .confirmation_protocol_v2 import CONFIRMATION_V2_STEPS
from .policy_v3 import (
    CALIBRATION_RAW_CENTRE_DEG,
    CALIBRATION_RAW_UP_DEG,
    Stage3PCandidateV3Spec,
)
from .policy_v4 import Stage3PCandidateV4Spec, Stage3PReplayPolicyV4, candidate_v4_spec
from .protocol import VERTICAL_STEPS
from .shadow import CoupledMotionShadow


SUPERSEDED_POLICY_PATH = (
    PROJECT_ROOT / "data/manifests/stage3p_selected_policy_v3.json"
).resolve()
SUPERSEDED_POLICY_FREEZE_PATH = (
    PROJECT_ROOT / "data/manifests/stage3p_selected_policy_v3_freeze.json"
).resolve()
V3_TOURNAMENT_PATH = (
    PROJECT_ROOT / "data/analysis/stage3p_candidate_v3_tournament.json"
).resolve()
HARDENING_PATH = (
    PROJECT_ROOT / "data/analysis/stage3p_candidate_v4_precollection_hardening.json"
).resolve()
INCIDENT_PATH = (
    PROJECT_ROOT / "data/manifests/stage3p_precollection_lease_timer_incident.json"
).resolve()
SELECTED_POLICY_PATH = (
    PROJECT_ROOT / "data/manifests/stage3p_selected_policy_v4.json"
).resolve()


def _selected_v3_spec() -> Stage3PCandidateV3Spec:
    selected = json.loads(SUPERSEDED_POLICY_PATH.read_text(encoding="utf-8"))
    tournament = json.loads(V3_TOURNAMENT_PATH.read_text(encoding="utf-8"))
    fingerprint = selected["fingerprint"]
    candidates = [
        item["spec"]
        for item in tournament["candidates"]
        if item["spec"]["fingerprint"] == fingerprint
    ]
    if len(candidates) != 1:
        raise ValueError("Superseded V3 policy cannot be resolved uniquely.")
    return Stage3PCandidateV3Spec(**{
        key: candidates[0][key] for key in Stage3PCandidateV3Spec.__dataclass_fields__
    })


def evaluate_trial_v4(
    step: Any,
    rows: list[dict[str, Any]],
    spec: Stage3PCandidateV4Spec,
    *,
    allow_legacy_box_bridge: bool = False,
) -> dict[str, Any]:
    policy = Stage3PReplayPolicyV4(spec, allow_legacy_box_bridge=allow_legacy_box_bridge)
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


def _replay_set(
    directory: Path,
    steps: tuple[Any, ...],
    spec: Stage3PCandidateV4Spec,
    *,
    legacy: bool = False,
) -> list[dict[str, Any]]:
    files = _accepted_files(directory, len(steps))
    return [
        evaluate_trial_v4(
            step,
            load_rows(directory / filename),
            spec,
            allow_legacy_box_bridge=legacy,
        )
        for step, filename in zip(steps, files)
    ]


def _synthetic_early_association_trial(spec: Stage3PCandidateV4Spec) -> dict[str, Any]:
    step = next(
        item
        for item in CONFIRMATION_V2_STEPS
        if item.role == "maintenance_transition" and item.target_pitch_deg == 10.0
    )
    rows: list[dict[str, Any]] = []
    for elapsed in range(0, 15_000, 200):
        before_move = elapsed < 7_000
        raw_eye = CALIBRATION_RAW_CENTRE_DEG if before_move else CALIBRATION_RAW_UP_DEG
        rows.append({
            "elapsed_ms": float(elapsed),
            "http_status": 200,
            "raw_angle_rad": 1.0,
            "acoustic_state": "TRACKING_AXIS" if before_move else "SEARCHING",
            "acoustic_confidence": 0.9 if before_move else 0.0,
            "hypothesis_a_deg": 0.0 if before_move else None,
            "hypothesis_b_deg": 180.0 if before_move else None,
            "speech_detected": before_move,
            "face_count": 1,
            "face_center_y_norm": pitch_to_center_y_norm(0.0 if before_move else 10.0),
            "face_eye_midpoint_y_norm": pitch_to_center_y_norm(raw_eye),
            "face_heading_deg": -4.0,
            "face_confidence": 0.95,
            "face_age_ms": 20.0,
        })
    return evaluate_trial_v4(step, rows, spec)


def run_precollection_hardening() -> dict[str, Any]:
    base = _selected_v3_spec()
    base_fingerprint = json.loads(
        SUPERSEDED_POLICY_PATH.read_text(encoding="utf-8")
    )["fingerprint"]
    spec = candidate_v4_spec(
        base,
        source_superseded_policy_fingerprint=base_fingerprint,
    )
    failed_trials = _replay_set(FAILED_CONFIRMATION_DIR, CONFIRMATION_STEPS, spec)
    failed_replay = _aggregate(failed_trials)
    original_trials = _replay_set(
        ORIGINAL_DEVELOPMENT_DIR, VERTICAL_STEPS, spec, legacy=True
    )
    original_negative_adjustments = sum(
        int(trial["post_transition_adjustments"])
        for trial in original_trials
        if trial["role"] == "hard_negative"
    )
    vad_confirmed_rows = 0
    vad_false_targets = 0
    for filename in _accepted_files(VAD_DIR, 3):
        policy = Stage3PReplayPolicyV4(spec)
        shadow = CoupledMotionShadow(maximum_abs_pitch_deg=10.0)
        for row in load_rows(VAD_DIR / filename):
            evidence = policy.process(row)
            vad_confirmed_rows += int(evidence.confirmed)
            vad_false_targets += int(
                shadow.process(_number(row, "elapsed_ms"), evidence).action
                == "WOULD_ADJUST"
            )
    longevity = _synthetic_early_association_trial(spec)
    gates = {
        **failed_replay["gates"],
        "failed_confirmation_hard_negatives": failed_replay[
            "hard_negative_would_adjust_rows"
        ]
        == 0,
        "original_development_hard_negatives": original_negative_adjustments == 0,
        "dedicated_silent_vad": vad_confirmed_rows == 0 and vad_false_targets == 0,
        "early_association_survives_final_scoring_window": (
            longevity["pretransition_association_confirmed"] is True
            and longevity["scored_adjustments"] > 0
            and longevity["wrong_sign_adjustments_after_move"] == 0
        ),
    }
    payload = {
        "schema": "reachy-stage3p-candidate-v4-precollection-hardening-v1",
        "status": "PRECOLLECTION_DEVELOPMENT_REPLAY_ONLY_NOT_HELD_OUT_NOT_AUTHORISED_FOR_ACTUATION",
        "candidate_count": 1,
        "selected_policy_fingerprint": spec.payload()["fingerprint"] if all(gates.values()) else None,
        "candidate": {
            "spec": spec.payload(),
            "selection_gates": gates,
            "all_selection_gates_passed": all(gates.values()),
            "vad_confirmed_rows": vad_confirmed_rows,
            "vad_false_targets": vad_false_targets,
            "original_development_hard_negative_adjustments": original_negative_adjustments,
            "failed_confirmation_replay": {**failed_replay, "trials": failed_trials},
            "early_association_longevity_test": longevity,
        },
        "selection_rule": (
            "Preserve every V3 offline safety/performance gate and additionally require an "
            "association established at the earliest possible time to remain evaluable through "
            "the final post-MOVE scoring window by refreshing only on valid matching evidence."
        ),
        "actuation_commands": 0,
        "cloud_requests": 0,
    }
    HARDENING_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    incident = {
        "schema": "reachy-stage3p-precollection-lease-timer-incident-v1",
        "status": "DETECTED_BY_TEST_BEFORE_COLLECTION_SUPERSEDED_WITHOUT_DATA",
        "superseded_policy_fingerprint": base_fingerprint,
        "superseded_policy_freeze": SUPERSEDED_POLICY_FREEZE_PATH.relative_to(PROJECT_ROOT).as_posix(),
        "superseded_protocol": "data/manifests/stage3p_confirmation_protocol_v2.json",
        "human_trials_collected_under_superseded_protocol": 0,
        "issue": "A lease starting at very early acquisition could expire before MOVE+4s final scoring.",
        "repair": "Refresh the ten-second lease only when fresh matching acoustic/visual evidence reconfirms the associated face.",
        "fresh_held_out_collection_required": True,
        "actuation_commands": 0,
        "cloud_requests": 0,
    }
    INCIDENT_PATH.write_text(json.dumps(incident, indent=2) + "\n", encoding="utf-8")
    if payload["selected_policy_fingerprint"] is not None:
        selected = {
            **spec.payload(),
            "status": "FROZEN_SELECTED_POLICY_REQUIRES_FRESH_HELD_OUT_STAGE3P_V3_VALIDATION",
            "selection_evidence": {
                "hardening": HARDENING_PATH.relative_to(PROJECT_ROOT).as_posix(),
                "incident": INCIDENT_PATH.relative_to(PROJECT_ROOT).as_posix(),
                "selection_gates": gates,
                "fresh_held_out_required": True,
            },
            "actuation_commands": 0,
            "cloud_requests": 0,
        }
        SELECTED_POLICY_PATH.write_text(json.dumps(selected, indent=2) + "\n", encoding="utf-8")
    return payload
