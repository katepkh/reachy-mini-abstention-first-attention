#!/usr/bin/env python3
"""Write/check an end-to-end synthetic dry run of the pilot analysis."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile

from reachy_avsync.pilot import analyze_pilot
from reachy_avsync.pilot_synthetic import write_synthetic_pilot


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = PROJECT_ROOT / "evidence" / "analysis" / "av_synchrony_pilot_synthetic_dry_run_v1.json"
SIDECAR = OUTPUT.with_suffix(OUTPUT.suffix + ".sha256")


def render() -> bytes:
    with tempfile.TemporaryDirectory(prefix="reachy-avsync-pilot-") as directory:
        write_synthetic_pilot(Path(directory))
        report = analyze_pilot(Path(directory))
    report["status"] = "SYNTHETIC_DRY_RUN_ONLY_NOT_EXPERIMENTAL_DATA"
    report["source_bundle_sha256"] = "OMITTED_SYNTHETIC_TEMPORARY_INPUTS"
    report["sources"] = [
        {"trial_id": item["trial_id"], "file": item["file"], "sha256": "SYNTHETIC_NOT_RETAINED"}
        for item in report["sources"]
    ]
    report["claim_boundary"] = (
        "Constructed signals exercise loading, validation, grid search, and deterministic selection. "
        "They do not calibrate a real signal or justify freezing the selected candidate."
    )
    if not report["selection_succeeded"]:
        raise RuntimeError("The synthetic pilot dry run did not find an eligible candidate.")
    return json.dumps(report, indent=2, sort_keys=True).encode("utf-8") + b"\n"


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
    if not OUTPUT.is_file() or OUTPUT.read_bytes() != content:
        print("FAIL: synchrony pilot dry-run artifact is missing or stale.")
        return 1
    if not SIDECAR.is_file() or SIDECAR.read_bytes() != sidecar:
        print("FAIL: synchrony pilot dry-run sidecar is missing or stale.")
        return 1
    print("PASS: synchrony pilot synthetic dry-run artifact is current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

