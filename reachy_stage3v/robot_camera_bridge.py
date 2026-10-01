"""Receive-only Reachy camera bridge with a single transient RAM frame."""

from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass

from reachy_stage2a.config import CAMERA_PROXY_HOST
from reachy_stage2a.stream_client import LocalVideoSession


@dataclass(frozen=True, slots=True)
class RobotCameraBridgeSnapshot:
    status: str
    error_code: str
    transport_frames: int
    analysis_frames: int
    last_transport_monotonic: float | None
    latest_sequence: int
    latest_jpeg: bytes | None
    latest_encoded_monotonic: float | None
    width_px: int | None
    height_px: int | None
    encode_ms: float | None


class RobotCameraFrameBridge:
    """Own one local receive-only video session and overwrite its RAM frame."""

    def __init__(self, *, analysis_hz: float = 60.0, maximum_width_px: int = 640) -> None:
        self._session = LocalVideoSession(
            detection_hz=analysis_hz,
            signalling_host=CAMERA_PROXY_HOST,
        )
        self._maximum_width_px = max(160, int(maximum_width_px))
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._status = "IDLE"
        self._error_code = ""
        self._transport_frames = 0
        self._analysis_frames = 0
        self._last_transport_monotonic: float | None = None
        self._latest_sequence = 0
        self._latest_jpeg: bytes | None = None
        self._latest_encoded_monotonic: float | None = None
        self._width_px: int | None = None
        self._height_px: int | None = None
        self._encode_ms: float | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._thread_main,
            name="reachy-camera-commissioning",
            daemon=True,
        )
        self._thread.start()

    def stop(self, *, timeout: float = 8.0) -> bool:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=max(0.1, float(timeout)))
        return not bool(thread is not None and thread.is_alive())

    def snapshot(self) -> RobotCameraBridgeSnapshot:
        with self._lock:
            return RobotCameraBridgeSnapshot(
                self._status,
                self._error_code,
                self._transport_frames,
                self._analysis_frames,
                self._last_transport_monotonic,
                self._latest_sequence,
                self._latest_jpeg,
                self._latest_encoded_monotonic,
                self._width_px,
                self._height_px,
                self._encode_ms,
            )

    def _set_status(self, status: str, error_code: str) -> None:
        with self._lock:
            if (
                status == "STOPPED"
                and not error_code
                and self._status in {"AUTO_STOPPING", "ERROR"}
                and self._error_code
            ):
                # LocalVideoSession reports its bounded-runtime reason before
                # final cleanup, and may report a transport error before the
                # same final STOPPED transition. Preserve either reason so the
                # UI can distinguish expiry from an actual camera failure.
                error_code = self._error_code
            self._status = status
            self._error_code = error_code
            if status in {"ERROR", "STOPPED", "STOPPING", "AUTO_STOPPING"}:
                self._latest_jpeg = None
                self._latest_encoded_monotonic = None

    def _mark_transport_frame(self, received_monotonic: float) -> None:
        with self._lock:
            self._transport_frames += 1
            self._last_transport_monotonic = float(received_monotonic)

    def _encode_frame(self, pixels: object) -> None:
        import cv2

        started = time.perf_counter()
        frame = pixels
        height, width = frame.shape[:2]
        if width > self._maximum_width_px:
            scale = self._maximum_width_px / float(width)
            frame = cv2.resize(
                frame,
                (self._maximum_width_px, max(1, int(round(height * scale)))),
                interpolation=cv2.INTER_AREA,
            )
        encoded_height, encoded_width = frame.shape[:2]
        ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
        if not ok:
            self._set_status("ERROR", "JPEG_ENCODE_FAILED")
            return
        completed = time.perf_counter()
        with self._lock:
            self._analysis_frames += 1
            self._latest_sequence += 1
            self._latest_jpeg = bytes(buffer)
            # Timestamp from the start of conversion/encoding so the exposed
            # age conservatively includes local image preparation time.
            self._latest_encoded_monotonic = started
            self._width_px = int(encoded_width)
            self._height_px = int(encoded_height)
            self._encode_ms = 1000.0 * (completed - started)

    def _thread_main(self) -> None:
        async def run() -> None:
            await self._session.run(
                self._stop.is_set,
                self._encode_frame,
                self._set_status,
                self._mark_transport_frame,
            )

        try:
            asyncio.run(run())
        except Exception as exc:
            self._set_status("ERROR", type(exc).__name__.upper()[:64])
