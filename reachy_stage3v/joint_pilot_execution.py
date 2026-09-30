"""Content-addressed execution contract for the v2 joint no-motion pilot."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .joint_instrument import JOINT_INSTRUMENT_SPEC_V1
from .joint_pilot_protocol import joint_pilot_protocol_payload


ROOT = Path(__file__).resolve().parents[1]
EXECUTION_MANIFEST = ROOT / "evidence" / "manifests" / "joint_shadow_pilot_execution_v2.json"
EXECUTION_FILES = (
    "reachy_avsync/synchrony.py",
    "reachy_doa/angles.py",
    "reachy_doa/client.py",
    "reachy_doa/models.py",
    "reachy_stage2a/calibration.py",
    "reachy_stage3v/joint_instrument.py",
    "reachy_stage3v/joint_pilot_protocol.py",
    "reachy_stage3v/joint_pilot_analysis.py",
    "reachy_stage3v/joint_pilot_synthetic.py",
    "reachy_stage3v/joint_pilot_execution.py",
    "reachy_stage3v/joint_pilot_private.py",
    "scripts/analyze_joint_shadow_pilot.py",
    "scripts/freeze_joint_shadow_pilot_execution.py",
    "scripts/prepare_joint_shadow_pilot_workspace.py",
    "scripts/run_joint_shadow_instrument.py",
    "tools/joint_pilot_quality.mjs",
    "tools/joint_shadow_recorder.html",
    "models/avsync_v2/face_landmarker.task",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def runtime_bundle(root: Path = ROOT) -> dict[str, Any]:
    runtime = root / "models" / "avsync_v2" / "runtime"
    files = []
    for path in sorted(item for item in runtime.rglob("*") if item.is_file()):
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    encoded = "\n".join(
        f"{item['path']}:{item['bytes']}:{item['sha256']}" for item in files
    ).encode("utf-8")
    return {
        "file_count": len(files),
        "bundle_sha256": hashlib.sha256(encoded).hexdigest(),
        "files": files,
    }


def build_execution_payload(root: Path = ROOT) -> dict[str, Any]:
    files = []
    for relative in EXECUTION_FILES:
        path = root / relative
        files.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    core: dict[str, Any] = {
        "schema": "reachy-joint-shadow-pilot-execution-v2",
        "status": "V2_ANALYSIS_FROZEN_PRIVATE_BINDINGS_REQUIRED",
        "protocol_fingerprint": joint_pilot_protocol_payload()["fingerprint"],
        "instrument_fingerprint": JOINT_INSTRUMENT_SPEC_V1.payload()["fingerprint"],
        "files": files,
        "runtime_bundle": runtime_bundle(root),
        "privacy": {
            "raw_media_saved": False,
            "raw_media_uploaded": False,
            "private_bindings_committed": False,
        },
        "authority": {
            "robot_connections_during_analysis": 0,
            "motion_commands": 0,
            "response_commands": 0,
        },
    }
    encoded = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**core, "fingerprint": hashlib.sha256(encoded).hexdigest()}
