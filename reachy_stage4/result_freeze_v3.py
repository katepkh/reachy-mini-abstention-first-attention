"""Integrity freeze for the failed Stage 4A V3 mechanical diagnostic."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from .config import PROJECT_ROOT


FREEZE_PATH = (
    PROJECT_ROOT / "data/manifests/stage4a_supervised_motion_pilot_v3_diagnostic_freeze.json"
).resolve()
COLLECTION_DIR = (PROJECT_ROOT / "data/stage4a_supervised_motion_pilot_v3").resolve()
PROTOCOL_PATH = (
    PROJECT_ROOT / "data/manifests/stage4a_supervised_motion_pilot_v3.json"
).resolve()
EXPECTED_PROTOCOL_FINGERPRINT = (
    "0f9b1e8d076cf3ce6a3d4ca138aa8f07a691fae98543e9ad02db545c021f52af"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path) -> str:
    resolved = path.resolve()
    if not resolved.is_relative_to(PROJECT_ROOT):
        raise ValueError(f"Stage 4A V3 freeze path escaped the project: {resolved}")
    return resolved.relative_to(PROJECT_ROOT).as_posix()


def result_files() -> tuple[Path, ...]:
    collection = tuple(sorted(
        (path.resolve() for path in COLLECTION_DIR.rglob("*") if path.is_file()),
        key=_relative,
    ))
    return tuple(sorted((*collection, PROTOCOL_PATH), key=_relative))


def _bundle_hash(records: Iterable[dict[str, Any]]) -> str:
    canonical = json.dumps(list(records), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def _verify_signed(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected = str(payload.get("integrity_sha256") or "")
    body = {key: value for key, value in payload.items() if key != "integrity_sha256"}
    observed = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if not expected or expected != observed:
        raise ValueError(f"Stage 4A V3 signed record changed: {path.name}")
    return body


def _project(rotation: Any) -> np.ndarray:
    u, _, vt = np.linalg.svd(np.asarray(rotation, dtype=np.float64))
    projected = u @ vt
    if np.linalg.det(projected) < 0:
        u[:, -1] *= -1.0
        projected = u @ vt
    return projected


def _distance(first: Any, second: Any) -> float:
    a = _project(np.asarray(first, dtype=np.float64)[:3, :3])
    b = _project(np.asarray(second, dtype=np.float64)[:3, :3])
    cosine = float(np.clip((np.trace(a.T @ b) - 1.0) / 2.0, -1.0, 1.0))
    return math.degrees(math.acos(cosine))


def _validated_state() -> dict[str, Any]:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    if protocol.get("fingerprint") != EXPECTED_PROTOCOL_FINGERPRINT:
        raise ValueError("Stage 4A V3 protocol fingerprint changed.")
    sessions = COLLECTION_DIR / "sessions"
    preflights = sorted(sessions.glob("*_preflight.json"))
    results = sorted(sessions.glob("*_result.json"))
    consumed = sorted(sessions.glob("*.consumed"))
    if (len(preflights), len(results), len(consumed)) != (4, 2, 2):
        raise ValueError("Stage 4A V3 diagnostic attempt counts changed.")
    preflight_by_id = {
        item["session_id"]: item for item in (_verify_signed(path) for path in preflights)
    }
    result_items = [_verify_signed(path) for path in results]
    commanded = [item for item in result_items if item.get("actuation_commands") == 2]
    blocked = [item for item in result_items if item.get("actuation_commands") == 0]
    if len(commanded) != 1 or len(blocked) != 1:
        raise ValueError("Stage 4A V3 commanded/blocked result split changed.")
    trial = commanded[0]
    baseline = preflight_by_id[trial["session_id"]]["baseline_pose"]
    target = trial["target_measured_pose"]
    restored = trial["restored_measured_pose"]
    if trial.get("mechanical_gate_passed") is not False or trial.get("operator_review") != "NOT_ELIGIBLE":
        raise ValueError("The failed V3 trial disposition changed.")
    if blocked[0].get("mechanical_gate_passed") is not False or blocked[0].get("failure") != "RuntimeError: Computed target escaped the 3° envelope: 1.71°.":
        raise ValueError("The zero-command V3 block changed.")
    if any(int(item.get(key) or 0) for item in result_items for key in (
        "body_yaw_commands", "antenna_commands", "torque_or_motor_mode_commands",
        "media_access", "cloud_requests",
    )):
        raise ValueError("Stage 4A V3 exceeded the head-only local boundary.")
    robust_return = _distance(restored, baseline)
    if not 1.67 <= robust_return <= 1.69:
        raise ValueError("The robust V3 return diagnostic changed.")
    return {
        "read_only_preflights": len(preflights),
        "consumed_preflights": len(consumed),
        "result_records": len(results),
        "physical_motion_trials": 1,
        "zero_command_execution_blocks": 1,
        "total_head_only_commands": sum(int(item.get("head_only_commands") or 0) for item in result_items),
        "total_body_yaw_commands": 0,
        "total_antenna_commands": 0,
        "total_torque_or_motor_mode_commands": 0,
        "commanded_trial_mechanical_gate_passed": False,
        "legacy_saved_target_error_deg": trial["target_error_deg"],
        "legacy_saved_return_error_deg": trial["restore_error_deg"],
        "robust_measured_motion_from_baseline_deg": _distance(target, baseline),
        "robust_target_to_requested_target_error_deg": 2.0794591418416877,
        "robust_return_to_baseline_error_deg": robust_return,
        "root_causes": [
            "target pose sampled before the frozen settling dwell",
            "return pose sampled with no settling dwell",
            "trace angle applied directly to slightly non-orthonormal FK matrices",
            "absolute-neutral target did not guarantee a 3 degree increment from the captured baseline",
        ],
        "thresholds_weakened_after_outcome": False,
        "failed_attempt_deleted_or_relabelled": False,
    }


def build_result_freeze() -> dict[str, Any]:
    state = _validated_state()
    records = [
        {"path": _relative(path), "bytes": path.stat().st_size, "sha256": _sha256(path)}
        for path in result_files()
    ]
    return {
        "schema": "reachy-stage4a-v3-failed-mechanical-diagnostic-freeze-v1",
        "status": "FROZEN_FAILED_RESULT_SUPERSEDED_WITHOUT_RELABEL_OR_DELETION",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "protocol_fingerprint": EXPECTED_PROTOCOL_FINGERPRINT,
        "validated_state": state,
        "file_count": len(records),
        "files": records,
        "bundle_sha256": _bundle_hash(records),
        "scientific_boundary": {
            "v3_may_not_be_accepted": True,
            "v3_may_not_be_retried_under_the_same_protocol": True,
            "corrected_protocol_must_be_versioned_and_frozen": True,
            "no_acceptance_threshold_may_be_weakened": True,
        },
    }


def write_result_freeze(path: Path = FREEZE_PATH) -> dict[str, Any]:
    if path.exists():
        raise FileExistsError(f"Stage 4A V3 diagnostic is already frozen: {path}")
    payload = build_result_freeze()
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def verify_result_freeze(path: Path = FREEZE_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = []
    failures = []
    for frozen in payload.get("files") or []:
        artifact = (PROJECT_ROOT / frozen["path"]).resolve()
        if not artifact.is_relative_to(PROJECT_ROOT) or not artifact.is_file():
            failures.append(f"missing:{frozen['path']}")
            continue
        current = {"path": frozen["path"], "bytes": artifact.stat().st_size, "sha256": _sha256(artifact)}
        records.append(current)
        if current != frozen:
            failures.append(f"changed:{frozen['path']}")
    expected = {item["path"] for item in payload.get("files") or []}
    actual = {_relative(item) for item in result_files()}
    failures.extend(f"added:{item}" for item in sorted(actual - expected))
    if not failures and _bundle_hash(records) != payload.get("bundle_sha256"):
        failures.append("bundle-hash-mismatch")
    if failures:
        raise ValueError("Stage 4A V3 diagnostic freeze failed: " + ", ".join(failures))
    return {
        "verified": True,
        "file_count": len(records),
        "bundle_sha256": payload["bundle_sha256"],
        "mechanical_gate_passed": payload["validated_state"]["commanded_trial_mechanical_gate_passed"],
    }
