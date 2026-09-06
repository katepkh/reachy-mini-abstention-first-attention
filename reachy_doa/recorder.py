"""CSV and metadata persistence constrained to the project data directory."""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .angles import doa_radians_to_degrees
from .config import DATA_DIR
from .models import CSV_COLUMNS, DoAReading, TrialDefinition


def safe_run_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip()).strip("-_")
    if not cleaned:
        raise ValueError("Enter a trial name using letters or numbers.")
    return cleaned[:100]


class TrialRecorder:
    def __init__(self, definition: TrialDefinition) -> None:
        self.definition = TrialDefinition(
            run_id=safe_run_id(definition.run_id),
            true_position_deg=definition.true_position_deg,
            condition=definition.condition.strip()[:100],
            notes=definition.notes.strip()[:1000],
        )
        self.rows: list[dict[str, object]] = []
        self.started_monotonic: float | None = None
        self.stopped = False

    def start(self, now_monotonic: float) -> None:
        self.started_monotonic = now_monotonic
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True

    @property
    def active(self) -> bool:
        return self.started_monotonic is not None and not self.stopped

    def add(
        self,
        reading: DoAReading,
        sequence: int,
        smoothed_angle_deg: float | None,
    ) -> None:
        if not self.active or self.started_monotonic is None:
            return
        raw_degrees = (
            doa_radians_to_degrees(reading.raw_angle_rad)
            if reading.raw_angle_rad is not None
            else None
        )
        self.rows.append(
            {
                "run_id": self.definition.run_id,
                "sequence": sequence,
                "client_time_iso": reading.client_time_iso,
                "elapsed_ms": round(
                    (reading.captured_monotonic - self.started_monotonic) * 1000.0, 3
                ),
                "true_position_deg": self.definition.true_position_deg,
                "condition": self.definition.condition,
                "raw_angle_rad": reading.raw_angle_rad,
                "raw_angle_deg": raw_degrees,
                "smoothed_angle_deg": smoothed_angle_deg,
                "speech_detected": reading.speech_detected,
                "http_latency_ms": round(reading.http_latency_ms, 3),
                "http_status": reading.http_status,
                "valid": reading.valid,
                "error": reading.error,
            }
        )

    def csv_text(self) -> str:
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(self.rows)
        return buffer.getvalue()

    def save(
        self,
        data_dir: Path = DATA_DIR,
        extra_metadata: dict[str, object] | None = None,
    ) -> tuple[Path, Path]:
        resolved = data_dir.resolve()
        if resolved != DATA_DIR and DATA_DIR not in resolved.parents:
            raise ValueError("Trial data must remain inside the project data folder.")
        resolved.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
        base = f"{self.definition.run_id}_{stamp}"
        csv_path = resolved / f"{base}.csv"
        metadata_path = resolved / f"{base}_metadata.json"
        csv_path.write_text(self.csv_text(), encoding="utf-8", newline="")
        metadata = asdict(self.definition) | {
            "saved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "sample_count": len(self.rows),
            "csv_file": csv_path.name,
        }
        if extra_metadata:
            metadata["guided_trial"] = extra_metadata
        metadata_path.write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return csv_path, metadata_path
