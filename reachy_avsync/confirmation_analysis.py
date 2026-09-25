"""Outcome-blind, trial-level analysis for the AV-synchrony confirmation study.

The module reads only derived numeric CSV files.  It cannot open sensors,
contact a robot, identify a person, or issue an actuation command.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from statistics import median
from typing import Any, Callable, Iterable

import numpy as np

from .confirmation_protocol import confirmation_protocol_payload
from .synchrony import NumericSeries, SynchronySpec, evaluate_synchrony


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXECUTION_MANIFEST = (
    PROJECT_ROOT
    / "evidence"
    / "manifests"
    / "av_synchrony_confirmation_execution_v1.json"
)
REQUIRED_COLUMNS = [
    "timestamp_ms",
    "audio_dbfs",
    "lip_aperture",
    "face_scale",
    "face_count",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_numeric_trial(path: Path) -> dict[str, np.ndarray]:
    columns: list[list[float]] = [[] for _ in REQUIRED_COLUMNS]
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != REQUIRED_COLUMNS:
            raise ValueError(f"{path.name}: columns must be exactly {REQUIRED_COLUMNS}.")
        for row_number, row in enumerate(reader, 2):
            try:
                values = [float(row[key]) for key in REQUIRED_COLUMNS]
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{path.name}:{row_number}: nonnumeric value.") from exc
            if not all(math.isfinite(value) for value in values):
                raise ValueError(f"{path.name}:{row_number}: nonfinite value.")
            for target, value in zip(columns, values, strict=True):
                target.append(value)
    timestamps, audio, lip, scale, count_values = columns
    counts = np.asarray(count_values, dtype=float)
    if any(value not in (0.0, 1.0, 2.0) for value in counts):
        raise ValueError(f"{path.name}: face_count must be zero, one, or two.")
    audio_values = np.asarray(audio, dtype=float)
    lip_values = np.asarray(lip, dtype=float)
    scale_values = np.asarray(scale, dtype=float)
    if ((audio_values < -120.0) | (audio_values > 0.0)).any():
        raise ValueError(f"{path.name}: audio_dbfs must be in [-120, 0].")
    if ((lip_values < 0.0) | (lip_values > 1.0)).any():
        raise ValueError(f"{path.name}: lip_aperture must be in [0, 1].")
    if ((scale_values < 0.0) | (scale_values > 1.0)).any():
        raise ValueError(f"{path.name}: face_scale must be in [0, 1].")
    return {
        "timestamps_ms": np.asarray(timestamps, dtype=float),
        "audio_dbfs": audio_values,
        "lip_aperture": lip_values,
        "face_scale": scale_values,
        "face_count": counts.astype(int),
    }


def assess_quality(trial: dict[str, Any], data: dict[str, np.ndarray]) -> dict[str, Any]:
    gates = confirmation_protocol_payload()["quality_gates"]
    timestamps = data["timestamps_ms"]
    audio = data["audio_dbfs"]
    lip = data["lip_aperture"]
    scale = data["face_scale"]
    count = data["face_count"]
    failures: list[str] = []
    if len(timestamps) < int(gates["minimum_samples"]):
        failures.append("INSUFFICIENT_SAMPLES")
    differences = np.diff(timestamps)
    if len(timestamps) < 2 or (differences <= 0.0).any():
        failures.append("TIMESTAMPS_NOT_STRICTLY_INCREASING")
    span = float(timestamps[-1] - timestamps[0]) if len(timestamps) >= 2 else 0.0
    maximum_gap = float(differences.max(initial=0.0))
    if span < float(gates["minimum_span_ms"]):
        failures.append("OBSERVATION_SPAN_TOO_SHORT")
    if maximum_gap > float(gates["maximum_sample_gap_ms"]):
        failures.append("SAMPLE_GAP_EXCESSIVE")
    single = count == 1
    single_fraction = float(single.mean()) if len(single) else 0.0
    multiple_rows = int((count > 1).sum())
    if single_fraction < float(gates["minimum_single_face_fraction"]):
        failures.append("SINGLE_FACE_FRACTION_TOO_LOW")
    if multiple_rows > int(gates["multiple_face_rows_allowed"]):
        failures.append("MULTIPLE_FACES_OBSERVED")
    median_scale = float(np.median(scale[single])) if single.any() else 0.0
    if median_scale < float(gates["minimum_median_face_scale"]):
        failures.append("FACE_SCALE_TOO_SMALL")
    audio_std = float(np.std(audio)) if len(audio) else 0.0
    if audio_std < float(gates["minimum_audio_dbfs_std"]):
        failures.append("AUDIO_DYNAMIC_RANGE_TOO_LOW")
    lip_std = float(np.std(lip[single])) if single.any() else 0.0
    if (
        trial["condition_id"] in gates["motion_required_conditions"]
        and lip_std < float(gates["minimum_lip_aperture_std_when_motion_required"])
    ):
        failures.append("LIP_DYNAMIC_RANGE_TOO_LOW")
    valid_gaps = np.diff(timestamps[single])
    maximum_valid_gap = float(valid_gaps.max(initial=0.0))
    if maximum_valid_gap > float(gates["maximum_sample_gap_ms"]):
        failures.append("VALID_FACE_GAP_EXCESSIVE")
    return {
        "passed": not failures,
        "failures": failures,
        "sample_count": len(timestamps),
        "span_ms": span,
        "maximum_sample_gap_ms": maximum_gap,
        "single_face_fraction": single_fraction,
        "multiple_face_rows": multiple_rows,
        "median_face_scale": median_scale,
        "audio_dbfs_std": audio_std,
        "lip_aperture_std": lip_std,
        "maximum_valid_face_gap_ms": maximum_valid_gap,
    }


def _smooth(values: np.ndarray, samples: int) -> np.ndarray:
    if samples == 1:
        return values.copy()
    left = samples // 2
    right = samples - 1 - left
    padded = np.pad(values, (left, right), mode="edge")
    return np.convolve(padded, np.ones(samples, dtype=float) / samples, mode="valid")


def frozen_candidate_spec() -> SynchronySpec:
    candidate = confirmation_protocol_payload()["frozen_candidate"]
    gates = confirmation_protocol_payload()["quality_gates"]
    return SynchronySpec(
        min_correlation=float(candidate["min_correlation"]),
        max_abs_lag_ms=float(candidate["max_abs_lag_ms"]),
        min_audio_std=float(gates["minimum_audio_dbfs_std"]),
        min_mouth_std=float(gates["minimum_lip_aperture_std_when_motion_required"]),
        required_stable_windows=int(candidate["required_stable_windows"]),
        max_consensus_gap_ms=float(candidate["max_consensus_gap_ms"]),
    )


def evaluate_trial(trial: dict[str, Any], data: dict[str, np.ndarray]) -> dict[str, Any]:
    quality = assess_quality(trial, data)
    if not quality["passed"]:
        raise ValueError(
            f"{trial['trial_id']}: canonical file failed frozen quality gates: "
            + ",".join(quality["failures"])
        )
    valid = data["face_count"] == 1
    timestamps = data["timestamps_ms"][valid]
    smoothing = int(confirmation_protocol_payload()["frozen_candidate"]["moving_average_samples"])
    audio = _smooth(data["audio_dbfs"][valid], smoothing)
    lip = _smooth(data["lip_aperture"][valid], smoothing)
    score = evaluate_synchrony(
        NumericSeries.from_sequences(timestamps, audio),
        NumericSeries.from_sequences(timestamps, lip),
        frozen_candidate_spec(),
    )
    gates = confirmation_protocol_payload()["quality_gates"]
    audio_only = quality["audio_dbfs_std"] >= float(gates["minimum_audio_dbfs_std"])
    visual_only = quality["lip_aperture_std"] >= float(
        gates["minimum_lip_aperture_std_when_motion_required"]
    )
    candidate = score.status == "CANDIDATE"
    return {
        **{key: trial[key] for key in (
            "trial_id",
            "room",
            "visible_heading_deg",
            "condition_id",
            "role",
            "playback_voice_id",
            "playback_heading_deg",
        )},
        "quality": quality,
        "candidate_proposed": candidate,
        "candidate_status": score.status,
        "candidate_reason": score.reason,
        "candidate_correlation": score.correlation,
        "candidate_lag_ms": score.lag_ms,
        "acoustic_only_proposed": audio_only,
        "visual_only_proposed": visual_only,
        "non_abstaining_proposed": True,
        "spatial_design_proxy_proposed": trial["condition_id"]
        in {
            "live_visible_continuous",
            "live_visible_interrupted",
            "silent_face_colocated_playback",
            "silent_mouthing_shifted_playback",
            "live_speech_plus_opposite_playback",
        },
        "first_proposal_latency_ms": None,
        "observed_abstention_ms": quality["span_ms"] if not candidate else None,
        "heading_outcome_boundary": (
            "not measured by the five-column laptop instrument; a passing synchrony "
            "candidate would inherit the marked visible heading"
        ),
    }


def wilson_interval(successes: int, trials: int, z: float = 1.959963984540054) -> list[float]:
    if trials <= 0 or successes < 0 or successes > trials:
        raise ValueError("Wilson interval requires 0 <= successes <= trials and trials > 0.")
    proportion = successes / trials
    denominator = 1.0 + z * z / trials
    centre = (proportion + z * z / (2.0 * trials)) / denominator
    half_width = z * math.sqrt(
        proportion * (1.0 - proportion) / trials + z * z / (4.0 * trials * trials)
    ) / denominator
    return [max(0.0, centre - half_width), min(1.0, centre + half_width)]


def exact_mcnemar_pvalue(first_only: int, second_only: int) -> float:
    if first_only < 0 or second_only < 0:
        raise ValueError("Discordant counts must be nonnegative.")
    discordant = first_only + second_only
    if discordant == 0:
        return 1.0
    tail = sum(math.comb(discordant, k) for k in range(min(first_only, second_only) + 1))
    return min(1.0, 2.0 * tail / (2**discordant))


def _aggregate(outcomes: Iterable[dict[str, Any]], field: str) -> dict[str, Any]:
    rows = tuple(outcomes)
    positives = tuple(item for item in rows if item["role"] == "matching_positive")
    negatives = tuple(item for item in rows if item["role"] == "hard_negative")
    positive_proposals = sum(bool(item[field]) for item in positives)
    negative_proposals = sum(bool(item[field]) for item in negatives)
    result: dict[str, Any] = {
        "trials": len(rows),
        "matching_positive_trials": len(positives),
        "matching_positive_proposals": positive_proposals,
        "hard_negative_trials": len(negatives),
        "hard_negative_proposals": negative_proposals,
    }
    if positives:
        result["matching_positive_coverage"] = positive_proposals / len(positives)
        result["matching_positive_coverage_wilson95"] = wilson_interval(
            positive_proposals, len(positives)
        )
    if negatives:
        result["hard_negative_false_proposal_rate"] = negative_proposals / len(negatives)
        result["hard_negative_false_proposal_wilson95"] = wilson_interval(
            negative_proposals, len(negatives)
        )
    return result


def _stratify(outcomes: list[dict[str, Any]], field: str) -> dict[str, list[dict[str, Any]]]:
    dimensions: dict[str, Callable[[dict[str, Any]], str]] = {
        "room": lambda row: str(row["room"]),
        "condition": lambda row: str(row["condition_id"]),
        "visible_heading_deg": lambda row: str(row["visible_heading_deg"]),
        "playback_voice": lambda row: str(row["playback_voice_id"] or "none"),
    }
    result: dict[str, list[dict[str, Any]]] = {}
    for dimension, accessor in dimensions.items():
        levels = sorted({accessor(row) for row in outcomes})
        result[dimension] = [
            {"level": level, **_aggregate((row for row in outcomes if accessor(row) == level), field)}
            for level in levels
        ]
    return result


def analyze_confirmation(input_dir: Path) -> dict[str, Any]:
    protocol = confirmation_protocol_payload()
    schedule = protocol["randomization"]["schedule"]
    input_dir = input_dir.resolve()
    outcomes: list[dict[str, Any]] = []
    sources: list[dict[str, str]] = []
    for trial in schedule:
        filename = f"{trial['trial_id']}.csv"
        path = (input_dir / filename).resolve()
        if path.parent != input_dir or not path.is_file():
            raise FileNotFoundError(f"Missing confirmation trial: {filename}")
        data = load_numeric_trial(path)
        outcomes.append(evaluate_trial(trial, data))
        sources.append({"trial_id": trial["trial_id"], "file": filename, "sha256": sha256_file(path)})

    fields = {
        "frozen_synchrony_candidate": "candidate_proposed",
        "acoustic_only_activity": "acoustic_only_proposed",
        "visual_only_mouth_motion": "visual_only_proposed",
        "non_abstaining": "non_abstaining_proposed",
        "spatial_design_proxy": "spatial_design_proxy_proposed",
    }
    summaries = {name: _aggregate(outcomes, field) for name, field in fields.items()}
    candidate = summaries["frozen_synchrony_candidate"]
    hard_negatives = [row for row in outcomes if row["role"] == "hard_negative"]
    candidate_only = sum(
        row["candidate_proposed"] and not row["spatial_design_proxy_proposed"]
        for row in hard_negatives
    )
    proxy_only = sum(
        row["spatial_design_proxy_proposed"] and not row["candidate_proposed"]
        for row in hard_negatives
    )
    synchrony_rules_pass = (
        candidate["hard_negative_proposals"] == 0
        and candidate["matching_positive_proposals"] >= 15
    )
    bundle = "\n".join(
        f"{item['trial_id']}:{item['file']}:{item['sha256']}" for item in sources
    ).encode("utf-8")
    return {
        "schema": "reachy-av-synchrony-confirmation-analysis-v1",
        "status": (
            "SYNCHRONY_RULES_PASSED_SPATIAL_COMPARATOR_UNRESOLVED"
            if synchrony_rules_pass
            else "CONFIRMATION_CRITERIA_NOT_MET"
        ),
        "protocol_fingerprint": protocol["fingerprint"],
        "source_bundle_sha256": hashlib.sha256(bundle).hexdigest(),
        "sources": sources,
        "frozen_candidate_spec": asdict(frozen_candidate_spec()),
        "baseline_definitions": {
            "acoustic_only_activity": "proposal iff full-trial audio dBFS SD is at least 0.5 dB",
            "visual_only_mouth_motion": "proposal iff full-trial single-face lip-aperture SD is at least 0.002",
            "non_abstaining": "proposal on every accepted trial",
            "spatial_design_proxy": (
                "protocol-geometry proxy only; proposal when the design contains a source at "
                "the visible heading; this is not a replay of the frozen Stage 3V policy"
            ),
        },
        "summaries": summaries,
        "stratified_candidate_results": _stratify(outcomes, "candidate_proposed"),
        "paired_hard_negative_proxy_comparison": {
            "candidate_only": candidate_only,
            "proxy_only": proxy_only,
            "exact_two_sided_mcnemar_p": exact_mcnemar_pvalue(candidate_only, proxy_only),
            "boundary": "exploratory proxy comparison; not the frozen Stage 3V comparator",
        },
        "trial_outcomes": outcomes,
        "abstention_reasons": dict(
            Counter(row["candidate_reason"] for row in outcomes if not row["candidate_proposed"])
        ),
        "synchrony_rules_passed": synchrony_rules_pass,
        "full_v1_confirmation_passed": False,
        "unresolved_primary_endpoint": (
            "The five-column laptop instrument records no acoustic direction or Stage 3V "
            "policy inputs, so it cannot produce the frozen spatial comparator on these trials."
        ),
        "secondary_endpoint_boundary": (
            "Full-trial V2 scoring does not identify first-proposal latency; heading error and "
            "wrong-sign outcomes are not independently measured by this instrument."
        ),
        "robot_connections": 0,
        "actuation_commands": 0,
    }


__all__ = [
    "analyze_confirmation",
    "assess_quality",
    "evaluate_trial",
    "exact_mcnemar_pvalue",
    "frozen_candidate_spec",
    "load_numeric_trial",
    "wilson_interval",
]
