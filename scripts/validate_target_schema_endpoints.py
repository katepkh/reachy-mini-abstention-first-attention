"""Validate the target-state schema patch against extracted Reachy Mini 1.9.0 routes.

The public mode extracts two files from a supplied official wheel, runs a
negative control against the released schema, applies the repository patch to a
second copy, and exercises the real `/state/full` and `/state/ws/full` route
functions through FastAPI TestClient. The private probe mode is used only in a
fresh subprocess so the clean and patched modules cannot contaminate each
other. No SDK client, daemon process, network socket, or robot command is used.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import types
import zipfile
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATCH = PROJECT_ROOT / "patches/reachy-mini-v1.9.0-target-state-observability.patch"
DEFAULT_OUTPUT = PROJECT_ROOT / "data/private/stage4a_target_schema_integration_v1/report.json"
SCHEMA_VERSION = "reachy-stage4-target-schema-endpoint-integration-v1"
TARGET_FIELDS = {
    "target_head_pose",
    "target_head_joints",
    "target_body_yaw",
    "target_antennas_position",
}
WHEEL_MEMBERS = (
    "reachy_mini/daemon/app/models.py",
    "reachy_mini/daemon/app/routers/state.py",
)


def _load_module(name: str, path: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _install_package_stub(name: str) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__path__ = []  # type: ignore[attr-defined]
    sys.modules[name] = module
    return module


def _probe_extracted_source(source_root: Path) -> dict[str, Any]:
    """Exercise the extracted models and routes in an isolated interpreter."""

    import numpy as np
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    class MotorControlMode(Enum):
        Disabled = "disabled"
        Enabled = "enabled"

    for package in (
        "reachy_mini",
        "reachy_mini.io",
        "reachy_mini.daemon",
        "reachy_mini.daemon.backend",
        "reachy_mini.daemon.app",
        "reachy_mini.daemon.app.routers",
    ):
        _install_package_stub(package)

    protocol = types.ModuleType("reachy_mini.io.protocol")
    protocol.MotorControlMode = MotorControlMode
    sys.modules[protocol.__name__] = protocol

    backend_module = types.ModuleType("reachy_mini.daemon.backend.abstract")
    backend_module.Backend = object
    sys.modules[backend_module.__name__] = backend_module

    def missing_backend() -> None:
        raise RuntimeError("The integration probe must override this dependency.")

    dependencies = types.ModuleType("reachy_mini.daemon.app.dependencies")
    dependencies.get_backend = missing_backend
    dependencies.ws_get_backend = missing_backend
    sys.modules[dependencies.__name__] = dependencies

    models = _load_module(
        "reachy_mini.daemon.app.models",
        source_root / "src/reachy_mini/daemon/app/models.py",
    )
    state = _load_module(
        "reachy_mini.daemon.app.routers.state",
        source_root / "src/reachy_mini/daemon/app/routers/state.py",
    )

    class OneShotReady:
        def __init__(self) -> None:
            self.remaining = 1

        def is_set(self) -> bool:
            if self.remaining > 0:
                self.remaining -= 1
                return True
            return False

    class StubBackend:
        def __init__(self) -> None:
            self.ready = OneShotReady()
            self.doa = None
            self.target_head_pose = np.eye(4)
            self.target_head_joint_positions = np.arange(7, dtype=float) / 10.0
            self.target_body_yaw = 0.2
            self.target_antenna_joint_positions = np.array([-0.2, 0.2])

        def get_motor_control_mode(self) -> MotorControlMode:
            return MotorControlMode.Enabled

        def get_present_head_pose(self) -> Any:
            return np.eye(4)

        def get_present_head_joint_positions(self) -> Any:
            return np.zeros(7)

        def get_present_body_yaw(self) -> float:
            return 0.0

        def get_present_antenna_joint_positions(self) -> Any:
            return np.array([-0.1, 0.1])

    app = FastAPI()
    app.include_router(state.router)
    client = TestClient(app)

    query = {
        "with_target_head_pose": "true",
        "with_target_head_joints": "true",
        "with_target_body_yaw": "true",
        "with_target_antenna_positions": "true",
    }

    def target_keys(value: dict[str, Any]) -> list[str]:
        return sorted(set(value) & TARGET_FIELDS)

    rest_results: dict[str, Any] = {}
    for representation, use_matrix in (("matrix", True), ("xyz_rpy", False)):
        backend = StubBackend()
        app.dependency_overrides[dependencies.get_backend] = lambda backend=backend: backend
        response = client.get(
            "/state/full", params={**query, "use_pose_matrix": str(use_matrix).lower()}
        )
        if response.status_code != 200:
            raise RuntimeError(f"REST probe failed: {response.status_code} {response.text}")
        payload = response.json()
        rest_results[representation] = {
            "target_fields_present": target_keys(payload),
            "target_head_pose": payload.get("target_head_pose"),
        }

    ws_backend = StubBackend()
    app.dependency_overrides[dependencies.ws_get_backend] = lambda: ws_backend
    ws_query = "&".join(f"{key}={value}" for key, value in {**query, "use_pose_matrix": "true"}.items())
    with client.websocket_connect(f"/state/ws/full?{ws_query}") as websocket:
        websocket_payload = websocket.receive_json()

    return {
        "full_state_model_module": str(Path(models.__file__).resolve()),
        "rest": rest_results,
        "websocket": {
            "target_fields_present": target_keys(websocket_payload),
            "target_head_pose": websocket_payload.get("target_head_pose"),
        },
        "robot_commands_sent": 0,
    }


def _extract_source(wheel: Path, destination: Path) -> str:
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        missing = set(WHEEL_MEMBERS) - names
        if missing:
            raise ValueError(f"Wheel is missing required members: {sorted(missing)}")
        metadata_name = next(
            (name for name in names if name.endswith(".dist-info/METADATA")), None
        )
        if metadata_name is None:
            raise ValueError("Wheel has no METADATA file.")
        metadata = archive.read(metadata_name).decode("utf-8")
        version_line = next(
            (line for line in metadata.splitlines() if line.startswith("Version: ")), None
        )
        if version_line is None:
            raise ValueError("Wheel METADATA has no version.")
        version = version_line.partition(":")[2].strip()
        for member in WHEEL_MEMBERS:
            target = destination / "src" / member
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(member))
    return version


def _run_subprocess_probe(source_root: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--probe-source", str(source_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _write_immutable_report(report: dict[str, Any], output: Path) -> str:
    path = output.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    sidecar = path.with_suffix(path.suffix + ".sha256")
    with path.open("xb") as stream:
        stream.write(payload)
    try:
        with sidecar.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(f"{digest}  {path.name}\n")
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return digest


def _all_target_surfaces(result: dict[str, Any]) -> list[list[str]]:
    return [
        result["rest"]["matrix"]["target_fields_present"],
        result["rest"]["xyz_rpy"]["target_fields_present"],
        result["websocket"]["target_fields_present"],
    ]


def validate(wheel: Path, patch: Path, output: Path) -> tuple[dict[str, Any], str]:
    wheel_payload = wheel.read_bytes()
    patch_payload = patch.read_bytes()
    with tempfile.TemporaryDirectory(prefix="reachy-target-schema-") as directory:
        root = Path(directory)
        released = root / "released"
        patched = root / "patched"
        version = _extract_source(wheel, released)
        if version != "1.9.0":
            raise ValueError(f"Expected Reachy Mini 1.9.0 wheel, received {version}.")
        shutil.copytree(released, patched)
        subprocess.run(
            ["git", "-C", str(patched), "apply", "--check", str(patch.resolve())],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "-C", str(patched), "apply", str(patch.resolve())],
            check=True,
            capture_output=True,
            text=True,
        )
        released_result = _run_subprocess_probe(released)
        patched_result = _run_subprocess_probe(patched)

    empty = []
    expected = sorted(TARGET_FIELDS)
    if any(fields != empty for fields in _all_target_surfaces(released_result)):
        raise AssertionError("Negative control unexpectedly retained target fields.")
    if any(fields != expected for fields in _all_target_surfaces(patched_result)):
        raise AssertionError("Patched source did not retain all target fields.")

    report = {
        "schema": SCHEMA_VERSION,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "wheel_version": version,
        "wheel_sha256": hashlib.sha256(wheel_payload).hexdigest(),
        "patch_sha256": hashlib.sha256(patch_payload).hexdigest(),
        "surfaces_tested": ["REST matrix", "REST xyz/RPY", "WebSocket matrix"],
        "released_negative_control": released_result,
        "patched_positive_control": patched_result,
        "diagnostic_status": "TARGET_FIELDS_DROPPED_RELEASED_AND_PRESERVED_PATCHED",
        "claim_boundary": (
            "This validates endpoint serialization against extracted 1.9.0 source with "
            "a non-hardware stub backend. It is not a daemon-on-robot test, deployment, "
            "runtime target observation, or motion authorization."
        ),
        "robot_connections": 0,
        "robot_commands_sent": 0,
        "robot_commands_authorized": 0,
    }
    digest = _write_immutable_report(report, output)
    return report, digest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--patch", type=Path, default=DEFAULT_PATCH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--probe-source", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.probe_source is not None:
        print(json.dumps(_probe_extracted_source(args.probe_source), sort_keys=True))
        return 0
    if args.wheel is None:
        parser.error("--wheel is required.")

    report, digest = validate(args.wheel, args.patch, args.output)
    print(f"Target schema endpoint report: {args.output.resolve()}")
    print(f"SHA-256: {digest}")
    print(f"Status: {report['diagnostic_status']}")
    print("Robot connections: 0; robot commands sent: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
