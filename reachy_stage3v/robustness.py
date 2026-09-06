"""Deterministic, exploratory trial-level robustness analysis for Stage 3V.

This module replays already-public numeric evidence.  It has no camera, media,
network, robot SDK, or actuation capability.  The frozen V3 result remains the
confirmatory result; every threshold sweep and ablation here is post-hoc.
"""

from __future__ import annotations

import csv
import hashlib
import math
from collections import deque
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from statistics import median
from typing import Any, Callable, Iterable

from reachy_stage2a.calibration import circular_distance_degrees
from reachy_stage3a.controller import MotionShadowController

from .analysis import load_rows
from .protocol import VALIDATION_STEPS, ValidationStep
from .revised_policy import RevisedEvidence, _integer, _number, _truth
from .revised_policy_v3 import (
    FROZEN_REVISED_POLICY_V3,
    RevisedPolicyV3Spec,
    RevisedReplayPolicyV3,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DATA_DIR = PROJECT_ROOT / "evidence" / "stage3v_v3"
ACCEPTED_TRIALS_CSV = (
    PROJECT_ROOT / "evidence" / "analysis" / "stage3v_confirmation_validation_v3_trials.csv"
)


@dataclass(frozen=True, slots=True)
class PublicTrial:
    step: ValidationStep
    filename: str
    rows: tuple[dict[str, Any], ...]
    sha256: str


@dataclass(frozen=True, slots=True)
class TrialOutcome:
    step: int
    condition: str
    role: str
    repetition: int
    true_heading_deg: float
    rows: int
    proposed: bool
    would_move_rows: int
    first_proposal_latency_ms: float | None
    observed_abstention_ms: float
    maximum_target_error_deg: float | None
    wrong_sign_moves: int


PolicyFactory = Callable[[], Any]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_public_trials() -> tuple[PublicTrial, ...]:
    """Load exactly the 18 accepted confirmation trials from the public index."""

    if not ACCEPTED_TRIALS_CSV.is_file():
        raise FileNotFoundError(f"Missing accepted-trial index: {ACCEPTED_TRIALS_CSV}")
    with ACCEPTED_TRIALS_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        accepted = list(csv.DictReader(handle))
    if len(accepted) != len(VALIDATION_STEPS):
        raise ValueError("The public Stage 3V index must contain exactly 18 accepted trials.")

    trials: list[PublicTrial] = []
    for step, record in zip(VALIDATION_STEPS, accepted):
        if int(record["step"]) != step.index or record["condition"] != step.condition_id:
            raise ValueError(f"Accepted-trial index diverges at step {step.index}.")
        filename = Path(record["file"]).name
        path = (PUBLIC_DATA_DIR / filename).resolve()
        if path.parent != PUBLIC_DATA_DIR.resolve() or not path.is_file():
            raise FileNotFoundError(f"Missing accepted public trial: {filename}")
        trials.append(
            PublicTrial(
                step=step,
                filename=filename,
                rows=tuple(load_rows(path)),
                sha256=sha256_file(path),
            )
        )
    return tuple(trials)


def wilson_interval(successes: int, trials: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """Return a two-sided Wilson score interval for a binomial proportion."""

    if trials <= 0 or successes < 0 or successes > trials:
        raise ValueError("Wilson interval requires 0 <= successes <= trials and trials > 0.")
    proportion = successes / trials
    denominator = 1.0 + z * z / trials
    centre = (proportion + z * z / (2.0 * trials)) / denominator
    half_width = (
        z
        * math.sqrt(proportion * (1.0 - proportion) / trials + z * z / (4.0 * trials * trials))
        / denominator
    )
    return max(0.0, centre - half_width), min(1.0, centre + half_width)


class _TemporalBaselinePolicy:
    """Small conservative consensus wrapper used only for named ablations."""

    def __init__(
        self,
        candidate: Callable[[dict[str, Any]], RevisedEvidence],
        *,
        required_hits: int = 3,
        window_ms: float = 600.0,
        heading_tolerance_deg: float = 8.0,
        require_recent_speech: bool = False,
        speech_latch_ms: float = 800.0,
    ) -> None:
        self._candidate = candidate
        self._required_hits = required_hits
        self._window_ms = window_ms
        self._heading_tolerance_deg = heading_tolerance_deg
        self._require_recent_speech = require_recent_speech
        self._speech_latch_ms = speech_latch_ms
        self._hits: deque[tuple[float, float]] = deque()
        self._last_speech_ms = -math.inf

    def process(self, row: dict[str, Any]) -> RevisedEvidence:
        elapsed = _number(row, "elapsed_ms") or 0.0
        if _truth(row.get("speech_detected")):
            self._last_speech_ms = elapsed
        candidate = self._candidate(row)
        if candidate.heading_deg is None:
            self._hits.clear()
            return candidate
        while self._hits and elapsed - self._hits[0][0] > self._window_ms:
            self._hits.popleft()
        if self._require_recent_speech and elapsed - self._last_speech_ms > self._speech_latch_ms:
            return RevisedEvidence(False, None, "RECENT_SPEECH_REQUIRED")
        self._hits.append((elapsed, candidate.heading_deg))
        stable = [
            item
            for item in self._hits
            if circular_distance_degrees(item[1], candidate.heading_deg)
            <= self._heading_tolerance_deg
        ]
        if len(stable) < self._required_hits:
            return RevisedEvidence(False, None, "CONSENSUS_PENDING")
        return RevisedEvidence(True, candidate.heading_deg, "TEMPORAL_CONSENSUS")


def _visual_candidate(row: dict[str, Any]) -> RevisedEvidence:
    if _integer(row, "face_count") == 0 or _number(row, "face_heading_deg") is None:
        return RevisedEvidence(False, None, "NO_FACE")
    if _integer(row, "face_count") != 1:
        return RevisedEvidence(False, None, "MULTIPLE_FACES")
    if (_number(row, "face_confidence") or 0.0) < 0.55:
        return RevisedEvidence(False, None, "FACE_LOW_CONFIDENCE")
    age = _number(row, "face_age_ms")
    if age is None or age < 0.0 or age > 1500.0:
        return RevisedEvidence(False, None, "CAMERA_OBSERVATION_STALE")
    raw = _number(row, "face_heading_deg")
    assert raw is not None
    heading = FROZEN_REVISED_POLICY_V3.face_heading_multiplier * raw + FROZEN_REVISED_POLICY_V3.face_heading_offset_deg
    return RevisedEvidence(False, heading, "VISUAL_ELIGIBLE", visual_heading_deg=heading)


def _audio_front_candidate(row: dict[str, Any]) -> RevisedEvidence:
    if _integer(row, "http_status") != 200 or _number(row, "raw_angle_rad") is None:
        return RevisedEvidence(False, None, "NETWORK_INVALID")
    if row.get("acoustic_state") != "TRACKING_AXIS":
        return RevisedEvidence(False, None, "ACOUSTIC_NOT_TRACKING")
    if (_number(row, "acoustic_confidence") or 0.0) < 0.60:
        return RevisedEvidence(False, None, "ACOUSTIC_LOW_CONFIDENCE")
    heading = _number(row, "hypothesis_a_deg")
    if heading is None:
        return RevisedEvidence(False, None, "ACOUSTIC_HYPOTHESIS_MISSING")
    return RevisedEvidence(False, heading, "AUDIO_FRONT_HYPOTHESIS_ELIGIBLE")


class _SpeechRemovedV3:
    """Replay V3 while counterfactually treating every row as speech-positive."""

    def __init__(self) -> None:
        self._delegate = RevisedReplayPolicyV3(FROZEN_REVISED_POLICY_V3)

    def process(self, row: dict[str, Any]) -> RevisedEvidence:
        adjusted = dict(row)
        adjusted["speech_detected"] = True
        return self._delegate.process(adjusted)


def policy_factories() -> dict[str, PolicyFactory]:
    frozen = FROZEN_REVISED_POLICY_V3
    return {
        "full_frozen_v3": lambda: RevisedReplayPolicyV3(frozen),
        "single_frame_audio_visual": lambda: RevisedReplayPolicyV3(replace(frozen, required_hits=1)),
        "audio_visual_without_speech_gate": _SpeechRemovedV3,
        "visual_only_temporal": lambda: _TemporalBaselinePolicy(_visual_candidate),
        "audio_only_front_hypothesis": lambda: _TemporalBaselinePolicy(
            _audio_front_candidate, require_recent_speech=True
        ),
    }


def evaluate_trial(trial: PublicTrial, policy_factory: PolicyFactory) -> TrialOutcome:
    policy = policy_factory()
    controller = MotionShadowController()
    targets: list[float] = []
    proposal_times: list[float] = []
    first_elapsed = _number(trial.rows[0], "elapsed_ms") or 0.0
    last_elapsed = first_elapsed
    for row in trial.rows:
        elapsed = _number(row, "elapsed_ms") or 0.0
        last_elapsed = elapsed
        source = policy.process(row)
        decision = controller.process(elapsed, source)
        if decision.action == "WOULD_MOVE" and decision.target_yaw_deg is not None:
            targets.append(float(decision.target_yaw_deg))
            proposal_times.append(elapsed)
    errors = (
        [abs(target - trial.step.true_heading_deg) for target in targets]
        if trial.step.role == "matching_positive"
        else []
    )
    wrong_sign = (
        sum(
            target != 0.0
            and math.copysign(1.0, target) != math.copysign(1.0, trial.step.true_heading_deg)
            for target in targets
        )
        if trial.step.role == "matching_positive"
        else 0
    )
    duration = max(0.0, last_elapsed - first_elapsed)
    first_latency = proposal_times[0] - first_elapsed if proposal_times else None
    return TrialOutcome(
        step=trial.step.index,
        condition=trial.step.condition_id,
        role=trial.step.role,
        repetition=trial.step.repetition,
        true_heading_deg=trial.step.true_heading_deg,
        rows=len(trial.rows),
        proposed=bool(targets),
        would_move_rows=len(targets),
        first_proposal_latency_ms=first_latency,
        observed_abstention_ms=first_latency if first_latency is not None else duration,
        maximum_target_error_deg=max(errors) if errors else None,
        wrong_sign_moves=wrong_sign,
    )


def aggregate_outcomes(name: str, outcomes: Iterable[TrialOutcome]) -> dict[str, Any]:
    outcomes = tuple(outcomes)
    positives = tuple(item for item in outcomes if item.role == "matching_positive")
    negatives = tuple(item for item in outcomes if item.role == "hard_negative")
    positive_moves = sum(item.proposed for item in positives)
    negative_moves = sum(item.proposed for item in negatives)
    proposed_trials = positive_moves + negative_moves
    positive_ci = wilson_interval(positive_moves, len(positives))
    negative_ci = wilson_interval(negative_moves, len(negatives))
    selective_ci = wilson_interval(negative_moves, proposed_trials) if proposed_trials else None
    latencies = [
        float(item.first_proposal_latency_ms)
        for item in positives
        if item.first_proposal_latency_ms is not None
    ]
    negative_abstentions = [item.observed_abstention_ms for item in negatives]
    errors = [
        float(item.maximum_target_error_deg)
        for item in positives
        if item.maximum_target_error_deg is not None
    ]
    return {
        "policy": name,
        "positive_trials": len(positives),
        "positive_trials_with_proposal": positive_moves,
        "positive_coverage": positive_moves / len(positives),
        "positive_coverage_wilson95": list(positive_ci),
        "hard_negative_trials": len(negatives),
        "hard_negative_trials_with_proposal": negative_moves,
        "hard_negative_false_proposal_rate": negative_moves / len(negatives),
        "hard_negative_false_proposal_wilson95": list(negative_ci),
        "proposed_trials": proposed_trials,
        "selective_risk_given_proposal": negative_moves / proposed_trials if proposed_trials else None,
        "selective_risk_wilson95": list(selective_ci) if selective_ci else None,
        "hard_negative_would_move_rows": sum(item.would_move_rows for item in negatives),
        "wrong_sign_moves": sum(item.wrong_sign_moves for item in positives),
        "median_positive_first_proposal_latency_ms": median(latencies) if latencies else None,
        "median_hard_negative_observed_abstention_ms": median(negative_abstentions),
        "maximum_positive_target_error_deg": max(errors) if errors else None,
    }


def evaluate_factory(name: str, factory: PolicyFactory, trials: Iterable[PublicTrial]) -> tuple[dict[str, Any], tuple[TrialOutcome, ...]]:
    outcomes = tuple(evaluate_trial(trial, factory) for trial in trials)
    return aggregate_outcomes(name, outcomes), outcomes


def evaluate_spec(spec: RevisedPolicyV3Spec, trials: Iterable[PublicTrial], name: str) -> dict[str, Any]:
    summary, _ = evaluate_factory(name, lambda: RevisedReplayPolicyV3(spec), trials)
    return summary


def _rounded_summary(summary: dict[str, Any]) -> dict[str, Any]:
    rounded: dict[str, Any] = {}
    for key, value in summary.items():
        if isinstance(value, float):
            rounded[key] = round(value, 9)
        elif isinstance(value, list):
            rounded[key] = [round(item, 9) if isinstance(item, float) else item for item in value]
        else:
            rounded[key] = value
    return rounded


def build_robustness_report() -> dict[str, Any]:
    trials = load_public_trials()
    ablations: list[dict[str, Any]] = []
    full_outcomes: tuple[TrialOutcome, ...] = ()
    for name, factory in policy_factories().items():
        summary, outcomes = evaluate_factory(name, factory, trials)
        ablations.append(_rounded_summary(summary))
        if name == "full_frozen_v3":
            full_outcomes = outcomes

    one_at_a_time: list[dict[str, Any]] = []
    sensitivity_grid: dict[str, tuple[float | int, ...]] = {
        "face_heading_offset_deg": (-6.0, -5.0, -4.0, -3.0, -2.0),
        "maximum_geometry_error_deg": (6.0, 8.0, 10.0, 12.0, 14.0),
        "required_hits": (1, 2, 3, 4, 5),
        "window_ms": (400.0, 600.0, 800.0, 1000.0),
        "heading_tolerance_deg": (4.0, 6.0, 8.0, 10.0, 12.0),
        "disagreement_lockout_ms": (0.0, 750.0, 1500.0, 2250.0),
        "speech_latch_ms": (0.0, 400.0, 800.0, 1200.0, 1600.0),
    }
    for parameter, values in sensitivity_grid.items():
        for value in values:
            spec = replace(FROZEN_REVISED_POLICY_V3, **{parameter: value})
            summary = evaluate_spec(spec, trials, f"{parameter}={value}")
            one_at_a_time.append(
                {
                    "parameter": parameter,
                    "value": value,
                    "is_frozen_value": value == getattr(FROZEN_REVISED_POLICY_V3, parameter),
                    **_rounded_summary(summary),
                }
            )

    operating_points: list[dict[str, Any]] = []
    for geometry_error in (6.0, 8.0, 10.0, 12.0, 14.0):
        for required_hits in (1, 2, 3, 4, 5):
            spec = replace(
                FROZEN_REVISED_POLICY_V3,
                maximum_geometry_error_deg=geometry_error,
                required_hits=required_hits,
            )
            summary = evaluate_spec(
                spec,
                trials,
                f"geometry={geometry_error},hits={required_hits}",
            )
            operating_points.append(
                {
                    "maximum_geometry_error_deg": geometry_error,
                    "required_hits": required_hits,
                    **_rounded_summary(summary),
                }
            )

    leave_one_out: list[dict[str, Any]] = []
    frozen_factory = policy_factories()["full_frozen_v3"]
    for omitted in trials:
        retained = tuple(trial for trial in trials if trial.step.index != omitted.step.index)
        summary, _ = evaluate_factory("full_frozen_v3", frozen_factory, retained)
        leave_one_out.append(
            {
                "omitted_step": omitted.step.index,
                "omitted_role": omitted.step.role,
                **_rounded_summary(summary),
            }
        )

    source_entries = [
        {"step": trial.step.index, "file": trial.filename, "sha256": trial.sha256}
        for trial in trials
    ]
    bundle_material = "\n".join(
        f"{entry['step']}:{entry['file']}:{entry['sha256']}" for entry in source_entries
    ).encode("utf-8")
    return {
        "schema": "reachy-stage3v-exploratory-trial-robustness-v1",
        "status": "POST_HOC_EXPLORATORY_REPLAY_NOT_HARDWARE_AUTHORIZATION",
        "experimental_unit": "accepted trial",
        "source_stage": "Stage 3V V3 fresh passive confirmation",
        "frozen_policy": FROZEN_REVISED_POLICY_V3.payload(),
        "source_bundle_sha256": hashlib.sha256(bundle_material).hexdigest(),
        "sources": source_entries,
        "trial_counts": {"total": 18, "matching_positive": 12, "hard_negative": 6},
        "confidence_interval": "two-sided Wilson score, nominal 95%",
        "ablations": ablations,
        "one_at_a_time_sensitivity": one_at_a_time,
        "risk_coverage_operating_points": operating_points,
        "leave_one_trial_out": leave_one_out,
        "frozen_trial_outcomes": [asdict(item) for item in full_outcomes],
        "interpretation_limits": [
            "Rows within a trial are correlated; intervals use trial counts only.",
            "The original frozen V3 policy was held out, but all analyses in this file were chosen after seeing its results.",
            "Ablations are diagnostic counterfactual replays, not randomized comparisons or causal evidence.",
            "The audio-only front-hypothesis baseline encodes a front-hemisphere choice and is not a general DoA resolver.",
            "Risk/coverage points are finite policy operating points on one small single-site dataset, not a calibrated population curve.",
            "No result authorizes a robot command or establishes speaker identity, ownership, consent, or mechanical safety.",
        ],
    }

