#!/usr/bin/env python3
"""Reanalyze private V2 pilot inputs and write an immutable candidate freeze."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from reachy_avsync.pilot_v2_freeze import build_pilot_v2_candidate_freeze


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = build_pilot_v2_candidate_freeze(args.input, PROJECT_ROOT)
    content = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    output = args.output.resolve()
    sidecar = output.with_suffix(output.suffix + ".sha256")
    sidecar_content = f"{hashlib.sha256(content).hexdigest()}  {output.name}\n".encode("ascii")
    if output.exists() and output.read_bytes() != content:
        raise RuntimeError(f"Refusing to overwrite different freeze: {output}")
    if sidecar.exists() and sidecar.read_bytes() != sidecar_content:
        raise RuntimeError(f"Refusing to overwrite different sidecar: {sidecar}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(content)
    sidecar.write_bytes(sidecar_content)
    print(f"Candidate freeze: {payload['fingerprint']}")
    print(f"Wrote {output}; robot connections: 0; actuation commands: 0.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
