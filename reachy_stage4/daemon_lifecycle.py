"""Pure construction of the proposed state-only temporary-daemon launch plan.

Nothing in this module starts a process, opens a socket, connects to a robot, or
authorizes a command.  The returned command is review material only.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any


SCHEMA_VERSION = "reachy-stage4a-observation-daemon-plan-v1"
STATUS_DESIGN_ONLY = "DESIGN_ONLY_DO_NOT_LAUNCH"
DEFAULT_SERIAL_PORT = "/dev/ttyAMA3"
DEFAULT_BIND_HOST = "127.0.0.1"


def _absolute_posix_path(value: str, name: str) -> str:
    text = str(value).strip()
    path = PurePosixPath(text)
    if not text or not path.is_absolute() or "\n" in text or "\r" in text:
        raise ValueError(f"{name} must be an absolute POSIX path.")
    return str(path)


def build_observation_daemon_plan(
    checkout_root: str,
    session_root: str,
    *,
    serial_port: str = DEFAULT_SERIAL_PORT,
    port: int = 8000,
) -> dict[str, Any]:
    """Return the exact proposed invocation without executing it."""

    checkout = PurePosixPath(_absolute_posix_path(checkout_root, "checkout_root"))
    session = PurePosixPath(_absolute_posix_path(session_root, "session_root"))
    serial = _absolute_posix_path(serial_port, "serial_port")
    if not 1024 <= int(port) <= 65535:
        raise ValueError("port must be between 1024 and 65535.")

    command = [
        str(checkout / ".venv/bin/reachy-mini-daemon"),
        "--serialport",
        serial,
        "--hardware-config-filepath",
        str(checkout / "src/reachy_mini/assets/config/hardware_config.yaml"),
        "--no-media",
        "--no-wake-up-on-start",
        "--no-goto-sleep-on-stop",
        "--no-reflash-motors-on-start",
        "--no-startup-app",
        "--no-mdns",
        "--no-preload-datasets",
        "--dataset-update-interval",
        "0",
        "--fastapi-host",
        DEFAULT_BIND_HOST,
        "--fastapi-port",
        str(int(port)),
        "--timeout-health-check",
        "60",
        "--log-file",
        str(session / "temporary-daemon.log"),
    ]
    if "--wireless-version" in command:
        raise AssertionError("The state-only plan must bypass Wireless maintenance hooks.")

    return {
        "schema": SCHEMA_VERSION,
        "status": STATUS_DESIGN_ONLY,
        "command": command,
        "environment": {
            "PYTHONNOUSERSITE": "1",
            "UV_CACHE_DIR": str(session / "uv-cache"),
            "XDG_CACHE_HOME": str(session / "xdg-cache"),
        },
        "required_patches": [
            "patches/reachy-mini-v1.9.0-target-state-observability.patch",
            "patches/reachy-mini-v1.9.0-observation-lifecycle.patch",
        ],
        "preconditions": [
            "exact v1.9.0 source and both patch bytes verified",
            "baseline inventory complete before stopping the stock service",
            "stock daemon reports no hardware error before shutdown",
            "stock shutdown reaches its torque-disable path without an error; post-close torque is not independently measured",
            "temporary checkout, caches, log, and PID locations enumerated",
            "operator and robot remain physically clear",
        ],
        "runtime_acceptance": [
            "API bound only to 127.0.0.1",
            "daemon reports running with media disabled",
            "motor control reports disabled before trace capture",
            "no startup app, mDNS advertisement, dataset update, wake, or sleep motion",
            "zero application-level robot commands",
            "bounded 60-second health-check lifetime",
        ],
        "limitations": [
            "the lifecycle patch suppresses reflash_motors_if_needed only",
            "motor-controller 1.5.5 may still reboot a motor with a pre-existing non-voltage hardware error during controller construction",
            "graceful close does not itself prove that torque was disabled",
            "this plan is not an executor and does not establish physical safety",
        ],
        "robot_connections": 0,
        "robot_commands_authorized": 0,
        "robot_commands_sent": 0,
    }
