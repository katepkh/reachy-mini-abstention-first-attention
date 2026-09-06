"""Freeze V2 evidence and select one Stage 3V V3 policy by offline replay."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from statistics import median
from typing import Any

from .analysis import load_rows
from .config import ANALYSIS_DIR, PROJECT_ROOT
from .protocol import VALIDATION_STEPS
from .revised_policy import aggregate_revised_trials
from .revised_policy_v3 import (
    FROZEN_REVISED_POLICY_V3,
    RevisedPolicyV3Spec,
    evaluate_revised_trial_v3,
)


MANIFEST_DIR = (PROJECT_ROOT / "data" / "manifests").resolve()
V2_FREEZE_PATH = (MANIFEST_DIR / "stage3v_confirmation_result_v2_freeze.json").resolve()
V3_DIAGNOSIS_JSON_PATH = (ANALYSIS_DIR / "stage3v_policy_v3_diagnosis.json").resolve()
V3_DIAGNOSIS_REPORT_PATH = (ANALYSIS_DIR / "stage3v_policy_v3_diagnosis.md").resolve()
V3_POLICY_MANIFEST_PATH = (MANIFEST_DIR / "stage3v_revised_policy_v3.json").resolve()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _manifest_entry(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    return {
        "path": resolved.relative_to(PROJECT_ROOT).as_posix(),
        "bytes": resolved.stat().st_size,
        "sha256": _sha256(resolved),
    }


def freeze_v2_confirmation() -> dict[str, Any]:
    """Create once, then verify rather than mutate, the completed V2 result."""
    if V2_FREEZE_PATH.is_file():
        frozen = json.loads(V2_FREEZE_PATH.read_text(encoding="utf-8"))
        for entry in frozen["files"]:
            path = (PROJECT_ROOT / entry["path"]).resolve()
            if not path.is_file() or _sha256(path) != entry["sha256"]:
                raise ValueError(f"Frozen V2 evidence changed: {entry['path']}")
        return frozen

    evidence_dir = PROJECT_ROOT / "data" / "stage3v_confirmation_v2"
    progress = json.loads((evidence_dir / "progress.json").read_text(encoding="utf-8"))
    if progress.get("accepted_steps") != 18 or len(progress.get("accepted_csv_files", [])) != 18:
        raise ValueError("V2 held-out confirmation is not complete.")
    result_path = ANALYSIS_DIR / "stage3v_confirmation_validation_v2.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    expected = {
        "safety_passed": True,
        "direction_passed": True,
        "coverage_passed": False,
        "accuracy_passed": False,
    }
    if any(bool(result.get(key)) != value for key, value in expected.items()):
        raise ValueError("The V2 result no longer matches the audited PASS/PASS/FAIL/FAIL outcome.")

    files = sorted(path for path in evidence_dir.iterdir() if path.is_file())
    files.extend(
        [
            result_path,
            ANALYSIS_DIR / "stage3v_confirmation_validation_v2_trials.csv",
            ANALYSIS_DIR / "stage3v_confirmation_validation_v2.md",
            MANIFEST_DIR / "stage3v_revised_policy_v2.json",
            MANIFEST_DIR / "stage3v_confirmation_protocol_v2.json",
        ]
    )
    frozen = {
        "schema": "reachy-stage3v-v2-held-out-result-freeze-v1",
        "status": "FROZEN_FAILED_HELD_OUT_RESULT",
        "accepted_steps": 18,
        **expected,
        "policy_fingerprint": result["policy_fingerprint"],
        "protocol_fingerprint": result["protocol_fingerprint"],
        "includes_unaccepted_and_superseded_attempts": True,
        "files": [_manifest_entry(path) for path in files],
        "not_authorized_for_actuation": True,
    }
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    V2_FREEZE_PATH.write_text(json.dumps(frozen, indent=2) + "\n", encoding="utf-8")
    return frozen


def _load_dataset(relative_dir: str) -> tuple[list[str], list[list[dict[str, Any]]]]:
    directory = (PROJECT_ROOT / relative_dir).resolve()
    progress = json.loads((directory / "progress.json").read_text(encoding="utf-8"))
    files = list(progress.get("accepted_csv_files", []))
    if progress.get("accepted_steps") != 18 or len(files) != 18:
        raise ValueError(f"Incomplete Stage 3V dataset: {relative_dir}")
    return files, [load_rows(directory / filename) for filename in files]


def _candidate_specs() -> tuple[RevisedPolicyV3Spec, ...]:
    return tuple(
        RevisedPolicyV3Spec(
            name=(
                FROZEN_REVISED_POLICY_V3.name
                if offset == FROZEN_REVISED_POLICY_V3.face_heading_offset_deg
                else f"Stage 3V V3 candidate yaw offset {offset:+.1f} degrees"
            ),
            face_heading_multiplier=-1.0,
            face_heading_offset_deg=offset,
            maximum_geometry_error_deg=10.0,
            required_hits=3,
            window_ms=600.0,
            heading_tolerance_deg=8.0,
            disagreement_lockout_ms=1500.0,
            speech_latch_ms=800.0,
            clear_speech_latch_on_fault=True,
            target_source="visual",
        )
        for offset in (index / 2.0 for index in range(-16, 9))
    )


def _evaluate_dataset(
    files: list[str],
    rows_by_trial: list[list[dict[str, Any]]],
    spec: RevisedPolicyV3Spec,
) -> dict[str, Any]:
    trials = [
        {**evaluate_revised_trial_v3(step, rows, spec), "file": filename}
        for step, filename, rows in zip(VALIDATION_STEPS, files, rows_by_trial)
    ]
    return {**aggregate_revised_trials(trials), "trials": trials}


def _compact_evaluation(evaluation: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in evaluation.items() if key != "trials"}


def _dataset_diagnostics(
    files: list[str], rows_by_trial: list[list[dict[str, Any]]]
) -> dict[str, Any]:
    headings: dict[str, list[float]] = {str(int(value)): [] for value in (-20, -10, 10, 20)}
    silent_speech: list[dict[str, Any]] = []
    for step, filename, rows in zip(VALIDATION_STEPS, files, rows_by_trial):
        if step.role == "matching_positive":
            values = [
                -float(row["face_heading_deg"])
                for row in rows
                if row.get("face_heading_deg") not in (None, "")
                and int(float(row.get("face_count") or 0)) == 1
            ]
            if values:
                headings[str(int(step.true_heading_deg))].append(median(values))
        elif step.condition_id.startswith("silent-face"):
            silent_speech.append(
                {
                    "step": step.index,
                    "file": filename,
                    "speech_positive_rows": sum(
                        str(row.get("speech_detected", "")).strip().lower() == "true" for row in rows
                    ),
                    "rows": len(rows),
                }
            )
    return {
        "uncalibrated_visual_trial_medians_by_true_heading_deg": headings,
        "silent_trial_speech_flags": silent_speech,
    }


def run_v3_diagnosis() -> dict[str, Any]:
    freeze = freeze_v2_confirmation()
    datasets = {
        "original_development": _load_dataset("data/stage3v"),
        "failed_v1_heldout_now_development": _load_dataset("data/stage3v_confirmation"),
        "failed_v2_heldout_now_development": _load_dataset("data/stage3v_confirmation_v2"),
    }
    candidates: list[dict[str, Any]] = []
    full_by_fingerprint: dict[str, dict[str, Any]] = {}
    for spec in _candidate_specs():
        evaluations = {
            name: _evaluate_dataset(files, rows_by_trial, spec)
            for name, (files, rows_by_trial) in datasets.items()
        }
        passes = all(
            result[key]
            for result in evaluations.values()
            for key in ("safety_passed", "direction_passed", "coverage_passed", "accuracy_passed")
        )
        finite_errors = [
            float(row["maximum_target_error_deg"])
            for evaluation in evaluations.values()
            for row in evaluation["heading_summary"]
            if row["maximum_target_error_deg"] is not None
        ]
        compact = {
            "policy": spec.payload(),
            "passes_all_development_gates_in_all_datasets": passes,
            "worst_target_error_deg": max(finite_errors) if finite_errors else None,
            "datasets": {name: _compact_evaluation(value) for name, value in evaluations.items()},
        }
        candidates.append(compact)
        full_by_fingerprint[spec.payload()["fingerprint"]] = evaluations

    passing = [row for row in candidates if row["passes_all_development_gates_in_all_datasets"]]
    if not passing:
        raise ValueError("No V3 offset candidate passes all development datasets.")
    selected = min(passing, key=lambda row: float(row["worst_target_error_deg"]))
    frozen_payload = FROZEN_REVISED_POLICY_V3.payload()
    if selected["policy"]["fingerprint"] != frozen_payload["fingerprint"]:
        raise ValueError("Best passing candidate does not match the frozen V3 policy.")
    if float(selected["worst_target_error_deg"]) > 6.0:
        raise ValueError("The selected V3 candidate lacks the predeclared 2 degree accuracy margin.")

    diagnostics = {
        name: _dataset_diagnostics(files, rows_by_trial)
        for name, (files, rows_by_trial) in datasets.items()
    }
    selected_full = full_by_fingerprint[selected["policy"]["fingerprint"]]
    return {
        "schema": "reachy-stage3v-policy-v3-offline-diagnosis-v1",
        "status": "DEVELOPMENT_ONLY_REQUIRES_NEW_V3_HELD_OUT_CONFIRMATION",
        "v2_result_freeze_sha256": _sha256(V2_FREEZE_PATH),
        "v2_failed_result": {
            "safety_passed": freeze["safety_passed"],
            "direction_passed": freeze["direction_passed"],
            "coverage_passed": freeze["coverage_passed"],
            "accuracy_passed": freeze["accuracy_passed"],
        },
        "causal_diagnosis": (
            "The corrected visual bearing had a repeatable horizontal zero-point bias: negative "
            "targets were under-magnitude while positive targets were over-magnitude. At +20 degrees "
            "that bias also pushed visual/acoustic disagreement beyond the unchanged 10 degree gate."
        ),
        "controlled_change": (
            "Apply one fixed -4.0 degree camera-to-diagram yaw offset after sign conversion. Retain "
            "the V2 speech latch, three-hit/600 ms consensus, geometry threshold, disagreement "
            "lockout, camera-fault resets, visual target and all aggregate pass criteria unchanged."
        ),
        "speech_flag_diagnosis": (
            "Silent trials contain speech-positive flags, so endpoint speech detection is noisy. "
            "No waveform was retained, therefore VAD cannot be recalibrated from these datasets. "
            "Speech remains insufficient by itself: geometry, temporal consensus and disagreement "
            "lockout continue to prevent hard-negative moves."
        ),
        "selection_rule": (
            "Test fixed offsets from -8.0 to +4.0 degrees in 0.5 degree steps across all three "
            "now-development datasets; require zero hard-negative movement rows, zero wrong-sign "
            "moves, at least two moving trials per heading, <=8 degree target error, then choose the "
            "passing offset with the smallest worst-case error and require <=6 degrees for margin."
        ),
        "datasets_are_not_v3_validation": True,
        "diagnostics": diagnostics,
        "candidates": candidates,
        "selected_policy": selected["policy"],
        "selected_worst_target_error_deg": selected["worst_target_error_deg"],
        "selected_development_results": selected_full,
        "robot_requests": 0,
        "camera_requests": 0,
        "cloud_requests": 0,
        "actuation_commands": 0,
        "contains_pixels": False,
        "contains_audio": False,
        "contains_transcript": False,
    }


def write_v3_diagnosis_artifacts() -> dict[str, Any]:
    result = run_v3_diagnosis()
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    V3_DIAGNOSIS_JSON_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    policy_manifest = {
        "schema": "reachy-stage3v-revised-policy-freeze-v3",
        "status": "FROZEN_BEFORE_V3_HELD_OUT_COLLECTION",
        "development_evidence_only": True,
        "prior_results_preserved": True,
        "not_authorized_for_actuation": True,
        "selection_rule": result["selection_rule"],
        "policy": result["selected_policy"],
        "development_results": result["selected_development_results"],
        "v2_result_freeze_sha256": result["v2_result_freeze_sha256"],
        "contains_pixels": False,
        "contains_audio": False,
        "contains_transcript": False,
        "robot_requests": 0,
        "cloud_requests": 0,
        "actuation_commands": 0,
    }
    V3_POLICY_MANIFEST_PATH.write_text(json.dumps(policy_manifest, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Stage 3V V3 offline diagnosis",
        "",
        "Status: **development-only; a new V3 held-out confirmation is required**.",
        "",
        "All three earlier datasets are now development evidence. None can validate V3.",
        "",
        "## Root cause",
        "",
        result["causal_diagnosis"],
        "",
        "## Controlled repair",
        "",
        result["controlled_change"],
        "",
        f"Frozen V3 policy fingerprint: `{result['selected_policy']['fingerprint']}`",
        f"Development replay worst target error: **{result['selected_worst_target_error_deg']:.2f}°**.",
        "",
        "| Dataset | Moving trials (−20/−10/+10/+20) | Worst error | Negative rows | Wrong-sign moves |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, evaluation in result["selected_development_results"].items():
        moves = "/".join(str(row["trials_with_move"]) for row in evaluation["heading_summary"])
        errors = [
            float(row["maximum_target_error_deg"])
            for row in evaluation["heading_summary"]
            if row["maximum_target_error_deg"] is not None
        ]
        lines.append(
            f"| {name} | {moves} | {max(errors):.2f}° | "
            f"{evaluation['hard_negative_would_move_rows']} | {evaluation['wrong_sign_moves']} |"
        )
    lines.extend(
        [
            "",
            "## Speech endpoint limitation",
            "",
            result["speech_flag_diagnosis"],
            "",
            "> Offline replay selected V3 on observed data. Only a fresh independent V3 collection can validate it; no physical movement is authorized.",
        ]
    )
    V3_DIAGNOSIS_REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result
