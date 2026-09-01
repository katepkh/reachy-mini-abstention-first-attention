"""Background numeric sampler for Stage 3V.

The Streamlit browser is deliberately refreshed more slowly than the requested
DoA rate.  This worker keeps acquisition cadence independent of UI rendering
and stores only numeric endpoint and face-position observations in RAM.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass

from reachy_doa.models import DoAReading
from reachy_stage2a.camera_worker import CameraSnapshot, CameraWorker


@dataclass(slots=True, frozen=True)
class NumericSample:
    sequence: int
    sampled_monotonic: float
    reading: DoAReading
    camera: CameraSnapshot | None


@dataclass(slots=True, frozen=True)
class SamplerSnapshot:
    running: bool
    sample_count: int
    latest: NumericSample | None
    error_code: str


class NumericSampler:
    """Poll the audited GET-only client at a stable rate on one thread."""

    def __init__(
        self,
        client: object,
        camera_worker: CameraWorker | None,
        *,
        poll_hz: float,
        maximum_buffer_seconds: float = 300.0,
    ) -> None:
        rate = float(poll_hz)
        if rate <= 0.0:
            raise ValueError("poll_hz must be positive")
        self._client = client
        self._camera_worker = camera_worker
        self._period = 1.0 / rate
        self._samples: deque[NumericSample] = deque(
            maxlen=max(100, int(rate * float(maximum_buffer_seconds)))
        )
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._sequence = 0
        self._error_code = ""

    def start(self) -> None:
        if self.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="stage3v-numeric-sampler",
            daemon=True,
        )
        self._thread.start()

    def stop(self, *, timeout: float = 3.0) -> bool:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=max(0.1, float(timeout)))
        stopped = thread is None or not thread.is_alive()
        if stopped:
            self._thread = None
        return stopped

    def is_alive(self) -> bool:
        thread = self._thread
        return bool(thread is not None and thread.is_alive())

    def set_camera_worker(self, worker: CameraWorker | None) -> None:
        with self._lock:
            self._camera_worker = worker

    def snapshot(self) -> SamplerSnapshot:
        with self._lock:
            return SamplerSnapshot(
                running=self.is_alive(),
                sample_count=len(self._samples),
                latest=self._samples[-1] if self._samples else None,
                error_code=self._error_code,
            )

    def samples_between(self, start: float, end: float) -> tuple[NumericSample, ...]:
        lower = float(start)
        upper = float(end)
        with self._lock:
            return tuple(
                sample
                for sample in self._samples
                if lower <= sample.sampled_monotonic <= upper
            )

    def count_between(self, start: float, end: float) -> int:
        return len(self.samples_between(start, end))

    def _run(self) -> None:
        next_due = time.perf_counter()
        while not self._stop.is_set():
            try:
                reading = self._client.read()
                sampled = float(reading.captured_monotonic)
                with self._lock:
                    camera_worker = self._camera_worker
                camera = camera_worker.snapshot() if camera_worker is not None else None
                with self._lock:
                    self._sequence += 1
                    self._samples.append(
                        NumericSample(self._sequence, sampled, reading, camera)
                    )
                    self._error_code = ""
            except Exception as exc:
                with self._lock:
                    self._error_code = type(exc).__name__.upper()[:64]

            next_due += self._period
            current = time.perf_counter()
            if next_due < current - self._period:
                next_due = current
            self._stop.wait(max(0.0, next_due - current))

