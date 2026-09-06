#!/usr/bin/env python3
"""Run/check the deterministic local-mock Stage 4A fault rehearsal."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile

from reachy_stage4.offline_fault_rehearsal import run_offline_fault_rehearsal


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = PROJECT_ROOT / "evidence/analysis/stage4a_offline_fault_rehearsal_v1.json"
SIDECAR = OUTPUT.with_suffix(OUTPUT.suffix + ".sha256")


def render() -> bytes:
    with tempfile.TemporaryDirectory(prefix="reachy-offline-fault-rehearsal-") as directory:
        report = run_offline_fault_rehearsal(Path(directory))
    return json.dumps(report, indent=2, sort_keys=True).encode("utf-8") + b"\n"


def sidecar_for(content: bytes) -> bytes:
    return f"{hashlib.sha256(content).hexdigest()}  {OUTPUT.name}\n".encode("ascii")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()

    content = render()
    sidecar = sidecar_for(content)
    if args.write:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_bytes(content)
        SIDECAR.write_bytes(sidecar)
        print(f"Wrote {OUTPUT.relative_to(PROJECT_ROOT)} and SHA-256 sidecar.")
        return 0

    if not OUTPUT.is_file() or OUTPUT.read_bytes() != content:
        print("FAIL: offline fault-rehearsal report is missing or stale.")
        return 1
    if not SIDECAR.is_file() or SIDECAR.read_bytes() != sidecar:
        print("FAIL: offline fault-rehearsal SHA-256 sidecar is missing or stale.")
        return 1
    print("PASS: offline fault-rehearsal report matches four fresh mock-process runs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
