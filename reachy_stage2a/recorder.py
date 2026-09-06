"""Constrained numeric-metadata persistence for Stage 2A."""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import STAGE2A_DATA_DIR
from .models import STAGE2A_CSV_COLUMNS


def _safe_run_id(run_id: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", run_id.strip()).strip("-")
    return (cleaned or "stage2a-session")[:80]


def numeric_session_downloads(
    run_id: str,
    rows: list[dict[str, Any]],
    *,
    condition_code: str,
) -> tuple[str, bytes, str, bytes]:
    """Build derived-only CSV/JSON payloads in RAM for browser download."""
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    stem = f"{_safe_run_id(run_id)}_{stamp}"
    csv_buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        csv_buffer,
        fieldnames=STAGE2A_CSV_COLUMNS,
        extrasaction="ignore",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column) for column in STAGE2A_CSV_COLUMNS})
    metadata = {
        "schema": "reachy-stage2a-derived-metadata-v1",
        "condition_code": str(condition_code)[:64],
        "row_count": len(rows),
        "contains_pixels": False,
        "contains_audio": False,
        "contains_transcript": False,
        "contains_identity_embedding": False,
    }
    return (
        f"{stem}.csv",
        csv_buffer.getvalue().encode("utf-8"),
        f"{stem}_metadata.json",
        json.dumps(metadata, indent=2).encode("utf-8"),
    )


def save_numeric_session(
    run_id: str,
    rows: list[dict[str, Any]],
    *,
    condition_code: str,
) -> tuple[Path, Path]:
    """Save derived numbers/states only under data/stage2a."""
    STAGE2A_DATA_DIR.mkdir(parents=True, exist_ok=True)
    csv_name, csv_bytes, metadata_name, metadata_bytes = numeric_session_downloads(
        run_id,
        rows,
        condition_code=condition_code,
    )
    csv_path = (STAGE2A_DATA_DIR / csv_name).resolve()
    metadata_path = (STAGE2A_DATA_DIR / metadata_name).resolve()
    if csv_path.parent != STAGE2A_DATA_DIR or metadata_path.parent != STAGE2A_DATA_DIR:
        raise ValueError("Stage 2A output escaped its local data folder.")
    csv_path.write_bytes(csv_bytes)
    metadata_path.write_bytes(metadata_bytes)
    return csv_path, metadata_path
