"""Offline-only daemon failure rehearsal using a fixed isolated mock process.

This module never imports Reachy, opens a socket, addresses a serial port, or
accepts an executable from its caller.  The only child process it can start is
the current Python interpreter running ``MOCK_WORKER_SOURCE`` below.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


SCHEMA_VERSION = "reachy-stage4a-offline-fault-rehearsal-v1"
SCENARIOS = (
    "START_FAILURE",
    "HEALTH_TIMEOUT",
    "STATE_STREAM_DISCONNECT",
    "SHUTDOWN_HANG",
)

MOCK_WORKER_SOURCE = r"""
import json
import sys
import time

scenario = sys.argv[1]

def emit(event):
    print(json.dumps({"event": event}, sort_keys=True), flush=True)

if scenario == "START_FAILURE":
    emit("MOCK_START_REJECTED")
    raise SystemExit(17)

emit("MOCK_PROCESS_STARTED")

if scenario == "HEALTH_TIMEOUT":
    time.sleep(30)
elif scenario == "STATE_STREAM_DISCONNECT":
    emit("MOCK_HEALTHY")
    emit("MOCK_STATE_STREAM_DISCONNECTED")
    time.sleep(30)
elif scenario == "SHUTDOWN_HANG":
    emit("MOCK_HEALTHY")
    emit("MOCK_STOP_REQUEST_IGNORED")
    time.sleep(30)
else:
    raise SystemExit(99)
"""


class ExclusiveMockDaemonLease:
    """Tiny filesystem lease used only to rehearse duplicate-start refusal."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.held = False

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            os.write(descriptor, b"OFFLINE_MOCK_ONLY\n")
        finally:
            os.close(descriptor)
        self.held = True

    def release(self) -> None:
        if not self.held:
            raise RuntimeError("Cannot release an unheld mock-daemon lease.")
        self.path.unlink()
        self.held = False


def _events_from_output(output: str | bytes | None) -> list[str]:
    if output is None:
        return []
    if isinstance(output, bytes):
        output = output.decode("utf-8", errors="replace")
    events = []
    for line in output.splitlines():
        try:
            event = json.loads(line).get("event")
        except (json.JSONDecodeError, AttributeError):
            continue
        if isinstance(event, str):
            events.append(event)
    return events


def _require_mock_stopped(process: subprocess.Popen[str], lease: ExclusiveMockDaemonLease) -> None:
    if process.poll() is None or lease.held:
        raise RuntimeError("Stock restoration blocked until the mock process exits and releases its lease.")


def _expectations(scenario: str, returncode: int, timed_out: bool, events: list[str]) -> bool:
    if scenario == "START_FAILURE":
        return returncode == 17 and not timed_out and events == ["MOCK_START_REJECTED"]
    if scenario == "HEALTH_TIMEOUT":
        return timed_out and "MOCK_HEALTHY" not in events
    if scenario == "STATE_STREAM_DISCONNECT":
        return timed_out and {
            "MOCK_HEALTHY",
            "MOCK_STATE_STREAM_DISCONNECTED",
        }.issubset(events)
    if scenario == "SHUTDOWN_HANG":
        return timed_out and {
            "MOCK_HEALTHY",
            "MOCK_STOP_REQUEST_IGNORED",
        }.issubset(events)
    raise ValueError(f"Unknown rehearsal scenario: {scenario}")


