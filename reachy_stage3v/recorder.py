"""Numeric-only Stage 3V persistence and browser recovery payloads."""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from reachy_stage2a.models import STAGE2A_CSV_COLUMNS

from .config import DATA_DIR
from .protocol import ValidationStep, protocol_payload


def _safe_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip()).strip("-")
    return (cleaned or "stage3v-trial")[:120]


def trial_payloads(
    run_id: str,
    rows: list[dict[str, Any]],
    step: ValidationStep,
    *,
    protocol_fingerprint: str | None = None,
    data_mode: str = "privacy_validation",
    audit_clip_id: str | None = None,
    metadata_overrides: dict[str, Any] | None = None,
) -> tuple[str, bytes, str, bytes]:
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    stem = f"{_safe_id(run_id)}_{stamp}"
    csv_buffer = io.StringIO(newline="")
    writer = csv.DictWriter(csv_buffer, fieldnames=STAGE2A_CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column) for column in STAGE2A_CSV_COLUMNS})
    is_vertical = hasattr(step, "target_pitch_deg")
    metadata = {
        "schema": (
            "reachy-stage3p-passive-vertical-trial-v1"
            if is_vertical else "reachy-stage3v-off-axis-trial-v1"
        ),
        "protocol_fingerprint": protocol_fingerprint or protocol_payload()["fingerprint"],
        "step_index": step.index,
        "condition_id": step.condition_id,
        "role": step.role,
        "repetition": step.repetition,
        "true_heading_deg": getattr(step, "true_heading_deg", None),
        "face_heading_deg": getattr(step, "face_heading_deg", None),
        "sound_heading_deg": getattr(step, "sound_heading_deg", None),
        "initial_pitch_deg": getattr(step, "initial_pitch_deg", None),
        "target_pitch_deg": getattr(step, "target_pitch_deg", None),
        "face_yaw_deg": getattr(step, "face_yaw_deg", None),
        "sound_yaw_deg": getattr(step, "sound_yaw_deg", None),
        "transition_at_s": getattr(step, "transition_at_s", None),
        "row_count": len(rows),
        "contains_pixels": False,
        "contains_audio": False,
        "contains_transcript": False,
        "contains_identity_embedding": False,
        "data_mode": data_mode,
        "separate_encrypted_audit_clip_id": audit_clip_id,
        "audit_sidecar_contains_video_audio": bool(audit_clip_id),
        "audit_sidecar_cloud_transfer": False,
        "actuation_commands": 0,
        "cloud_requests": 0,
    }
    if metadata_overrides:
        protected = {
            "protocol_fingerprint", "step_index", "condition_id", "role",
            "repetition", "row_count", "contains_pixels", "contains_audio",
            "contains_transcript", "contains_identity_embedding", "robot_requests",
            "cloud_requests", "actuation_commands",
        }
        overlap = protected.intersection(metadata_overrides)
        if overlap:
            raise ValueError(
                "Trial metadata overrides cannot replace protected fields: "
                + ", ".join(sorted(overlap))
            )
        metadata.update(metadata_overrides)
    return (
        f"{stem}.csv",
        csv_buffer.getvalue().encode("utf-8"),
        f"{stem}_metadata.json",
        json.dumps(metadata, indent=2).encode("utf-8"),
    )


def save_trial(
    run_id: str,
    rows: list[dict[str, Any]],
    step: ValidationStep,
    *,
    protocol_fingerprint: str | None = None,
    data_mode: str = "privacy_validation",
    audit_clip_id: str | None = None,
    metadata_overrides: dict[str, Any] | None = None,
) -> tuple[Path, Path]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    csv_name, csv_bytes, json_name, json_bytes = trial_payloads(
        run_id,
        rows,
        step,
        protocol_fingerprint=protocol_fingerprint,
        data_mode=data_mode,
        audit_clip_id=audit_clip_id,
        metadata_overrides=metadata_overrides,
    )
    csv_path = (DATA_DIR / csv_name).resolve()
    json_path = (DATA_DIR / json_name).resolve()
    if csv_path.parent != DATA_DIR or json_path.parent != DATA_DIR:
        raise ValueError("Stage 3V output escaped its local data folder.")
    csv_path.write_bytes(csv_bytes)
    json_path.write_bytes(json_bytes)
    return csv_path, json_path


def attach_audit_reference(metadata_path: Path, audit_clip_id: str) -> None:
    """Attach a separately encrypted clip after an external-device upload."""
    path = metadata_path.resolve()
    if path.parent != DATA_DIR:
        raise ValueError("Stage 3V metadata escaped its local data folder.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["data_mode"] = "development_audit"
    payload["separate_encrypted_audit_clip_id"] = str(audit_clip_id)
    payload["audit_sidecar_contains_video_audio"] = True
    payload["audit_sidecar_cloud_transfer"] = False
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
