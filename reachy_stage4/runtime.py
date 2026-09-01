"""Minimal client for the official Reachy Mini 1.9.0 WebSocket protocol.

The official package could not import because Windows Application Control
blocked its newly downloaded SciPy DLL. This transport reproduces only the
official read/status/head-pose messages and ``GotoTaskRequest`` used by Stage
4A. It has no other robot command method.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import threading
import time
from typing import Any
from uuid import uuid4

import numpy as np
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect

from .config import REACHY_PORT
from .safety import as_pose, look_at_world_pose


class ReachySdkAdapter:
    """Protocol-compatible adapter exposing one head-only task method."""

    def __init__(self, host: str) -> None:
        self._socket = connect(f"ws://{host}:{REACHY_PORT}/ws/sdk", open_timeout=5.0)
        self._stop = threading.Event()
        self._head_pose_event = threading.Event()
        self._status_event = threading.Event()
        self._latest_head_pose: np.ndarray | None = None
        self._latest_status: dict[str, Any] | None = None
        self._latest_head_pose_monotonic: float | None = None
        self._latest_status_monotonic: float | None = None
        self._task_events: dict[str, threading.Event] = {}
        self._task_errors: dict[str, str | None] = {}
        self._receiver = threading.Thread(target=self._receive, daemon=True)
        self._receiver.start()
        if not self._head_pose_event.wait(5.0) or not self._status_event.wait(5.0):
            self.disconnect()
            raise TimeoutError("Reachy did not publish status and head pose within five seconds.")

    def _receive(self) -> None:
        try:
            for raw in self._socket:
                if self._stop.is_set():
                    return
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                try:
                    message = json.loads(raw)
                except (TypeError, json.JSONDecodeError):
                    continue
                kind = message.get("type")
                if kind == "head_pose":
                    try:
                        self._latest_head_pose = as_pose(message["head_pose"])
                        self._latest_head_pose_monotonic = time.monotonic()
                        self._head_pose_event.set()
                    except (KeyError, TypeError, ValueError):
                        continue
                elif kind == "daemon_status":
                    self._latest_status = message
                    self._latest_status_monotonic = time.monotonic()
                    self._status_event.set()
                elif kind == "task_progress":
                    identifier = str(message.get("uuid") or "")
                    event = self._task_events.get(identifier)
                    if event is not None:
                        self._task_errors[identifier] = message.get("error")
                        if message.get("finished") is True:
                            event.set()
        except ConnectionClosed:
            return

    def status(self) -> dict[str, Any]:
        if self._latest_status is None:
            raise RuntimeError("No Reachy daemon status is available.")
        status = self._latest_status
        backend = status.get("backend_status") or {}
        control_stats = backend.get("control_loop_stats") or {}
        now = time.monotonic()
        return {
            "state": status.get("state"),
            "backend_ready": backend.get("ready"),
            "motor_control_mode": backend.get("motor_control_mode"),
            "error": status.get("error") or backend.get("error"),
            "simulation_enabled": status.get("simulation_enabled"),
            "mockup_sim_enabled": status.get("mockup_sim_enabled"),
            "daemon_version": status.get("version"),
            "robot_name": status.get("robot_name"),
            "control_loop_frequency_hz": control_stats.get("mean_control_loop_frequency"),
            "control_loop_max_interval_s": control_stats.get("max_control_loop_interval"),
            "control_loop_error_count": control_stats.get("nb_error"),
            "motor_controller_status": control_stats.get("motor_controller"),
            "head_pose_age_s": None
            if self._latest_head_pose_monotonic is None
            else now - self._latest_head_pose_monotonic,
            "daemon_status_age_s": None
            if self._latest_status_monotonic is None
            else now - self._latest_status_monotonic,
        }

    def current_pose(self) -> np.ndarray:
        if self._latest_head_pose is None:
            raise RuntimeError("No Reachy head pose is available.")
        return self._latest_head_pose.copy()

    def target_pose(self, point: tuple[float, float, float]) -> np.ndarray:
        return look_at_world_pose(point)

    def goto_head_only(self, pose: np.ndarray, duration_s: float) -> None:
        identifier = str(uuid4())
        event = threading.Event()
        self._task_events[identifier] = event
        self._task_errors[identifier] = None
        request = {
            "type": "task",
            "uuid": identifier,
            "req": {
                "head": as_pose(pose).flatten().tolist(),
                "antennas": None,
                "duration": float(duration_s),
                "method": "minjerk",
                "body_yaw": None,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._socket.send(json.dumps(request, separators=(",", ":")))
        if not event.wait(float(duration_s) + 2.0):
            raise TimeoutError("Reachy's head-only task did not finish before the bounded timeout.")
        error = self._task_errors.get(identifier)
        self._task_events.pop(identifier, None)
        self._task_errors.pop(identifier, None)
        if error:
            raise RuntimeError(f"Reachy's head-only task failed: {error}")

    def disconnect(self) -> None:
        self._stop.set()
        try:
            self._socket.close()
        except Exception:
            pass
