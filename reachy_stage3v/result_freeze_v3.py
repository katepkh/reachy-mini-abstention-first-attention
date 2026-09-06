"""Integrity freeze for the completed Stage 3V V3 held-out result.

The freeze covers the complete collection directory, including rejected
attempts and their compliance sidecars, plus the frozen protocol/policy and
final analysis artifacts.  It does not alter or delete any source file.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .config import PROJECT_ROOT


FREEZE_PATH = (
    PROJECT_ROOT / "data" / "manifests" / "stage3v_confirmation_result_v3_freeze.json"
).resolve()
COLLECTION_DIR = (PROJECT_ROOT / "data" / "stage3v_confirmation_v3").resolve()
RESULT_JSON = (
    PROJECT_ROOT / "data" / "analysis" / "stage3v_confirmation_validation_v3.json"
).resolve()
RESULT_ARTIFACTS = (
    RESULT_JSON,
    (PROJECT_ROOT / "data" / "analysis" / "stage3v_confirmation_validation_v3_trials.csv").resolve(),
    (PROJECT_ROOT / "data" / "analysis" / "stage3v_confirmation_validation_v3.md").resolve(),
    (PROJECT_ROOT / "data" / "manifests" / "stage3v_confirmation_protocol_v3.json").resolve(),
    (PROJECT_ROOT / "data" / "manifests" / "stage3v_revised_policy_v3.json").resolve(),
)

EXPECTED_PROTOCOL_FINGERPRINT = (
    "d2f1182dd1a4d2a3e6e2a6215277c94f07223abe36e619f6eedbaed15ed766d0"
)
EXPECTED_POLICY_FINGERPRINT = (
    "34382c415d44cb595c1d03bb95f6fdbe4b4ea3a1b6372df012e79896473ec0d1"
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


def v3_result_files() -> tuple[Path, ...]:
    """Return every immutable input covered by the V3 result freeze."""
    collection = tuple(sorted(path.resolve() for path in COLLECTION_DIR.rglob("*") if path.is_file()))
    return tuple(sorted({*collection, *RESULT_ARTIFACTS}, key=_relative))


def _bundle_hash(file_records: Iterable[dict[str, Any]]) -> str:
    canonical = json.dumps(list(file_records), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _validated_result_state() -> dict[str, Any]:
    result = json.loads(RESULT_JSON.read_text(encoding="utf-8"))
    progress = json.loads((COLLECTION_DIR / "progress.json").read_text(encoding="utf-8"))
    gates = {
        name: bool(result.get(name))
        for name in ("safety_passed", "direction_passed", "coverage_passed", "accuracy_passed")
    }
    if not all(gates.values()):
        raise ValueError(f"Cannot freeze a V3 result with failed gates: {gates}")
    if result.get("protocol_fingerprint") != EXPECTED_PROTOCOL_FINGERPRINT:
        raise ValueError("The V3 result protocol fingerprint is not the audited fingerprint.")
    if result.get("policy_fingerprint") != EXPECTED_POLICY_FINGERPRINT:
        raise ValueError("The V3 result policy fingerprint is not the audited fingerprint.")
    accepted = list(progress.get("accepted_csv_files") or [])
    if progress.get("accepted_steps") != 18 or progress.get("total_steps") != 18 or len(accepted) != 18:
        raise ValueError("The V3 progress file does not contain exactly 18 accepted trials.")
    result_files = [str(item.get("file")) for item in result.get("trials") or []]
    if result_files != accepted:
        raise ValueError("Accepted progress files and final-result trial files differ.")

    all_csv = sorted(COLLECTION_DIR.glob("*.csv"))
    compliance = sorted(COLLECTION_DIR.glob("*_compliance.json"))
    verdicts = [json.loads(path.read_text(encoding="utf-8")).get("verdict") for path in compliance]
    return {
        "accepted_trials": len(accepted),
        "all_csv_attempts": len(all_csv),
        "rejected_or_noncompliant_attempts": sum(verdict != "COMPLIANT" for verdict in verdicts),
        "gates": gates,
        "positive_trials_with_move": int(result.get("positive_trials_with_move", 0)),
        "hard_negative_would_move_rows": int(result.get("hard_negative_would_move_rows", 0)),
        "wrong_sign_moves": int(result.get("wrong_sign_moves", 0)),
        "maximum_target_error_deg": max(
            float(item["maximum_target_error_deg"])
            for item in result.get("heading_summary") or []
            if item.get("maximum_target_error_deg") is not None
        ),
    }


def build_v3_result_freeze() -> dict[str, Any]:
    state = _validated_result_state()
    records = [
        {
            "path": _relative(path),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path in v3_result_files()
    ]
    return {
        "schema": "reachy-stage3v-v3-result-integrity-freeze-v1",
        "status": "FROZEN_PASSIVE_HELD_OUT_RESULT_NOT_AUTHORISED_FOR_ACTUATION",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "protocol_fingerprint": EXPECTED_PROTOCOL_FINGERPRINT,
        "policy_fingerprint": EXPECTED_POLICY_FINGERPRINT,
        "scope": {
            "complete_collection_directory": _relative(COLLECTION_DIR),
            "includes_accepted_attempts": True,
            "includes_rejected_and_noncompliant_attempts": True,
            "includes_metadata_and_compliance_sidecars": True,
            "includes_final_analysis_artifacts": True,
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
        },
        "actuation_commands": 0,
        "cloud_requests": 0,
    }


def write_v3_result_freeze(path: Path = FREEZE_PATH) -> dict[str, Any]:
    """Create the freeze once; refuse to replace an existing frozen record."""
    destination = path.resolve()
    if destination.exists():
        raise FileExistsError(f"V3 result is already frozen: {destination}")
    if destination.parent != (PROJECT_ROOT / "data" / "manifests").resolve():
        raise ValueError("The V3 freeze must remain in the project manifest directory.")
    payload = build_v3_result_freeze()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def verify_v3_result_freeze(path: Path = FREEZE_PATH) -> dict[str, Any]:
    """Re-hash the frozen bundle and raise on any missing or changed artifact."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    failures: list[str] = []
    current: list[dict[str, Any]] = []
    for record in payload.get("files") or []:
        artifact = (PROJECT_ROOT / str(record["path"])).resolve()
        if not artifact.is_relative_to(PROJECT_ROOT) or not artifact.is_file():
            failures.append(f"missing:{record['path']}")
            continue
        observed = {"path": record["path"], "bytes": artifact.stat().st_size, "sha256": _sha256(artifact)}
        current.append(observed)
        if observed != record:
            failures.append(f"changed:{record['path']}")
    expected_paths = {record["path"] for record in payload.get("files") or []}
    actual_paths = {_relative(path) for path in v3_result_files()}
    for added in sorted(actual_paths - expected_paths):
        failures.append(f"added:{added}")
    if not failures and _bundle_hash(current) != payload.get("bundle_sha256"):
        failures.append("bundle-hash-mismatch")
    if failures:
        raise ValueError("V3 result freeze verification failed: " + ", ".join(failures))
    return {
        "verified": True,
        "file_count": len(current),
        "bundle_sha256": payload["bundle_sha256"],
        "frozen_at_utc": payload["frozen_at_utc"],
    }
