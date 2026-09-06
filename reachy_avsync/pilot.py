"""Offline loader and deterministic threshold search for the development pilot."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import asdict, replace
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np

from .pilot_protocol import canonical_pilot_trials, pilot_protocol_payload
from .synchrony import NumericSeries, SynchronySpec, evaluate_synchrony


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_numeric_trial(path: Path) -> tuple[NumericSeries, NumericSeries]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = ["timestamp_ms", "audio_energy", "mouth_motion"]
        if reader.fieldnames != required:
            raise ValueError(f"{path.name}: columns must be exactly {required}.")
        timestamps: list[float] = []
        audio: list[float] = []
        mouth: list[float] = []
        for row_number, row in enumerate(reader, 2):
            try:
                values = tuple(float(row[key]) for key in required)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{path.name}:{row_number}: nonnumeric value.") from exc
            if not all(math.isfinite(value) for value in values):
                raise ValueError(f"{path.name}:{row_number}: nonfinite value.")
            timestamp, audio_value, mouth_value = values
            timestamps.append(timestamp)
            audio.append(audio_value)
            mouth.append(mouth_value)
    if len(timestamps) < 30:
        raise ValueError(f"{path.name}: fewer than 30 samples.")
    differences = np.diff(np.asarray(timestamps, dtype=float))
    if (differences <= 0.0).any():
        raise ValueError(f"{path.name}: timestamps are not strictly increasing.")
    if float(differences.max(initial=0.0)) > 160.0:
        raise ValueError(f"{path.name}: sample gap exceeds 160 ms.")
    if timestamps[-1] - timestamps[0] < 1200.0:
        raise ValueError(f"{path.name}: observation span is shorter than 1200 ms.")
    return (
        NumericSeries.from_sequences(timestamps, audio),
        NumericSeries.from_sequences(timestamps, mouth),
    )


def candidate_specs() -> list[SynchronySpec]:
    grid = pilot_protocol_payload()["threshold_grid"]
    base = SynchronySpec()
    return [
        replace(
            base,
            min_correlation=correlation,
            max_abs_lag_ms=lag,
            min_audio_std=audio_std,
            min_mouth_std=mouth_std,
        )
        for correlation, lag, audio_std, mouth_std in product(
            grid["min_correlation"],
            grid["max_abs_lag_ms"],
            grid["min_audio_std"],
            grid["min_mouth_std"],
        )
    ]


def _evaluate_spec(
    spec: SynchronySpec,
    loaded: list[tuple[dict[str, Any], NumericSeries, NumericSeries]],
) -> dict[str, Any]:
    trials: list[dict[str, Any]] = []
    for trial, audio, mouth in loaded:
        score = evaluate_synchrony(audio, mouth, spec)
        trials.append(
            {
                "trial_id": trial["trial_id"],
                "condition_id": trial["condition_id"],
                "role": trial["role"],
                "candidate": score.status == "CANDIDATE",
                "status": score.status,
                "reason": score.reason,
                "correlation": score.correlation,
                "lag_ms": score.lag_ms,
            }
        )
    positives = [trial for trial in trials if trial["role"] == "matching_positive"]
    negatives = [trial for trial in trials if trial["role"] == "hard_negative"]
    positive_candidates = sum(trial["candidate"] for trial in positives)
    negative_candidates = sum(trial["candidate"] for trial in negatives)
    return {
        "spec": asdict(spec),
        "matching_positive_candidates": positive_candidates,
        "matching_positive_trials": len(positives),
        "hard_negative_candidates": negative_candidates,
        "hard_negative_trials": len(negatives),
        "eligible": negative_candidates == 0 and positive_candidates >= 4,
        "trials": trials,
    }


def _selection_key(result: dict[str, Any]) -> tuple[float, ...]:
    spec = result["spec"]
    return (
        float(result["matching_positive_candidates"]),
        float(spec["min_correlation"]),
        -float(spec["max_abs_lag_ms"]),
        float(spec["min_audio_std"]),
        float(spec["min_mouth_std"]),
    )


def analyze_pilot(input_dir: Path) -> dict[str, Any]:
    input_dir = input_dir.resolve()
    loaded: list[tuple[dict[str, Any], NumericSeries, NumericSeries]] = []
    sources: list[dict[str, Any]] = []
    for trial in canonical_pilot_trials():
        filename = f"{trial['trial_id']}.csv"
        path = (input_dir / filename).resolve()
        if path.parent != input_dir or not path.is_file():
            raise FileNotFoundError(f"Missing pilot trial: {filename}")
        audio, mouth = load_numeric_trial(path)
        loaded.append((trial, audio, mouth))
        sources.append({"trial_id": trial["trial_id"], "file": filename, "sha256": _sha256(path)})

    results = [_evaluate_spec(spec, loaded) for spec in candidate_specs()]
    eligible = [result for result in results if result["eligible"]]
    selected = max(eligible, key=_selection_key) if eligible else None
    candidate_summaries = [
        {key: value for key, value in result.items() if key != "trials"}
        for result in results
    ]
    bundle = "\n".join(
        f"{item['trial_id']}:{item['file']}:{item['sha256']}" for item in sources
    ).encode("utf-8")
    return {
        "schema": "reachy-av-synchrony-off-robot-pilot-result-v1",
        "status": "DEVELOPMENT_ONLY_CANDIDATE_NOT_FROZEN_NOT_CONFIRMATION",
        "protocol_fingerprint": pilot_protocol_payload()["fingerprint"],
        "source_bundle_sha256": hashlib.sha256(bundle).hexdigest(),
        "sources": sources,
        "candidate_count": len(results),
        "eligible_candidate_count": len(eligible),
        "selected_candidate": selected,
        "selection_succeeded": selected is not None,
        "all_candidates": candidate_summaries,
        "robot_connections": 0,
        "actuation_commands": 0,
        "claim_boundary": (
            "This development result may choose a candidate threshold for a later freeze. "
            "It is not confirmation evidence and does not establish identity or authorization."
        ),
    }
