"""Append-only laboratory notes stored inside the local data folder."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .config import DATA_DIR


LAB_RECORD = (DATA_DIR / "laboratory_record.md").resolve()


def append_trial_entry(
    run_id: str,
    csv_name: str,
    condition: str,
    notes: str,
    summary: dict[str, object],
    record_path: Path = LAB_RECORD,
) -> Path:
    resolved = record_path.resolve()
    if resolved != LAB_RECORD and DATA_DIR not in resolved.parents:
        raise ValueError("The laboratory record must remain inside the project data folder.")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    if not resolved.exists():
        resolved.write_text(
            "# Reachy Acoustic Lab — laboratory record\n\n"
            "Local, read-only DoA experiments. No audio, images, video, transcripts, or cloud AI data are stored.\n",
            encoding="utf-8",
        )
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    entry = (
        f"\n## {run_id}\n\n"
        f"- Recorded: {timestamp}\n"
        f"- File: `{csv_name}`\n"
        f"- Condition: {condition}\n"
        f"- Operator notes: {notes or 'None'}\n"
        f"- Samples: {summary.get('sample_count')} total; {summary.get('valid_count')} valid\n"
        f"- Speech-positive: {summary.get('speech_positive_rate_pct')}%\n"
        f"- Median / P95 latency: {summary.get('median_latency_ms')} / {summary.get('p95_latency_ms')} ms\n"
        f"- Median directional error: {summary.get('median_abs_error_deg')}°\n"
        f"- Automatic status: **{summary.get('status')}**\n"
        f"- Findings: {summary.get('findings')}\n"
    )
    with resolved.open("a", encoding="utf-8") as handle:
        handle.write(entry)
    return resolved


def append_observation(run_id: str, observation: str, record_path: Path = LAB_RECORD) -> Path:
    """Add a post-trial physical observation without altering source metadata."""
    resolved = record_path.resolve()
    if resolved != LAB_RECORD and DATA_DIR not in resolved.parents:
        raise ValueError("The laboratory record must remain inside the project data folder.")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    with resolved.open("a", encoding="utf-8") as handle:
        handle.write(
            f"\n### Post-trial observation · {run_id}\n\n"
            f"- Added: {timestamp}\n"
            f"- Observation: {observation.strip()[:1000]}\n"
        )
    return resolved
