"""Audit canonical and quality-failed V2 pilot CSV attempts without altering them."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from .pilot_v2 import assess_pilot_v2_quality, load_pilot_v2_trial
from .pilot_v2_protocol import canonical_pilot_v2_trials, pilot_v2_protocol_payload


TRIAL_ID = re.compile(r"^(avsync-v2-pilot-[0-9]{2})(?:\.csv|-.*\.csv)$")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_pilot_v2_attempts(input_dir: Path) -> dict[str, Any]:
    input_dir = input_dir.resolve()
    trial_by_id = {trial["trial_id"]: trial for trial in canonical_pilot_v2_trials()}
    expected = {f"{trial_id}.csv" for trial_id in trial_by_id}
    paths = sorted(input_dir.glob("avsync-v2-pilot-*.csv"), key=lambda path: path.name)
    entries: list[dict[str, Any]] = []
    for path in paths:
        match = TRIAL_ID.fullmatch(path.name)
        if match is None or match.group(1) not in trial_by_id:
            raise ValueError(f"Unrecognized V2 pilot filename: {path.name}")
        disposition = (
            "canonical" if path.name in expected else "quality_failed_attempt"
            if "quality-failed" in path.name else "unrecognized"
        )
        if disposition == "unrecognized":
            raise ValueError(f"Unrecognized V2 attempt disposition: {path.name}")
        quality = assess_pilot_v2_quality(
            trial_by_id[match.group(1)], load_pilot_v2_trial(path)
        )
        if disposition == "canonical" and not quality["passed"]:
            raise ValueError(f"Canonical file fails quality: {path.name}")
        if disposition == "quality_failed_attempt" and quality["passed"]:
            raise ValueError(f"Failed-attempt file now passes quality: {path.name}")
        entries.append(
            {
                "file": path.name,
                "sha256": _sha256(path),
                "disposition": disposition,
                "quality": quality,
            }
        )
    present_canonical = {entry["file"] for entry in entries if entry["disposition"] == "canonical"}
    missing = sorted(expected - present_canonical)
    if missing:
        raise FileNotFoundError(f"Missing canonical V2 pilot files: {', '.join(missing)}")
    encoded = "\n".join(
        f"{entry['file']}:{entry['sha256']}:{entry['disposition']}" for entry in entries
    ).encode("utf-8")
    return {
        "schema": "reachy-av-synchrony-pilot-v2-attempt-audit",
        "protocol_fingerprint": pilot_v2_protocol_payload()["fingerprint"],
        "attempt_bundle_sha256": hashlib.sha256(encoded).hexdigest(),
        "attempt_count": len(entries),
        "canonical_count": sum(entry["disposition"] == "canonical" for entry in entries),
        "quality_failed_attempt_count": sum(
            entry["disposition"] == "quality_failed_attempt" for entry in entries
        ),
        "entries": entries,
        "robot_connections": 0,
        "actuation_commands": 0,
    }
