"""Frozen, offline counterfactual tournament for Stage 2A numeric metadata.

This module reads already-saved derived CSV files only. It has no robot, camera,
network, cloud, media or actuation capability.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .calibration import circular_distance_degrees
from .config import PROJECT_ROOT


MATRIX_DIR = PROJECT_ROOT / "data" / "stage2a"
ANALYSIS_DIR = PROJECT_ROOT / "data" / "analysis"
MANIFEST_PATH = PROJECT_ROOT / "data" / "manifests" / "stage2a_tournament_split_v1.json"
SUMMARY_CSV_PATH = ANALYSIS_DIR / "stage2a_policy_tournament_summary_v1.csv"
TRIAL_CSV_PATH = ANALYSIS_DIR / "stage2a_policy_tournament_trials_v1.csv"
SUMMARY_JSON_PATH = ANALYSIS_DIR / "stage2a_policy_tournament_v1.json"
REPORT_PATH = ANALYSIS_DIR / "stage2a_policy_tournament_v1.md"

_MATRIX_RE = re.compile(
    r"stage2a-matrix_(?P<step>\d{2})-of-15_(?P<condition>[a-z0-9-]+)_"
    r"take(?P<repetition>\d{2})_(?P<timestamp>\d{8}-\d{6})\.csv$"
)

ROLE_BY_CONDITION = {
    "visible-silent-face": "hard_negative",
    "speech-no-visible-face": "hard_negative",
    "matching-face-speech": "matching_positive",
    "mismatched-face-phone-right": "hard_negative",
    "partial-edge-face-speech": "boundary_challenge",
}

FLOAT_FIELDS = {
    "elapsed_ms", "raw_angle_rad", "raw_angle_deg", "http_latency_ms",
    "acoustic_confidence", "hypothesis_a_deg", "hypothesis_b_deg",
    "face_center_x_norm", "face_center_y_norm", "face_heading_deg",
    "face_confidence", "face_score_raw", "face_age_ms",
    "confirmed_heading_deg", "agreement_error_deg",
}
INT_FIELDS = {"sequence", "http_status", "face_count"}
BOOL_FIELDS = {"speech_detected", "face_detected"}


@dataclass(frozen=True, slots=True)
class PolicySpec:
    name: str
    kind: str
    hold_ms: float = 0.0
    lockout_ms: float = 0.0
    required_hits: int = 1
    window_ms: float = 0.0
    heading_tolerance_deg: float = 20.0


POLICY_SPECS = (
    PolicySpec("Recorded Stage 2A", "recorded"),
    PolicySpec("Current speech only", "current_speech"),
    PolicySpec(
        "Short hold 250 ms + disagreement reset",
        "short_hold",
        hold_ms=250.0,
        lockout_ms=750.0,
        heading_tolerance_deg=12.0,
    ),
    PolicySpec(
        "2-hit consensus + reset",
        "consensus",
        hold_ms=200.0,
        lockout_ms=750.0,
        required_hits=2,
        window_ms=600.0,
        heading_tolerance_deg=12.0,
    ),
    PolicySpec(
        "3-hit safety consensus",
        "consensus",
        hold_ms=0.0,
        lockout_ms=1000.0,
        required_hits=3,
        window_ms=900.0,
        heading_tolerance_deg=10.0,
    ),
)


@dataclass(frozen=True, slots=True)
class GeometryResult:
    eligible: bool
    heading_deg: float | None
    reason: str


@dataclass(frozen=True, slots=True)
class CounterfactualDecision:
    confirmed: bool
    heading_deg: float | None
    reason: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _coerce_value(name: str, value: str) -> Any:
    if value == "":
        return None
    if name in BOOL_FIELDS:
        return value.strip().lower() == "true"
    if name in INT_FIELDS:
        try:
            return int(float(value))
        except ValueError:
            return None
    if name in FLOAT_FIELDS:
        try:
            return float(value)
        except ValueError:
            return None
    return value


def load_trial_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [
            {name: _coerce_value(name, value) for name, value in row.items()}
            for row in csv.DictReader(handle)
        ]


def discover_accepted_matrix_files(data_dir: Path = MATRIX_DIR) -> tuple[Path, ...]:
    """Select the latest saved capture for each immutable matrix step."""
    by_step: dict[int, tuple[str, Path]] = {}
    for path in data_dir.glob("*.csv"):
        match = _MATRIX_RE.search(path.name)
        if not match:
            continue
        step = int(match.group("step"))
        candidate = (match.group("timestamp"), path)
        if step not in by_step or candidate[0] > by_step[step][0]:
            by_step[step] = candidate
    missing = [step for step in range(1, 16) if step not in by_step]
    if missing:
        raise ValueError(f"Stage 2A matrix is incomplete; missing steps: {missing}")
    return tuple(by_step[step][1] for step in range(1, 16))


def build_split_manifest(data_dir: Path = MATRIX_DIR) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for path in discover_accepted_matrix_files(data_dir):
        match = _MATRIX_RE.search(path.name)
        assert match is not None
        repetition = int(match.group("repetition"))
        condition = match.group("condition")
        metadata_path = path.with_name(path.stem + "_metadata.json")
        entries.append(
            {
                "step": int(match.group("step")),
                "condition": condition,
                "role": ROLE_BY_CONDITION[condition],
                "repetition": repetition,
                "split": "development" if repetition in {1, 2} else "evaluation",
                "file": path.name,
                "csv_sha256": _sha256(path),
                "metadata_file": metadata_path.name if metadata_path.exists() else None,
                "metadata_sha256": _sha256(metadata_path) if metadata_path.exists() else None,
            }
        )
    canonical = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
    fingerprint = hashlib.sha256(canonical).hexdigest()
    return {
        "schema": "reachy-stage2a-policy-tournament-split-v1",
        "frozen_after_full_matrix_inspection": True,
        "evaluation_status": "retrospectively_frozen_not_pristine_blind_holdout",
        "guardrail": (
            "Repetitions 1-2 are development and repetition 3 is evaluation. "
            "The complete matrix had already been inspected before formalising this split, "
            "so evaluation is comparative internal evidence, not an unbiased generalisation claim."
        ),
        "development_rule": "repetitions 1 and 2",
        "evaluation_rule": "repetition 3",
        "selection_rule": (
            "On development only: prefer zero hard-negative confirmed rows; then maximise "
            "matching-positive row coverage; then matching trial coverage. If none has zero, "
            "minimise hard-negative confirmations before maximising coverage."
        ),
        "fingerprint": fingerprint,
        "entries": entries,
    }


def validate_manifest(manifest: dict[str, Any], data_dir: Path = MATRIX_DIR) -> None:
    entries = manifest.get("entries", [])
    if len(entries) != 15:
        raise ValueError("Tournament manifest must contain exactly 15 accepted trials")
    if {entry["step"] for entry in entries} != set(range(1, 16)):
        raise ValueError("Tournament manifest must contain each matrix step exactly once")
    for entry in entries:
        path = data_dir / entry["file"]
        if not path.is_file() or _sha256(path) != entry["csv_sha256"]:
            raise ValueError(f"Frozen tournament file changed or is missing: {entry['file']}")


def geometry_result(row: dict[str, Any], max_error_deg: float = 20.0) -> GeometryResult:
    if row.get("http_status") != 200 or row.get("raw_angle_rad") is None:
        return GeometryResult(False, None, "NETWORK_INVALID")
    if row.get("acoustic_state") != "TRACKING_AXIS":
        return GeometryResult(False, None, "ACOUSTIC_NOT_TRACKING")
    if float(row.get("acoustic_confidence") or 0.0) < 0.60:
        return GeometryResult(False, None, "ACOUSTIC_LOW_CONFIDENCE")
    if int(row.get("face_count") or 0) == 0 or row.get("face_heading_deg") is None:
        return GeometryResult(False, None, "NO_FACE")
    if int(row.get("face_count") or 0) != 1:
        return GeometryResult(False, None, "MULTIPLE_FACES")
    if float(row.get("face_confidence") or 0.0) < 0.55:
        return GeometryResult(False, None, "FACE_LOW_CONFIDENCE")
    if float(row.get("face_age_ms") or 0.0) > 750.0:
        return GeometryResult(False, None, "CAMERA_OBSERVATION_STALE")
    face_heading = float(row["face_heading_deg"])
    hypotheses = [
        float(value)
        for value in (row.get("hypothesis_a_deg"), row.get("hypothesis_b_deg"))
        if value is not None
    ]
    matches = [
        value for value in hypotheses
        if circular_distance_degrees(face_heading, value) <= max_error_deg
    ]
    if len(matches) == 0:
        return GeometryResult(False, None, "ACOUSTIC_VISUAL_DISAGREEMENT")
    if len(matches) > 1:
        return GeometryResult(False, None, "VISUAL_HYPOTHESIS_AMBIGUOUS")
    return GeometryResult(True, matches[0], "ACOUSTIC_VISUAL_AGREEMENT")


class _ReplayPolicy:
    def __init__(self, spec: PolicySpec) -> None:
        self.spec = spec
        self.lockout_until_ms = -math.inf
        self.last_confirm_ms: float | None = None
        self.last_heading_deg: float | None = None
        self.hits: deque[tuple[float, float]] = deque()

    def _reset_track(self) -> None:
        self.last_confirm_ms = None
        self.last_heading_deg = None
        self.hits.clear()

    def _disagreement_reset(self, elapsed_ms: float, reason: str) -> None:
        if reason == "ACOUSTIC_VISUAL_DISAGREEMENT":
            self.lockout_until_ms = elapsed_ms + self.spec.lockout_ms
            self._reset_track()
        elif reason in {
            "NETWORK_INVALID", "NO_FACE", "MULTIPLE_FACES",
            "FACE_LOW_CONFIDENCE", "CAMERA_OBSERVATION_STALE",
        }:
            self._reset_track()

    def process(self, row: dict[str, Any]) -> CounterfactualDecision:
        elapsed = float(row.get("elapsed_ms") or 0.0)
        current_speech = row.get("speech_detected") is True

        if self.spec.kind == "recorded":
            confirmed = row.get("fusion_state") == "CONFIRMED"
            return CounterfactualDecision(
                confirmed,
                float(row["confirmed_heading_deg"]) if confirmed and row.get("confirmed_heading_deg") is not None else None,
                "RECORDED_CONFIRMATION" if confirmed else str(row.get("reason_code") or "WITHHELD"),
            )

        if self.spec.kind == "current_speech":
            confirmed = row.get("fusion_state") == "CONFIRMED" and current_speech
            return CounterfactualDecision(
                confirmed,
                float(row["confirmed_heading_deg"]) if confirmed and row.get("confirmed_heading_deg") is not None else None,
                "CURRENT_SPEECH_CONFIRMATION" if confirmed else "CURRENT_SPEECH_REQUIRED",
            )

        geometry = geometry_result(row)
        self._disagreement_reset(elapsed, geometry.reason)
        if elapsed < self.lockout_until_ms:
            return CounterfactualDecision(False, None, "DISAGREEMENT_LOCKOUT")

        direct = geometry.eligible and current_speech and geometry.heading_deg is not None
        if self.spec.kind == "short_hold":
            if direct:
                self.last_confirm_ms = elapsed
                self.last_heading_deg = geometry.heading_deg
                return CounterfactualDecision(True, geometry.heading_deg, "CURRENT_SPEECH_ACQUIRE")
            if (
                geometry.eligible
                and self.last_confirm_ms is not None
                and self.last_heading_deg is not None
                and elapsed - self.last_confirm_ms <= self.spec.hold_ms
                and circular_distance_degrees(geometry.heading_deg, self.last_heading_deg)
                <= self.spec.heading_tolerance_deg
            ):
                return CounterfactualDecision(True, geometry.heading_deg, "SHORT_HOLD")
            return CounterfactualDecision(False, None, geometry.reason)

        if self.spec.kind == "consensus":
            while self.hits and elapsed - self.hits[0][0] > self.spec.window_ms:
                self.hits.popleft()
            if direct:
                self.hits.append((elapsed, float(geometry.heading_deg)))
                stable_hits = [
                    hit for hit in self.hits
                    if circular_distance_degrees(hit[1], float(geometry.heading_deg))
                    <= self.spec.heading_tolerance_deg
                ]
                if len(stable_hits) >= self.spec.required_hits:
                    self.last_confirm_ms = elapsed
                    self.last_heading_deg = geometry.heading_deg
                    return CounterfactualDecision(True, geometry.heading_deg, "TEMPORAL_CONSENSUS")
                return CounterfactualDecision(False, None, "CONSENSUS_PENDING")
            if (
                geometry.eligible
                and self.spec.hold_ms > 0
                and self.last_confirm_ms is not None
                and self.last_heading_deg is not None
                and elapsed - self.last_confirm_ms <= self.spec.hold_ms
                and circular_distance_degrees(geometry.heading_deg, self.last_heading_deg)
                <= self.spec.heading_tolerance_deg
            ):
                return CounterfactualDecision(True, geometry.heading_deg, "CONSENSUS_SHORT_HOLD")
            return CounterfactualDecision(False, None, geometry.reason)

        raise ValueError(f"Unknown tournament policy kind: {self.spec.kind}")


def replay_policy(spec: PolicySpec, rows: Iterable[dict[str, Any]]) -> list[CounterfactualDecision]:
    policy = _ReplayPolicy(spec)
    return [policy.process(row) for row in rows]


def _episode_count(decisions: list[CounterfactualDecision]) -> int:
    episodes = 0
    previous = False
    for decision in decisions:
        if decision.confirmed and not previous:
            episodes += 1
        previous = decision.confirmed
    return episodes


def evaluate_trial(
    entry: dict[str, Any],
    spec: PolicySpec,
    data_dir: Path = MATRIX_DIR,
) -> dict[str, Any]:
    rows = load_trial_rows(data_dir / entry["file"])
    decisions = replay_policy(spec, rows)
    confirmed = sum(decision.confirmed for decision in decisions)
    tracking = sum(row.get("acoustic_state") == "TRACKING_AXIS" for row in rows)
    first_confirmation = next(
        (
            float(row.get("elapsed_ms") or 0.0)
            for row, decision in zip(rows, decisions)
            if decision.confirmed
        ),
        None,
    )
    return {
        "policy": spec.name,
        "split": entry["split"],
        "step": entry["step"],
        "condition": entry["condition"],
        "role": entry["role"],
        "repetition": entry["repetition"],
        "file": entry["file"],
        "rows": len(rows),
        "tracking_rows": tracking,
        "confirmed_rows": confirmed,
        "confirmed_pct": 100.0 * confirmed / len(rows) if rows else 0.0,
        "confirmed_per_tracking_pct": 100.0 * confirmed / tracking if tracking else 0.0,
        "confirmation_episodes": _episode_count(decisions),
        "first_confirmation_ms": first_confirmation,
    }


def aggregate_metrics(trials: list[dict[str, Any]]) -> dict[str, Any]:
    if not trials:
        raise ValueError("Cannot aggregate an empty tournament trial list")
    matching = [row for row in trials if row["role"] == "matching_positive"]
    negative = [row for row in trials if row["role"] == "hard_negative"]
    boundary = [row for row in trials if row["role"] == "boundary_challenge"]

    def total(rows: list[dict[str, Any]], field: str) -> int:
        return sum(int(row[field]) for row in rows)

    matching_rows = total(matching, "rows")
    matching_tracking = total(matching, "tracking_rows")
    matching_confirmed = total(matching, "confirmed_rows")
    negative_rows = total(negative, "rows")
    negative_tracking = total(negative, "tracking_rows")
    negative_confirmed = total(negative, "confirmed_rows")
    tracking = total(trials, "tracking_rows")
    confirmed = total(trials, "confirmed_rows")

    condition_confirms = {
        condition: total([row for row in trials if row["condition"] == condition], "confirmed_rows")
        for condition in ROLE_BY_CONDITION
    }
    return {
        "policy": trials[0]["policy"],
        "split": trials[0]["split"],
        "trials": len(trials),
        "rows": total(trials, "rows"),
        "tracking_rows": tracking,
        "confirmed_rows": confirmed,
        "matching_rows": matching_rows,
        "matching_tracking_rows": matching_tracking,
        "matching_confirmed_rows": matching_confirmed,
        "matching_coverage_pct": 100.0 * matching_confirmed / matching_rows if matching_rows else 0.0,
        "matching_tracked_coverage_pct": (
            100.0 * matching_confirmed / matching_tracking if matching_tracking else 0.0
        ),
        "matching_trials_with_confirmation": sum(row["confirmed_rows"] > 0 for row in matching),
        "matching_trials": len(matching),
        "hard_negative_rows": negative_rows,
        "hard_negative_tracking_rows": negative_tracking,
        "hard_negative_confirmed_rows": negative_confirmed,
        "hard_negative_false_confirmation_pct": 100.0 * negative_confirmed / negative_rows if negative_rows else 0.0,
        "hard_negative_false_per_tracking_pct": (
            100.0 * negative_confirmed / negative_tracking if negative_tracking else 0.0
        ),
        "hard_negative_trials_with_confirmation": sum(row["confirmed_rows"] > 0 for row in negative),
        "boundary_rows": total(boundary, "rows"),
        "boundary_confirmed_rows": total(boundary, "confirmed_rows"),
        "visible_silent_confirmed": condition_confirms["visible-silent-face"],
        "no_visible_face_confirmed": condition_confirms["speech-no-visible-face"],
        "mismatched_phone_confirmed": condition_confirms["mismatched-face-phone-right"],
        "partial_edge_confirmed": condition_confirms["partial-edge-face-speech"],
        "confirmation_episodes": total(trials, "confirmation_episodes"),
    }


def select_development_winner(summary_rows: list[dict[str, Any]]) -> str:
    development = [row for row in summary_rows if row["split"] == "development"]
    if not development:
        raise ValueError("Tournament has no development summaries")

    def rank(row: dict[str, Any]) -> tuple[float, ...]:
        false_count = int(row["hard_negative_confirmed_rows"])
        safety_class = 0 if false_count == 0 else 1
        return (
            safety_class,
            false_count,
            -float(row["matching_coverage_pct"]),
            -int(row["matching_trials_with_confirmation"]),
            int(row["confirmation_episodes"]),
        )

    return min(development, key=rank)["policy"]


def evaluate_tournament(
    manifest: dict[str, Any],
    data_dir: Path = MATRIX_DIR,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    validate_manifest(manifest, data_dir)
    trial_rows: list[dict[str, Any]] = []
    for spec in POLICY_SPECS:
        for entry in manifest["entries"]:
            trial_rows.append(evaluate_trial(entry, spec, data_dir))
    summary_rows: list[dict[str, Any]] = []
    for spec in POLICY_SPECS:
        for split in ("development", "evaluation"):
            group = [
                row for row in trial_rows
                if row["policy"] == spec.name and row["split"] == split
            ]
            summary_rows.append(aggregate_metrics(group))
    winner = select_development_winner(summary_rows)
    return summary_rows, trial_rows, winner


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _report_markdown(
    manifest: dict[str, Any],
    summaries: list[dict[str, Any]],
    winner: str,
) -> str:
    evaluation = [row for row in summaries if row["split"] == "evaluation"]
    development = [row for row in summaries if row["split"] == "development"]
    lines = [
        "# Stage 2A offline counterfactual policy tournament v1",
        "",
        f"Frozen evidence fingerprint: `{manifest['fingerprint']}`",
        "",
        "> This is a retrospective internal comparison, not a pristine blind holdout. The complete matrix had already been inspected before the split was formalised.",
        "",
        "## Fixed split and selection",
        "",
        "- Development: repetitions 1–2 (10 trials).",
        "- Evaluation: repetition 3 (5 trials).",
        "- Winner selected on development only using the frozen lexicographic safety rule in the manifest.",
        f"- Development-selected policy: **{winner}**.",
        "",
        "## Development comparison",
        "",
        "| Policy | Matching confirmations / tracked | Matching tracked coverage | Hard-negative confirmations / tracked | Hard-negative tracked false rate | Boundary confirmations |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in development:
        lines.append(
            f"| {row['policy']} | {row['matching_confirmed_rows']} / {row['matching_tracking_rows']} | "
            f"{row['matching_tracked_coverage_pct']:.2f}% | "
            f"{row['hard_negative_confirmed_rows']} / {row['hard_negative_tracking_rows']} | "
            f"{row['hard_negative_false_per_tracking_pct']:.2f}% | "
            f"{row['boundary_confirmed_rows']} |"
        )
    lines.extend([
        "",
        "## Retrospectively frozen evaluation",
        "",
        "| Policy | Matching confirmations / tracked | Matching tracked coverage | Hard-negative confirmations / tracked | Hard-negative tracked false rate | Silent / no-face / mismatch false confirms | Boundary confirmations |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for row in evaluation:
        lines.append(
            f"| {row['policy']} | {row['matching_confirmed_rows']} / {row['matching_tracking_rows']} | "
            f"{row['matching_tracked_coverage_pct']:.2f}% | "
            f"{row['hard_negative_confirmed_rows']} / {row['hard_negative_tracking_rows']} | "
            f"{row['hard_negative_false_per_tracking_pct']:.2f}% | "
            f"{row['visible_silent_confirmed']} / {row['no_visible_face_confirmed']} / "
            f"{row['mismatched_phone_confirmed']} | {row['boundary_confirmed_rows']} |"
        )
    winner_eval = next(row for row in evaluation if row["policy"] == winner)
    baseline_eval = next(row for row in evaluation if row["policy"] == "Recorded Stage 2A")
    lines.extend([
        "",
        "## Result",
        "",
        f"The development-selected policy was **{winner}**. On the retrospective evaluation repetition it confirmed "
        f"{winner_eval['hard_negative_confirmed_rows']} hard-negative rows at "
        f"{winner_eval['matching_confirmed_rows']}/{winner_eval['matching_tracking_rows']} tracked matching rows "
        f"({winner_eval['matching_tracked_coverage_pct']:.2f}%). The recorded policy confirmed "
        f"{baseline_eval['hard_negative_confirmed_rows']} hard-negative rows at "
        f"{baseline_eval['matching_confirmed_rows']}/{baseline_eval['matching_tracking_rows']} tracked matching rows "
        f"({baseline_eval['matching_tracked_coverage_pct']:.2f}%).",
        "",
        "The evaluation repetition also shows why this is a frontier rather than a deployment winner: "
        "the current-speech-only rule had zero hard-negative confirmations and higher matching coverage "
        "than the stricter consensus variants on that small retrospective split, while it was less safe "
        "on development. More independent repetitions are required to estimate that trade-off.",
        "",
        "This result measures a counterfactual decision rule on one robot, room and operator. It does not validate autonomous actuation, source identity or generalisation.",
    ])
    return "\n".join(lines) + "\n"


def write_tournament_artifacts() -> dict[str, Any]:
    manifest = build_split_manifest()
    summaries, trials, winner = evaluate_tournament(manifest)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    _write_csv(SUMMARY_CSV_PATH, summaries)
    _write_csv(TRIAL_CSV_PATH, trials)
    result = {
        "schema": "reachy-stage2a-policy-tournament-result-v1",
        "manifest_fingerprint": manifest["fingerprint"],
        "evaluation_status": manifest["evaluation_status"],
        "selected_policy": winner,
        "policies": [spec.__dict__ if hasattr(spec, "__dict__") else {
            "name": spec.name,
            "kind": spec.kind,
            "hold_ms": spec.hold_ms,
            "lockout_ms": spec.lockout_ms,
            "required_hits": spec.required_hits,
            "window_ms": spec.window_ms,
            "heading_tolerance_deg": spec.heading_tolerance_deg,
        } for spec in POLICY_SPECS],
        "summary": summaries,
        "contains_pixels": False,
        "contains_audio": False,
        "contains_transcript": False,
        "robot_requests": 0,
        "cloud_requests": 0,
        "actuation_commands": 0,
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    REPORT_PATH.write_text(_report_markdown(manifest, summaries, winner), encoding="utf-8")
    return result


if __name__ == "__main__":
    output = write_tournament_artifacts()
    print(json.dumps({
        "selected_policy": output["selected_policy"],
        "manifest_fingerprint": output["manifest_fingerprint"],
        "robot_requests": output["robot_requests"],
    }, indent=2))
