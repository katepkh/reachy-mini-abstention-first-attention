"""Validation of owner-scope and independent-review provenance records."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any


OWNER_SCHEMA = "reachy-stage4a-owner-scope-record-v2"
REVIEW_SCHEMA = "reachy-stage4a-independent-protocol-review-v2"
OWNER_OBSERVABILITY_ACTIONS = {
    "powered_baseline_inventory_and_receive_only_capture",
    "temporary_target_state_observability_environment",
    "stop_original_start_temporary_and_restore_original_daemon",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_verified_external_record(
    record_path: Path,
    *,
    expected_schema: str,
) -> dict[str, Any]:
    """Load a record and verify the referenced response artifact byte-for-byte."""

    path = record_path.resolve()
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("schema") != expected_schema:
        raise ValueError(f"Expected external record schema {expected_schema}.")
    for field in ("decision", "recorded_by", "recorded_at_utc"):
        if not isinstance(record.get(field), str) or not record[field].strip():
            raise ValueError(f"Missing external record field: {field}")
    if not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", record["recorded_at_utc"]
    ):
        raise ValueError("recorded_at_utc must be a whole-second UTC timestamp.")

    source = record.get("source_artifact")
    if not isinstance(source, dict):
        raise ValueError("source_artifact must identify the preserved external reply.")
    reference = source.get("path")
    expected_hash = str(source.get("sha256") or "").lower()
    if not isinstance(reference, str) or not reference.strip():
        raise ValueError("source_artifact.path is required.")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        raise ValueError("source_artifact.sha256 must contain 64 lowercase hex characters.")
    artifact_path = (path.parent / reference).resolve()
    observed_hash = sha256_file(artifact_path)
    if observed_hash != expected_hash:
        raise ValueError("External response artifact SHA-256 does not match the record.")
    record["verified_source_artifact_path"] = str(artifact_path)
    return record


def require_owner_observability_scope(record_path: Path) -> dict[str, Any]:
    record = load_verified_external_record(record_path, expected_schema=OWNER_SCHEMA)
    if record["decision"] != "SCOPE_CONFIRMED":
        raise ValueError("Robot owner has not confirmed the proposed scope.")
    actions = record.get("approved_actions")
    if not isinstance(actions, list) or any(not isinstance(item, str) for item in actions):
        raise ValueError("approved_actions must be a list of action identifiers.")
    missing = sorted(OWNER_OBSERVABILITY_ACTIONS - set(actions))
    if missing:
        raise ValueError("Owner scope does not include: " + ", ".join(missing))
    if not isinstance(record.get("return_condition_definition"), str) or not record[
        "return_condition_definition"
    ].strip():
        raise ValueError("Owner must define the accepted return condition.")
    return record


def require_independent_protocol_approval(
    record_path: Path,
    *,
    review_manifest_path: Path | None = None,
) -> dict[str, Any]:
    record = load_verified_external_record(record_path, expected_schema=REVIEW_SCHEMA)
    if record["decision"] != "PROTOCOL_APPROVED":
        raise ValueError("Independent reviewer has not approved the proposed protocol.")
    if not isinstance(record.get("reviewer_expertise"), str) or not record[
        "reviewer_expertise"
    ].strip():
        raise ValueError("reviewer_expertise is required.")
    if record.get("return_protocol_decision") != "APPROVED":
        raise ValueError("Independent reviewer has not approved the return protocol.")
    if record.get("vendor_review_required") is not False:
        raise ValueError(
            "Reviewer must explicitly state that vendor review is not required, "
            "or vendor review must be obtained separately."
        )
    manifest_hash = str(record.get("reviewed_manifest_sha256") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", manifest_hash):
        raise ValueError("reviewed_manifest_sha256 must bind the exact review packet.")
    if review_manifest_path is not None:
        observed_manifest_hash = sha256_file(review_manifest_path.resolve())
        if manifest_hash != observed_manifest_hash:
            raise ValueError(
                "Independent approval does not match the current review manifest."
            )
    return record
