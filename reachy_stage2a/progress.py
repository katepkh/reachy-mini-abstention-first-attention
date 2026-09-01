"""Small local checkpoint for accepted Stage 2A matrix progress."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .config import STAGE2A_DATA_DIR


PROGRESS_PATH = (STAGE2A_DATA_DIR / "matrix_progress.json").resolve()


def load_matrix_progress(max_steps: int) -> int:
    """Load a validated accepted-step count; invalid checkpoints fail closed to zero."""
    try:
        payload = json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
        accepted = int(payload.get("accepted_steps", 0))
    except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError):
        return 0
    return accepted if 0 <= accepted <= max_steps else 0


def save_matrix_progress(accepted_steps: int, max_steps: int) -> Path:
    """Persist only the accepted count inside the constrained Stage 2A data folder."""
    if not 0 <= accepted_steps <= max_steps:
        raise ValueError("Accepted Stage 2A progress is outside the matrix bounds.")
    STAGE2A_DATA_DIR.mkdir(parents=True, exist_ok=True)
    if PROGRESS_PATH.parent != STAGE2A_DATA_DIR:
        raise ValueError("Stage 2A progress escaped its local data folder.")
    payload = {
        "schema": "reachy-stage2a-matrix-progress-v1",
        "accepted_steps": accepted_steps,
        "total_steps": max_steps,
        "updated_time_iso": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "contains_pixels": False,
        "contains_audio": False,
        "contains_transcript": False,
    }
    temporary = Path(f"{PROGRESS_PATH}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(PROGRESS_PATH)
    return PROGRESS_PATH
