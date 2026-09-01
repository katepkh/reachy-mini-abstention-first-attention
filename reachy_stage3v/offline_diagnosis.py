"""Reproducible offline diagnosis and policy tournament for Stage 3V."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from statistics import median
from typing import Any

from reachy_doa.angles import physical_heading_to_expected_doa

from .analysis import load_rows
from .config import ANALYSIS_DIR, PROJECT_ROOT
from .protocol import VALIDATION_STEPS
from .revised_policy import (
    FROZEN_REVISED_POLICY,
    RevisedPolicySpec,
    aggregate_revised_trials,
    evaluate_revised_trial,
)


ORIGINAL_DATA_DIR = (PROJECT_ROOT / "data" / "stage3v").resolve()
ORIGINAL_PROGRESS_PATH = (ORIGINAL_DATA_DIR / "progress.json").resolve()
MANIFEST_DIR = (PROJECT_ROOT / "data" / "manifests").resolve()
DIAGNOSIS_JSON_PATH = (ANALYSIS_DIR / "stage3v_coverage_diagnosis_v1.json").resolve()
DIAGNOSIS_CSV_PATH = (ANALYSIS_DIR / "stage3v_policy_candidates_v1.csv").resolve()
DIAGNOSIS_REPORT_PATH = (ANALYSIS_DIR / "stage3v_coverage_diagnosis_v1.md").resolve()
POLICY_MANIFEST_PATH = (MANIFEST_DIR / "stage3v_revised_policy_v1.json").resolve()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _accepted_files() -> list[str]:
    payload = json.loads(ORIGINAL_PROGRESS_PATH.read_text(encoding="utf-8"))
    files = list(payload.get("accepted_csv_files", []))
    if int(payload.get("accepted_steps", 0)) != 18 or len(files) != 18:
        raise ValueError("The corrected Stage 3V development set is incomplete.")
    return files


def _candidate_specs() -> tuple[RevisedPolicySpec, ...]:
    specs = [
        RevisedPolicySpec(
            "Original Stage 3A gate",
            1.0,
            20.0,
            3,
            600.0,
            8.0,
            1500.0,
            "acoustic",
        ),
        RevisedPolicySpec(
            "Sign correction only",
            -1.0,
            20.0,
            3,
            600.0,
            8.0,
            1500.0,
            "acoustic",
        ),
    ]
    for maximum_error in (6.0, 8.0, 10.0, 12.0):
        for required_hits in (3, 2):
            for window_ms in (600.0, 900.0, 1200.0):
                for target_source in ("acoustic", "visual"):
                    is_frozen = (
                        maximum_error == 10.0
                        and required_hits == 2
                        and window_ms == 1200.0
                        and target_source == "visual"
                    )
                    specs.append(
                        RevisedPolicySpec(
                            name=(
                                FROZEN_REVISED_POLICY.name
                                if is_frozen
                                else (
                                    f"Sign corrected · error {maximum_error:.0f}° · "
                                    f"{required_hits} hits/{window_ms:.0f} ms · {target_source} target"
                                )
                            ),
                            face_heading_multiplier=-1.0,
                            maximum_geometry_error_deg=maximum_error,
                            required_hits=required_hits,
                            window_ms=window_ms,
                            heading_tolerance_deg=8.0,
                            disagreement_lockout_ms=1500.0,
                            target_source=target_source,
                        )
                    )
    return tuple(specs)


def _median(values: list[float]) -> float | None:
    return median(values) if values else None


def _trial_diagnostics(step: Any, filename: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    faces = [float(row["face_heading_deg"]) for row in rows if row.get("face_heading_deg") is not None]
    speech_rows = [row for row in rows if row.get("speech_detected") is True]
    speech_doa = [float(row["raw_angle_deg"]) for row in speech_rows if row.get("raw_angle_deg") is not None]
    expected = (
        physical_heading_to_expected_doa(float(step.sound_heading_deg))
        if step.sound_heading_deg is not None
        else None
    )
    return {
        "step": step.index,
        "condition": step.condition_id,
        "role": step.role,
        "true_heading_deg": step.true_heading_deg,
        "file": filename,
        "rows": len(rows),
        "speech_positive": len(speech_rows),
        "speech_positive_pct": 100.0 * len(speech_rows) / len(rows) if rows else 0.0,
        "median_stored_face_heading_deg": _median(faces),
        "median_diagram_face_heading_deg": _median([-value for value in faces]),
        "expected_doa_deg": expected,
        "median_speech_positive_doa_deg": _median(speech_doa),
        "doa_bias_deg": (
            _median(speech_doa) - expected
            if speech_doa and expected is not None
            else None
        ),
    }


def run_diagnosis() -> dict[str, Any]:
    files = _accepted_files()
    loaded = [load_rows(ORIGINAL_DATA_DIR / filename) for filename in files]
    trial_diagnostics = [
        _trial_diagnostics(step, filename, rows)
        for step, filename, rows in zip(VALIDATION_STEPS, files, loaded)
    ]
    candidates: list[dict[str, Any]] = []
    for spec in _candidate_specs():
        trials = [
            {**evaluate_revised_trial(step, rows, spec), "file": filename}
            for step, filename, rows in zip(VALIDATION_STEPS, files, loaded)
        ]
        aggregate = aggregate_revised_trials(trials)
        candidates.append(
            {
                "name": spec.name,
                "policy_fingerprint": spec.payload()["fingerprint"],
                "face_heading_multiplier": spec.face_heading_multiplier,
                "maximum_geometry_error_deg": spec.maximum_geometry_error_deg,
                "required_hits": spec.required_hits,
                "window_ms": spec.window_ms,
                "target_source": spec.target_source,
                **{key: value for key, value in aggregate.items() if key != "heading_summary"},
                "heading_summary": aggregate["heading_summary"],
                "passes_all_development_gates": all(
                    aggregate[key]
                    for key in (
                        "safety_passed",
                        "direction_passed",
                        "coverage_passed",
                        "accuracy_passed",
                    )
                ),
            }
        )

    passing = [row for row in candidates if row["passes_all_development_gates"]]
    if not passing:
        raise ValueError("No candidate passed the frozen development gates.")
    passing.sort(
        key=lambda row: (
            float(row["maximum_geometry_error_deg"]),
            -int(row["required_hits"]),
            float(row["window_ms"]),
            0 if row["target_source"] == "visual" else 1,
        )
    )
    selected = passing[0]
    frozen_payload = FROZEN_REVISED_POLICY.payload()
    if selected["policy_fingerprint"] != frozen_payload["fingerprint"]:
        raise ValueError("The selected candidate does not match the frozen revised policy.")

    file_manifest = [
        {"step": step.index, "file": filename, "sha256": _sha256(ORIGINAL_DATA_DIR / filename)}
        for step, filename in zip(VALIDATION_STEPS, files)
    ]
    hard_negative_speech = [
        {
            "step": row["step"],
            "condition": row["condition"],
            "speech_positive": row["speech_positive"],
            "speech_positive_pct": row["speech_positive_pct"],
        }
        for row in trial_diagnostics
        if row["role"] == "hard_negative"
    ]
    result = {
        "schema": "reachy-stage3v-coverage-diagnosis-v1",
        "status": "DEVELOPMENT_ONLY_REQUIRES_NEW_HELD_OUT_CONFIRMATION",
        "development_set": {
            "trials": 18,
            "matching_trials": 12,
            "hard_negative_trials": 6,
            "full_dataset_previously_inspected": True,
            "files": file_manifest,
        },
        "findings": {
            "camera_to_diagram_sign": (
                "Stored camera-right face headings have the opposite sign to the frozen "
                "diagram-left-negative floor frame; multiply stored face heading by -1."
            ),
            "target_geometry": (
                "Use the unique acoustic hypothesis to disambiguate the physical side, then "
                "use the sign-corrected visual bearing as the bounded target. The acoustic "
                "hypotheses were biased inward at the outer headings."
            ),
            "temporal_gate": (
                "Three current-speech hits inside 600 ms suppressed valid trials. The smallest "
                "tested gate that met all development criteria was two hits inside 1200 ms."
            ),
            "speech_flag": (
                "Speech-positive rows occurred in silent-face controls, so the flag is not proof "
                "of live speech. A strict 10° acoustic/visual geometry gate is still required."
            ),
            "outer_angle_doa": (
                "Observed ±20° speech DoA values were generally pulled toward the front axis; "
                "the acoustic estimate should disambiguate side rather than set final gaze."
            ),
        },
        "hard_negative_speech": hard_negative_speech,
        "trial_diagnostics": trial_diagnostics,
        "candidates": candidates,
        "selection_rule": (
            "Require zero hard-negative WOULD_MOVE rows, zero wrong-sign moves, at least two "
            "moving trials per heading and <=8° maximum error. Among passing candidates choose "
            "the smallest geometry tolerance, then more hits, then the shortest window."
        ),
        "selected_policy": frozen_payload,
        "selected_development_result": selected,
        "robot_requests": 0,
        "camera_requests": 0,
        "cloud_requests": 0,
        "actuation_commands": 0,
        "contains_pixels": False,
        "contains_audio": False,
        "contains_transcript": False,
    }
    return result


def write_diagnosis_artifacts() -> dict[str, Any]:
    result = run_diagnosis()
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    DIAGNOSIS_JSON_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    flat_candidates = []
    for row in result["candidates"]:
        flat_candidates.append({key: value for key, value in row.items() if key != "heading_summary"})
    with DIAGNOSIS_CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(flat_candidates[0]))
        writer.writeheader()
        writer.writerows(flat_candidates)

    selected = result["selected_development_result"]
    policy_manifest = {
        "schema": "reachy-stage3v-revised-policy-freeze-v1",
        "status": "FROZEN_BEFORE_NEW_CONFIRMATION_COLLECTION",
        "development_evidence_only": True,
        "not_authorized_for_actuation": True,
        "selection_rule": result["selection_rule"],
        "policy": result["selected_policy"],
        "development_result": selected,
        "development_files": result["development_set"]["files"],
        "contains_pixels": False,
        "contains_audio": False,
        "contains_transcript": False,
        "robot_requests": 0,
        "cloud_requests": 0,
        "actuation_commands": 0,
    }
    POLICY_MANIFEST_PATH.write_text(
        json.dumps(policy_manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    heading_rows = selected["heading_summary"]
    lines = [
        "# Stage 3V offline coverage diagnosis",
        "",
        "Status: **development-only; a new held-out run is required**.",
        "",
        "## Root causes",
        "",
        "1. The camera and floor-diagram heading signs were opposite.",
        "2. The original policy used the inward-biased acoustic hypothesis as the final target.",
        "3. Three speech-positive hits in 600 ms were too sparse for most matching trials.",
        "4. Silent controls contained speech-positive endpoint rows, so relaxing speech alone is unsafe.",
        "5. Outer-angle DoA estimates were biased toward the front axis.",
        "",
        "## Frozen revised policy",
        "",
        f"Fingerprint: `{result['selected_policy']['fingerprint']}`",
        "",
        "- Negate stored face heading into the floor-diagram frame.",
        "- Require one acoustic hypothesis within 10° of that visual bearing.",
        "- Require two current-speech matches inside 1200 ms.",
        "- Keep the 1500 ms disagreement lockout and 8° hit stability tolerance.",
        "- Use the visual bearing—not the biased acoustic hypothesis—as the bounded shadow target.",
        "",
        "## Development replay only",
        "",
        "| Heading | Trials with shadow move | Maximum target error | Coverage | Accuracy |",
        "|---:|---:|---:|---:|---:|",
    ]
    for row in heading_rows:
        lines.append(
            f"| {row['heading_deg']:+.0f}° | {row['trials_with_move']}/{row['trials']} | "
            f"{row['maximum_target_error_deg']:.2f}° | "
            f"{'PASS' if row['coverage_passed'] else 'FAIL'} | "
            f"{'PASS' if row['accuracy_passed'] else 'FAIL'} |"
        )
    lines.extend(
        [
            "",
            f"Hard-negative movement rows: **{selected['hard_negative_would_move_rows']}**.",
            "",
            "> These results selected the policy on already-inspected data. They are not an unbiased validation and do not authorize movement.",
        ]
    )
    DIAGNOSIS_REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result
