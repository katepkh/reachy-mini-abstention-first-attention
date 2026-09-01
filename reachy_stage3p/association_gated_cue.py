"""Fail-closed visual MOVE-cue gate for passive Stage 3P protocols.

This state machine emits only a UI cue decision.  It contains no robot SDK,
network, motor, media, or actuation capability.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AssociationGatedCueSpec:
    minimum_consecutive_confirmed_center_rows: int = 3
    center_pitch_tolerance_deg: float = 2.5
    maximum_wait_ms: float = 12000.0


@dataclass(frozen=True, slots=True)
class CueDecision:
    action: str
    ready_streak: int
    reason: str


class AssociationGatedMoveCue:
    """Wait for stable centered association or abort without issuing MOVE."""

    def __init__(self, spec: AssociationGatedCueSpec | None = None) -> None:
        self.spec = spec or AssociationGatedCueSpec()
        if self.spec.minimum_consecutive_confirmed_center_rows < 1:
            raise ValueError("The cue gate requires at least one confirmed row.")
        if self.spec.maximum_wait_ms <= 0.0:
            raise ValueError("The cue timeout must be positive.")
        self._ready_streak = 0
        self._cue_emitted = False
        self._aborted = False

    def process(self, elapsed_ms: float, evidence: Any) -> CueDecision:
        elapsed = float(elapsed_ms)
        if self._cue_emitted:
            return CueDecision("HOLD", self._ready_streak, "MOVE_CUE_ALREADY_EMITTED")
        if self._aborted:
            return CueDecision("ABORT", 0, "READY_TIMEOUT_ALREADY_REACHED")
        if elapsed > self.spec.maximum_wait_ms:
            self._ready_streak = 0
            self._aborted = True
            return CueDecision("ABORT", 0, "ASSOCIATION_READY_TIMEOUT")

        target_pitch = getattr(evidence, "target_pitch_deg", None)
        centered = (
            bool(getattr(evidence, "confirmed", False))
            and target_pitch is not None
            and abs(float(target_pitch)) <= self.spec.center_pitch_tolerance_deg
        )
        self._ready_streak = self._ready_streak + 1 if centered else 0
        if self._ready_streak < self.spec.minimum_consecutive_confirmed_center_rows:
            reason = "CENTER_ASSOCIATION_ACCUMULATING" if centered else "CENTER_ASSOCIATION_NOT_READY"
            return CueDecision("WAIT", self._ready_streak, reason)

        self._cue_emitted = True
        return CueDecision("MOVE_CUE", self._ready_streak, "CENTER_ASSOCIATION_STABLE")
