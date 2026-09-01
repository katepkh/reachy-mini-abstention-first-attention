"""Evidence features and a development-only directional reliability envelope."""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from statistics import median

from .analysis import analyse_csv
from .angles import percentile
from .config import DATA_DIR
from .replay import ReplayObservation


@dataclass(slots=True, frozen=True)
class ReliabilityEnvelope:
    """Piecewise-linear reliability prior fitted only from development trials."""

    scores: tuple[tuple[float, float], ...]

    def score(self, angle_deg: float | None) -> float:
        if angle_deg is None or not self.scores:
            return 0.5
        angle = min(180.0, max(0.0, float(angle_deg)))
        ordered = sorted(self.scores)
        if angle <= ordered[0][0]:
            return ordered[0][1]
        if angle >= ordered[-1][0]:
            return ordered[-1][1]
        for (left_angle, left_score), (right_angle, right_score) in zip(ordered, ordered[1:]):
            if left_angle <= angle <= right_angle:
                fraction = (angle - left_angle) / (right_angle - left_angle)
                return left_score * (1.0 - fraction) + right_score * fraction
        return 0.5

    def as_dict(self) -> dict[str, float]:
        return {f"{angle:g}": round(score, 6) for angle, score in self.scores}


def fit_reliability_envelope(entries: list[dict[str, object]]) -> ReliabilityEnvelope:
    """Fit five axis anchors from development calibration files only."""
    buckets: dict[float, list[float]] = {axis: [] for axis in (0.0, 45.0, 90.0, 135.0, 180.0)}
    for entry in entries:
        if entry.get("split") != "development" or entry.get("plan_id") != "direction-calibration":
            continue
        summary = analyse_csv(DATA_DIR / str(entry["file"]))
        expected = summary.get("expected_doa_deg")
        if expected is None:
            continue
        valid = float(summary.get("valid_rate_pct") or 0.0) / 100.0
        speech = min(1.0, float(summary.get("speech_positive_rate_pct") or 0.0) / 35.0)
        error = summary.get("median_abs_error_deg")
        accuracy = math.exp(-float(error) / 30.0) if error is not None else 0.0
        # Transparent engineering prior: network validity, detection coverage and angle accuracy.
        score = min(1.0, max(0.05, 0.25 * valid + 0.35 * speech + 0.40 * accuracy))
        nearest = min(buckets, key=lambda axis: abs(axis - float(expected)))
        buckets[nearest].append(score)
    anchors = tuple(
        (axis, sum(values) / len(values) if values else 0.5)
        for axis, values in sorted(buckets.items())
    )
    return ReliabilityEnvelope(anchors)


@dataclass(slots=True, frozen=True)
class WindowFeatures:
    total_count: int
    valid_count: int
    speech_count: int
    valid_rate: float
    speech_rate: float
    median_angle_deg: float | None
    angle_mad_deg: float | None
    stability: float
    reliability_prior: float
    p95_latency_ms: float | None
    invalid_streak: int
    competing_sources: bool
    confidence: float


def _competing(angles: list[float]) -> bool:
    """Flag two separated, repeatedly occupied one-dimensional DoA clusters."""
    if len(angles) < 6:
        return False
    ordered = sorted(angles)
    gaps = [(ordered[index + 1] - ordered[index], index) for index in range(len(ordered) - 1)]
    gap, split_index = max(gaps, default=(0.0, 0))
    left = ordered[: split_index + 1]
    right = ordered[split_index + 1 :]
    if gap < 35.0 or min(len(left), len(right)) < 2:
        return False
    left_mad = median(abs(value - median(left)) for value in left)
    right_mad = median(abs(value - median(right)) for value in right)
    return left_mad <= 25.0 and right_mad <= 25.0


class FeatureWindow:
    """Rolling endpoint-only evidence; never stores audio or transcripts."""

    def __init__(self, reliability: ReliabilityEnvelope, window_ms: float = 1200.0) -> None:
        self.reliability = reliability
        self.window_ms = float(window_ms)
        self.items: deque[ReplayObservation] = deque()

    def add(self, observation: ReplayObservation) -> WindowFeatures:
        self.items.append(observation)
        cutoff = observation.elapsed_ms - self.window_ms
        while self.items and self.items[0].elapsed_ms < cutoff:
            self.items.popleft()
        return self.features()

    def features(self) -> WindowFeatures:
        items = list(self.items)
        valid = [item for item in items if item.valid]
        speech = [item for item in valid if item.speech_detected is True and item.angle_deg is not None]
        angles = [float(item.angle_deg) for item in speech]
        total_count = len(items)
        valid_count = len(valid)
        speech_count = len(speech)
        valid_rate = valid_count / total_count if total_count else 0.0
        speech_rate = speech_count / valid_count if valid_count else 0.0
        centre = median(angles) if angles else None
        mad = median(abs(value - centre) for value in angles) if centre is not None else None
        stability = math.exp(-float(mad) / 20.0) if mad is not None else 0.0
        prior = self.reliability.score(centre)
        latency = percentile([item.latency_ms for item in valid], 0.95)
        invalid_streak = 0
        for item in reversed(items):
            if item.valid:
                break
            invalid_streak += 1
        latency_score = 1.0 if latency is None or latency <= 100.0 else max(0.0, 1.0 - (latency - 100.0) / 900.0)
        evidence = min(1.0, speech_count / 3.0) * min(1.0, speech_rate / 0.25) if speech_count else 0.0
        if evidence <= 0.0:
            confidence = 0.0
        else:
            components = [valid_rate, evidence, stability, prior, latency_score]
            confidence = math.prod(max(0.01, value) for value in components) ** (1.0 / len(components))
        return WindowFeatures(
            total_count=total_count,
            valid_count=valid_count,
            speech_count=speech_count,
            valid_rate=valid_rate,
            speech_rate=speech_rate,
            median_angle_deg=centre,
            angle_mad_deg=mad,
            stability=stability,
            reliability_prior=prior,
            p95_latency_ms=latency,
            invalid_streak=invalid_streak,
            competing_sources=_competing(angles),
            confidence=min(1.0, max(0.0, confidence)),
        )