def rehearse_scenario(
    scenario: str,
    session_root: Path,
    *,
    timeout_seconds: float = 1.5,
) -> dict[str, Any]:
    """Run one fixed local mock scenario and return a deterministic result."""

    scenario = str(scenario).strip().upper()
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown rehearsal scenario: {scenario}")
    if not 0.1 <= float(timeout_seconds) <= 5.0:
        raise ValueError("timeout_seconds must be between 0.1 and 5.0.")

    lease = ExclusiveMockDaemonLease(Path(session_root) / "mock-daemon.lock")
    lease.acquire()
    duplicate_start_blocked = False
    duplicate = ExclusiveMockDaemonLease(lease.path)
    try:
        duplicate.acquire()
    except FileExistsError:
        duplicate_start_blocked = True
    else:
        duplicate.release()

    process = subprocess.Popen(
        [sys.executable, "-I", "-c", MOCK_WORKER_SOURCE, scenario],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=False,
    )
    timed_out = False
    forced_mock_termination = False
    try:
        stdout, stderr = process.communicate(timeout=float(timeout_seconds))
    except subprocess.TimeoutExpired as timeout:
        timed_out = True
        stdout = timeout.stdout or ""
        stderr = timeout.stderr or ""
        restoration_blocked_while_active = False
        try:
            _require_mock_stopped(process, lease)
        except RuntimeError:
            restoration_blocked_while_active = True
        process.kill()
        forced_mock_termination = True
        final_stdout, final_stderr = process.communicate()
        # TimeoutExpired may already contain the output; avoid double-counting it.
        if final_stdout:
            stdout = final_stdout
        if final_stderr:
            stderr = final_stderr
    else:
        restoration_blocked_while_active = False
        try:
            _require_mock_stopped(process, lease)
        except RuntimeError:
            restoration_blocked_while_active = True

    returncode = int(process.returncode)
    events = _events_from_output(stdout)
    lease.release()
    _require_mock_stopped(process, lease)

    expectations_met = _expectations(scenario, returncode, timed_out, events)
    fails_closed = (
        duplicate_start_blocked
        and restoration_blocked_while_active
        and expectations_met
    )
    return {
        "scenario": scenario,
        "result": "PASS" if fails_closed else "FAIL",
        "events": events,
        "mock_returncode": None if forced_mock_termination else returncode,
        "mock_exit_class": (
            "FORCED_BY_OFFLINE_HARNESS"
            if forced_mock_termination
            else f"EXIT_{returncode}"
        ),
        "mock_timed_out": timed_out,
        "forced_mock_termination": forced_mock_termination,
        "duplicate_start_blocked": duplicate_start_blocked,
        "restoration_blocked_while_mock_active_or_lease_held": restoration_blocked_while_active,
        "mock_process_exit_confirmed": process.poll() is not None,
        "mock_restore_gate_open_after_exit_and_lease_release": True,
        "hardware_restoration_authorized": False,
        "unit_specific_recovery_guidance_still_required": True,
        "stderr_empty": not bool(stderr),
        "mock_processes_started": 1,
        "robot_connections": 0,
        "robot_commands_authorized": 0,
        "robot_commands_sent": 0,
    }


def run_offline_fault_rehearsal(
    session_root: Path,
    *,
    timeout_seconds: float = 1.5,
) -> dict[str, Any]:
    """Run every fixed mock scenario; never authorize a hardware action."""

    root = Path(session_root)
    results = [
        rehearse_scenario(
            scenario,
            root / scenario.lower(),
            timeout_seconds=timeout_seconds,
        )
        for scenario in SCENARIOS
    ]
    passed = all(item["result"] == "PASS" for item in results)
    return {
        "schema": SCHEMA_VERSION,
        "status": "PASS_OFFLINE_MOCK_ONLY" if passed else "FAIL_OFFLINE_MOCK_ONLY",
        "scenarios": results,
        "scenario_count": len(results),
        "all_scenarios_fail_closed": passed,
        "limitations": [
            "Only fixed local Python mock processes were started.",
            "Mock exit and lease release do not prove that a real motor backend released hardware resources or disabled torque.",
            "Forced termination applies only to the mock and is not a recommendation for Reachy.",
            "No stock or temporary Reachy daemon was started or stopped.",
            "External unit-specific recovery guidance remains required before hardware execution.",
        ],
        "robot_connections": 0,
        "robot_commands_authorized": 0,
        "robot_commands_sent": 0,
    }
