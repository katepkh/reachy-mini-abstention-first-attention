#!/usr/bin/env python3
"""Verify the public evidence bundle and its headline frozen claims.

This script intentionally uses only the Python standard library. It does not
open a network connection, camera, microphone, or robot transport.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence"
ANALYSIS = EVIDENCE / "analysis"
MANIFESTS = EVIDENCE / "manifests"


def fail(message: str) -> None:
    raise AssertionError(message)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def public_path(original: str) -> Path | None:
    path = original.replace("\\", "/")
    if path.startswith("data/stage4a_supervised_motion_pilot_v3/"):
        # The public bundle flattens the original sessions/ subdirectory.
        return EVIDENCE / "stage4a_v3" / Path(path).name
    mappings = (
        ("data/analysis/", ANALYSIS),
        ("data/manifests/", MANIFESTS),
        ("data/stage3v_confirmation_v3/", EVIDENCE / "stage3v_v3"),
        ("data/stage3p_cue_confirmation_v1/", EVIDENCE / "stage3p_cue_v1"),
        ("data/stage3p_cue_confirmation_v1_audit/", EVIDENCE / "stage3p_cue_v1_audit"),
    )
    for prefix, destination in mappings:
        if path.startswith(prefix):
            return destination / path.removeprefix(prefix)
    return None


def verify_listed_files(manifest_path: Path, expected_count: int) -> int:
    manifest = load_json(manifest_path)
    files = manifest["files"]
    require(manifest["file_count"] == expected_count, f"Unexpected file_count in {manifest_path.name}")
    require(len(files) == expected_count, f"Manifest list length mismatch in {manifest_path.name}")
    checked = 0
    for item in files:
        candidate = public_path(item["path"])
        if candidate is None:
            fail(f"No public path mapping for {item['path']}")
        require(candidate.is_file(), f"Missing public evidence file: {candidate.relative_to(ROOT)}")
        require(candidate.stat().st_size == item["bytes"], f"Size mismatch: {candidate.relative_to(ROOT)}")
        require(sha256(candidate) == item["sha256"], f"SHA-256 mismatch: {candidate.relative_to(ROOT)}")
        checked += 1
    return checked


def verify_stage2a() -> int:
    split = load_json(MANIFESTS / "stage2a_tournament_split_v1.json")
    result = load_json(ANALYSIS / "stage2a_policy_tournament_v1.json")
    require(len(split["entries"]) == 15, "Stage 2A split must contain 15 trials")
    require(split["frozen_after_full_matrix_inspection"] is True, "Stage 2A retrospective caveat changed")
    require(result["manifest_fingerprint"] == split["fingerprint"], "Stage 2A fingerprint mismatch")
    require(result["selected_policy"] == "3-hit safety consensus", "Stage 2A selected policy changed")

    checked = 0
    for entry in split["entries"]:
        for name_key, hash_key in (("file", "csv_sha256"), ("metadata_file", "metadata_sha256")):
            candidate = EVIDENCE / "stage2a_trials" / entry[name_key]
            require(candidate.is_file(), f"Missing Stage 2A evidence: {candidate.name}")
            require(sha256(candidate) == entry[hash_key], f"Stage 2A SHA-256 mismatch: {candidate.name}")
            checked += 1

    evaluation = {
        row["policy"]: row
        for row in result["summary"]
        if row["split"] == "evaluation"
    }
    recorded = evaluation["Recorded Stage 2A"]
    selected = evaluation["3-hit safety consensus"]
    require((recorded["matching_confirmed_rows"], recorded["matching_tracking_rows"]) == (24, 31), "Recorded matching result changed")
    require((recorded["hard_negative_confirmed_rows"], recorded["hard_negative_tracking_rows"]) == (5, 37), "Recorded hard-negative result changed")
    require((selected["matching_confirmed_rows"], selected["matching_tracking_rows"]) == (2, 31), "Selected matching result changed")
    require((selected["hard_negative_confirmed_rows"], selected["hard_negative_tracking_rows"]) == (0, 37), "Selected hard-negative result changed")

    matrix_report = (ANALYSIS / "stage2a_matrix_complete_v1.md").read_text(encoding="utf-8")
    for frozen_text in (
        "815 numeric observations; 801 valid DoA responses (98.28%)",
        "62 confirmations over 71 tracked rows (87.3%)",
        "13/63 tracked rows (20.6%)",
    ):
        require(frozen_text in matrix_report, f"Stage 2A report claim changed: {frozen_text}")
    return checked


def verify_stage3v() -> int:
    freeze_path = MANIFESTS / "stage3v_confirmation_result_v3_freeze.json"
    freeze = load_json(freeze_path)
    state = freeze["validated_state"]
    require(state["accepted_trials"] == 18 and state["all_csv_attempts"] == 21, "Stage 3V attempt counts changed")
    require(state["positive_trials_with_move"] == 12, "Stage 3V positive coverage changed")
    require(state["hard_negative_would_move_rows"] == 0, "Stage 3V hard-negative safety changed")
    require(state["wrong_sign_moves"] == 0, "Stage 3V direction result changed")
    require(abs(state["maximum_target_error_deg"] - 2.647237290037083) < 1e-12, "Stage 3V target error changed")
    require(all(state["gates"].values()), "A Stage 3V gate is not passing")
    return verify_listed_files(freeze_path, 69)


def verify_stage3p() -> int:
    freeze_path = MANIFESTS / "stage3p_association_gated_cue_confirmation_result_v1_freeze.json"
    state = load_json(freeze_path)["validated_state"]
    require((state["accepted_trials"], state["all_csv_attempts"], state["superseded_attempts"]) == (9, 18, 9), "Stage 3P attempt counts changed")
    require(state["transition_trials"] == 6 and state["fail_closed_controls"] == 3, "Stage 3P condition counts changed")
    require(all(state["gates"].values()) and state["overall_passed"] is True, "A Stage 3P gate is not passing")
    require(state["control_gate_authorised_adjustments"] == 0, "A Stage 3P control authorized movement")
    require(state["robot_requests"] == state["actuation_commands"] == state["cloud_requests"] == 0, "Stage 3P passive boundary changed")
    return verify_listed_files(freeze_path, 62)


def verify_stage4() -> int:
    freeze_path = MANIFESTS / "stage4a_supervised_motion_pilot_v3_diagnostic_freeze.json"
    freeze = load_json(freeze_path)
    state = freeze["validated_state"]
    require(state["physical_motion_trials"] == 1, "Stage 4 physical-trial count changed")
    require(state["total_head_only_commands"] == 2, "Stage 4 head-command count changed")
    require(state["total_body_yaw_commands"] == state["total_antenna_commands"] == state["total_torque_or_motor_mode_commands"] == 0, "Stage 4 command boundary changed")
    require(state["commanded_trial_mechanical_gate_passed"] is False, "Failed Stage 4 result was relabeled")
    require(abs(state["robust_measured_motion_from_baseline_deg"] - 1.3498870639247806) < 1e-12, "Stage 4 measured motion changed")
    require(abs(state["robust_target_to_requested_target_error_deg"] - 2.0794591418416877) < 1e-12, "Stage 4 target error changed")
    require(abs(state["robust_return_to_baseline_error_deg"] - 1.6778474296274293) < 1e-12, "Stage 4 return error changed")
    require(state["thresholds_weakened_after_outcome"] is False, "Stage 4 threshold history changed")
    require(freeze["scientific_boundary"]["v3_may_not_be_accepted"] is True, "Stage 4 scientific boundary changed")
    return verify_listed_files(freeze_path, 10)


def main() -> int:
    try:
        counts = {
            "Stage 2A": verify_stage2a(),
            "Stage 3V": verify_stage3v(),
            "Stage 3P": verify_stage3p(),
            "Stage 4A": verify_stage4(),
        }
    except (AssertionError, KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print("Evidence verification")
    for stage, count in counts.items():
        print(f"  {stage:<9} {count:>3} source files verified")
    print(f"  {'Total':<9} {sum(counts.values()):>3} source files verified")
    print("PASS: hashes, frozen states, command boundaries, and headline claims agree.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
