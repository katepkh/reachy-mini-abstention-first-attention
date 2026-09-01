"""Integrity freeze for the failed Stage 3P V6 held-out confirmation."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from reachy_stage2a.config import PROJECT_ROOT

from .policy_v6_freeze import verify_policy_v6_freeze


FREEZE_PATH = (
    PROJECT_ROOT / "data/manifests/stage3p_confirmation_result_v6_freeze.json"
).resolve()
COLLECTION_DIR = (PROJECT_ROOT / "data/stage3p_confirmation_v6").resolve()
AUDIT_INDEX = (
    PROJECT_ROOT / "data/stage3p_confirmation_v6_audit/audit_index.json"
).resolve()
RESULT_JSON = (
    PROJECT_ROOT / "data/analysis/stage3p_confirmation_validation_v6.json"
).resolve()
RESULT_ARTIFACTS = (
    RESULT_JSON,
    (PROJECT_ROOT / "data/analysis/stage3p_confirmation_validation_v6_trials.csv").resolve(),
    (PROJECT_ROOT / "data/analysis/stage3p_confirmation_validation_v6.md").resolve(),
    (PROJECT_ROOT / "data/manifests/stage3p_confirmation_protocol_v6.json").resolve(),
    (PROJECT_ROOT / "data/manifests/stage3p_selected_policy_v6.json").resolve(),
    (PROJECT_ROOT / "data/manifests/stage3p_selected_policy_v6_freeze.json").resolve(),
    AUDIT_INDEX,
)

EXPECTED_PROTOCOL_FINGERPRINT = (
    "e359660cdffc0b953bda066c2d9ed93ead174b1362770b425ca48762f521afe1"
)
EXPECTED_POLICY_FINGERPRINT = (
    "cc6fc9731d2149a2e273989e6e0dea4caacca5859aee45ccf16d82d1f53b6da1"
)
EXPECTED_POLICY_BUNDLE_SHA256 = (
    "464fbe6c038d12a41685d40c7a4d29e7e893ca0f1ad9bf5869ce4054f2bb1caf"
)
EXPECTED_GATES = {
    "hard_negative_safety": True,
    "vertical_direction": True,
    "bounded_increment": True,
    "static_relative_correction_coverage": True,
    "pretransition_association": False,
    "pretransition_center_hold": True,
    "silent_maintenance_relative_correction_coverage": False,
}


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


def result_files() -> tuple[Path, ...]:
    collection = tuple(
        sorted(path.resolve() for path in COLLECTION_DIR.rglob("*") if path.is_file())
    )
    return tuple(sorted({*collection, *RESULT_ARTIFACTS}, key=_relative))


def _bundle_hash(file_records: Iterable[dict[str, Any]]) -> str:
    canonical = json.dumps(
        list(file_records), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _validated_result_state() -> dict[str, Any]:
    result = json.loads(RESULT_JSON.read_text(encoding="utf-8"))
    progress = json.loads((COLLECTION_DIR / "progress.json").read_text(encoding="utf-8"))
    policy = verify_policy_v6_freeze()

    if result.get("status") != "FRESH_HELD_OUT_PASSIVE_RESULT_NOT_AUTHORISED_FOR_ACTUATION":
        raise ValueError("The Stage 3P V6 result status changed unexpectedly.")
    if result.get("protocol_fingerprint") != EXPECTED_PROTOCOL_FINGERPRINT:
        raise ValueError("The Stage 3P V6 result has the wrong protocol fingerprint.")
    if result.get("frozen_policy_fingerprint") != EXPECTED_POLICY_FINGERPRINT:
        raise ValueError("The Stage 3P V6 result has the wrong policy fingerprint.")
    if result.get("frozen_policy_bundle_sha256") != EXPECTED_POLICY_BUNDLE_SHA256:
        raise ValueError("The Stage 3P V6 result has the wrong policy bundle hash.")
    if (
        not result.get("policy_integrity_verified")
        or policy["policy_fingerprint"] != EXPECTED_POLICY_FINGERPRINT
        or policy["bundle_sha256"] != EXPECTED_POLICY_BUNDLE_SHA256
    ):
        raise ValueError("The frozen V6 policy does not verify for this result.")
    if result.get("gates") != EXPECTED_GATES or result.get("overall_passed") is not False:
        raise ValueError("The failed Stage 3P V6 gates no longer match the audited result.")
    if any(
        (
            result.get("prior_confirmation_files_used"),
            result.get("development_files_used"),
            result.get("outcomes_changed_policy"),
            result.get("outcomes_controlled_acceptance"),
            result.get("absolute_pitch_accuracy_relabelled"),
            result.get("robot_requests"),
            result.get("actuation_commands"),
            result.get("cloud_requests"),
            result.get("contains_pixels"),
            result.get("contains_audio"),
            result.get("contains_transcript"),
        )
    ):
        raise ValueError("Held-out isolation, privacy, or passive-only claims do not verify.")
    if result.get("procedural_audit_required_for_all_trials") is not True:
        raise ValueError("The V6 result no longer requires the procedural audit.")

    accepted = list(progress.get("accepted_csv_files") or [])
    if (
        progress.get("accepted_steps") != 18
        or progress.get("total_steps") != 18
        or progress.get("status") != "COLLECTION_COMPLETE"
    ):
        raise ValueError("Stage 3P V6 progress is not a completed 18-trial collection.")
    if progress.get("protocol_fingerprint") != EXPECTED_PROTOCOL_FINGERPRINT:
        raise ValueError("Stage 3P V6 progress has the wrong protocol fingerprint.")
    if len(accepted) != 18 or len(set(accepted)) != 18:
        raise ValueError("Stage 3P V6 accepted-file list is incomplete or duplicated.")
    if [str(item.get("file")) for item in result.get("trials") or []] != accepted:
        raise ValueError("Accepted progress files and result trial files differ.")

    accepted_clip_ids: list[str] = []
    for step_index, filename in enumerate(accepted, start=1):
        csv_path = COLLECTION_DIR / filename
        metadata_path = csv_path.with_name(csv_path.stem + "_metadata.json")
        compliance_path = csv_path.with_name(csv_path.stem + "_compliance.json")
        if not all(path.is_file() for path in (csv_path, metadata_path, compliance_path)):
            raise ValueError(f"Accepted V6 sidecars are incomplete: {filename}")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        compliance = json.loads(compliance_path.read_text(encoding="utf-8"))
        if (
            metadata.get("protocol_fingerprint") != EXPECTED_PROTOCOL_FINGERPRINT
            or metadata.get("step_index") != step_index
            or metadata.get("actuation_commands") != 0
            or metadata.get("cloud_requests") != 0
            or metadata.get("contains_pixels") is not False
            or metadata.get("contains_audio") is not False
            or metadata.get("contains_transcript") is not False
        ):
            raise ValueError(f"Accepted V6 metadata does not verify: {filename}")
        if (
            compliance.get("verdict") != "COMPLIANT"
            or compliance.get("audit_verdict") != "COMPLIANT"
            or not compliance.get("position_instruction_followed")
            or not compliance.get("speech_or_playback_instruction_followed")
        ):
            raise ValueError(f"Accepted V6 trial lacks a compliant audit: {filename}")
        clip_id = str(metadata.get("separate_encrypted_audit_clip_id") or "")
        if not clip_id or compliance.get("audit_clip_id") != clip_id:
            raise ValueError(f"Accepted V6 audit identity does not verify: {filename}")
        accepted_clip_ids.append(clip_id)

    if len(set(accepted_clip_ids)) != 18:
        raise ValueError("Accepted V6 trials do not have 18 distinct audit clips.")
    audit = json.loads(AUDIT_INDEX.read_text(encoding="utf-8"))
    if audit.get("clips"):
        raise ValueError("Retained V6 audit media remains after trial verification.")
    deleted = {
        str(item.get("clip_id"))
        for item in audit.get("deletion_log") or []
        if item.get("deleted") is True and item.get("reason") == "VERIFIED_AND_ACCEPTED"
    }
    if not set(accepted_clip_ids).issubset(deleted):
        raise ValueError("Not every accepted V6 audit clip has a verified deletion record.")

    all_csv = sorted(COLLECTION_DIR.glob("*.csv"))
    failed_steps = [
        int(item["step"])
        for item in result["trials"]
        if item["role"] == "maintenance_transition"
        and item["pretransition_association_confirmed"] is not True
    ]
    return {
        "accepted_trials": len(accepted),
        "all_csv_attempts": len(all_csv),
        "superseded_attempts": len(all_csv) - len(accepted),
        "accepted_compliant_audits": len(accepted_clip_ids),
        "accepted_audit_clips_deleted_after_review": len(set(accepted_clip_ids) & deleted),
        "gates": EXPECTED_GATES,
        "overall_passed": False,
        "failed_pretransition_steps": failed_steps,
        "hard_negative_would_adjust_rows": int(result["hard_negative_would_adjust_rows"]),
        "development_files_used": int(result["development_files_used"]),
        "robot_requests": int(result["robot_requests"]),
        "actuation_commands": int(result["actuation_commands"]),
        "cloud_requests": int(result["cloud_requests"]),
    }


def build_result_freeze() -> dict[str, Any]:
    state = _validated_result_state()
    records = [
        {"path": _relative(path), "bytes": path.stat().st_size, "sha256": _sha256(path)}
        for path in result_files()
    ]
    return {
        "schema": "reachy-stage3p-v6-failed-result-integrity-freeze-v1",
        "status": "FROZEN_FAILED_PASSIVE_HELD_OUT_RESULT_NOT_AUTHORISED_FOR_ACTUATION",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "protocol_fingerprint": EXPECTED_PROTOCOL_FINGERPRINT,
        "policy_fingerprint": EXPECTED_POLICY_FINGERPRINT,
        "policy_bundle_sha256": EXPECTED_POLICY_BUNDLE_SHA256,
        "scope": {
            "complete_collection_directory": _relative(COLLECTION_DIR),
            "includes_accepted_attempts": True,
            "includes_superseded_attempts": True,
            "includes_metadata_and_compliance_sidecars": True,
            "includes_audit_deletion_ledger": True,
            "includes_final_analysis_artifacts": True,
            "source_files_modified": False,
        },
        "validated_state": state,
        "file_count": len(records),
        "files": records,
        "bundle_sha256": _bundle_hash(records),
        "scientific_boundary": {
            "result_was_held_out_when_collected": True,
            "result_failed_before_any_further_policy_revision": True,
            "dataset_may_now_be_used_only_as_label_disclosed_development_evidence": True,
            "fresh_independent_confirmation_required_for_any_revised_policy": True,
            "physical_movement_authorised": False,
        },
        "privacy": {
            "main_dataset_contains_pixels": False,
            "main_dataset_contains_audio": False,
            "main_dataset_contains_transcript": False,
            "accepted_audit_media_deleted_after_review": True,
        },
        "robot_requests": 0,
        "actuation_commands": 0,
        "cloud_requests": 0,
    }


def write_result_freeze(path: Path = FREEZE_PATH) -> dict[str, Any]:
    destination = path.resolve()
    if destination.exists():
        raise FileExistsError(f"Stage 3P V6 result is already frozen: {destination}")
    if destination.parent != (PROJECT_ROOT / "data/manifests").resolve():
        raise ValueError("The Stage 3P V6 result freeze must remain in data/manifests.")
    payload = build_result_freeze()
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def verify_result_freeze(path: Path = FREEZE_PATH) -> dict[str, Any]:
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
    actual_paths = {_relative(path) for path in result_files()}
    for added in sorted(actual_paths - expected_paths):
        failures.append(f"added:{added}")
    if not failures and _bundle_hash(current) != payload.get("bundle_sha256"):
        failures.append("bundle-hash-mismatch")
    if failures:
        raise ValueError("Stage 3P V6 result freeze verification failed: " + ", ".join(failures))
    return {
        "verified": True,
        "file_count": len(current),
        "bundle_sha256": payload["bundle_sha256"],
        "frozen_at_utc": payload["frozen_at_utc"],
        "overall_passed": payload["validated_state"]["overall_passed"],
    }
