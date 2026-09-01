"""Integrity freeze for the pre-collection-hardened Stage 3P V4 policy."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from reachy_stage2a.config import PROJECT_ROOT

from .policy_v3_freeze import verify_policy_v3_freeze
from .result_freeze_v1 import verify_result_freeze


FREEZE_PATH = (
    PROJECT_ROOT / "data/manifests/stage3p_selected_policy_v4_freeze.json"
).resolve()
POLICY_PATH = (
    PROJECT_ROOT / "data/manifests/stage3p_selected_policy_v4.json"
).resolve()
HARDENING_PATH = (
    PROJECT_ROOT / "data/analysis/stage3p_candidate_v4_precollection_hardening.json"
).resolve()
INCIDENT_PATH = (
    PROJECT_ROOT / "data/manifests/stage3p_precollection_lease_timer_incident.json"
).resolve()
SOURCE_FILES = (
    POLICY_PATH,
    HARDENING_PATH,
    INCIDENT_PATH,
    (PROJECT_ROOT / "reachy_stage3p/policy_v4.py").resolve(),
    (PROJECT_ROOT / "reachy_stage3p/analysis_v4.py").resolve(),
    (PROJECT_ROOT / "data/manifests/stage3p_selected_policy_v3_freeze.json").resolve(),
    (PROJECT_ROOT / "data/manifests/stage3p_confirmation_result_v1_freeze.json").resolve(),
    (PROJECT_ROOT / "data/manifests/stage3p_calibration_result_v1_freeze.json").resolve(),
    (PROJECT_ROOT / "data/manifests/stage3p_vad_diagnostic_result_v1_freeze.json").resolve(),
    (PROJECT_ROOT / "data/manifests/stage3v_confirmation_result_v3_freeze.json").resolve(),
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


def _bundle_hash(records: Iterable[dict[str, Any]]) -> str:
    canonical = json.dumps(list(records), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _validate_selection() -> dict[str, Any]:
    selected = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    hardening = json.loads(HARDENING_PATH.read_text(encoding="utf-8"))
    incident = json.loads(INCIDENT_PATH.read_text(encoding="utf-8"))
    fingerprint = str(selected.get("fingerprint") or "")
    candidate = hardening.get("candidate") or {}
    source = candidate.get("spec") or {}
    core = {key: value for key, value in source.items() if key != "fingerprint"}
    observed = hashlib.sha256(
        json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if observed != fingerprint or hardening.get("selected_policy_fingerprint") != fingerprint:
        raise ValueError("Selected Stage 3P V4 fingerprint does not verify.")
    for key, value in source.items():
        if key != "status" and selected.get(key) != value:
            raise ValueError(f"Selected V4 policy differs from hardening source at {key}.")
    gates = candidate.get("selection_gates") or {}
    if not gates or not all(gates.values()):
        raise ValueError(f"Selected V4 policy has failed hardening gates: {gates}")
    if not source.get("refresh_maintenance_lease_on_valid_reconfirmation"):
        raise ValueError("Selected V4 policy lacks the lease-refresh repair.")
    if incident.get("human_trials_collected_under_superseded_protocol") != 0:
        raise ValueError("The superseded pre-collection protocol unexpectedly contains trials.")
    prior = verify_policy_v3_freeze()
    failed = verify_result_freeze()
    if source.get("source_superseded_policy_fingerprint") != prior["policy_fingerprint"]:
        raise ValueError("V4 does not point to the preserved superseded V3 policy.")
    return {
        "policy_fingerprint": fingerprint,
        "selection_gates": gates,
        "superseded_policy_fingerprint": prior["policy_fingerprint"],
        "superseded_policy_bundle_sha256": prior["bundle_sha256"],
        "failed_result_bundle_sha256": failed["bundle_sha256"],
        "fresh_held_out_stage3p_required": True,
        "physical_actuation_authorised": False,
    }


def build_policy_v4_freeze() -> dict[str, Any]:
    validated = _validate_selection()
    records = [
        {"path": _relative(path), "bytes": path.stat().st_size, "sha256": _sha256(path)}
        for path in SOURCE_FILES
    ]
    return {
        "schema": "reachy-stage3p-selected-policy-v4-integrity-freeze-v1",
        "status": "FROZEN_FOR_FRESH_HELD_OUT_PASSIVE_STAGE3P_V3_NOT_AUTHORISED_FOR_ACTUATION",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "validated_selection": validated,
        "file_count": len(records),
        "files": records,
        "bundle_sha256": _bundle_hash(records),
        "scientific_boundary": {
            "superseded_candidate_preserved": True,
            "timer_issue_detected_before_human_collection": True,
            "failed_held_out_data_used_only_as_disclosed_development_evidence": True,
            "fresh_data_required_for_validation": True,
            "no_physical_motion_authorised": True,
        },
        "actuation_commands": 0,
        "cloud_requests": 0,
    }


def write_policy_v4_freeze(path: Path = FREEZE_PATH) -> dict[str, Any]:
    destination = path.resolve()
    if destination.exists():
        raise FileExistsError(f"Stage 3P V4 policy is already frozen: {destination}")
    if destination.parent != (PROJECT_ROOT / "data/manifests").resolve():
        raise ValueError("The V4 policy freeze must remain in data/manifests.")
    payload = build_policy_v4_freeze()
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def verify_policy_v4_freeze(path: Path = FREEZE_PATH) -> dict[str, Any]:
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
    if not failures and _bundle_hash(current) != payload.get("bundle_sha256"):
        failures.append("bundle-hash-mismatch")
    if failures:
        raise ValueError("Stage 3P V4 policy freeze verification failed: " + ", ".join(failures))
    return {
        "verified": True,
        "policy_fingerprint": payload["validated_selection"]["policy_fingerprint"],
        "file_count": len(current),
        "bundle_sha256": payload["bundle_sha256"],
        "frozen_at_utc": payload["frozen_at_utc"],
    }
