"""Freeze V1 evidence and select one Stage 3V V2 policy by offline replay."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from .analysis import load_rows
from .config import ANALYSIS_DIR, PROJECT_ROOT
from .protocol import VALIDATION_STEPS
from .revised_policy import aggregate_revised_trials
from .revised_policy_v2 import (
    FROZEN_REVISED_POLICY_V2,
    RevisedPolicyV2Spec,
    evaluate_revised_trial_v2,
)


MANIFEST_DIR = (PROJECT_ROOT / "data" / "manifests").resolve()
V1_FREEZE_PATH = (MANIFEST_DIR / "stage3v_confirmation_result_v1_freeze.json").resolve()
V2_DIAGNOSIS_JSON_PATH = (ANALYSIS_DIR / "stage3v_policy_v2_diagnosis.json").resolve()
V2_DIAGNOSIS_CSV_PATH = (ANALYSIS_DIR / "stage3v_policy_v2_candidates.csv").resolve()
V2_DIAGNOSIS_REPORT_PATH = (ANALYSIS_DIR / "stage3v_policy_v2_diagnosis.md").resolve()
V2_POLICY_MANIFEST_PATH = (MANIFEST_DIR / "stage3v_revised_policy_v2.json").resolve()


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


def freeze_v1_confirmation() -> dict[str, Any]:
    """Create once, then verify rather than mutate, the failed V1 evidence freeze."""
    if V1_FREEZE_PATH.is_file():
        frozen = json.loads(V1_FREEZE_PATH.read_text(encoding="utf-8"))
        for entry in frozen["files"]:
            path = (PROJECT_ROOT / entry["path"]).resolve()
            if not path.is_file() or _sha256(path) != entry["sha256"]:
                raise ValueError(f"Frozen V1 evidence changed: {entry['path']}")
        return frozen

    progress_path = PROJECT_ROOT / "data" / "stage3v_confirmation" / "progress.json"
    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    if progress.get("accepted_steps") != 18 or len(progress.get("accepted_csv_files", [])) != 18:
        raise ValueError("V1 held-out confirmation is not complete.")
    result_path = ANALYSIS_DIR / "stage3v_confirmation_validation_v1.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("coverage_passed") or result.get("accuracy_passed"):
        raise ValueError("The V1 freeze expects the recorded failed coverage/accuracy result.")

    evidence_dir = PROJECT_ROOT / "data" / "stage3v_confirmation"
    files = sorted(path for path in evidence_dir.iterdir() if path.is_file())
    files.extend(
        [
            ANALYSIS_DIR / "stage3v_confirmation_validation_v1.json",
            ANALYSIS_DIR / "stage3v_confirmation_validation_v1_trials.csv",
            ANALYSIS_DIR / "stage3v_confirmation_validation_v1.md",
            MANIFEST_DIR / "stage3v_revised_policy_v1.json",
            MANIFEST_DIR / "stage3v_confirmation_protocol_v1.json",
        ]
    )
    frozen = {
        "schema": "reachy-stage3v-v1-held-out-result-freeze-v1",
        "status": "FROZEN_FAILED_HELD_OUT_RESULT",
        "accepted_steps": 18,
        "safety_passed": bool(result["safety_passed"]),
        "direction_passed": bool(result["direction_passed"]),
        "coverage_passed": bool(result["coverage_passed"]),
        "accuracy_passed": bool(result["accuracy_passed"]),
        "policy_fingerprint": result["policy_fingerprint"],
        "protocol_fingerprint": result["protocol_fingerprint"],
        "includes_unaccepted_and_superseded_attempts": True,
        "files": [_manifest_entry(path) for path in files],
        "not_authorized_for_actuation": True,
    }
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    V1_FREEZE_PATH.write_text(json.dumps(frozen, indent=2) + "\n", encoding="utf-8")
    return frozen


def _load_dataset(relative_dir: str) -> tuple[list[str], list[list[dict[str, Any]]]]:
    directory = (PROJECT_ROOT / relative_dir).resolve()
    progress = json.loads((directory / "progress.json").read_text(encoding="utf-8"))
    files = list(progress.get("accepted_csv_files", []))
    if progress.get("accepted_steps") != 18 or len(files) != 18:
        raise ValueError(f"Incomplete Stage 3V dataset: {relative_dir}")
    return files, [load_rows(directory / filename) for filename in files]


def _candidate_specs() -> tuple[RevisedPolicyV2Spec, ...]:
    return tuple(
        RevisedPolicyV2Spec(
            name=(
                FROZEN_REVISED_POLICY_V2.name
                if latch == FROZEN_REVISED_POLICY_V2.speech_latch_ms
                else f"Stage 3V V2 speech latch {latch:.0f} ms"
            ),
            face_heading_multiplier=-1.0,
            maximum_geometry_error_deg=10.0,
            required_hits=3,
            window_ms=600.0,
            heading_tolerance_deg=8.0,
            disagreement_lockout_ms=1500.0,
            speech_latch_ms=latch,
            clear_speech_latch_on_fault=True,
            target_source="visual",
        )
        for latch in (0.0, 200.0, 400.0, 600.0, 800.0, 1000.0, 1200.0)
    )


def _evaluate_dataset(
    files: list[str],
    rows_by_trial: list[list[dict[str, Any]]],
    spec: RevisedPolicyV2Spec,
) -> dict[str, Any]:
    trials = [
        {**evaluate_revised_trial_v2(step, rows, spec), "file": filename}
        for step, filename, rows in zip(VALIDATION_STEPS, files, rows_by_trial)
    ]
    return {**aggregate_revised_trials(trials), "trials": trials}


def run_v2_diagnosis() -> dict[str, Any]:
    freeze = freeze_v1_confirmation()
    datasets: dict[str, tuple[list[str], list[list[dict[str, Any]]]]] = {
        "original_development": _load_dataset("data/stage3v"),
        "failed_v1_heldout_now_development": _load_dataset("data/stage3v_confirmation"),
    }
    candidates: list[dict[str, Any]] = []
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
        candidates.append(
            {
                "policy": spec.payload(),
                "passes_all_development_gates_in_both_datasets": passes,
                "datasets": evaluations,
            }
        )
    passing = [row for row in candidates if row["passes_all_development_gates_in_both_datasets"]]
    if not passing:
        raise ValueError("No V2 candidate passes both development datasets.")
    selected = min(passing, key=lambda row: float(row["policy"]["speech_latch_ms"]))
    if selected["policy"]["fingerprint"] != FROZEN_REVISED_POLICY_V2.payload()["fingerprint"]:
        raise ValueError("Selected candidate does not match the frozen V2 policy.")

    return {
        "schema": "reachy-stage3v-policy-v2-offline-diagnosis-v1",
        "status": "DEVELOPMENT_ONLY_REQUIRES_NEW_V2_HELD_OUT_CONFIRMATION",
        "v1_result_freeze_sha256": _sha256(V1_FREEZE_PATH),
        "v1_failed_result": {
            "safety_passed": freeze["safety_passed"],
            "direction_passed": freeze["direction_passed"],
            "coverage_passed": freeze["coverage_passed"],
            "accuracy_passed": freeze["accuracy_passed"],
        },
        "causal_diagnosis": (
            "Speech-positive endpoint samples and TRACKING_AXIS geometry samples were asynchronous. "
            "V1 required them to coincide repeatedly, so 159 matching geometry-eligible rows produced "
            "only nine source-confirmed rows and four moving trials."
        ),
        "controlled_change": (
            "Latch a speech-positive sample for a bounded interval, clear the latch on disagreement "
            "or camera faults, and otherwise retain the three-hit/600 ms spatial consensus, 10 degree "
            "geometry gate, 1500 ms disagreement lockout and visual target."
        ),
        "selection_rule": (
            "Across both now-development datasets require zero hard-negative movement rows, zero "
            "wrong-sign moves, at least two moving trials per heading and <=8 degree maximum target "
            "error; select the shortest tested speech latch."
        ),
        "datasets_are_not_v2_validation": True,
        "candidates": candidates,
        "selected_policy": selected["policy"],
        "selected_development_results": selected["datasets"],
        "robot_requests": 0,
        "camera_requests": 0,
        "cloud_requests": 0,
        "actuation_commands": 0,
        "contains_pixels": False,
        "contains_audio": False,
        "contains_transcript": False,
    }


def write_v2_diagnosis_artifacts() -> dict[str, Any]:
    result = run_v2_diagnosis()
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    V2_DIAGNOSIS_JSON_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    flat: list[dict[str, Any]] = []
    for candidate in result["candidates"]:
        row: dict[str, Any] = {
            **candidate["policy"],
            "passes_both": candidate["passes_all_development_gates_in_both_datasets"],
        }
        for dataset_name, evaluation in candidate["datasets"].items():
            row[f"{dataset_name}_positive_trials_with_move"] = evaluation["positive_trials_with_move"]
            row[f"{dataset_name}_hard_negative_would_move_rows"] = evaluation[
                "hard_negative_would_move_rows"
            ]
            row[f"{dataset_name}_per_heading_moves"] = "/".join(
                str(item["trials_with_move"]) for item in evaluation["heading_summary"]
            )
        flat.append(row)
    with V2_DIAGNOSIS_CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(flat[0]))
        writer.writeheader()
        writer.writerows(flat)

    selected = result["selected_policy"]
    policy_manifest = {
        "schema": "reachy-stage3v-revised-policy-freeze-v2",
        "status": "FROZEN_BEFORE_V2_HELD_OUT_COLLECTION",
        "development_evidence_only": True,
        "failed_v1_result_preserved": True,
        "not_authorized_for_actuation": True,
        "selection_rule": result["selection_rule"],
        "policy": selected,
        "development_results": result["selected_development_results"],
        "v1_result_freeze_sha256": result["v1_result_freeze_sha256"],
        "contains_pixels": False,
        "contains_audio": False,
        "contains_transcript": False,
        "robot_requests": 0,
        "cloud_requests": 0,
        "actuation_commands": 0,
    }
    V2_POLICY_MANIFEST_PATH.write_text(json.dumps(policy_manifest, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Stage 3V V2 offline diagnosis",
        "",
        "Status: **development-only; a new V2 held-out confirmation is required**.",
        "",
        "The failed V1 held-out result remains frozen and is now development evidence for V2.",
        "It cannot be used to validate V2.",
        "",
        "## Root cause",
        "",
        result["causal_diagnosis"],
        "",
        "## Controlled repair",
        "",
        result["controlled_change"],
        "",
        f"Frozen V2 policy fingerprint: `{selected['fingerprint']}`",
        "",
        "## Development replay",
        "",
        "| Dataset | Per-heading moving trials (−20/−10/+10/+20) | Hard-negative movement rows |",
        "|---|---:|---:|",
    ]
    for name, evaluation in result["selected_development_results"].items():
        moves = "/".join(str(item["trials_with_move"]) for item in evaluation["heading_summary"])
        lines.append(f"| {name} | {moves} | {evaluation['hard_negative_would_move_rows']} |")
    lines.extend(
        [
            "",
            "> This replay selected V2 on already observed data. It is not an unbiased validation and does not authorize movement.",
        ]
    )
    V2_DIAGNOSIS_REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result
