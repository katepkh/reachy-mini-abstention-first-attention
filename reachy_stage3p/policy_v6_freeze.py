"""Integrity freeze for the selected passive Stage 3P V6 association repair."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from reachy_stage2a.config import PROJECT_ROOT

from .analysis_v6 import DIAGNOSIS_PATH, REPORT_PATH, SELECTED_POLICY_PATH, TOURNAMENT_PATH
from .result_freeze_v5 import verify_result_freeze as verify_v5_result_freeze


FREEZE_PATH = (
    PROJECT_ROOT / "data/manifests/stage3p_selected_policy_v6_freeze.json"
).resolve()
SOURCE_FILES = (
    SELECTED_POLICY_PATH,
    TOURNAMENT_PATH,
    DIAGNOSIS_PATH,
    REPORT_PATH,
    (PROJECT_ROOT / "reachy_stage3p/policy_v6.py").resolve(),
    (PROJECT_ROOT / "reachy_stage3p/analysis_v6.py").resolve(),
    (PROJECT_ROOT / "data/manifests/stage3p_confirmation_result_v5_freeze.json").resolve(),
    (PROJECT_ROOT / "data/manifests/stage3p_selected_policy_v5_freeze.json").resolve(),
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
    canonical = json.dumps(list(records), sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(canonical).hexdigest()


def _validate_selection() -> dict[str, Any]:
    selected = json.loads(SELECTED_POLICY_PATH.read_text(encoding="utf-8"))
    tournament = json.loads(TOURNAMENT_PATH.read_text(encoding="utf-8"))
    candidate = tournament.get("selected_candidate") or {}
    source = candidate.get("spec") or {}
    fingerprint = str(selected.get("fingerprint") or "")
    core = {key: value for key, value in source.items() if key != "fingerprint"}
    observed = hashlib.sha256(
        json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if observed != fingerprint or source.get("fingerprint") != fingerprint:
        raise ValueError("Selected Stage 3P V6 fingerprint does not verify.")
    if tournament.get("selected_policy_fingerprint") != fingerprint:
        raise ValueError("Tournament and selected V6 policy fingerprints differ.")
    for key, value in source.items():
        if key != "status" and selected.get(key) != value:
            raise ValueError(f"Selected V6 policy differs from tournament at {key}.")
    gates = candidate.get("gates") or {}
    if not candidate.get("all_gates_passed") or not gates or not all(gates.values()):
        raise ValueError(f"Selected V6 policy has failed known-data gates: {gates}")
    if int(tournament.get("candidate_count") or 0) != 48:
        raise ValueError("The complete disclosed 48-candidate V6 grid was not evaluated.")
    if int(tournament.get("passing_candidate_count") or 0) != 9:
        raise ValueError("The expected nine V6 candidates did not pass every gate.")
    if (
        float(source.get("fallback_geometry_error_deg") or 0.0) != 13.0
        or float(source.get("fallback_speech_onset_window_ms") or 0.0) != 2500.0
        or int(source.get("association_consensus_hits") or 0) != 2
    ):
        raise ValueError("The V6 selection rule did not choose the minimal passing repair.")
    if (
        source.get("control_mode") != "BOUNDED_INCREMENTAL_RELATIVE_EYE_ERROR"
        or float(source.get("maximum_abs_increment_deg") or 0.0) != 3.0
        or float(source.get("incremental_pitch_deadband_deg") or 0.0) != 2.5
    ):
        raise ValueError("The selected V6 policy changed the frozen V5 control law.")
    v5 = verify_v5_result_freeze()
    if tournament.get("source_failed_v5_result_bundle_sha256") != v5["bundle_sha256"]:
        raise ValueError("The V6 tournament does not point to the frozen failed V5 result.")
    return {
        "policy_fingerprint": fingerprint,
        "candidate_count": tournament["candidate_count"],
        "passing_candidate_count": tournament["passing_candidate_count"],
        "selection_gates": gates,
        "failed_v5_result_bundle_sha256": v5["bundle_sha256"],
        "fallback_geometry_error_deg": source["fallback_geometry_error_deg"],
        "fallback_speech_onset_window_ms": source["fallback_speech_onset_window_ms"],
        "association_consensus_hits": source["association_consensus_hits"],
        "maximum_abs_increment_deg": source["maximum_abs_increment_deg"],
        "fresh_held_out_stage3p_v6_required": True,
        "physical_actuation_authorised": False,
    }


def build_policy_v6_freeze() -> dict[str, Any]:
    validated = _validate_selection()
    records = [
        {"path": _relative(path), "bytes": path.stat().st_size, "sha256": _sha256(path)}
        for path in SOURCE_FILES
    ]
    return {
        "schema": "reachy-stage3p-selected-policy-v6-integrity-freeze-v1",
        "status": (
            "FROZEN_FOR_FRESH_HELD_OUT_PASSIVE_STAGE3P_V6_"
            "NOT_AUTHORISED_FOR_ACTUATION"
        ),
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "validated_selection": validated,
        "file_count": len(records),
        "files": records,
        "bundle_sha256": _bundle_hash(records),
        "scientific_boundary": {
            "failed_held_out_v5_preserved_as_failure": True,
            "v5_now_used_only_as_disclosed_development_evidence": True,
            "association_repair_selected_after_observing_v5": True,
            "fresh_held_out_v6_confirmation_required": True,
            "no_physical_motion_authorised": True,
        },
        "robot_requests": 0,
        "actuation_commands": 0,
        "cloud_requests": 0,
    }


def write_policy_v6_freeze(path: Path = FREEZE_PATH) -> dict[str, Any]:
    destination = path.resolve()
    if destination.exists():
        raise FileExistsError(f"Stage 3P V6 policy is already frozen: {destination}")
    if destination.parent != (PROJECT_ROOT / "data/manifests").resolve():
        raise ValueError("The V6 policy freeze must remain in data/manifests.")
    payload = build_policy_v6_freeze()
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def verify_policy_v6_freeze(path: Path = FREEZE_PATH) -> dict[str, Any]:
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
        raise ValueError("Stage 3P V6 policy freeze verification failed: " + ", ".join(failures))
    return {
        "verified": True,
        "policy_fingerprint": payload["validated_selection"]["policy_fingerprint"],
        "file_count": len(current),
        "bundle_sha256": payload["bundle_sha256"],
        "frozen_at_utc": payload["frozen_at_utc"],
    }
