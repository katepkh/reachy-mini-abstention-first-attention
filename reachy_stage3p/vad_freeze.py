"""Integrity freeze for the completed passive Stage 3P silent-VAD diagnostic."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from reachy_stage2a.config import PROJECT_ROOT


FREEZE_PATH = (
    PROJECT_ROOT / "data/manifests/stage3p_vad_diagnostic_result_v1_freeze.json"
).resolve()
COLLECTION_DIR = (PROJECT_ROOT / "data/stage3p_vad_diagnostic").resolve()
AUDIT_DIR = (PROJECT_ROOT / "data/stage3p_vad_audit").resolve()
AUDIT_INDEX = (AUDIT_DIR / "audit_index.json").resolve()
RESULT_JSON = (PROJECT_ROOT / "data/analysis/stage3p_silent_vad_diagnostic_v1.json").resolve()
RESULT_ARTIFACTS = (
    RESULT_JSON,
    (PROJECT_ROOT / "data/analysis/stage3p_silent_vad_diagnostic_v1_trials.csv").resolve(),
    (PROJECT_ROOT / "data/analysis/stage3p_silent_vad_diagnostic_v1.md").resolve(),
    (PROJECT_ROOT / "data/manifests/stage3p_silent_vad_diagnostic_v1.json").resolve(),
)
EXPECTED_PROTOCOL_FINGERPRINT = (
    "0c960250a88760d3ca0191e9461c3573252c6abeb0af36f62940bfe786c1ac18"
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


def vad_result_files() -> tuple[Path, ...]:
    collection = tuple(
        sorted(path.resolve() for path in COLLECTION_DIR.rglob("*") if path.is_file())
    )
    # Encrypted audit media and its live deletion index are intentionally not
    # immutable bundle members: clips expire and are deleted by design.  Their
    # reviewed state and ciphertext hashes are snapshotted in the freeze.
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
        raise ValueError("VAD result protocol fingerprint is not the audited fingerprint.")
    if not result.get("collection_complete"):
        raise ValueError("Cannot freeze an incomplete silent-VAD diagnostic.")
    accepted = list(progress.get("accepted_csv_files") or [])
    if progress.get("accepted_steps") != 3 or progress.get("total_steps") != 3 or len(accepted) != 3:
        raise ValueError("VAD progress does not contain exactly three accepted trials.")
    result_files = [str(item.get("file")) for item in result.get("trials") or []]
    if result_files != accepted:
        raise ValueError("Accepted VAD files and result trial files differ.")

    compliance: list[str | None] = []
    for filename in accepted:
        csv_path = COLLECTION_DIR / filename
        sidecar = csv_path.with_name(csv_path.stem + "_compliance.json")
        compliance.append(json.loads(sidecar.read_text(encoding="utf-8")).get("verdict"))
    if compliance != ["COMPLIANT"] * 3:
        raise ValueError(f"Accepted VAD audit verdicts are not all compliant: {compliance}")

    audit = json.loads(AUDIT_INDEX.read_text(encoding="utf-8"))
    clips = list(audit.get("clips") or [])
    if len(clips) != 3 or any(clip.get("review_verdict") != "COMPLIANT" for clip in clips):
        raise ValueError("Expected exactly three compliant VAD audit clips.")
    audit_snapshot: list[dict[str, Any]] = []
    for clip in clips:
        encrypted = AUDIT_DIR / str(clip["encrypted_file"])
        if not encrypted.is_file():
            raise ValueError(f"Missing encrypted VAD audit clip: {encrypted.name}")
        audit_snapshot.append({
            "clip_id": clip.get("clip_id"),
            "trial_id": clip.get("trial_id"),
            "encrypted_file": clip.get("encrypted_file"),
            "ciphertext_bytes": encrypted.stat().st_size,
            "ciphertext_sha256": _sha256(encrypted),
            "encryption": clip.get("encryption"),
            "review_verdict": clip.get("review_verdict"),
            "reviewed_time_iso": clip.get("reviewed_time_iso"),
            "expires_time_iso": clip.get("expires_time_iso"),
        })
    return {
        "accepted_trials": 3,
        "all_csv_attempts": len(list(COLLECTION_DIR.glob("*.csv"))),
        "accepted_compliance_verdicts": compliance,
        "total_samples": int(result.get("total_samples") or 0),
        "speech_false_positive_samples": int(
            result.get("speech_false_positive_samples") or 0
        ),
        "speech_false_positive_pct": float(
            result.get("speech_false_positive_pct") or 0.0
        ),
        "persistent_positive_episodes": int(
            result.get("persistent_positive_episodes") or 0
        ),
        "classification": result.get("classification"),
        "audit_snapshot": audit_snapshot,
    }


def build_vad_result_freeze() -> dict[str, Any]:
    state = _validated_state()
    records = [
        {"path": _relative(path), "bytes": path.stat().st_size, "sha256": _sha256(path)}
        for path in vad_result_files()
    ]
    return {
        "schema": "reachy-stage3p-silent-vad-result-integrity-freeze-v1",
        "status": "FROZEN_DEVELOPMENT_DIAGNOSTIC_NOT_HELD_OUT_NOT_AUTHORISED_FOR_ACTUATION",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "protocol_fingerprint": EXPECTED_PROTOCOL_FINGERPRINT,
        "scope": {
            "complete_numeric_collection_directory": _relative(COLLECTION_DIR),
            "includes_all_numeric_attempts_and_sidecars": True,
            "includes_final_analysis_artifacts": True,
            "audit_media_is_expiring_sidecar_not_immutable_bundle_member": True,
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
            "encrypted_audit_clips_at_freeze": 3,
            "audit_clips_auto_expire": True,
        },
        "actuation_commands": 0,
        "cloud_requests": 0,
    }


def write_vad_result_freeze(path: Path = FREEZE_PATH) -> dict[str, Any]:
    destination = path.resolve()
    if destination.exists():
        raise FileExistsError(f"Silent-VAD result is already frozen: {destination}")
    if destination.parent != (PROJECT_ROOT / "data/manifests").resolve():
        raise ValueError("The VAD freeze must remain in the manifest directory.")
    payload = build_vad_result_freeze()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def verify_vad_result_freeze(path: Path = FREEZE_PATH) -> dict[str, Any]:
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
    actual_paths = {_relative(path) for path in vad_result_files()}
    failures.extend(f"added:{path}" for path in sorted(actual_paths - expected_paths))
    if not failures and _bundle_hash(current) != payload.get("bundle_sha256"):
        failures.append("bundle-hash-mismatch")
    if failures:
        raise ValueError("Silent-VAD freeze verification failed: " + ", ".join(failures))
    return {
        "verified": True,
        "file_count": len(current),
        "bundle_sha256": payload["bundle_sha256"],
        "frozen_at_utc": payload["frozen_at_utc"],
    }
