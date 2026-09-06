"""Integrity freeze for the selected passive Stage 3P V5 visual servo.

The freeze proves which offline evidence selected the policy.  It does not
authorize importing a motor/controller package or sending a robot command.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from reachy_stage2a.config import PROJECT_ROOT
from reachy_stage3v.result_freeze_v3 import verify_v3_result_freeze

from .calibration_freeze import verify_calibration_result_freeze
from .policy_v4_freeze import verify_policy_v4_freeze
from .result_freeze_v1 import verify_result_freeze as verify_v1_result_freeze
from .result_freeze_v3 import verify_result_freeze as verify_v3_stage3p_result_freeze
from .vad_freeze import verify_vad_result_freeze


FREEZE_PATH = (
    PROJECT_ROOT / "data/manifests/stage3p_selected_policy_v5_freeze.json"
).resolve()
POLICY_PATH = (
    PROJECT_ROOT / "data/manifests/stage3p_selected_policy_v5.json"
).resolve()
TOURNAMENT_PATH = (
    PROJECT_ROOT / "data/analysis/stage3p_candidate_v5_visual_servo_tournament.json"
).resolve()
DIAGNOSIS_PATH = (
    PROJECT_ROOT / "data/analysis/stage3p_visual_servo_v5_design_diagnosis.json"
).resolve()
SOURCE_FILES = (
    POLICY_PATH,
    TOURNAMENT_PATH,
    DIAGNOSIS_PATH,
    (PROJECT_ROOT / "data/analysis/stage3p_confirmation_v3_initial_diagnosis.md").resolve(),
    (PROJECT_ROOT / "reachy_stage3p/policy_v5.py").resolve(),
    (PROJECT_ROOT / "reachy_stage3p/analysis_v5.py").resolve(),
    (PROJECT_ROOT / "data/manifests/stage3p_selected_policy_v4_freeze.json").resolve(),
    (PROJECT_ROOT / "data/manifests/stage3p_confirmation_result_v1_freeze.json").resolve(),
    (PROJECT_ROOT / "data/manifests/stage3p_confirmation_result_v3_freeze.json").resolve(),
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
    canonical = json.dumps(list(records), sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(canonical).hexdigest()


def _validate_selection() -> dict[str, Any]:
    selected = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    tournament = json.loads(TOURNAMENT_PATH.read_text(encoding="utf-8"))
    candidate = tournament.get("selected_candidate") or {}
    source = candidate.get("spec") or {}
    fingerprint = str(selected.get("fingerprint") or "")

    core = {key: value for key, value in source.items() if key != "fingerprint"}
    observed = hashlib.sha256(
        json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if observed != fingerprint:
        raise ValueError("Selected Stage 3P V5 fingerprint does not verify.")
    if tournament.get("selected_policy_fingerprint") != fingerprint:
        raise ValueError("Tournament and selected V5 policy fingerprints differ.")
    for key, value in source.items():
        if key != "status" and selected.get(key) != value:
            raise ValueError(f"Selected V5 policy differs from tournament at {key}.")

    gates = candidate.get("gates") or {}
    if not candidate.get("all_gates_passed") or not gates or not all(gates.values()):
        raise ValueError(f"Selected V5 policy has failed offline gates: {gates}")
    if int(tournament.get("candidate_count") or 0) != 54:
        raise ValueError("The complete preregistered 54-candidate grid was not evaluated.")
    if int(tournament.get("passing_candidate_count") or 0) < 1:
        raise ValueError("No Stage 3P V5 candidate passed the offline gates.")
    if source.get("control_mode") != "BOUNDED_INCREMENTAL_RELATIVE_EYE_ERROR":
        raise ValueError("The selected policy is not the relative visual servo.")
    if float(source.get("maximum_abs_increment_deg") or 0.0) > 3.0:
        raise ValueError("The selected pitch increment is not the conservative 3-degree bound.")

    previous_policy = verify_policy_v4_freeze()
    v1 = verify_v1_result_freeze()
    v3 = verify_v3_stage3p_result_freeze()
    calibration = verify_calibration_result_freeze()
    vad = verify_vad_result_freeze()
    horizontal = verify_v3_result_freeze()
    if v1["overall_passed"] or v3["overall_passed"]:
        raise ValueError("The disclosed failed confirmations were relabelled unexpectedly.")
    if tournament.get("source_failed_v3_result_bundle_sha256") != v3["bundle_sha256"]:
        raise ValueError("The tournament does not point to the frozen failed V3 result.")

    return {
        "policy_fingerprint": fingerprint,
        "candidate_count": tournament["candidate_count"],
        "passing_candidate_count": tournament["passing_candidate_count"],
        "selection_gates": gates,
        "maximum_abs_increment_deg": source["maximum_abs_increment_deg"],
        "previous_policy_bundle_sha256": previous_policy["bundle_sha256"],
        "failed_v1_result_bundle_sha256": v1["bundle_sha256"],
        "failed_v3_result_bundle_sha256": v3["bundle_sha256"],
        "calibration_bundle_sha256": calibration["bundle_sha256"],
        "vad_bundle_sha256": vad["bundle_sha256"],
        "horizontal_v3_bundle_sha256": horizontal["bundle_sha256"],
        "fresh_held_out_stage3p_required": True,
        "physical_actuation_authorised": False,
    }


def build_policy_v5_freeze() -> dict[str, Any]:
    validated = _validate_selection()
    records = [
        {"path": _relative(path), "bytes": path.stat().st_size, "sha256": _sha256(path)}
        for path in SOURCE_FILES
    ]
    return {
        "schema": "reachy-stage3p-selected-policy-v5-integrity-freeze-v1",
        "status": (
            "FROZEN_FOR_FRESH_HELD_OUT_PASSIVE_STAGE3P_V5_"
            "NOT_AUTHORISED_FOR_ACTUATION"
        ),
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "validated_selection": validated,
        "file_count": len(records),
        "files": records,
        "bundle_sha256": _bundle_hash(records),
        "scientific_boundary": {
            "failed_held_out_v1_and_v3_preserved_as_failures": True,
            "failed_data_now_used_only_as_disclosed_development_evidence": True,
            "absolute_target_accuracy_not_relabelled": True,
            "fresh_data_required_for_validation": True,
            "no_physical_motion_authorised": True,
        },
        "actuation_commands": 0,
        "cloud_requests": 0,
    }


def write_policy_v5_freeze(path: Path = FREEZE_PATH) -> dict[str, Any]:
    destination = path.resolve()
    if destination.exists():
        raise FileExistsError(f"Stage 3P V5 policy is already frozen: {destination}")
    if destination.parent != (PROJECT_ROOT / "data/manifests").resolve():
        raise ValueError("The V5 policy freeze must remain in data/manifests.")
    payload = build_policy_v5_freeze()
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def verify_policy_v5_freeze(path: Path = FREEZE_PATH) -> dict[str, Any]:
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
        raise ValueError("Stage 3P V5 policy freeze verification failed: " + ", ".join(failures))
    return {
        "verified": True,
        "policy_fingerprint": payload["validated_selection"]["policy_fingerprint"],
        "file_count": len(current),
        "bundle_sha256": payload["bundle_sha256"],
        "frozen_at_utc": payload["frozen_at_utc"],
    }
