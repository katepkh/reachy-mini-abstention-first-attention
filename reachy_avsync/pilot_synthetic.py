"""Deterministic synthetic files for testing the off-robot pilot pipeline."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from .pilot_protocol import PILOT_SAMPLE_PERIOD_MS, canonical_pilot_trials


def write_synthetic_pilot(directory: Path) -> None:
    """Write constructed numeric inputs; never label them experimental data."""

    directory.mkdir(parents=True, exist_ok=True)
    timestamps = np.arange(200, dtype=float) * PILOT_SAMPLE_PERIOD_MS
    for trial in canonical_pilot_trials():
        rng = np.random.default_rng(6000 + int(trial["trial_id"].split("-")[-1]))
        latent = np.convolve(rng.normal(0.0, 1.0, 208), np.ones(9) / 9.0, mode="valid")
        latent = (latent - latent.min()) / (latent.max() - latent.min())
        audio = latent
        if trial["condition_id"] == "live_visible_continuous":
            mouth = np.clip(0.85 * latent + rng.normal(0.0, 0.025, len(latent)), 0.0, 1.0)
        elif trial["condition_id"] == "live_visible_interrupted":
            gate = ((timestamps // 1000) % 2 == 0).astype(float)
            audio = latent * gate
            mouth = np.clip(0.85 * audio + rng.normal(0.0, 0.02, len(latent)), 0.0, 1.0)
        elif trial["condition_id"] == "silent_face_colocated_playback":
            mouth = np.clip(0.02 + rng.normal(0.0, 0.0002, len(latent)), 0.0, 1.0)
        else:
            mouth = np.roll(latent, 20)
            mouth[:20] = rng.uniform(0.0, 1.0, 20)
        path = directory / f"{trial['trial_id']}.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(["timestamp_ms", "audio_energy", "mouth_motion"])
            writer.writerows(
                (f"{timestamp:.3f}", f"{audio_value:.9f}", f"{mouth_value:.9f}")
                for timestamp, audio_value, mouth_value in zip(timestamps, audio, mouth)
            )

