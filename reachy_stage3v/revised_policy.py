"""Offline-only revised Stage 3V evidence policy.

The policy consumes saved numeric rows and emits counterfactual targets.  It
contains no camera, network, media, robot SDK or actuation capability.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, deque
from dataclasses import asdict, dataclass
from statistics import median
from typing import Any, Iterable

from reachy_stage2a.calibration import circular_distance_degrees
from reachy_stage3a.controller import MotionShadowController


@dataclass(frozen=True, slots=True)
class RevisedPolicySpec:
    name: str
    face_heading_multiplier: float
    maximum_geometry_error_deg: float
    required_hits: int
    window_ms: float
    heading_tolerance_deg: float
    disagreement_lockout_ms: float
    target_source: str

    def payload(self) -> dict[str, Any]:
        core = asdict(self)
        encoded = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return {**core, "fingerprint": hashlib.sha256(encoded).hexdigest()}


FROZEN_REVISED_POLICY = RevisedPolicySpec(
    name="Stage 3V revised sign-corrected visual-target consensus",
    face_heading_multiplier=-1.0,
    maximum_geometry_error_deg=10.0,
    required_hits=2,
    window_ms=1200.0,
    heading_tolerance_deg=8.0,
    disagreement_lockout_ms=1500.0,
    target_source="visual",
)


@dataclass(frozen=True, slots=True)
class RevisedEvidence:
    confirmed: bool
    heading_deg: float | None
    reason: str
    visual_heading_deg: float | None = None
    matched_acoustic_heading_deg: float | None = None
    agreement_error_deg: float | None = None


def _number(row: dict[str, Any], key: str) -> float | None:
    try:
        value = row.get(key)
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def _integer(row: dict[str, Any], key: str) -> int:
    try:
        return int(float(row.get(key) or 0))
    except (TypeError, ValueError):
        return 0


def _truth(value: object) -> bool:
    return value is True or str(value).strip().lower() == "true"


def geometry_for_row(
    row: dict[str, Any],
    spec: RevisedPolicySpec,
) -> RevisedEvidence:
    """Return one unique acoustic/visual match in the diagram frame."""
    if _integer(row, "http_status") != 200 or _number(row, "raw_angle_rad") is None:
        return RevisedEvidence(False, None, "NETWORK_INVALID")
    if row.get("acoustic_state") != "TRACKING_AXIS":
        return RevisedEvidence(False, None, "ACOUSTIC_NOT_TRACKING")
    if (_number(row, "acoustic_confidence") or 0.0) < 0.60:
        return RevisedEvidence(False, None, "ACOUSTIC_LOW_CONFIDENCE")
    if _integer(row, "face_count") == 0 or _number(row, "face_heading_deg") is None:
        return RevisedEvidence(False, None, "NO_FACE")
    if _integer(row, "face_count") != 1:
        return RevisedEvidence(False, None, "MULTIPLE_FACES")
    if (_number(row, "face_confidence") or 0.0) < 0.55:
        return RevisedEvidence(False, None, "FACE_LOW_CONFIDENCE")
    face_age = _number(row, "face_age_ms")
    if face_age is None or face_age < 0.0 or face_age > 1500.0:
        return RevisedEvidence(False, None, "CAMERA_OBSERVATION_STALE")

    raw_face = _number(row, "face_heading_deg")
    assert raw_face is not None
    visual = spec.face_heading_multiplier * raw_face
    hypotheses = [
        value
        for value in (
            _number(row, "hypothesis_a_deg"),
            _number(row, "hypothesis_b_deg"),
        )
        if value is not None
    ]
    matches = [
        (value, circular_distance_degrees(visual, value))
        for value in hypotheses
        if circular_distance_degrees(visual, value) <= spec.maximum_geometry_error_deg
    ]
    if not matches:
        return RevisedEvidence(False, None, "ACOUSTIC_VISUAL_DISAGREEMENT", visual)
    if len(matches) > 1:
        return RevisedEvidence(False, None, "VISUAL_HYPOTHESIS_AMBIGUOUS", visual)

    acoustic, error = matches[0]
    target = visual if spec.target_source == "visual" else acoustic
    return RevisedEvidence(
        False,
        target,
        "GEOMETRY_ELIGIBLE",
        visual,
        acoustic,
        error,
    )


class RevisedReplayPolicy:
    """Apply current-speech consensus and disagreement lockout offline."""

    _RESET_REASONS = {
        "NETWORK_INVALID",
        "NO_FACE",
        "MULTIPLE_FACES",
        "FACE_LOW_CONFIDENCE",
        "CAMERA_OBSERVATION_STALE",
    }

    def __init__(self, spec: RevisedPolicySpec) -> None:
        self.spec = spec
        self._hits: deque[tuple[float, float]] = deque()
        self._lockout_until_ms = -math.inf

    def process(self, row: dict[str, Any]) -> RevisedEvidence:
        elapsed = _number(row, "elapsed_ms") or 0.0
        geometry = geometry_for_row(row, self.spec)
        if geometry.reason == "ACOUSTIC_VISUAL_DISAGREEMENT":
            self._hits.clear()
            self._lockout_until_ms = elapsed + self.spec.disagreement_lockout_ms
        elif geometry.reason in self._RESET_REASONS:
            self._hits.clear()

        while self._hits and elapsed - self._hits[0][0] > self.spec.window_ms:
            self._hits.popleft()
        if elapsed < self._lockout_until_ms:
            return RevisedEvidence(
                False,
                None,
                "DISAGREEMENT_LOCKOUT",
                geometry.visual_heading_deg,
                geometry.matched_acoustic_heading_deg,
                geometry.agreement_error_deg,
            )
        if geometry.heading_deg is None or not _truth(row.get("speech_detected")):
            reason = geometry.reason if geometry.heading_deg is None else "CURRENT_SPEECH_REQUIRED"
            return RevisedEvidence(
                False,
                None,
                reason,
                geometry.visual_heading_deg,
                geometry.matched_acoustic_heading_deg,
                geometry.agreement_error_deg,
            )

        self._hits.append((elapsed, geometry.heading_deg))
        stable = [
            item
            for item in self._hits
            if circular_distance_degrees(item[1], geometry.heading_deg)
            <= self.spec.heading_tolerance_deg
        ]
        if len(stable) < self.spec.required_hits:
            return RevisedEvidence(
                False,
                None,
                "CONSENSUS_PENDING",
                geometry.visual_heading_deg,
                geometry.matched_acoustic_heading_deg,
                geometry.agreement_error_deg,
            )
        return RevisedEvidence(
            True,
            geometry.heading_deg,
            "TEMPORAL_CONSENSUS",
            geometry.visual_heading_deg,
            geometry.matched_acoustic_heading_deg,
            geometry.agreement_error_deg,
        )


def replay_revised_policy(
    spec: RevisedPolicySpec,
    rows: Iterable[dict[str, Any]],
) -> list[RevisedEvidence]:
    policy = RevisedReplayPolicy(spec)
    return [policy.process(row) for row in rows]


def evaluate_revised_trial(
    step: Any,
    rows: list[dict[str, Any]],
    spec: RevisedPolicySpec = FROZEN_REVISED_POLICY,
) -> dict[str, Any]:
    evidence = replay_revised_policy(spec, rows)
    controller = MotionShadowController()
    targets: list[float] = []
    actions: list[str] = []
    for row, source in zip(rows, evidence):
        decision = controller.process(_number(row, "elapsed_ms") or 0.0, source)
        actions.append(decision.action)
        if decision.action == "WOULD_MOVE" and decision.target_yaw_deg is not None:
            targets.append(float(decision.target_yaw_deg))
    errors = [abs(target - float(step.true_heading_deg)) for target in targets]
    wrong_sign = sum(
        target != 0.0
        and math.copysign(1.0, target) != math.copysign(1.0, float(step.true_heading_deg))
        for target in targets
    )
    reasons = Counter(item.reason for item in evidence)
    return {
        "step": int(step.index),
        "condition": str(step.condition_id),
        "role": str(step.role),
        "repetition": int(step.repetition),
        "true_heading_deg": float(step.true_heading_deg),
        "rows": len(rows),
        "speech_positive": sum(_truth(row.get("speech_detected")) for row in rows),
        "geometry_eligible_rows": sum(
            item.reason in {"GEOMETRY_ELIGIBLE", "CURRENT_SPEECH_REQUIRED", "CONSENSUS_PENDING", "TEMPORAL_CONSENSUS"}
            for item in evidence
        ),
        "source_confirmed_rows": sum(item.confirmed for item in evidence),
        "would_move_rows": sum(action == "WOULD_MOVE" for action in actions),
        "first_target_yaw_deg": targets[0] if targets else None,
        "median_target_yaw_deg": median(targets) if targets else None,
        "median_target_error_deg": median(errors) if errors else None,
        "maximum_target_error_deg": max(errors) if errors else None,
        "wrong_sign_moves": wrong_sign,
        "reason_counts": dict(sorted(reasons.items())),
    }


def aggregate_revised_trials(trials: list[dict[str, Any]]) -> dict[str, Any]:
    positives = [row for row in trials if row["role"] == "matching_positive"]
    negatives = [row for row in trials if row["role"] == "hard_negative"]
    heading_summary: list[dict[str, Any]] = []
    for heading in (-20.0, -10.0, 10.0, 20.0):
        group = [row for row in positives if row["true_heading_deg"] == heading]
        moving = [row for row in group if row["would_move_rows"] > 0]
        errors = [
            float(row["maximum_target_error_deg"])
            for row in moving
            if row["maximum_target_error_deg"] is not None
        ]
        heading_summary.append(
            {
                "heading_deg": heading,
                "trials": len(group),
                "trials_with_move": len(moving),
                "coverage_passed": len(moving) >= 2,
                "maximum_target_error_deg": max(errors) if errors else None,
                "accuracy_passed": bool(errors) and max(errors) <= 8.0,
                "wrong_sign_moves": sum(int(row["wrong_sign_moves"]) for row in group),
            }
        )
    unsafe_rows = sum(int(row["would_move_rows"]) for row in negatives)
    wrong_sign = sum(int(row["wrong_sign_moves"]) for row in positives)
    return {
        "safety_passed": unsafe_rows == 0,
        "direction_passed": wrong_sign == 0,
        "coverage_passed": all(row["coverage_passed"] for row in heading_summary),
        "accuracy_passed": all(row["accuracy_passed"] for row in heading_summary),
        "positive_trials_with_move": sum(row["would_move_rows"] > 0 for row in positives),
        "hard_negative_would_move_rows": unsafe_rows,
        "wrong_sign_moves": wrong_sign,
        "heading_summary": heading_summary,
    }
