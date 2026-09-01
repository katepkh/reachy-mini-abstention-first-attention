"""Fail-closed camera freshness checks for the Stage 3V conductor."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

from reachy_stage2a.models import FaceObservation


# Reachy's GStreamer producer can emit one negotiation frame and then pause for
# roughly ten seconds before its steady 30 fps stream begins.  This startup
# window must cover that whole warm-up, not merely the time to the first frame.
CAMERA_START_GRACE_SECONDS = 20.0
CAMERA_RESTART_COOLDOWN_SECONDS = 5.0
STAGE3V_MAX_FACE_AGE_MS = 1500.0
# The rolling preflight tolerates ordinary local WebRTC jitter, while the
# trial-start face check below remains stricter. A genuinely stopped stream is
# still rejected immediately by the current-sample checks in the conductor.
STAGE3V_PREFLIGHT_MAX_FRAME_AGE_MS = 2500.0
STAGE3V_PREFLIGHT_MAX_OBSERVATION_AGE_MS = 2500.0
# A frame older than MAX_FACE_AGE_MS must immediately lock recording, but a
# short detector/transport pause should not tear down a healthy WebRTC session.
# Reconnect only after the heartbeat has been continuously stale for this long.
CAMERA_STALE_RECONNECT_SECONDS = 15.0
CAMERA_HEALTH_CHECK_SECONDS = 15.0
CAMERA_HEALTH_MIN_OBSERVATIONS = 10
CAMERA_HEALTH_MIN_SAMPLES = 30
CAMERA_HEALTH_MIN_READY_FRACTION = 0.90


def observation_age_ms(
    observation: FaceObservation | None,
    *,
    now_monotonic: float,
) -> float | None:
    """Return a non-negative observation age, or ``None`` when absent."""
    if observation is None:
        return None
    return max(0.0, (float(now_monotonic) - observation.captured_monotonic) * 1000.0)


def observation_is_fresh_single_face(
    observation: FaceObservation | None,
    *,
    now_monotonic: float,
    maximum_age_ms: float = STAGE3V_MAX_FACE_AGE_MS,
) -> bool:
    """Require one valid, current face observation before a trial may start."""
    age_ms = observation_age_ms(observation, now_monotonic=now_monotonic)
    return bool(
        observation is not None
        and observation.valid
        and observation.detected
        and observation.face_count == 1
        and observation.heading_deg is not None
        and age_ms is not None
        and age_ms <= maximum_age_ms
    )


def row_has_fresh_single_face(
    row: dict[str, Any],
    *,
    maximum_age_ms: float = STAGE3V_MAX_FACE_AGE_MS,
) -> bool:
    """Validate freshness from saved numeric metadata without accessing pixels."""
    try:
        face_count = int(float(row.get("face_count") or 0))
        age_ms = float(row["face_age_ms"])
    except (KeyError, TypeError, ValueError):
        return False
    return face_count == 1 and 0.0 <= age_ms <= maximum_age_ms


def camera_health_reason(
    *,
    status: str,
    observation: FaceObservation | None,
    now_monotonic: float,
    error_code: str = "",
) -> str:
    """Return ``READY`` or a concise fail-closed reason for the dashboard."""
    if status == "ERROR" and error_code:
        return error_code
    if status != "RECEIVING":
        return f"CAMERA_{status or 'IDLE'}"
    if observation is None:
        return "CAMERA_NO_OBSERVATION"
    age_ms = observation_age_ms(observation, now_monotonic=now_monotonic)
    if age_ms is None or age_ms > STAGE3V_MAX_FACE_AGE_MS:
        return "CAMERA_OBSERVATION_STALE"
    if not observation.valid:
        return observation.error_code or "CAMERA_INVALID"
    if not observation.detected or observation.face_count == 0:
        return "NO_FACE"
    if observation.face_count != 1:
        return "MULTIPLE_FACES"
    if observation.heading_deg is None:
        return "FACE_HEADING_UNAVAILABLE"
    return "READY"


def camera_transport_reason(
    *,
    status: str,
    observation: FaceObservation | None,
    now_monotonic: float,
    frames_received: int,
    last_frame_received_monotonic: float | None,
    error_code: str = "",
    maximum_frame_age_ms: float = STAGE3V_PREFLIGHT_MAX_FRAME_AGE_MS,
) -> str:
    """Return frame-transport health without using face-detector state."""
    if status == "ERROR" and error_code:
        return error_code
    if status != "RECEIVING":
        return f"CAMERA_{status or 'IDLE'}"
    if frames_received <= 0 or last_frame_received_monotonic is None:
        return "CAMERA_NO_FRAME"
    frame_age_ms = max(
        0.0,
        (float(now_monotonic) - float(last_frame_received_monotonic)) * 1000.0,
    )
    if frame_age_ms > maximum_frame_age_ms:
        return "CAMERA_FRAME_STALE"
    return "READY"


def camera_detector_reason(
    observation: FaceObservation | None,
    *,
    now_monotonic: float,
    maximum_age_ms: float = STAGE3V_PREFLIGHT_MAX_OBSERVATION_AGE_MS,
) -> str:
    """Return detector-pipeline health independently of face presence."""
    if observation is None:
        return "CAMERA_NO_OBSERVATION"
    age_ms = observation_age_ms(observation, now_monotonic=now_monotonic)
    if age_ms is None or age_ms > maximum_age_ms:
        return "CAMERA_OBSERVATION_STALE"
    if not observation.valid:
        return observation.error_code or "CAMERA_INVALID"
    return "READY"


def face_detection_status(
    observation: FaceObservation | None,
    *,
    now_monotonic: float,
) -> str:
    """Describe face analysis without conflating it with frame transport."""
    if observation is None:
        return "NO_OBSERVATION"
    age_ms = observation_age_ms(observation, now_monotonic=now_monotonic)
    if age_ms is None or age_ms > STAGE3V_MAX_FACE_AGE_MS:
        return "STALE"
    if not observation.valid:
        return observation.error_code or "INVALID"
    if observation.face_count == 0:
        return "NO_FACE"
    if observation.face_count > 1:
        return "MULTIPLE_FACES"
    if observation.heading_deg is None:
        return "HEADING_UNAVAILABLE"
    return "ONE_FACE"


@dataclass
class CameraHealthGate:
    """Qualify camera readiness over a rolling, jitter-tolerant window.

    A single delayed poll is retained as a failed sample instead of erasing all
    prior progress. The gate passes only when the full observation window has
    been covered, enough distinct detector results exist, at least the required
    fraction of samples are healthy, and the current sample is healthy.
    """

    duration_seconds: float = CAMERA_HEALTH_CHECK_SECONDS
    minimum_observations: int = CAMERA_HEALTH_MIN_OBSERVATIONS
    minimum_samples: int = CAMERA_HEALTH_MIN_SAMPLES
    minimum_ready_fraction: float = CAMERA_HEALTH_MIN_READY_FRACTION
    stable_since: float | None = None
    last_observation_capture: float | None = None
    unique_observations: int = 0
    passed: bool = False
    last_reason: str = "NOT_STARTED"
    last_failure_reason: str = "NOT_STARTED"
    last_failure_monotonic: float | None = None
    samples: deque[tuple[float, bool, str, float | None]] = field(
        default_factory=deque,
        repr=False,
    )

    def reset(self, reason: str = "RESET") -> None:
        self.stable_since = None
        self.last_observation_capture = None
        self.unique_observations = 0
        self.passed = False
        self.last_reason = reason
        self.last_failure_reason = reason
        self.last_failure_monotonic = None
        self.samples.clear()

    def update(
        self,
        *,
        status: str,
        observation: FaceObservation | None,
        now_monotonic: float,
        frames_received: int,
        last_frame_received_monotonic: float | None,
        error_code: str = "",
    ) -> str:
        transport_reason = camera_transport_reason(
            status=status,
            observation=observation,
            now_monotonic=now_monotonic,
            frames_received=frames_received,
            last_frame_received_monotonic=last_frame_received_monotonic,
            error_code=error_code,
        )
        detector_reason = camera_detector_reason(
            observation,
            now_monotonic=now_monotonic,
        )
        reason = (
            transport_reason
            if transport_reason != "READY"
            else detector_reason
        )

        if self.stable_since is None:
            self.stable_since = float(now_monotonic)
        ready = reason == "READY"
        observation_capture = (
            observation.captured_monotonic
            if ready and observation is not None
            else None
        )
        self.samples.append(
            (float(now_monotonic), ready, reason, observation_capture)
        )
        cutoff = float(now_monotonic) - self.duration_seconds
        while self.samples and self.samples[0][0] < cutoff:
            self.samples.popleft()

        captures = {
            sample[3]
            for sample in self.samples
            if sample[3] is not None
        }
        self.unique_observations = len(captures)
        self.last_observation_capture = max(captures) if captures else None
        self.last_reason = reason
        if not ready:
            self.last_failure_reason = reason
            self.last_failure_monotonic = float(now_monotonic)
        self.passed = bool(
            self.elapsed_seconds(now_monotonic) >= self.duration_seconds
            and self.unique_observations >= self.minimum_observations
            and self.sample_count >= self.minimum_samples
            and self.ready_fraction >= self.minimum_ready_fraction
            and ready
        )
        return reason

    def elapsed_seconds(self, now_monotonic: float) -> float:
        if self.stable_since is None:
            return 0.0
        return max(0.0, float(now_monotonic) - self.stable_since)

    def progress_fraction(self, now_monotonic: float) -> float:
        time_progress = self.elapsed_seconds(now_monotonic) / max(
            0.001, self.duration_seconds
        )
        observation_progress = self.unique_observations / max(
            1, self.minimum_observations
        )
        sample_progress = self.sample_count / max(1, self.minimum_samples)
        quality_progress = self.ready_fraction / max(
            0.001, self.minimum_ready_fraction
        )
        return min(
            1.0,
            time_progress,
            observation_progress,
            sample_progress,
            quality_progress,
        )

    @property
    def sample_count(self) -> int:
        return len(self.samples)

    @property
    def ready_samples(self) -> int:
        return sum(1 for _, ready, _, _ in self.samples if ready)

    @property
    def ready_fraction(self) -> float:
        if not self.samples:
            return 0.0
        return self.ready_samples / len(self.samples)

    @property
    def failure_count(self) -> int:
        return self.sample_count - self.ready_samples

    def last_failure_age_seconds(self, now_monotonic: float) -> float | None:
        if self.last_failure_monotonic is None:
            return None
        return max(0.0, float(now_monotonic) - self.last_failure_monotonic)


def stable_face_observation(
    current: FaceObservation | None,
    last_single_face: FaceObservation | None,
    *,
    now_monotonic: float,
    maximum_age_ms: float = STAGE3V_MAX_FACE_AGE_MS,
) -> FaceObservation | None:
    """Bridge one intermittent no-face result with a recent numeric detection.

    Invalid or multiple-face observations always win and fail closed. Only a
    valid zero-face frame may fall back to the most recent single-face numeric
    observation, and never beyond the Stage 3V freshness bound.
    """
    if current is None:
        return None
    if not current.valid or current.face_count > 1:
        return current
    if current.detected and current.face_count == 1 and current.heading_deg is not None:
        return current
    if current.face_count != 0 or last_single_face is None:
        return current
    if not observation_is_fresh_single_face(
        last_single_face,
        now_monotonic=now_monotonic,
        maximum_age_ms=maximum_age_ms,
    ):
        return current
    return last_single_face
