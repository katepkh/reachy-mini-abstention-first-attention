"""Procedural-compliance records kept separate from numeric trial outcomes."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import DATA_DIR, STUDY_PROFILE


def compliance_path(csv_path: Path) -> Path:
    resolved = csv_path.resolve()
    if resolved.parent != DATA_DIR:
        raise ValueError("Compliance record escaped the active Stage 3V data folder.")
    return resolved.with_name(resolved.stem + "_compliance.json")


def save_compliance_review(
    csv_path: Path,
    *,
    protocol_fingerprint: str,
    step_index: int,
    data_mode: str,
    position_followed: bool,
    speech_or_playback_followed: bool,
    audit_clip_id: str | None = None,
    audit_verdict: str | None = None,
) -> Path:
    compliant = bool(position_followed and speech_or_playback_followed)
    if data_mode == "development_audit":
        compliant = compliant and audit_verdict == "COMPLIANT" and bool(audit_clip_id)
    payload: dict[str, Any] = {
        "schema": (
            "reachy-stage3p-held-out-compliance-v3"
            if STUDY_PROFILE == "stage3p_confirmation_v3"
            else "reachy-stage3p-calibration-compliance-v1"
            if STUDY_PROFILE == "stage3p_calibration"
            else "reachy-stage3p-held-out-compliance-v2"
            if STUDY_PROFILE == "stage3p_confirmation_v2"
            else "reachy-stage3p-held-out-compliance-v1"
            if STUDY_PROFILE == "stage3p_confirmation"
            else "reachy-stage3p-vad-diagnostic-compliance-v1"
            if STUDY_PROFILE == "stage3p_vad_diagnostic"
            else "reachy-stage3p-procedural-compliance-v1"
            if STUDY_PROFILE == "stage3p_development"
            else "reachy-stage3v-procedural-compliance-v1"
        ),
        "protocol_fingerprint": str(protocol_fingerprint),
        "step_index": int(step_index),
        "trial_file": csv_path.name,
        "data_mode": str(data_mode),
        "position_instruction_followed": bool(position_followed),
        "speech_or_playback_instruction_followed": bool(speech_or_playback_followed),
        "audit_clip_id": audit_clip_id,
        "audit_verdict": audit_verdict,
        "verdict": "COMPLIANT" if compliant else "NONCOMPLIANT",
        "reviewed_time_iso": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "contains_pixels": False,
        "contains_audio": False,
        "contains_transcript": False,
    }
    path = compliance_path(csv_path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path
