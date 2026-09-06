#!/usr/bin/env python3
"""Analyze the twelve V2 laptop-only pilot files without contacting a robot."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from reachy_avsync.pilot_v2 import analyze_pilot_v2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = analyze_pilot_v2(args.input)
    content = json.dumps(report, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(content)
    output.with_suffix(output.suffix + ".sha256").write_text(
        f"{hashlib.sha256(content).hexdigest()}  {output.name}\n", encoding="ascii"
    )
    print(f"Status: {report['status']}")
    print(
        f"Eligible development settings: {report['eligible_development_candidate_count']} / "
        f"{report['candidate_count']}"
    )
    print(f"Wrote {output}; robot connections: 0.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

