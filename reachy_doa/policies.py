"""Offline-only shadow attention policies. No policy can command Reachy."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .angles import doa_to_physical_hypotheses, wrap_degrees
from .confidence import FeatureWindow, ReliabilityEnvelope
from .replay import ReplayObservation


PUBLISHED_THRESHOLD_RAD = 0.004
INTENDED_TWO_DEGREE_RAD = math.radians(2.0)


@dataclass(slots=True, frozen=True)
class PolicyDecision:
    policy: str
    sequence: int
    elapsed_ms: float
    state: str
    axis_deg: float | None
    hypothesis_a_deg: float | None
    hypothesis_b_deg: float | None
    confidence: float
    valid_rate: float
    speech_evidence: float
    stability: float
    reliability_prior: float
    p95_latency_ms: float | None
    front_back_ambiguous: bool
    would_attend_axis: bool
    would_propose_physical_target: bool
    reason: str


def _physical_fields(axis: float | None) -> tuple[float | None, float | None, bool]:
    if axis is None:
        return None, None, False
    hypotheses = doa_to_physical_hypotheses(min(180.0, max(0.0, axis)))
    if len(hypotheses) == 1:
        return hypotheses[0], None, False
    separation = abs(wrap_degrees(hypotheses[0] - hypotheses[1]))
    return hypotheses[0], hypotheses[1], separation > 20.0


class ThresholdPolicy:
    """Example-style last-angle policy with no persistence or abstention logic."""

    def __init__(self, threshold_rad: float, name: str) -> None:
        self.threshold_rad = float(threshold_rad)
        self.name = name
        self.target_rad: float | None = None

    def process(self, observation: ReplayObservation) -> PolicyDecision:
        if not observation.valid:
            return PolicyDecision(
                self.name, observation.sequence, observation.elapsed_ms, "NETWORK_ERROR",
                None, None, None, 0.0, 0.0, 0.0, 0.0, 0.5,
                observation.latency_ms, False, False, False,
                "Latest endpoint response is invalid; the example-style policy has no recovery model.",
            )
        if observation.speech_detected is not True or observation.angle_rad is None:
            return PolicyDecision(
                self.name, observation.sequence, observation.elapsed_ms, "SEARCHING",
                None, None, None, 0.0, 1.0, 0.0, 0.0, 0.5,
                observation.latency_ms, False, False, False,
                "No speech-positive observation.",
            )
        if self.target_rad is None or abs(observation.angle_rad - self.target_rad) > self.threshold_rad:
            self.target_rad = observation.angle_rad
        axis = math.degrees(self.target_rad)
        first, second, ambiguous = _physical_fields(axis)
        return PolicyDecision(
            self.name, observation.sequence, observation.elapsed_ms, "TRACKING_LATEST",
            axis, first, second, 1.0, 1.0, 1.0, 1.0, 0.5,
            observation.latency_ms, ambiguous, True, True,
            "Speech flag is true; immediately accept the latest angle and assume the first physical hypothesis.",
        )


class ConfidenceAwarePolicy:
    """Persistent, ambiguity-preserving shadow controller for numerical DoA data."""

    name = "Confidence-aware shadow"

    def __init__(
        self,
        reliability: ReliabilityEnvelope,
        window_ms: float = 1200.0,
        acquire_ms: float = 600.0,
        switch_ms: float = 800.0,
        release_ms: float = 1000.0,
    ) -> None:
        self.window = FeatureWindow(reliability, window_ms)
        self.acquire_ms = acquire_ms
        self.switch_ms = switch_ms
        self.release_ms = release_ms
        self.candidate_axis: float | None = None
        self.candidate_started_ms: float | None = None
        self.tracking_axis: float | None = None
        self.last_speech_ms: float | None = None

    def _decision(
        self,
        observation: ReplayObservation,
        features,
        state: str,
        axis: float | None,
        attend_axis: bool,
        reason: str,
    ) -> PolicyDecision:
        first, second, ambiguous = _physical_fields(axis)
        physical_proposal = bool(attend_axis and not ambiguous and features.confidence >= 0.60)
        return PolicyDecision(
            self.name, observation.sequence, observation.elapsed_ms, state,
            axis, first, second, features.confidence, features.valid_rate,
            features.speech_rate, features.stability, features.reliability_prior,
            features.p95_latency_ms, ambiguous, attend_axis, physical_proposal, reason,
        )

    def process(self, observation: ReplayObservation) -> PolicyDecision:
        features = self.window.add(observation)
        if observation.valid and observation.speech_detected is True:
            self.last_speech_ms = observation.elapsed_ms

        if features.invalid_streak >= 2 or (features.total_count >= 3 and features.valid_rate < 0.60):
            return self._decision(
                observation, features, "NETWORK_DEGRADED", None, False,
                "Repeated missing responses or rolling validity below 60%; withhold attention.",
            )
        if features.competing_sources:
            return self._decision(
                observation, features, "COMPETING_SOURCES", features.median_angle_deg, False,
                "Two separated DoA clusters persist in the rolling evidence; no single source is selected.",
            )
        since_speech = (
            observation.elapsed_ms - self.last_speech_ms
            if self.last_speech_ms is not None else math.inf
        )
        if features.speech_count == 0 or since_speech > self.release_ms:
            self.candidate_axis = None
            self.candidate_started_ms = None
            self.tracking_axis = None
            return self._decision(
                observation, features, "SEARCHING", None, False,
                "No sustained speech-positive evidence in the rolling window.",
            )
        if features.median_angle_deg is None:
            return self._decision(
                observation, features, "ABSTAIN", None, False,
                "An acoustic event is present but has no usable direction.",
            )
        if features.confidence < 0.45:
            return self._decision(
                observation, features, "ABSTAIN", features.median_angle_deg, False,
                "Endpoint evidence is insufficiently valid, stable or reliable; source type remains unknown.",
            )

        proposed = features.median_angle_deg
        if self.candidate_axis is None or abs(proposed - self.candidate_axis) > 25.0:
            self.candidate_axis = proposed
            self.candidate_started_ms = observation.elapsed_ms
        else:
            self.candidate_axis = 0.75 * self.candidate_axis + 0.25 * proposed
        persisted = observation.elapsed_ms - float(self.candidate_started_ms)

        if self.tracking_axis is None:
            if features.confidence >= 0.60 and persisted >= self.acquire_ms:
                self.tracking_axis = self.candidate_axis
            else:
                return self._decision(
                    observation, features, "CANDIDATE", self.candidate_axis, False,
                    f"Candidate has persisted {persisted:.0f} ms; acquisition requires {self.acquire_ms:.0f} ms and confidence 0.60.",
                )
        elif abs(self.candidate_axis - self.tracking_axis) > 25.0:
            if features.confidence >= 0.68 and persisted >= self.switch_ms:
                self.tracking_axis = self.candidate_axis
            else:
                return self._decision(
                    observation, features, "CANDIDATE", self.tracking_axis, True,
                    "A replacement direction is present, but the stronger switch threshold and persistence are not met.",
                )
        else:
            self.tracking_axis = 0.85 * self.tracking_axis + 0.15 * self.candidate_axis

        first, second, ambiguous = _physical_fields(self.tracking_axis)
        reason = "Stable acoustic axis acquired."
        if ambiguous:
            reason += " Front/back remains unresolved, so no physical target is proposed."
        return self._decision(
            observation, features, "TRACKING_AXIS", self.tracking_axis, True, reason,
        )


def make_policies(reliability: ReliabilityEnvelope):
    return (
        ThresholdPolicy(PUBLISHED_THRESHOLD_RAD, "Example threshold · 0.004 rad"),
        ThresholdPolicy(INTENDED_TWO_DEGREE_RAD, "Comment-intended threshold · 2°"),
        ConfidenceAwarePolicy(reliability),
    )


def run_policy(policy, observations: tuple[ReplayObservation, ...]) -> tuple[PolicyDecision, ...]:
    return tuple(policy.process(observation) for observation in observations)
