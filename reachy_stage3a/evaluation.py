"""Frozen Stage 3A replay, evaluation and report generation."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from reachy_stage2a.tournament import (
    PolicySpec,
    load_trial_rows,
    replay_policy,
    validate_manifest,
)

from .config import (
    ANALYSIS_DIR,
    DATA_DIR,
    MANIFEST_PATH,
    REPORT_PATH,
    SUMMARY_JSON_PATH,
    TRIAL_CSV_PATH,
)
from .controller import MotionEnvelope, MotionShadowController


STAGE3A_POLICY = PolicySpec(
    name="Stage 3A development-selected motion gate",
    kind="consensus",
    hold_ms=0.0,
    lockout_ms=1500.0,
    required_hits=3,
    window_ms=600.0,
    heading_tolerance_deg=8.0,
)


def load_frozen_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    validate_manifest(manifest, DATA_DIR)
    return manifest


def replay_motion_trial(
    entry: dict[str, Any],
    envelope: MotionEnvelope | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = load_trial_rows(DATA_DIR / entry["file"])
    evidence = replay_policy(STAGE3A_POLICY, rows)
    controller = MotionShadowController(envelope)
    decisions: list[dict[str, Any]] = []
    previous_action = "HOLD"
    episodes = 0
    for row, source in zip(rows, evidence):
        decision = controller.process(float(row.get("elapsed_ms") or 0.0), source)
        if decision.action != "HOLD" and previous_action == "HOLD":
            episodes += 1
        previous_action = decision.action
        decisions.append(
            {
                "sequence": row.get("sequence"),
                "elapsed_ms": row.get("elapsed_ms"),
                "speech_detected": row.get("speech_detected"),
                "acoustic_state": row.get("acoustic_state"),
                "face_count": row.get("face_count"),
                "source_confirmed": source.confirmed,
                **decision.as_dict(),
            }
        )
    would_move = sum(row["action"] == "WOULD_MOVE" for row in decisions)
    return_neutral = sum(row["action"] == "RETURN_NEUTRAL" for row in decisions)
    summary = {
        "step": entry["step"],
        "condition": entry["condition"],
        "role": entry["role"],
        "split": entry["split"],
        "repetition": entry["repetition"],
        "file": entry["file"],
        "rows": len(rows),
        "source_confirmed_rows": sum(item.confirmed for item in evidence),
        "would_move_rows": would_move,
        "return_neutral_rows": return_neutral,
        "motion_rows": would_move + return_neutral,
        "motion_episodes": episodes,
    }
    return decisions, summary


def _aggregate(rows: list[dict[str, Any]], split: str) -> dict[str, Any]:
    group = [row for row in rows if row["split"] == split]
    matching = [row for row in group if row["role"] == "matching_positive"]
    hard_negative = [row for row in group if row["role"] == "hard_negative"]
    boundary = [row for row in group if row["role"] == "boundary_challenge"]
    return {
        "split": split,
        "trials": len(group),
        "matching_trials": len(matching),
        "matching_trials_with_would_move": sum(row["would_move_rows"] > 0 for row in matching),
        "matching_would_move_rows": sum(row["would_move_rows"] for row in matching),
        "hard_negative_trials": len(hard_negative),
        "hard_negative_motion_rows": sum(row["motion_rows"] for row in hard_negative),
        "hard_negative_trials_with_motion": sum(row["motion_rows"] > 0 for row in hard_negative),
        "boundary_motion_rows": sum(row["motion_rows"] for row in boundary),
        "total_motion_rows": sum(row["motion_rows"] for row in group),
    }


def evaluate_motion_shadow(
    manifest: dict[str, Any] | None = None,
    envelope: MotionEnvelope | None = None,
) -> dict[str, Any]:
    manifest = manifest or load_frozen_manifest()
    envelope = envelope or MotionEnvelope()
    trial_rows = [replay_motion_trial(entry, envelope)[1] for entry in manifest["entries"]]
    summaries = [_aggregate(trial_rows, split) for split in ("development", "evaluation")]
    hard_negative_total = sum(row["hard_negative_motion_rows"] for row in summaries)
    return {
        "schema": "reachy-stage3a-offline-motion-shadow-v1",
        "status": "SHADOW_ONLY_NOT_APPROVED_FOR_ACTUATION",
        "selection_note": (
            "The temporal gate was selected on development repetitions only: among the "
            "tested zero-development-hard-negative candidates, 3 hits in 600 ms retained "
            "the greatest matching-row coverage. Evaluation remains retrospectively frozen."
        ),
        "manifest_fingerprint": manifest["fingerprint"],
        "policy": asdict(STAGE3A_POLICY),
        "envelope": asdict(envelope),
        "summary": summaries,
        "trials": trial_rows,
        "safety_gate_passed": hard_negative_total == 0,
        "contains_pixels": False,
        "contains_audio": False,
        "contains_transcript": False,
        "robot_requests": 0,
        "cloud_requests": 0,
        "actuation_commands": 0,
    }


def write_motion_shadow_artifacts() -> dict[str, Any]:
    artifact = evaluate_motion_shadow()
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON_PATH.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    trial_rows = artifact["trials"]
    with TRIAL_CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(trial_rows[0]))
        writer.writeheader()
        writer.writerows(trial_rows)
    development, evaluation = artifact["summary"]
    report = f"""# Stage 3A offline motion-shadow evaluation

Status: **{artifact['status']}**

The controller replays frozen, derived Stage 2A metadata. It cannot connect to
Reachy and cannot send a motion command.

## Frozen results

| Split | Matching trials with WOULD_MOVE | Hard-negative motion rows | Total motion rows |
|---|---:|---:|---:|
| Development | {development['matching_trials_with_would_move']} / {development['matching_trials']} | {development['hard_negative_motion_rows']} | {development['total_motion_rows']} |
| Evaluation | {evaluation['matching_trials_with_would_move']} / {evaluation['matching_trials']} | {evaluation['hard_negative_motion_rows']} | {evaluation['total_motion_rows']} |

Safety gate on this frozen matrix: **{'PASS' if artifact['safety_gate_passed'] else 'FAIL'}**.

This is retrospective internal evidence, not permission to actuate and not a
generalisation claim. A new supervised off-axis validation set is required
before any physical controller is considered.
"""
    REPORT_PATH.write_text(report, encoding="utf-8")
    return artifact
