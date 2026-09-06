"""Small data models for readings and trial rows."""

from __future__ import annotations

from dataclasses import dataclass


CSV_COLUMNS = [
    "run_id",
    "sequence",
    "client_time_iso",
    "elapsed_ms",
    "true_position_deg",
    "condition",
    "raw_angle_rad",
    "raw_angle_deg",
    "smoothed_angle_deg",
    "speech_detected",
    "http_latency_ms",
    "http_status",
    "valid",
    "error",
]


@dataclass(slots=True, frozen=True)
class DoAReading:
    client_time_iso: str
    captured_monotonic: float
    raw_angle_rad: float | None
    speech_detected: bool | None
    http_latency_ms: float
    http_status: int | None
    valid: bool
    error: str


@dataclass(slots=True, frozen=True)
class TrialDefinition:
    run_id: str
    true_position_deg: float | None
    condition: str
    notes: str
