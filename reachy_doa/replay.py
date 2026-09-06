"""Deterministic offline replay of saved numerical DoA observations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .angles import doa_radians_to_degrees
from .config import DATA_DIR


@dataclass(slots=True, frozen=True)
class ReplayObservation:
    sequence: int
    elapsed_ms: float
    angle_rad: float | None
    angle_deg: float | None
    speech_detected: bool | None
    latency_ms: float
    http_status: int | None
    valid: bool
    error: str


def _boolean(value: object) -> bool:
    return str(value).strip().lower() == "true"


def load_replay(csv_path: Path) -> tuple[ReplayObservation, ...]:
    resolved = csv_path.resolve()
    if resolved.parent != DATA_DIR and DATA_DIR not in resolved.parents:
        raise ValueError("Replay is restricted to the project data folder.")
    frame = pd.read_csv(resolved)
    required = {
        "sequence", "elapsed_ms", "raw_angle_rad", "speech_detected",
        "http_latency_ms", "http_status", "valid", "error",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Replay CSV is missing columns: {', '.join(missing)}")
    observations: list[ReplayObservation] = []
    for row in frame.sort_values(["elapsed_ms", "sequence"]).itertuples(index=False):
        valid = _boolean(getattr(row, "valid"))
        angle_value = getattr(row, "raw_angle_rad")
        angle_rad = float(angle_value) if valid and pd.notna(angle_value) else None
        speech_value = getattr(row, "speech_detected")
        speech = _boolean(speech_value) if valid and pd.notna(speech_value) else None
        status_value = getattr(row, "http_status")
        status = int(float(status_value)) if pd.notna(status_value) else None
        observations.append(
            ReplayObservation(
                sequence=int(getattr(row, "sequence")),
                elapsed_ms=float(getattr(row, "elapsed_ms")),
                angle_rad=angle_rad,
                angle_deg=doa_radians_to_degrees(angle_rad) if angle_rad is not None else None,
                speech_detected=speech,
                latency_ms=float(getattr(row, "http_latency_ms")),
                http_status=status,
                valid=valid,
                error="" if pd.isna(getattr(row, "error")) else str(getattr(row, "error")),
            )
        )
    return tuple(observations)
