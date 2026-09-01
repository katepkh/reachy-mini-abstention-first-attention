"""Atomic startup validation for Stage 3V's two passive live inputs."""

from __future__ import annotations

import time
from dataclasses import dataclass

from reachy_doa.client import ReadOnlyDoAClient
from reachy_stage2a.camera_worker import CameraWorker
from reachy_stage3v.sampler import NumericSampler


CAMERA_STARTUP_TIMEOUT_SECONDS = 25.0
CAMERA_STARTUP_MIN_FRAMES = 5
CAMERA_STARTUP_MIN_OBSERVATIONS = 1


_STARTUP_MESSAGES = {
    "NETWORK_ACCESS_DENIED": (
        "Windows denied this Stage 3V process access to the local/private network. "
        "Close this server and relaunch it from a normal PowerShell session, or grant "
        "network access before launching it. Retrying inside this process cannot recover."
    ),
    "CAMERA_NETWORK_ACCESS_DENIED": (
        "Windows denied this Stage 3V process access to Reachy Mini Control's camera proxy. "
        "Close this server and relaunch it with local-network access; automatic reconnects "
        "cannot repair an OS-level denial."
    ),
    "DOA_UNAVAILABLE": (
        "Reachy's DoA endpoint is not reachable. Confirm Reachy Mini Control shows Ready "
        "and that this computer remains on Reachy's network."
    ),
    "DOA_INVALID": "Reachy's DoA endpoint returned an invalid response.",
    "CAMERA_PROXY_UNAVAILABLE": (
        "Reachy Mini Control's localhost camera proxy is unavailable. Keep Reachy Mini "
        "Control open, connected and showing a working camera preview."
    ),
    "VIDEO_PRODUCER_NOT_AVAILABLE": (
        "The camera proxy is reachable but Reachy's video producer is not available."
    ),
    "CAMERA_STARTUP_TIMEOUT": (
        "The camera connection did not deliver enough decoded frames and numeric face-analysis "
        "observations before the startup deadline."
    ),
}


class LiveInputStartupError(RuntimeError):
    """A fail-closed, operator-actionable live-input startup failure."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = str(code or "LIVE_INPUT_STARTUP_FAILED")[:64]
        self.detail = str(detail or "")[:240]
        self.user_message = _STARTUP_MESSAGES.get(
            self.code,
            "The passive live-input pipeline could not be started safely.",
        )
        super().__init__(self.code)


@dataclass(slots=True)
class LiveInputs:
    client: ReadOnlyDoAClient
    worker: CameraWorker
    sampler: NumericSampler


def doa_failure_code(error: str) -> str:
    """Classify a stored requests error without exposing it as camera trouble."""
    normalized = str(error or "").upper()
    if "WINERROR 10013" in normalized or "PERMISSION DENIED" in normalized:
        return "NETWORK_ACCESS_DENIED"
    if any(
        marker in normalized
        for marker in (
            "CONNECTIONERROR",
            "CONNECTION REFUSED",
            "FAILED TO ESTABLISH",
            "MAX RETRIES EXCEEDED",
            "TIMED OUT",
        )
    ):
        return "DOA_UNAVAILABLE"
    return "DOA_INVALID"


def start_live_inputs(
    robot_ip: str,
    detection_hz: float,
    *,
    startup_timeout_seconds: float = CAMERA_STARTUP_TIMEOUT_SECONDS,
    minimum_frames: int = CAMERA_STARTUP_MIN_FRAMES,
    minimum_observations: int = CAMERA_STARTUP_MIN_OBSERVATIONS,
) -> LiveInputs:
    """Start only after DoA and the real decoded camera path both work.

    The camera host is deliberately not a parameter: Stage 3V always consumes
    Reachy Mini Control's fixed loopback proxy, while DoA alone uses the robot
    IP.  The returned worker is the same receiver used by the subsequent trial;
    startup validation therefore creates no extra or competing camera session.
    """
    client: ReadOnlyDoAClient | None = None
    worker: CameraWorker | None = None
    sampler: NumericSampler | None = None
    try:
        client = ReadOnlyDoAClient(robot_ip)
        initial_reading = client.read()
        if not initial_reading.valid:
            raise LiveInputStartupError(
                doa_failure_code(initial_reading.error),
                initial_reading.error,
            )

        worker = CameraWorker.acquire_local_proxy(detection_hz=detection_hz)
        deadline = time.perf_counter() + max(1.0, float(startup_timeout_seconds))
        while time.perf_counter() < deadline:
            snapshot = worker.snapshot()
            if snapshot.status == "ERROR":
                raise LiveInputStartupError(
                    snapshot.error_code or "CAMERA_STARTUP_FAILED"
                )
            if (
                snapshot.status == "RECEIVING"
                and snapshot.frames_received >= max(1, int(minimum_frames))
                and snapshot.observations_processed
                >= max(1, int(minimum_observations))
            ):
                sampler = NumericSampler(
                    client,
                    worker,
                    poll_hz=detection_hz,
                )
                sampler.start()
                return LiveInputs(client, worker, sampler)
            time.sleep(0.05)
        raise LiveInputStartupError("CAMERA_STARTUP_TIMEOUT")
    except Exception:
        if sampler is not None:
            sampler.stop()
        if worker is not None:
            worker.stop()
        if client is not None:
            client.close()
        raise
