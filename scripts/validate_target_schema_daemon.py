"""Exercise the target-state patch through complete isolated daemon processes.

This is a stronger follow-up to ``validate_target_schema_endpoints.py``.  It
starts two Reachy Mini 1.9.0 daemon application processes from extracted source:

* the released wheel source (negative control), and
* the same source with the repository observability patch applied (positive
  control).

Both processes use the official mockup backend, bind only to loopback, disable
media, dataset downloads, startup apps, and mDNS, and install a socket guard
that rejects non-loopback IPv4/IPv6 traffic.  No robot connection or command is
created by this harness.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "data/private/stage4a_target_schema_daemon_v2/daemon_process_report.json"
)
SCHEMA_VERSION = "reachy-stage4-target-schema-daemon-process-v2"
TARGET_FIELDS = {
    "target_head_pose",
    "target_head_joints",
    "target_body_yaw",
    "target_antennas_position",
}
SOURCE_FILES = (
    "reachy_mini/daemon/app/models.py",
    "reachy_mini/daemon/app/routers/state.py",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_loopback_host(host: object) -> bool:
    if not isinstance(host, str):
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _install_network_guard() -> None:
    """Reject non-loopback INET traffic inside the daemon process."""

    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_sendto = socket.socket.sendto
    original_bind = socket.socket.bind

    def _guard_address(sock: socket.socket, address: object, operation: str) -> None:
        if sock.family not in (socket.AF_INET, socket.AF_INET6):
            return
        if not isinstance(address, tuple) or not address:
            raise OSError(f"NETWORK_GUARD_BLOCKED {operation} malformed address")
        host = address[0]
        if not _is_loopback_host(host):
            raise OSError(f"NETWORK_GUARD_BLOCKED {operation} non-loopback host")

    def guarded_connect(sock: socket.socket, address: object) -> Any:
        _guard_address(sock, address, "connect")
        return original_connect(sock, address)  # type: ignore[arg-type]

    def guarded_connect_ex(sock: socket.socket, address: object) -> int:
        _guard_address(sock, address, "connect_ex")
        return original_connect_ex(sock, address)  # type: ignore[arg-type]

    def guarded_sendto(sock: socket.socket, data: bytes, *args: object) -> int:
        if not args:
            return original_sendto(sock, data)
        address = args[-1]
        _guard_address(sock, address, "sendto")
        return original_sendto(sock, data, *args)  # type: ignore[arg-type]

    def guarded_bind(sock: socket.socket, address: object) -> None:
        _guard_address(sock, address, "bind")
        return original_bind(sock, address)  # type: ignore[arg-type]

    socket.socket.connect = guarded_connect  # type: ignore[method-assign]
    socket.socket.connect_ex = guarded_connect_ex  # type: ignore[method-assign]
    socket.socket.sendto = guarded_sendto  # type: ignore[method-assign]
    socket.socket.bind = guarded_bind  # type: ignore[method-assign]


def _serve(source_root: Path, port: int) -> int:
    """Launch the official daemon app with isolation-only harness controls."""

    source_root = source_root.resolve()
    if not (source_root / "reachy_mini/__init__.py").is_file():
        raise ValueError(f"Not an extracted Reachy Mini source root: {source_root}")
    if not 1024 <= port <= 65535:
        raise ValueError("Port must be between 1024 and 65535.")

    sys.path.insert(0, str(source_root))
    _install_network_guard()

    from reachy_mini.daemon.app import main as daemon_main

    class DisabledMdns:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def register(self) -> None:
            pass

        def unregister(self) -> None:
            pass

    daemon_main.MdnsServiceRegistration = DisabledMdns
    daemon_main.startup_app_config.get_startup_app = lambda: None

    sys.stderr.write(
        "ISOLATION_GUARD active: loopback-only sockets; mDNS/startup-app disabled\n"
    )
    sys.stderr.flush()
    sys.argv = [
        "reachy-mini-daemon",
        "--mockup-sim",
        "--no-media",
        "--fastapi-host",
        "127.0.0.1",
        "--fastapi-port",
        str(port),
        "--dataset-update-interval",
        "0",
        "--no-preload-datasets",
        "--no-goto-sleep-on-stop",
        "--timeout-health-check",
        "4",
        "--robot-name",
        "isolated_target_schema_probe",
    ]
    daemon_main.main()
    return 0


def _request_json(url: str, *, method: str = "GET", timeout: float = 5.0) -> Any:
    request = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"{method} {url} returned HTTP {response.status}")
        return json.loads(response.read().decode("utf-8"))


def _wait_until_ready(process: subprocess.Popen[str], port: int) -> dict[str, Any]:
    deadline = time.monotonic() + 40.0
    status_url = f"http://127.0.0.1:{port}/api/daemon/status"
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            raise RuntimeError(
                f"Daemon exited before readiness ({process.returncode}).\n"
                f"stdout:\n{stdout}\nstderr:\n{stderr}"
            )
        try:
            status = _request_json(status_url, timeout=1.0)
            if status.get("state") == "running":
                return status
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            last_error = exc
        time.sleep(0.1)
    raise TimeoutError(f"Daemon did not become ready: {last_error}")


def _target_keys(payload: dict[str, Any]) -> list[str]:
    return sorted(set(payload) & TARGET_FIELDS)


def _probe_websocket(port: int, query: dict[str, str]) -> dict[str, Any]:
    from websockets.sync.client import connect

    url = f"ws://127.0.0.1:{port}/api/state/ws/full?{urllib.parse.urlencode(query)}"
    with connect(url, open_timeout=5.0, close_timeout=2.0) as websocket:
        payload = json.loads(websocket.recv(timeout=5.0))
    return {
        "target_fields_present": _target_keys(payload),
        "target_head_pose": payload.get("target_head_pose"),
    }


def _run_one(source_root: Path, port: int) -> dict[str, Any]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--serve",
        "--source-root",
        str(source_root.resolve()),
        "--port",
        str(port),
    ]
    environment = os.environ.copy()
    environment["PYTHONNOUSERSITE"] = "1"
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )
    try:
        status = _wait_until_ready(process, port)
        if status.get("mockup_sim_enabled") is not True:
            raise AssertionError(f"Daemon did not report mockup mode: {status}")
        if status.get("simulation_enabled") is not False:
            raise AssertionError(f"Unexpected MuJoCo simulation state: {status}")

        _request_json(f"http://127.0.0.1:{port}/health-check", method="POST")
        query = {
            "with_target_head_pose": "true",
            "with_target_head_joints": "true",
            "with_target_body_yaw": "true",
            "with_target_antenna_positions": "true",
        }
        rest: dict[str, Any] = {}
        for representation, use_matrix in (("matrix", True), ("xyz_rpy", False)):
            request_query = {**query, "use_pose_matrix": str(use_matrix).lower()}
            url = (
                f"http://127.0.0.1:{port}/api/state/full?"
                f"{urllib.parse.urlencode(request_query)}"
            )
            payload = _request_json(url)
            rest[representation] = {
                "target_fields_present": _target_keys(payload),
                "target_head_pose": payload.get("target_head_pose"),
            }
        websocket = _probe_websocket(port, {**query, "use_pose_matrix": "true"})

        try:
            stdout, stderr = process.communicate(timeout=8.0)
        except subprocess.TimeoutExpired:
            process.terminate()
            stdout, stderr = process.communicate(timeout=5.0)
            raise RuntimeError("Daemon did not stop through its health-check timeout.")

        blocked = [line for line in stderr.splitlines() if "NETWORK_GUARD_BLOCKED" in line]
        if blocked:
            raise AssertionError(f"Daemon attempted non-loopback traffic: {blocked}")
        if process.returncode != 0:
            raise RuntimeError(
                f"Daemon exited with {process.returncode}.\nstdout:\n{stdout}\nstderr:\n{stderr}"
            )
        return {
            "source_root": str(source_root.resolve()),
            "port": port,
            "daemon_status": status,
            "rest": rest,
            "websocket": websocket,
            "isolation": {
                "bind_host": "127.0.0.1",
                "mockup_sim": True,
                "media_disabled": True,
                "mdns_disabled": True,
                "startup_app_disabled": True,
                "dataset_updates_disabled": True,
                "non_loopback_attempts_blocked_or_observed": len(blocked),
            },
            "shutdown": "graceful_health_check_timeout",
            "process_exit_code": process.returncode,
            "log_tail": stderr.splitlines()[-30:],
            "robot_connections": 0,
            "robot_commands_sent": 0,
        }
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5.0)


def _all_surfaces(result: dict[str, Any]) -> list[list[str]]:
    return [
        result["rest"]["matrix"]["target_fields_present"],
        result["rest"]["xyz_rpy"]["target_fields_present"],
        result["websocket"]["target_fields_present"],
    ]


def _verify_provenance(
    wheel: Path,
    patch: Path,
    released_source: Path,
    patched_source: Path,
) -> dict[str, Any]:
    """Bind the extracted controls to the exact wheel and patch artifacts."""

    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        metadata_name = next(
            (name for name in names if name.endswith(".dist-info/METADATA")), None
        )
        if metadata_name is None:
            raise ValueError("Wheel has no METADATA file.")
        metadata = archive.read(metadata_name).decode("utf-8")
        version_line = next(
            (line for line in metadata.splitlines() if line.startswith("Version: ")),
            None,
        )
        if version_line is None:
            raise ValueError("Wheel METADATA has no version.")
        version = version_line.partition(":")[2].strip()
        if version != "1.9.0":
            raise ValueError(f"Expected Reachy Mini 1.9.0 wheel, received {version}.")
        for relative in SOURCE_FILES:
            if relative not in names:
                raise ValueError(f"Wheel is missing {relative}.")
            extracted = (released_source / relative).read_bytes()
            if extracted != archive.read(relative):
                raise AssertionError(f"Released source differs from wheel member: {relative}")

    reverse_check = subprocess.run(
        [
            "git",
            "-C",
            str(patched_source),
            "apply",
            "-p2",
            "--reverse",
            "--check",
            str(patch.resolve()),
        ],
        capture_output=True,
        text=True,
    )
    if reverse_check.returncode != 0:
        raise AssertionError(
            "Patched source does not reverse-check against the supplied patch:\n"
            f"{reverse_check.stderr}"
        )
    return {
        "wheel_version": version,
        "wheel_sha256": _sha256(wheel),
        "patch_sha256": _sha256(patch),
        "released_files_match_wheel_byte_for_byte": True,
        "patched_tree_reverse_checks_against_patch": True,
    }


def _write_immutable_report(report: dict[str, Any], output: Path) -> str:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    sidecar = output.with_suffix(output.suffix + ".sha256")
    with output.open("xb") as stream:
        stream.write(payload)
    try:
        with sidecar.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(f"{digest}  {output.name}\n")
    except Exception:
        output.unlink(missing_ok=True)
        raise
    return digest


def validate(
    released_source: Path,
    patched_source: Path,
    wheel: Path,
    patch: Path,
    output: Path,
    base_port: int,
) -> tuple[dict[str, Any], str]:
    for source in (released_source, patched_source):
        for relative in SOURCE_FILES:
            if not (source / relative).is_file():
                raise FileNotFoundError(source / relative)

    provenance = _verify_provenance(wheel, patch, released_source, patched_source)
    released = _run_one(released_source, base_port)
    patched = _run_one(patched_source, base_port + 1)
    expected = sorted(TARGET_FIELDS)
    if any(fields for fields in _all_surfaces(released)):
        raise AssertionError("Released negative control unexpectedly retained target fields.")
    if any(fields != expected for fields in _all_surfaces(patched)):
        raise AssertionError("Patched daemon did not retain all target fields.")

    report = {
        "schema": SCHEMA_VERSION,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "provenance": provenance,
        "source_hashes": {
            "released": {
                relative: _sha256(released_source / relative) for relative in SOURCE_FILES
            },
            "patched": {
                relative: _sha256(patched_source / relative) for relative in SOURCE_FILES
            },
        },
        "surfaces_tested": ["REST matrix", "REST xyz/RPY", "WebSocket matrix"],
        "released_negative_control": released,
        "patched_positive_control": patched,
        "diagnostic_status": (
            "TARGET_FIELDS_DROPPED_BY_RELEASED_FULL_DAEMON_AND_PRESERVED_BY_PATCHED_FULL_DAEMON"
        ),
        "claim_boundary": (
            "This validates complete daemon application processes with the official "
            "1.9.0 mockup backend under a loopback-only isolation harness. It is not "
            "deployment to the robot, observation of physical runtime targets, unit "
            "confirmation, calibration repair, or motion authorization."
        ),
        "robot_connections": 0,
        "robot_commands_sent": 0,
        "robot_commands_authorized": 0,
    }
    return report, _write_immutable_report(report, output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--released-source", type=Path)
    parser.add_argument("--patched-source", type=Path)
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--patch", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--base-port", type=int, default=18790)
    parser.add_argument("--serve", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--source-root", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.serve:
        if args.source_root is None or args.port is None:
            parser.error("--serve requires --source-root and --port")
        return _serve(args.source_root, args.port)
    if (
        args.released_source is None
        or args.patched_source is None
        or args.wheel is None
        or args.patch is None
    ):
        parser.error(
            "--released-source, --patched-source, --wheel, and --patch are required"
        )

    report, digest = validate(
        args.released_source.resolve(),
        args.patched_source.resolve(),
        args.wheel.resolve(),
        args.patch.resolve(),
        args.output,
        args.base_port,
    )
    print(f"Daemon process report: {args.output.resolve()}")
    print(f"SHA-256: {digest}")
    print(f"Status: {report['diagnostic_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
