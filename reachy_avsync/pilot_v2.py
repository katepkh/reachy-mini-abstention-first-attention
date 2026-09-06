"""Offline analysis for the face-landmark replacement development pilot."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import asdict, dataclass, replace
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np

from .pilot_v2_protocol import canonical_pilot_v2_trials, pilot_v2_protocol_payload
from .synchrony import NumericSeries, SynchronySpec, evaluate_synchrony


@dataclass(frozen=True, slots=True)
class PilotV2Input:
    timestamps_ms: tuple[float, ...]
    audio_dbfs: tuple[float, ...]
    lip_aperture: tuple[float, ...]
    face_scale: tuple[float, ...]
    face_count: tuple[int, ...]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_pilot_v2_trial(path: Path) -> PilotV2Input:
    required = pilot_v2_protocol_payload()["required_columns"]
    columns: list[list[float]] = [[] for _ in required]
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != required:
            raise ValueError(f"{path.name}: columns must be exactly {required}.")
        for row_number, row in enumerate(reader, 2):
            try:
                values = [float(row[key]) for key in required]
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{path.name}:{row_number}: nonnumeric value.") from exc
            if not all(math.isfinite(value) for value in values):
                raise ValueError(f"{path.name}:{row_number}: nonfinite value.")
            for target, value in zip(columns, values):
                target.append(value)
    timestamps, audio, lip, scale, face_count_float = columns
    face_count = [int(value) for value in face_count_float]
    if any(float(integer) != value or integer < 0 or integer > 2 for integer, value in zip(face_count, face_count_float)):
        raise ValueError(f"{path.name}: face_count must be an integer from zero to two.")
    if any(not -120.0 <= value <= 0.0 for value in audio):
        raise ValueError(f"{path.name}: audio_dbfs must be in [-120, 0].")
    if any(not 0.0 <= value <= 1.0 for value in lip):
        raise ValueError(f"{path.name}: lip_aperture must be in [0, 1].")
    if any(not 0.0 <= value <= 1.0 for value in scale):
        raise ValueError(f"{path.name}: face_scale must be in [0, 1].")
    return PilotV2Input(
        tuple(timestamps), tuple(audio), tuple(lip), tuple(scale), tuple(face_count)
    )


def assess_pilot_v2_quality(trial: dict[str, Any], data: PilotV2Input) -> dict[str, Any]:
    gates = pilot_v2_protocol_payload()["quality_gates"]
    timestamps = np.asarray(data.timestamps_ms, dtype=float)
    audio = np.asarray(data.audio_dbfs, dtype=float)
    lip = np.asarray(data.lip_aperture, dtype=float)
    scale = np.asarray(data.face_scale, dtype=float)
    count = np.asarray(data.face_count, dtype=int)
    failures: list[str] = []
    if len(timestamps) < int(gates["minimum_samples"]):
        failures.append("INSUFFICIENT_SAMPLES")
    differences = np.diff(timestamps)
    if len(timestamps) < 2 or (differences <= 0.0).any():
        failures.append("TIMESTAMPS_NOT_STRICTLY_INCREASING")
    span = float(timestamps[-1] - timestamps[0]) if len(timestamps) >= 2 else 0.0
    max_gap = float(differences.max(initial=0.0))
    if span < float(gates["minimum_span_ms"]):
        failures.append("OBSERVATION_SPAN_TOO_SHORT")
    if max_gap > float(gates["maximum_sample_gap_ms"]):
        failures.append("SAMPLE_GAP_EXCESSIVE")
    single = count == 1
    single_fraction = float(single.mean()) if len(single) else 0.0
    multiple_rows = int((count > 1).sum())
    if single_fraction < float(gates["minimum_single_face_fraction"]):
        failures.append("SINGLE_FACE_FRACTION_TOO_LOW")
    if multiple_rows > int(gates["multiple_face_rows_allowed"]):
        failures.append("MULTIPLE_FACES_OBSERVED")
    valid_scale = scale[single]
    median_scale = float(np.median(valid_scale)) if len(valid_scale) else 0.0
    if median_scale < float(gates["minimum_median_face_scale"]):
        failures.append("FACE_SCALE_TOO_SMALL")
    audio_std = float(np.std(audio)) if len(audio) else 0.0
    if audio_std < float(gates["minimum_audio_dbfs_std"]):
        failures.append("AUDIO_DYNAMIC_RANGE_TOO_LOW")
    valid_lip = lip[single]
    lip_std = float(np.std(valid_lip)) if len(valid_lip) else 0.0
    if (
        trial["condition_id"] in gates["motion_required_conditions"]
        and lip_std < float(gates["minimum_lip_aperture_std_when_motion_required"])
    ):
        failures.append("LIP_DYNAMIC_RANGE_TOO_LOW")
    valid_timestamps = timestamps[single]
    valid_gaps = np.diff(valid_timestamps)
    max_valid_gap = float(valid_gaps.max(initial=0.0))
    if max_valid_gap > float(gates["maximum_sample_gap_ms"]):
        failures.append("VALID_FACE_GAP_EXCESSIVE")
    return {
        "trial_id": trial["trial_id"],
        "condition_id": trial["condition_id"],
        "split": trial["split"],
        "role": trial["role"],
        "passed": not failures,
        "failures": failures,
        "sample_count": len(timestamps),
        "span_ms": span,
        "maximum_sample_gap_ms": max_gap,
        "single_face_fraction": single_fraction,
        "multiple_face_rows": multiple_rows,
        "median_face_scale": median_scale,
        "audio_dbfs_std": audio_std,
        "lip_aperture_std": lip_std,
        "maximum_valid_face_gap_ms": max_valid_gap,
    }


def _smooth(values: np.ndarray, samples: int) -> np.ndarray:
    if samples == 1:
        return values.copy()
    left = samples // 2
    right = samples - 1 - left
    padded = np.pad(values, (left, right), mode="edge")
    return np.convolve(padded, np.ones(samples, dtype=float) / samples, mode="valid")


def pilot_v2_candidate_specs() -> list[tuple[SynchronySpec, int]]:
    payload = pilot_v2_protocol_payload()
    grid = payload["threshold_grid"]
    gates = payload["quality_gates"]
    return [
        (
            replace(
                SynchronySpec(),
                min_correlation=correlation,
                max_abs_lag_ms=lag,
                min_audio_std=float(gates["minimum_audio_dbfs_std"]),
                min_mouth_std=float(gates["minimum_lip_aperture_std_when_motion_required"]),
            ),
            int(smoothing),
        )
        for correlation, lag, smoothing in product(
            grid["min_correlation"],
            grid["max_abs_lag_ms"],
            grid["moving_average_samples"],
        )
    ]


def _evaluate_setting(
    spec: SynchronySpec,
    smoothing: int,
    loaded: list[tuple[dict[str, Any], PilotV2Input, dict[str, Any]]],
) -> dict[str, Any]:
    trials: list[dict[str, Any]] = []
    for trial, data, quality in loaded:
        if not quality["passed"]:
            trials.append(
                {
                    "trial_id": trial["trial_id"],
                    "condition_id": trial["condition_id"],
                    "split": trial["split"],
                    "role": trial["role"],
                    "candidate": False,
                    "status": "ABSTAIN",
                    "reason": "QUALITY_GATE_FAILED:" + ",".join(quality["failures"]),
                    "correlation": None,
                    "lag_ms": None,
                }
            )
            continue
        valid = np.asarray(data.face_count, dtype=int) == 1
        timestamps = np.asarray(data.timestamps_ms, dtype=float)[valid]
        audio = _smooth(np.asarray(data.audio_dbfs, dtype=float)[valid], smoothing)
        lip = _smooth(np.asarray(data.lip_aperture, dtype=float)[valid], smoothing)
        score = evaluate_synchrony(
            NumericSeries.from_sequences(timestamps, audio),
            NumericSeries.from_sequences(timestamps, lip),
            spec,
        )
        trials.append(
            {
                "trial_id": trial["trial_id"],
                "condition_id": trial["condition_id"],
                "split": trial["split"],
                "role": trial["role"],
                "candidate": score.status == "CANDIDATE",
                "status": score.status,
                "reason": score.reason,
                "correlation": score.correlation,
                "lag_ms": score.lag_ms,
            }
        )
    development = [trial for trial in trials if trial["split"] == "development"]
    positives = [trial for trial in development if trial["role"] == "matching_positive"]
    negatives = [trial for trial in development if trial["role"] == "hard_negative"]
    positive_candidates = sum(trial["candidate"] for trial in positives)
    negative_candidates = sum(trial["candidate"] for trial in negatives)
    development_quality_passed = all(
        quality["passed"] for trial, _, quality in loaded if trial["split"] == "development"
    )
    return {
        "spec": asdict(spec),
        "moving_average_samples": smoothing,
        "development_matching_positive_candidates": positive_candidates,
        "development_matching_positive_trials": len(positives),
        "development_hard_negative_candidates": negative_candidates,
        "development_hard_negative_trials": len(negatives),
        "development_quality_passed": development_quality_passed,
        "eligible": (
            development_quality_passed
            and negative_candidates == 0
            and positive_candidates >= 3
        ),
        "trials": trials,
    }


def _selection_key(result: dict[str, Any]) -> tuple[float, ...]:
    spec = result["spec"]
    return (
        float(result["development_matching_positive_candidates"]),
        float(spec["min_correlation"]),
        -float(spec["max_abs_lag_ms"]),
        -float(result["moving_average_samples"]),
    )


def analyze_pilot_v2(input_dir: Path) -> dict[str, Any]:
    input_dir = input_dir.resolve()
    loaded: list[tuple[dict[str, Any], PilotV2Input, dict[str, Any]]] = []
    sources: list[dict[str, str]] = []
    for trial in canonical_pilot_v2_trials():
        filename = f"{trial['trial_id']}.csv"
        path = (input_dir / filename).resolve()
        if path.parent != input_dir or not path.is_file():
            raise FileNotFoundError(f"Missing V2 pilot trial: {filename}")
        data = load_pilot_v2_trial(path)
        quality = assess_pilot_v2_quality(trial, data)
        loaded.append((trial, data, quality))
        sources.append({"trial_id": trial["trial_id"], "file": filename, "sha256": _sha256(path)})

    settings = [
        _evaluate_setting(spec, smoothing, loaded)
        for spec, smoothing in pilot_v2_candidate_specs()
    ]
    eligible = [setting for setting in settings if setting["eligible"]]
    selected = max(eligible, key=_selection_key) if eligible else None
    validation: dict[str, Any] | None = None
    if selected is not None:
        trials = [trial for trial in selected["trials"] if trial["split"] == "internal_validation"]
        positives = [trial for trial in trials if trial["role"] == "matching_positive"]
        negatives = [trial for trial in trials if trial["role"] == "hard_negative"]
        validation_quality_passed = all(
            quality["passed"]
            for trial, _, quality in loaded
            if trial["split"] == "internal_validation"
        )
        validation = {
            "quality_passed": validation_quality_passed,
            "matching_positive_candidates": sum(trial["candidate"] for trial in positives),
            "matching_positive_trials": len(positives),
            "hard_negative_candidates": sum(trial["candidate"] for trial in negatives),
            "hard_negative_trials": len(negatives),
            "passed": (
                validation_quality_passed
                and sum(trial["candidate"] for trial in positives) == 2
                and sum(trial["candidate"] for trial in negatives) == 0
            ),
            "trials": trials,
        }
    validation_passed = bool(validation and validation["passed"])
    if selected is None:
        status = "DEVELOPMENT_INSTRUMENT_REJECTED_NO_THRESHOLD"
    elif not validation_passed:
        status = "DEVELOPMENT_CANDIDATE_FAILED_INTERNAL_VALIDATION"
    else:
        status = "DEVELOPMENT_CANDIDATE_AWAITS_SEPARATE_CODE_THRESHOLD_FREEZE"
    bundle = "\n".join(
        f"{item['trial_id']}:{item['file']}:{item['sha256']}" for item in sources
    ).encode("utf-8")
    return {
        "schema": "reachy-av-synchrony-off-robot-pilot-result-v2",
        "status": status,
        "protocol_fingerprint": pilot_v2_protocol_payload()["fingerprint"],
        "source_bundle_sha256": hashlib.sha256(bundle).hexdigest(),
        "sources": sources,
        "trial_quality": [quality for _, _, quality in loaded],
        "candidate_count": len(settings),
        "eligible_development_candidate_count": len(eligible),
        "selected_candidate": selected,
        "development_selection_succeeded": selected is not None,
        "internal_validation": validation,
        "internal_validation_passed": validation_passed,
        "all_candidates": [
            {key: value for key, value in setting.items() if key != "trials"}
            for setting in settings
        ],
        "robot_connections": 0,
        "actuation_commands": 0,
        "claim_boundary": (
            "A passing development result would justify only a separate code-and-threshold "
            "freeze. It would not be confirmation, identity, authorization, or robot evidence."
        ),
    }

