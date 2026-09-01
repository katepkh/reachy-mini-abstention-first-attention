"""Fresh held-out evaluation for the frozen Stage 3P V6 association repair."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from reachy_stage3v.analysis import load_rows, summarise_rows
from reachy_stage3v.config import ANALYSIS_DIR, DATA_DIR, REPORT_PATH, RESULT_CSV_PATH, RESULT_JSON_PATH

from .analysis_v6 import SELECTED_POLICY_PATH, TOURNAMENT_PATH
from .confirmation_protocol_v6 import CONFIRMATION_V6_STEPS, protocol_payload
from .confirmation_v5 import (
    aggregate_confirmation_v5_trials,
    evaluate_confirmation_v5_trial,
    quality_issues,
)
from .policy_v6 import Stage3PVisualServoV6Spec
from .policy_v6_freeze import verify_policy_v6_freeze


def frozen_selected_spec() -> Stage3PVisualServoV6Spec:
    verified = verify_policy_v6_freeze()
    selected = json.loads(SELECTED_POLICY_PATH.read_text(encoding="utf-8"))
    tournament = json.loads(TOURNAMENT_PATH.read_text(encoding="utf-8"))
    candidate = tournament.get("selected_candidate") or {}
    source = candidate.get("spec") or {}
    fingerprint = verified["policy_fingerprint"]
    if (
        selected.get("fingerprint") != fingerprint
        or source.get("fingerprint") != fingerprint
        or not candidate.get("all_gates_passed")
    ):
        raise ValueError("The frozen selected Stage 3P V6 policy cannot be resolved uniquely.")
    manifest = protocol_payload()
    if (
        manifest["source_policy_fingerprint"] != fingerprint
        or manifest["source_policy_freeze_bundle_sha256"] != verified["bundle_sha256"]
    ):
        raise ValueError("The V6 confirmation protocol does not match the frozen policy bundle.")
    return Stage3PVisualServoV6Spec(**{
        key: source[key] for key in Stage3PVisualServoV6Spec.__dataclass_fields__
    })


def evaluate_confirmation_v6_trial(
    step: Any,
    rows: list[dict[str, Any]],
    spec: Stage3PVisualServoV6Spec | None = None,
) -> dict[str, Any]:
    return evaluate_confirmation_v5_trial(step, rows, spec or frozen_selected_spec())


def _sidecar(csv_path: Path, suffix: str) -> Path:
    return csv_path.with_name(csv_path.stem + suffix)


def evaluate_saved_files(csv_files: list[str]) -> dict[str, Any]:
    if len(csv_files) != len(CONFIRMATION_V6_STEPS):
        raise ValueError("A complete fresh Stage 3P V6 confirmation requires 18 accepted files.")
    spec = frozen_selected_spec()
    fingerprint = protocol_payload()["fingerprint"]
    trials: list[dict[str, Any]] = []
    for step, filename in zip(CONFIRMATION_V6_STEPS, csv_files):
        path = (DATA_DIR / filename).resolve()
        if path.parent != DATA_DIR or not path.is_file():
            raise ValueError(f"Fresh held-out Stage 3P V6 file is missing: {filename}")
        rows = load_rows(path)
        issues = quality_issues(step, summarise_rows(rows))
        if issues:
            raise ValueError(f"Held-out V6 file fails quality: {filename}: {'; '.join(issues)}")
        metadata_path = _sidecar(path, "_metadata.json")
        compliance_path = _sidecar(path, "_compliance.json")
        if not metadata_path.is_file() or not compliance_path.is_file():
            raise ValueError(f"Held-out V6 sidecars are incomplete: {filename}")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        compliance = json.loads(compliance_path.read_text(encoding="utf-8"))
        if (
            metadata.get("protocol_fingerprint") != fingerprint
            or metadata.get("step_index") != step.index
            or metadata.get("actuation_commands") != 0
            or metadata.get("cloud_requests") != 0
        ):
            raise ValueError(f"Held-out V6 metadata integrity failed: {filename}")
        if (
            compliance.get("verdict") != "COMPLIANT"
            or compliance.get("protocol_fingerprint") != fingerprint
            or compliance.get("data_mode") != "development_audit"
            or not compliance.get("audit_clip_id")
            or compliance.get("audit_verdict") != "COMPLIANT"
        ):
            raise ValueError(f"Held-out V6 audit compliance is incomplete: {filename}")
        trials.append({**evaluate_confirmation_v6_trial(step, rows, spec), "file": filename})

    aggregate = aggregate_confirmation_v5_trials(trials)
    freeze = verify_policy_v6_freeze()
    return {
        "schema": "reachy-stage3p-held-out-association-repair-confirmation-result-v6",
        "status": "FRESH_HELD_OUT_PASSIVE_RESULT_NOT_AUTHORISED_FOR_ACTUATION",
        "protocol_fingerprint": fingerprint,
        "frozen_policy_fingerprint": freeze["policy_fingerprint"],
        "frozen_policy_bundle_sha256": freeze["bundle_sha256"],
        "policy_integrity_verified": True,
        "prior_confirmation_files_used": 0,
        "development_files_used": 0,
        "outcomes_changed_policy": False,
        "outcomes_controlled_acceptance": False,
        "absolute_pitch_accuracy_relabelled": False,
        "procedural_audit_required_for_all_trials": True,
        "maintenance_repositioning_interval_ms": 4000.0,
        **aggregate,
        "trials": trials,
        "contains_pixels": False,
        "contains_audio": False,
        "contains_transcript": False,
        "robot_requests": 0,
        "cloud_requests": 0,
        "actuation_commands": 0,
    }


def write_results(csv_files: list[str]) -> dict[str, Any]:
    result = evaluate_saved_files(csv_files)
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_JSON_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    rows = [
        {key: value for key, value in row.items() if key != "reason_counts"}
        for row in result["trials"]
    ]
    with RESULT_CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# Fresh held-out passive Stage 3P association-repair confirmation V6",
        "",
        f"Protocol fingerprint: `{result['protocol_fingerprint']}`",
        f"Frozen policy fingerprint: `{result['frozen_policy_fingerprint']}`",
        "",
        *[
            f"- {name.replace('_', ' ').title()}: **{'PASS' if passed else 'FAIL'}**"
            for name, passed in result["gates"].items()
        ],
        "",
        f"Overall passive held-out result: **{'PASS' if result['overall_passed'] else 'FAIL'}**",
        "",
        "> This result tests the frozen V6 association repair with bounded relative shadow",
        "> corrections. It does not authorize physical movement.",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result
