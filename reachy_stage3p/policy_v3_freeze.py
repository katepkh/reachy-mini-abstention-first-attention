"""Integrity freeze for the selected passive Stage 3P V3 policy."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from reachy_stage2a.config import PROJECT_ROOT

from .calibration_freeze import verify_calibration_result_freeze
from .result_freeze_v1 import verify_result_freeze
from .vad_freeze import verify_vad_result_freeze


FREEZE_PATH = (
    PROJECT_ROOT / "data/manifests/stage3p_selected_policy_v3_freeze.json"
).resolve()
POLICY_PATH = (
    PROJECT_ROOT / "data/manifests/stage3p_selected_policy_v3.json"
).resolve()
TOURNAMENT_PATH = (
    PROJECT_ROOT / "data/analysis/stage3p_candidate_v3_tournament.json"
).resolve()
DIAGNOSIS_PATH = (
    PROJECT_ROOT / "data/analysis/stage3p_failed_confirmation_offline_diagnosis_v1.json"
).resolve()
SOURCE_FILES = (
    POLICY_PATH,
    TOURNAMENT_PATH,
    DIAGNOSIS_PATH,
    (PROJECT_ROOT / "reachy_stage3p/policy_v3.py").resolve(),
    (PROJECT_ROOT / "reachy_stage3p/analysis_v3.py").resolve(),
    (PROJECT_ROOT / "data/manifests/stage3p_confirmation_result_v1_freeze.json").resolve(),
    (PROJECT_ROOT / "data/manifests/stage3p_calibration_result_v1_freeze.json").resolve(),
    (PROJECT_ROOT / "data/manifests/stage3p_vad_diagnostic_result_v1_freeze.json").resolve(),
    (PROJECT_ROOT / "data/manifests/stage3v_confirmation_result_v3_freeze.json").resolve(),
    (PROJECT_ROOT / "data/manifests/stage3v_revised_policy_v3.json").resolve(),
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


def _bundle_hash(file_records: Iterable[dict[str, Any]]) -> str:
    canonical = json.dumps(
        list(file_records), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _validate_selection() -> dict[str, Any]:
    selected = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    tournament = json.loads(TOURNAMENT_PATH.read_text(encoding="utf-8"))
    diagnosis = json.loads(DIAGNOSIS_PATH.read_text(encoding="utf-8"))
    fingerprint = str(selected.get("fingerprint") or "")
    candidates = [
        item
        for item in tournament.get("candidates") or []
        if (item.get("spec") or {}).get("fingerprint") == fingerprint
    ]
    if len(candidates) != 1:
        raise ValueError("Selected Stage 3P V3 policy has no unique tournament source.")
    candidate = candidates[0]
    source_spec = candidate["spec"]
    source_core = {key: value for key, value in source_spec.items() if key != "fingerprint"}
    observed = hashlib.sha256(
        json.dumps(source_core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if observed != fingerprint:
        raise ValueError("Selected Stage 3P V3 fingerprint does not verify.")
    for key, value in source_spec.items():
        if key != "status" and selected.get(key) != value:
            raise ValueError(f"Selected V3 policy differs from tournament source at {key}.")
    if tournament.get("selected_policy_fingerprint") != fingerprint:
        raise ValueError("Tournament and selected V3 policy fingerprints differ.")
    gates = candidate.get("selection_gates") or {}
    if not gates or not all(gates.values()):
        raise ValueError(f"Selected V3 policy has failed selection gates: {gates}")
    if candidate.get("vad_confirmed_rows") != 0 or candidate.get("vad_false_targets") != 0:
        raise ValueError("Selected V3 policy did not suppress the silent-VAD set.")
    if float(source_spec.get("fallback_geometry_error_deg", 999.0)) > 8.0:
        raise ValueError("Selected V3 fallback geometry is wider than the conservative winner.")
    if not source_spec.get("runtime_requires_eye_landmarks"):
        raise ValueError("Selected V3 runtime policy must require eye landmarks.")
    if not source_spec.get("retain_association_through_acoustic_conflict"):
        raise ValueError("Selected V3 policy did not preserve the diagnosed maintenance repair.")

    failed = verify_result_freeze()
    calibration = verify_calibration_result_freeze()
    vad = verify_vad_result_freeze()
    if source_spec.get("source_failed_result_bundle_sha256") != failed["bundle_sha256"]:
        raise ValueError("Selected V3 policy points to a different failed-result bundle.")
    if diagnosis.get("frozen_source_bundle_sha256") != failed["bundle_sha256"]:
        raise ValueError("Offline diagnosis points to a different failed-result bundle.")
    return {
        "policy_fingerprint": fingerprint,
        "selection_gates": gates,
        "failed_result_bundle_sha256": failed["bundle_sha256"],
        "calibration_bundle_sha256": calibration["bundle_sha256"],
        "vad_bundle_sha256": vad["bundle_sha256"],
        "fresh_held_out_stage3p_required": True,
        "physical_actuation_authorised": False,
    }


def build_policy_v3_freeze() -> dict[str, Any]:
    validated = _validate_selection()
    records = [
        {"path": _relative(path), "bytes": path.stat().st_size, "sha256": _sha256(path)}
        for path in SOURCE_FILES
    ]
    return {
        "schema": "reachy-stage3p-selected-policy-v3-integrity-freeze-v1",
        "status": "FROZEN_FOR_FRESH_HELD_OUT_PASSIVE_STAGE3P_V2_NOT_AUTHORISED_FOR_ACTUATION",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "validated_selection": validated,
        "file_count": len(records),
        "files": records,
        "bundle_sha256": _bundle_hash(records),
        "scientific_boundary": {
            "failed_held_out_result_frozen_before_reuse": True,
            "failed_held_out_data_now_disclosed_as_development_evidence": True,
            "fresh_data_required_for_validation": True,
            "runtime_requires_eye_landmarks": True,
            "stage3v_v3_yaw_target_unchanged": True,
            "no_physical_motion_authorised": True,
        },
        "actuation_commands": 0,
        "cloud_requests": 0,
    }


def write_policy_v3_freeze(path: Path = FREEZE_PATH) -> dict[str, Any]:
    destination = path.resolve()
    if destination.exists():
        raise FileExistsError(f"Stage 3P V3 policy is already frozen: {destination}")
    if destination.parent != (PROJECT_ROOT / "data/manifests").resolve():
        raise ValueError("The V3 policy freeze must remain in data/manifests.")
    payload = build_policy_v3_freeze()
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def verify_policy_v3_freeze(path: Path = FREEZE_PATH) -> dict[str, Any]:
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
        raise ValueError("Stage 3P V3 policy freeze verification failed: " + ", ".join(failures))
    return {
        "verified": True,
        "policy_fingerprint": payload["validated_selection"]["policy_fingerprint"],
        "file_count": len(current),
        "bundle_sha256": payload["bundle_sha256"],
        "frozen_at_utc": payload["frozen_at_utc"],
    }
