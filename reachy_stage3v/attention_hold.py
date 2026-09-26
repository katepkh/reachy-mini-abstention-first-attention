"""Pure bounded face-directed attention-hold contract.

This module consumes already-derived numeric face observations.  It has no
camera, network, robot SDK, speech, or actuation capability.  Its limits are
engineering defaults for replay/simulation and are not physically validated.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class AttentionHoldSpec:
    max_abs_x_error_norm: float = 0.08
    max_abs_y_error_norm: float = 0.10
    required_dwell_ms: float = 1200.0
    maximum_observation_age_ms: float = 500.0
    face_loss_timeout_ms: float = 500.0
    maximum_correction_error_norm: float = 0.30
    oscillation_window_ms: float = 2000.0
    maximum_x_sign_changes: int = 3
    minimum_sign_error_norm: float = 0.03
    motion_authority: bool = False
    response_authority: bool = False


ATTENTION_HOLD_SPEC_V1 = AttentionHoldSpec()


@dataclass(frozen=True, slots=True)
class FaceAttentionObservation:
    elapsed_ms: float
    healthy: bool
    health_reason: str
    face_track_id: str | None
    x_error_norm: float | None
    y_error_norm: float | None
    observation_age_ms: float | None


@dataclass(frozen=True, slots=True)
class AttentionHoldResult:
    state: str
    reason: str
    dwell_ms: float
    correction_x_norm: float | None = None
    correction_y_norm: float | None = None
    motion_authorized: bool = False
    response_authorized: bool = False
    actuation_commands: int = 0
    response_commands: int = 0

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


class AttentionHoldController:
    """Evaluate one selected face track without issuing correction commands."""

    def __init__(
        self,
        selected_face_track_id: str,
        spec: AttentionHoldSpec = ATTENTION_HOLD_SPEC_V1,
    ) -> None:
        if not str(selected_face_track_id).strip():
            raise ValueError("A selected face-track identifier is required.")
        self.selected_face_track_id = str(selected_face_track_id)
        self.spec = spec
        self._dwell_started_ms: float | None = None
        self._last_valid_face_ms: float | None = None
        self._x_signs: deque[tuple[float, int]] = deque()
        self._latched_abort_reason: str | None = None

    def _result(
        self,
        state: str,
        reason: str,
        *,
        now_ms: float,
        x: float | None = None,
        y: float | None = None,
    ) -> AttentionHoldResult:
        dwell = 0.0 if self._dwell_started_ms is None else max(0.0, now_ms - self._dwell_started_ms)
        return AttentionHoldResult(state, reason, dwell, x, y)

    def _abort(self, reason: str, now_ms: float) -> AttentionHoldResult:
        self._latched_abort_reason = reason
        self._dwell_started_ms = None
        return self._result("ABORT", reason, now_ms=now_ms)

    def process(self, observation: FaceAttentionObservation) -> AttentionHoldResult:
        now = float(observation.elapsed_ms)
        if not math.isfinite(now) or now < 0.0:
            return self._abort("INVALID_OBSERVATION_TIME", 0.0)
        if self._latched_abort_reason is not None:
            return self._result("ABORT", self._latched_abort_reason, now_ms=now)
        if not observation.healthy:
            return self._abort(f"HEALTH_BLOCK:{observation.health_reason}", now)

        age = observation.observation_age_ms
        if age is None or not math.isfinite(float(age)) or float(age) < 0.0:
            return self._abort("FACE_AGE_INVALID", now)
        if float(age) > self.spec.maximum_observation_age_ms:
            return self._abort("FACE_OBSERVATION_STALE", now)

        if observation.face_track_id != self.selected_face_track_id:
            self._dwell_started_ms = None
            if self._last_valid_face_ms is None:
                self._last_valid_face_ms = now
            if now - self._last_valid_face_ms > self.spec.face_loss_timeout_ms:
                return self._abort("SELECTED_FACE_LOST", now)
            return self._result("ACQUIRING", "SELECTED_FACE_TEMPORARILY_UNAVAILABLE", now_ms=now)

        x = observation.x_error_norm
        y = observation.y_error_norm
        if x is None or y is None or not all(math.isfinite(float(value)) for value in (x, y)):
            return self._abort("FACE_ERROR_INVALID", now)
        x_value = float(x)
        y_value = float(y)
        self._last_valid_face_ms = now

        if max(abs(x_value), abs(y_value)) > self.spec.maximum_correction_error_norm:
            return self._abort("FACE_OUTSIDE_BOUNDED_CORRECTION_SCOPE", now)

        if abs(x_value) >= self.spec.minimum_sign_error_norm:
            sign = 1 if x_value > 0.0 else -1
            if not self._x_signs or self._x_signs[-1][1] != sign:
                self._x_signs.append((now, sign))
        cutoff = now - self.spec.oscillation_window_ms
        while self._x_signs and self._x_signs[0][0] < cutoff:
            self._x_signs.popleft()
        sign_changes = max(0, len(self._x_signs) - 1)
        if sign_changes > self.spec.maximum_x_sign_changes:
            return self._abort("OSCILLATION_LIMIT_EXCEEDED", now)

        inside = (
            abs(x_value) <= self.spec.max_abs_x_error_norm
            and abs(y_value) <= self.spec.max_abs_y_error_norm
        )
        if not inside:
            self._dwell_started_ms = None
            return self._result(
                "CORRECTION_NEEDED",
                "FACE_OUTSIDE_ATTENTION_REGION",
                now_ms=now,
                x=x_value,
                y=y_value,
            )

        if self._dwell_started_ms is None:
            self._dwell_started_ms = now
        dwell = now - self._dwell_started_ms
        if dwell < self.spec.required_dwell_ms:
            return self._result("ACQUIRING", "ATTENTION_DWELL_PENDING", now_ms=now)
        return self._result("HELD", "BOUNDED_FACE_DIRECTED_ATTENTION_HELD", now_ms=now)
