"""Second frozen offline Stage 3V policy.

V2 bridges asynchronous endpoint events: a current speech-positive sample opens
a short latch in which three stable acoustic/visual geometry hits may arrive.
The latch is cleared by disagreement or any camera validity fault.  This module
contains no camera, network, robot SDK or actuation capability.
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

from .revised_policy import RevisedEvidence, _number, _truth, geometry_for_row


@dataclass(frozen=True, slots=True)
class RevisedPolicyV2Spec:
    name: str
    face_heading_multiplier: float
    maximum_geometry_error_deg: float
    required_hits: int
    window_ms: float
    heading_tolerance_deg: float
    disagreement_lockout_ms: float
    speech_latch_ms: float
    clear_speech_latch_on_fault: bool
    target_source: str

    def payload(self) -> dict[str, Any]:
        core = asdict(self)
        encoded = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return {**core, "fingerprint": hashlib.sha256(encoded).hexdigest()}


FROZEN_REVISED_POLICY_V2 = RevisedPolicyV2Spec(
    name="Stage 3V V2 speech-latched three-hit visual-target consensus",
    face_heading_multiplier=-1.0,
    maximum_geometry_error_deg=10.0,
    required_hits=3,
    window_ms=600.0,
    heading_tolerance_deg=8.0,
    disagreement_lockout_ms=1500.0,
    speech_latch_ms=800.0,
    clear_speech_latch_on_fault=True,
    target_source="visual",
)


class RevisedReplayPolicyV2:
    """Require recent speech plus three stable geometry hits, entirely offline."""

    _RESET_REASONS = {
        "NETWORK_INVALID",
        "NO_FACE",
        "MULTIPLE_FACES",
        "FACE_LOW_CONFIDENCE",
        "CAMERA_OBSERVATION_STALE",
    }

    def __init__(self, spec: RevisedPolicyV2Spec) -> None:
        self.spec = spec
        self._hits: deque[tuple[float, float]] = deque()
        self._last_speech_ms = -math.inf
        self._lockout_until_ms = -math.inf

    def process(self, row: dict[str, Any]) -> RevisedEvidence:
        elapsed = _number(row, "elapsed_ms") or 0.0
        if _truth(row.get("speech_detected")):
            self._last_speech_ms = elapsed

        geometry = geometry_for_row(row, self.spec)
        if geometry.reason == "ACOUSTIC_VISUAL_DISAGREEMENT":
            self._hits.clear()
            self._last_speech_ms = -math.inf
            self._lockout_until_ms = elapsed + self.spec.disagreement_lockout_ms
        elif geometry.reason in self._RESET_REASONS:
            self._hits.clear()
            if self.spec.clear_speech_latch_on_fault:
                self._last_speech_ms = -math.inf

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
        if geometry.heading_deg is None:
            return geometry
        if elapsed - self._last_speech_ms > self.spec.speech_latch_ms:
            return RevisedEvidence(
                False,
                None,
                "RECENT_SPEECH_REQUIRED",
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


def replay_revised_policy_v2(
    spec: RevisedPolicyV2Spec,
    rows: Iterable[dict[str, Any]],
) -> list[RevisedEvidence]:
    policy = RevisedReplayPolicyV2(spec)
    return [policy.process(row) for row in rows]


def evaluate_revised_trial_v2(
    step: Any,
    rows: list[dict[str, Any]],
    spec: RevisedPolicyV2Spec = FROZEN_REVISED_POLICY_V2,
) -> dict[str, Any]:
    evidence = replay_revised_policy_v2(spec, rows)
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
            item.reason
            in {
                "GEOMETRY_ELIGIBLE",
                "RECENT_SPEECH_REQUIRED",
                "CONSENSUS_PENDING",
                "TEMPORAL_CONSENSUS",
            }
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
