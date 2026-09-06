"""Deterministic numeric fixtures for the replacement-pilot pipeline."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from .pilot_v2_protocol import PILOT_V2_SAMPLE_PERIOD_MS, canonical_pilot_v2_trials


def write_synthetic_pilot_v2(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    timestamps = np.arange(200, dtype=float) * PILOT_V2_SAMPLE_PERIOD_MS
    for trial in canonical_pilot_v2_trials():
        index = int(trial["trial_id"].split("-")[-1])
        rng = np.random.default_rng(9200 + index)
        latent = np.convolve(rng.normal(0.0, 1.0, 208), np.ones(9) / 9.0, mode="valid")
        latent = (latent - latent.min()) / (latent.max() - latent.min())
        audio = -58.0 + 18.0 * latent
        if trial["condition_id"] == "live_visible_continuous":
            lip = 0.02 + 0.07 * latent + rng.normal(0.0, 0.001, len(latent))
        elif trial["condition_id"] == "live_visible_interrupted":
            gate = ((timestamps // 1000) % 2 == 0).astype(float)
            audio = -68.0 + gate * (10.0 + 14.0 * latent)
            lip = 0.02 + gate * 0.07 * latent + rng.normal(0.0, 0.001, len(latent))
        elif trial["condition_id"] == "silent_face_colocated_playback":
            lip = 0.025 + rng.normal(0.0, 0.0001, len(latent))
        else:
            unrelated = np.convolve(rng.normal(0.0, 1.0, 208), np.ones(9) / 9.0, mode="valid")
            unrelated = (unrelated - unrelated.min()) / (unrelated.max() - unrelated.min())
            lip = 0.02 + 0.07 * unrelated
        path = directory / f"{trial['trial_id']}.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(
                ["timestamp_ms", "audio_dbfs", "lip_aperture", "face_scale", "face_count"]
            )
            writer.writerows(
                (
                    f"{timestamp:.3f}",
                    f"{audio_value:.9f}",
                    f"{max(0.0, min(1.0, lip_value)):.9f}",
                    "0.250000000",
                    "1",
                )
                for timestamp, audio_value, lip_value in zip(timestamps, audio, lip)
            )

