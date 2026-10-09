#!/usr/bin/env python3
"""Write/check the deterministic synthetic V2 pilot dry-run artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile

from reachy_avsync.pilot_v2 import analyze_pilot_v2
from reachy_avsync.pilot_v2_synthetic import write_synthetic_pilot_v2
from reachy_avsync.synthetic_artifact_check import matches_frozen_report


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = PROJECT_ROOT / "evidence" / "analysis" / "av_synchrony_pilot_v2_synthetic_dry_run.json"
SIDECAR = OUTPUT.with_suffix(OUTPUT.suffix + ".sha256")


def render() -> bytes:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        write_synthetic_pilot_v2(root)
        report = analyze_pilot_v2(root)
    return json.dumps(report, indent=2, sort_keys=True).encode("utf-8") + b"\n"


def matches_frozen_analysis(stored: bytes, regenerated: bytes) -> bool:
    """Keep the protocol and outcomes exact while tolerating numeric roundoff."""

    return matches_frozen_report(
        stored,
        regenerated,
        roundoff_fields=frozenset({"correlation", "audio_dbfs_std", "lip_aperture_std"}),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = render()
    sidecar = f"{hashlib.sha256(content).hexdigest()}  {OUTPUT.name}\n".encode("ascii")
    if args.write:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_bytes(content)
        SIDECAR.write_bytes(sidecar)
        print(f"Wrote {OUTPUT.relative_to(PROJECT_ROOT)} and SHA-256 sidecar.")
        return 0
    if not OUTPUT.is_file() or not matches_frozen_analysis(OUTPUT.read_bytes(), content):
        print("FAIL: V2 pilot synthetic dry-run artifact is missing or stale.")
        return 1
    stored = OUTPUT.read_bytes()
    stored_sidecar = f"{hashlib.sha256(stored).hexdigest()}  {OUTPUT.name}\n".encode("ascii")
    if not SIDECAR.is_file() or SIDECAR.read_bytes() != stored_sidecar:
        print("FAIL: V2 pilot synthetic dry-run sidecar is missing or stale.")
        return 1
    print("PASS: V2 pilot synthetic dry-run artifact is current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

