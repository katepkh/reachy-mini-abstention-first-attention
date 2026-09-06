"""Thread boundary that prevents camera pixels entering Streamlit state."""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass

from .config import CAMERA_PROXY_HOST
from .face_detector import FacePositionDetector
from .models import FaceObservation
from .stream_client import LocalVideoSession


def is_expected_aioice_shutdown_race(
    context: dict[str, object],
    *,
    stop_requested: bool,
) -> bool:
    """Recognise aioice's harmless retry callback after a requested close.

    aioice 0.10 can run a queued ``Transaction.__retry`` callback after its
    future has already been cancelled.  It raises ``InvalidStateError`` only
    during teardown; the receiver and peer connection are already closing.
    Suppress exactly that callback while a stop is requested, never an active
    transport error.
    """
    return bool(
        stop_requested
        and isinstance(context.get("exception"), asyncio.InvalidStateError)
        and "Transaction.__retry" in repr(context.get("handle"))
    )


@dataclass(slots=True, frozen=True)
class CameraSnapshot:
    status: str
    error_code: str
    observation: FaceObservation | None
    last_single_face_observation: FaceObservation | None
    frames_received: int
    last_frame_received_monotonic: float | None
    observations_processed: int


class CameraWorker:
    """Own the camera session and publish numbers only."""

    _ownership_lock = threading.Lock()
    _active_owner: CameraWorker | None = None
    STOP_TIMEOUT_SECONDS = 8.0

    def __init__(
        self,
        *,
        detection_hz: float = 5.0,
        camera_host: str = CAMERA_PROXY_HOST,
    ) -> None:
        self._session = LocalVideoSession(
            detection_hz=detection_hz,
            signalling_host=camera_host,
        )
        self._detector = FacePositionDetector()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._status = "IDLE"
        self._error_code = ""
        self._observation: FaceObservation | None = None
        self._last_single_face_observation: FaceObservation | None = None
        self._frames_received = 0
        self._last_frame_received_monotonic: float | None = None
        self._observations_processed = 0

    @classmethod
    def acquire(
        cls,
        *,
        detection_hz: float = 5.0,
        camera_host: str = CAMERA_PROXY_HOST,
    ) -> CameraWorker:
        """Return the process receiver, adopting it after a page reload.

        Streamlit creates a new session when a tab reloads, but the receiver
        thread is process-wide. Reusing the live owner prevents an orphaned
        session from permanently blocking the new page with
        CAMERA_RECEIVER_ALREADY_ACTIVE.
        """
        with cls._ownership_lock:
            owner = cls._active_owner
            if owner is not None and owner.is_alive():
                return owner
            if owner is not None:
                cls._active_owner = None
        worker = cls(detection_hz=detection_hz, camera_host=camera_host)
        try:
            worker.start()
            return worker
        except RuntimeError:
            # A simultaneous Streamlit callback may have won the ownership
            # race between the check above and start(). Adopt that owner.
            with cls._ownership_lock:
                owner = cls._active_owner
                if owner is not None and owner.is_alive():
                    return owner
            raise

    @classmethod
    def acquire_local_proxy(
        cls,
        *,
        detection_hz: float = 5.0,
    ) -> CameraWorker:
        """Acquire the one receiver through Reachy Mini Control's loopback proxy.

        Stage 3V must never derive its camera signalling host from the robot's
        DoA address.  Keeping this entry point free of a host argument makes
        that endpoint separation explicit and regression-testable.
        """
        return cls.acquire(
            detection_hz=detection_hz,
            camera_host=CAMERA_PROXY_HOST,
        )

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        with type(self)._ownership_lock:
            owner = type(self)._active_owner
            if owner is not None and owner is not self and owner.is_alive():
                raise RuntimeError("CAMERA_RECEIVER_ALREADY_ACTIVE")
            type(self)._active_owner = self
        self._stop.clear()
        with self._lock:
            self._status = "CONNECTING"
            self._error_code = ""
            self._observation = None
            self._last_single_face_observation = None
            self._frames_received = 0
            self._last_frame_received_monotonic = None
            self._observations_processed = 0
        self._thread = threading.Thread(
            target=self._thread_main,
            name="stage2a-local-camera",
            daemon=True,
        )
        try:
            self._thread.start()
        except Exception:
            self._release_ownership()
            raise

    def stop(self, *, timeout: float = STOP_TIMEOUT_SECONDS) -> bool:
        """Stop and fully join the receiver before another may be created."""
        self._stop.set()
        with self._lock:
            self._status = "STOPPING"
            self._observation = None
            self._last_single_face_observation = None
        thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=max(0.1, float(timeout)))
        if thread is not None and thread.is_alive():
            self._set_status("ERROR", "CAMERA_SHUTDOWN_TIMEOUT")
            return False
        self._thread = None
        self._release_ownership()
        with self._lock:
            self._status = "STOPPED"
            self._error_code = ""
        return True

    def is_alive(self) -> bool:
        thread = self._thread
        return bool(thread is not None and thread.is_alive())

    def snapshot(self) -> CameraSnapshot:
        with self._lock:
            return CameraSnapshot(
                self._status,
                self._error_code,
                self._observation,
                self._last_single_face_observation,
                self._frames_received,
                self._last_frame_received_monotonic,
                self._observations_processed,
            )

    def _release_ownership(self) -> None:
        with type(self)._ownership_lock:
            if type(self)._active_owner is self:
                type(self)._active_owner = None

    def _set_status(self, status: str, error_code: str) -> None:
        with self._lock:
            self._status = status
            self._error_code = error_code
            if status in {"ERROR", "STOPPED", "STOPPING", "AUTO_STOPPING"}:
                self._observation = None
                self._last_single_face_observation = None

    def _observe(self, pixels: object) -> None:
        observation = self._detector.observe(pixels)
        with self._lock:
            self._observations_processed += 1
            self._observation = observation
            if (
                observation.valid
                and observation.detected
                and observation.face_count == 1
                and observation.heading_deg is not None
            ):
                self._last_single_face_observation = observation

    def _mark_frame_received(self, received_monotonic: float) -> None:
        with self._lock:
            self._frames_received += 1
            self._last_frame_received_monotonic = float(received_monotonic)

    def _thread_main(self) -> None:
        async def run_session() -> None:
            loop = asyncio.get_running_loop()
            previous_handler = loop.get_exception_handler()

            def handle_loop_exception(
                active_loop: asyncio.AbstractEventLoop,
                context: dict[str, object],
            ) -> None:
                if is_expected_aioice_shutdown_race(
                    context,
                    stop_requested=self._stop.is_set(),
                ):
                    return
                if previous_handler is not None:
                    previous_handler(active_loop, context)
                else:
                    active_loop.default_exception_handler(context)

            loop.set_exception_handler(handle_loop_exception)
            try:
                await self._session.run(
                    self._stop.is_set,
                    self._observe,
                    self._set_status,
                    self._mark_frame_received,
                )
            finally:
                # Let already-ready close callbacks run under the scoped
                # handler before asyncio tears the receiver loop down.
                await asyncio.sleep(0)
                loop.set_exception_handler(previous_handler)

        try:
            asyncio.run(run_session())
        except Exception as exc:
            self._set_status("ERROR", type(exc).__name__.upper()[:64])
        finally:
            self._release_ownership()
