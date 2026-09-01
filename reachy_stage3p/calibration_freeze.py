"""Integrity freeze for the completed passive Stage 3P calibration pilot."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from reachy_stage2a.config import PROJECT_ROOT


FREEZE_PATH = (
    PROJECT_ROOT / "data/manifests/stage3p_calibration_result_v1_freeze.json"
).resolve()
COLLECTION_DIR = (PROJECT_ROOT / "data/stage3p_calibration").resolve()
AUDIT_INDEX = (PROJECT_ROOT / "data/stage3p_calibration_audit/audit_index.json").resolve()
RESULT_JSON = (PROJECT_ROOT / "data/analysis/stage3p_calibration_pilot_v1.json").resolve()
RESULT_ARTIFACTS = (
    RESULT_JSON,
    (PROJECT_ROOT / "data/analysis/stage3p_calibration_pilot_v1_trials.csv").resolve(),
    (PROJECT_ROOT / "data/analysis/stage3p_calibration_pilot_v1.md").resolve(),
    (PROJECT_ROOT / "data/manifests/stage3p_calibration_pilot_v1.json").resolve(),
    AUDIT_INDEX,
)
EXPECTED_PROTOCOL_FINGERPRINT = (
    "f6d0f15e352740b8f1d3c7e25a96e81f060b757246817b813c23d439615cf3a8"
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
        raise ValueError(f"Freeze path escaped the project: {resolved}")
    return resolved.relative_to(PROJECT_ROOT).as_posix()


def calibration_result_files() -> tuple[Path, ...]:
    collection = tuple(
        sorted(path.resolve() for path in COLLECTION_DIR.rglob("*") if path.is_file())
    )
    return tuple(sorted({*collection, *RESULT_ARTIFACTS}, key=_relative))


def _bundle_hash(file_records: Iterable[dict[str, Any]]) -> str:
    canonical = json.dumps(
        list(file_records), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _validated_state() -> dict[str, Any]:
    result = json.loads(RESULT_JSON.read_text(encoding="utf-8"))
    progress = json.loads((COLLECTION_DIR / "progress.json").read_text(encoding="utf-8"))
    if result.get("protocol_fingerprint") != EXPECTED_PROTOCOL_FINGERPRINT:
        raise ValueError("Calibration result protocol fingerprint is not the audited fingerprint.")
    gates = {
        "collection_complete": bool(result.get("collection_complete")),
        "all_positions_covered": bool(result.get("all_positions_covered")),
        "stability_passed": bool(result.get("stability_passed")),
        "mapping_ready_for_offline_review": bool(
            result.get("mapping_ready_for_offline_review")
        ),
    }
    if not all(gates.values()):
        raise ValueError(f"Cannot freeze a calibration result with failed gates: {gates}")
    accepted = list(progress.get("accepted_csv_files") or [])
    if progress.get("accepted_steps") != 9 or progress.get("total_steps") != 9 or len(accepted) != 9:
        raise ValueError("Calibration progress does not contain exactly nine accepted trials.")
    result_files = [str(item.get("file")) for item in result.get("trials") or []]
    if result_files != accepted:
        raise ValueError("Accepted calibration files and result trial files differ.")
    compliance = []
    for filename in accepted:
        path = COLLECTION_DIR / filename
        sidecar = path.with_name(path.stem + "_compliance.json")
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        compliance.append(payload.get("verdict"))
    audit = json.loads(AUDIT_INDEX.read_text(encoding="utf-8"))
    deletion_log = list(audit.get("deletion_log") or [])
    return {
        "accepted_trials": len(accepted),
        "all_csv_attempts": len(list(COLLECTION_DIR.glob("*.csv"))),
        "accepted_compliance_verdicts": compliance,
        "verified_audit_clips_deleted": sum(
            row.get("deleted") is True and row.get("reason") == "VERIFIED_AND_ACCEPTED"
            for row in deletion_log
        ),
        "gates": gates,
        "linear_eye_pitch_mapping": result.get("linear_eye_pitch_mapping"),
    }


def build_calibration_result_freeze() -> dict[str, Any]:
    state = _validated_state()
    records = [
        {"path": _relative(path), "bytes": path.stat().st_size, "sha256": _sha256(path)}
        for path in calibration_result_files()
    ]
    return {
        "schema": "reachy-stage3p-calibration-result-integrity-freeze-v1",
        "status": "FROZEN_DEVELOPMENT_CALIBRATION_NOT_HELD_OUT_NOT_AUTHORISED_FOR_ACTUATION",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "protocol_fingerprint": EXPECTED_PROTOCOL_FINGERPRINT,
        "scope": {
            "complete_collection_directory": _relative(COLLECTION_DIR),
            "includes_all_attempts_and_sidecars": True,
            "includes_final_analysis_artifacts": True,
            "includes_audit_deletion_log": True,
            "source_files_modified": False,
        },
        "validated_state": state,
        "file_count": len(records),
        "files": records,
        "bundle_sha256": _bundle_hash(records),
        "privacy": {
            "main_dataset_contains_pixels": False,
            "main_dataset_contains_audio": False,
            "main_dataset_contains_transcript": False,
            "accepted_audit_clips_remaining": 0,
        },
        "actuation_commands": 0,
        "cloud_requests": 0,
    }


def write_calibration_result_freeze(path: Path = FREEZE_PATH) -> dict[str, Any]:
    destination = path.resolve()
    if destination.exists():
        raise FileExistsError(f"Calibration result is already frozen: {destination}")
    if destination.parent != (PROJECT_ROOT / "data/manifests").resolve():
        raise ValueError("The calibration freeze must remain in the manifest directory.")
    payload = build_calibration_result_freeze()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def verify_calibration_result_freeze(path: Path = FREEZE_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    failures: list[str] = []
    current: list[dict[str, Any]] = []
    for record in payload.get("files") or []:
        artifact = (PROJECT_ROOT / str(record["path"])).resolve()
        if not artifact.is_relative_to(PROJECT_ROOT) or not artifact.is_file():
            failures.append(f"missing:{record['path']}")
            continue
        observed = {
            "path": record["path"],
            "bytes": artifact.stat().st_size,
            "sha256": _sha256(artifact),
        }
        current.append(observed)
        if observed != record:
            failures.append(f"changed:{record['path']}")
    expected_paths = {record["path"] for record in payload.get("files") or []}
    actual_paths = {_relative(path) for path in calibration_result_files()}
    failures.extend(f"added:{path}" for path in sorted(actual_paths - expected_paths))
    if not failures and _bundle_hash(current) != payload.get("bundle_sha256"):
        failures.append("bundle-hash-mismatch")
    if failures:
        raise ValueError("Calibration freeze verification failed: " + ", ".join(failures))
    return {
        "verified": True,
        "file_count": len(current),
        "bundle_sha256": payload["bundle_sha256"],
        "frozen_at_utc": payload["frozen_at_utc"],
    }
