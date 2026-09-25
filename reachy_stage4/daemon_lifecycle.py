"""Pure construction of the proposed state-only temporary-daemon launch plan.

Nothing in this module starts a process, opens a socket, connects to a robot, or
authorizes a command.  The returned command is review material only.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any


SCHEMA_VERSION = "reachy-stage4a-observation-daemon-plan-v2"
SHUTDOWN_SCHEMA_VERSION = "reachy-stage4a-observation-shutdown-plan-v1"
STATUS_DESIGN_ONLY = "DESIGN_ONLY_DO_NOT_LAUNCH"
DEFAULT_SERIAL_PORT = "/dev/ttyAMA3"
DEFAULT_BIND_HOST = "127.0.0.1"
MOTOR_MODES = {"DISABLED", "ENABLED", "UNKNOWN"}


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
            "stock shutdown reports motor control disabled before its process exits",
            "temporary checkout, caches, log, and PID locations enumerated",
            "a clear drop zone is maintained beneath and around the Stewart platform",
            "the physical power control is immediately accessible",
            "operator and robot remain physically clear",
        ],
        "runtime_acceptance": [
            "API bound only to 127.0.0.1",
            "daemon reports running with media disabled",
            "motor control reports disabled before trace capture",
            "no startup app, mDNS advertisement, dataset update, wake, or sleep motion",
            "zero experimental application-level robot commands",
            "bounded 60-second health-check lifetime",
        ],
        "limitations": [
            "the lifecycle patch suppresses reflash_motors_if_needed only",
            "motor-controller 1.5.5 may still reboot a motor with a pre-existing non-voltage hardware error during controller construction",
            "with sleep-on-stop suppressed, graceful close does not itself send or prove motor disable",
            "one explicit safety-disable action is contingent on fresh responsive telemetry reporting motors enabled",
            "unresponsive or ambiguous state takes the predeclared physical-power-off branch; no replacement daemon is started",
            "this plan is not an executor and does not establish physical safety",
        ],
        "robot_connections": 0,
        "robot_commands_authorized": 0,
        "robot_commands_sent": 0,
    }


def plan_observation_shutdown(
    *,
    daemon_responsive: bool,
    telemetry_fresh: bool,
    motor_mode: str,
) -> dict[str, Any]:
    """Return the fail-closed terminal branch without performing it.

    ``motor_mode`` must be the fresh reported mode, not an expectation inferred
    from how the stock daemon was stopped.  The function deliberately keeps a
    safety-only disable distinct from an experimental command.
    """

    mode = str(motor_mode).strip().upper()
    if mode not in MOTOR_MODES:
        raise ValueError(f"Unknown motor mode: {motor_mode}")

    if not daemon_responsive or not telemetry_fresh or mode == "UNKNOWN":
        branch = "PHYSICAL_POWER_OFF"
        action = (
            "STAY_CLEAR_USE_PREAPPROVED_PHYSICAL_POWER_OFF_"
            "EXPECT_PASSIVE_PLATFORM_DROP"
        )
        safety_disable_actions_planned = 0
        stop_process_after_disable = False
        verification = [
            "do not start or reconnect another daemon",
            "keep the Stewart-platform drop zone clear",
            "use the preapproved physical power-off procedure",
            "confirm power is off and the mechanism is stable before inspection",
            "preserve logs and record the last fresh state separately",
        ]
    elif mode == "ENABLED":
        branch = "SAFETY_DISABLE_THEN_STOP"
        action = "ISSUE_ONE_SAFETY_DISABLE_VERIFY_DISABLED_THEN_STOP"
        safety_disable_actions_planned = 1
        stop_process_after_disable = True
        verification = [
            "issue only the predeclared motor-disable safety action",
            "obtain a fresh motor-control report of disabled",
            "stop the temporary daemon without sleep motion",
            "confirm temporary process exit and serial-resource release",
            "preserve logs and the terminal state record",
        ]
    else:
        branch = "ALREADY_DISABLED_STOP"
        action = "STOP_TEMPORARY_DAEMON_VERIFY_EXIT_AND_SERIAL_RELEASE"
        safety_disable_actions_planned = 0
        stop_process_after_disable = True
        verification = [
            "preserve the fresh motor-control report of disabled",
            "stop the temporary daemon without sleep motion",
            "confirm temporary process exit and serial-resource release",
            "preserve logs and the terminal state record",
        ]

    return {
        "schema": SHUTDOWN_SCHEMA_VERSION,
        "status": "DESIGN_ONLY_NO_COMMAND_AUTHORITY",
        "branch": branch,
        "action": action,
        "motor_mode": mode,
        "daemon_responsive": bool(daemon_responsive),
        "telemetry_fresh": bool(telemetry_fresh),
        "verification": verification,
        "automatic_return": False,
        "replacement_daemon_before_terminal_verification": False,
        "stop_process_after_disable": stop_process_after_disable,
        "safety_disable_actions_planned": safety_disable_actions_planned,
        "experimental_commands_planned": 0,
        "robot_connections": 0,
        "robot_commands_authorized": 0,
        "robot_commands_sent": 0,
    }


def stock_restart_acceptance() -> dict[str, Any]:
    """Describe the evidence gate for restoring the untouched stock daemon."""

    return {
        "schema": "reachy-stage4a-stock-restart-acceptance-v1",
        "status": "DESIGN_ONLY_NO_RESTART_AUTHORITY",
        "preconditions": [
            "temporary process is confirmed exited",
            "temporary process no longer owns the serial resource",
            "robot is physically stable and visually unchanged",
            "any physical-power-off branch has completed before power restoration",
            "temporary checkout, caches, logs, and PID paths are preserved for review",
        ],
        "acceptance": [
            "exact stock service and version are restored",
            "only one daemon owns the motor bus",
            "expected motor inventory is present",
            "daemon and controller report no hardware error",
            "motor-control mode and posture are recorded before any optional wake or motion",
            "baseline configuration and persistent-surface inventory show no unexplained change",
        ],
        "automatic_motion_authorized": False,
        "robot_connections": 0,
        "robot_commands_authorized": 0,
        "robot_commands_sent": 0,
    }
