"""Deterministic, command-free fusion of spatial and synchrony evidence.

This module is the M5 shadow decision boundary.  It accepts already-derived
numeric evidence and can select at most one *visible attention candidate*.
Selection is not speaker identity, liveness, conversational intent, motion
permission, or response permission.  The module imports no media, network,
Reachy SDK, or actuation capability.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from typing import Any

from reachy_avsync.synchrony import SynchronyDecision

from .revised_policy import RevisedEvidence


EVIDENCE_STATUSES = frozenset({"SUPPORTED", "PENDING", "ABSTAIN", "CONFLICT", "UNAVAILABLE"})
DECISION_STATES = frozenset({"SELECT", "HOLD", "ABSTAIN"})


@dataclass(frozen=True, slots=True)
class ShadowFusionSpec:
    """Interface limits for the first visible-speaker-only shadow prototype.

    These values guard stale or incoherent inputs.  They are software-contract
    defaults, not validated end-to-end scientific thresholds.
    """

    name: str = "M5 visible-candidate fused shadow interface v1"
    max_input_age_ms: float = 800.0
    max_future_skew_ms: float = 50.0
    max_evidence_skew_ms: float = 250.0
    max_abs_heading_deg: float = 90.0
    require_same_face_track: bool = True
    visible_speaker_only: bool = True
    motion_authority: bool = False
    response_authority: bool = False

    def payload(self) -> dict[str, Any]:
        core = asdict(self)
        encoded = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return {**core, "fingerprint": hashlib.sha256(encoded).hexdigest()}


FUSED_SHADOW_SPEC_V1 = ShadowFusionSpec()


@dataclass(frozen=True, slots=True)
class SpatialEvidence:
    status: str
    observed_ms: float
    face_track_id: str | None
    heading_deg: float | None
    reason: str


@dataclass(frozen=True, slots=True)
class SynchronyEvidence:
    status: str
    observed_ms: float
    face_track_id: str | None
    correlation: float | None
    lag_ms: float | None
    reason: str


@dataclass(frozen=True, slots=True)
class ShadowObservation:
    elapsed_ms: float
    healthy: bool
    health_reason: str
    spatial: SpatialEvidence
    synchrony: SynchronyEvidence


@dataclass(frozen=True, slots=True)
class ShadowDecision:
    state: str
    reason: str
    candidate_face_track_id: str | None = None
    candidate_heading_deg: float | None = None
    motion_authorized: bool = False
    response_authorized: bool = False
    actuation_commands: int = 0
    response_commands: int = 0

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _decision(
    state: str,
    reason: str,
    *,
    face_track_id: str | None = None,
    heading_deg: float | None = None,
) -> ShadowDecision:
    if state not in DECISION_STATES:
        raise ValueError(f"Unknown shadow decision state: {state}")
    return ShadowDecision(
        state=state,
        reason=reason,
        candidate_face_track_id=face_track_id,
        candidate_heading_deg=heading_deg,
    )


def _valid_time(now_ms: float, observed_ms: float, spec: ShadowFusionSpec) -> str | None:
    if not math.isfinite(observed_ms):
        return "NONFINITE_EVIDENCE_TIME"
    age = now_ms - observed_ms
    if age < -spec.max_future_skew_ms:
        return "EVIDENCE_FROM_FUTURE"
    if age > spec.max_input_age_ms:
        return "STALE_EVIDENCE"
    return None


def _finite_number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def fuse_shadow_observation(
    observation: ShadowObservation,
    spec: ShadowFusionSpec = FUSED_SHADOW_SPEC_V1,
) -> ShadowDecision:
    """Fuse one same-clock observation without authorizing any side effect."""

    now = _finite_number(observation.elapsed_ms)
    if now is None or now < 0.0:
        return _decision("ABSTAIN", "INVALID_OBSERVATION_TIME")
    if not observation.healthy:
        return _decision("ABSTAIN", f"HEALTH_BLOCK:{observation.health_reason}")

    spatial = observation.spatial
    synchrony = observation.synchrony
    if not isinstance(spatial.status, str) or spatial.status not in EVIDENCE_STATUSES:
        return _decision("ABSTAIN", "INVALID_SPATIAL_STATUS")
    if not isinstance(synchrony.status, str) or synchrony.status not in EVIDENCE_STATUSES:
        return _decision("ABSTAIN", "INVALID_SYNCHRONY_STATUS")

    spatial_time = _finite_number(spatial.observed_ms)
    synchrony_time = _finite_number(synchrony.observed_ms)
    if spatial_time is None:
        return _decision("ABSTAIN", "SPATIAL_NONFINITE_EVIDENCE_TIME")
    if synchrony_time is None:
        return _decision("ABSTAIN", "SYNCHRONY_NONFINITE_EVIDENCE_TIME")
    for label, observed in (("SPATIAL", spatial_time), ("SYNCHRONY", synchrony_time)):
        issue = _valid_time(now, observed, spec)
        if issue:
            return _decision("ABSTAIN", f"{label}_{issue}")
    if abs(spatial_time - synchrony_time) > spec.max_evidence_skew_ms:
        return _decision("ABSTAIN", "EVIDENCE_CLOCK_SKEW_EXCESSIVE")

    if spatial.status == "CONFLICT":
        return _decision("ABSTAIN", f"SPATIAL_CONFLICT:{spatial.reason}")
    if synchrony.status == "CONFLICT":
        return _decision("ABSTAIN", f"SYNCHRONY_CONFLICT:{synchrony.reason}")
    if spatial.status == "ABSTAIN":
        return _decision("ABSTAIN", f"SPATIAL_ABSTAIN:{spatial.reason}")
    if synchrony.status == "ABSTAIN":
        return _decision("ABSTAIN", f"SYNCHRONY_ABSTAIN:{synchrony.reason}")
    if spatial.status == "UNAVAILABLE":
        return _decision("ABSTAIN", f"SPATIAL_UNAVAILABLE:{spatial.reason}")
    if synchrony.status == "UNAVAILABLE":
        return _decision("ABSTAIN", f"SYNCHRONY_UNAVAILABLE:{synchrony.reason}")
    if spatial.status == "PENDING":
        return _decision("HOLD", f"SPATIAL_PENDING:{spatial.reason}")
    if synchrony.status == "PENDING":
        return _decision("HOLD", f"SYNCHRONY_PENDING:{synchrony.reason}")

    if not spatial.face_track_id or not synchrony.face_track_id:
        return _decision("ABSTAIN", "FACE_TRACK_ID_MISSING")
    if spec.require_same_face_track and spatial.face_track_id != synchrony.face_track_id:
        return _decision("ABSTAIN", "FACE_TRACK_MISMATCH")
    heading = _finite_number(spatial.heading_deg)
    if heading is None:
        return _decision("ABSTAIN", "SPATIAL_HEADING_INVALID")
    if abs(heading) > spec.max_abs_heading_deg:
        return _decision("ABSTAIN", "SPATIAL_HEADING_OUTSIDE_SHADOW_SCOPE")

    return _decision(
        "SELECT",
        "SPATIAL_AND_SYNCHRONY_SUPPORTED_WITHIN_VISIBLE_SCOPE",
        face_track_id=spatial.face_track_id,
        heading_deg=heading,
    )


_SPATIAL_PENDING = frozenset(
    {"GEOMETRY_ELIGIBLE", "CURRENT_SPEECH_REQUIRED", "RECENT_SPEECH_REQUIRED", "CONSENSUS_PENDING"}
)
_SPATIAL_CONFLICT = frozenset(
    {"ACOUSTIC_VISUAL_DISAGREEMENT", "VISUAL_HYPOTHESIS_AMBIGUOUS", "DISAGREEMENT_LOCKOUT"}
)


def spatial_from_revised(
    observed_ms: float,
    face_track_id: str | None,
    evidence: RevisedEvidence,
) -> SpatialEvidence:
    """Adapt the frozen Stage 3V output to the M5 interface."""

    if evidence.confirmed:
        status = "SUPPORTED"
    elif evidence.reason in _SPATIAL_PENDING:
        status = "PENDING"
    elif evidence.reason in _SPATIAL_CONFLICT:
        status = "CONFLICT"
    else:
        status = "ABSTAIN"
    return SpatialEvidence(
        status=status,
        observed_ms=float(observed_ms),
        face_track_id=face_track_id,
        heading_deg=evidence.heading_deg,
        reason=evidence.reason,
    )


def synchrony_from_decision(observed_ms: float, decision: SynchronyDecision) -> SynchronyEvidence:
    """Adapt stable synchrony output without upgrading it to liveness or identity."""

    if decision.status == "SUPPORTED_CANDIDATE":
        status = "SUPPORTED"
    elif decision.status == "CANDIDATE" or "SYNCHRONY_CONSENSUS_PENDING" in decision.reason:
        status = "PENDING"
    elif decision.status == "CONFLICT":
        status = "CONFLICT"
    elif decision.status == "ABSTAIN":
        status = "ABSTAIN"
    else:
        status = "UNAVAILABLE"
    return SynchronyEvidence(
        status=status,
        observed_ms=float(observed_ms),
        face_track_id=decision.candidate_face_id,
        correlation=decision.correlation,
        lag_ms=decision.lag_ms,
        reason=decision.reason,
    )
