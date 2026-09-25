#!/usr/bin/env python3
"""Analyze all 54 accepted confirmation CSVs without opening sensors or a robot."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from reachy_avsync.confirmation_analysis import analyze_confirmation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = analyze_confirmation(args.input)
    content = json.dumps(report, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(content)
    output.with_suffix(output.suffix + ".sha256").write_text(
        f"{hashlib.sha256(content).hexdigest()}  {output.name}\n", encoding="ascii"
    )
    candidate = report["summaries"]["frozen_synchrony_candidate"]
    print(f"Status: {report['status']}")
    print(
        "Frozen candidate: "
        f"{candidate['matching_positive_proposals']}/{candidate['matching_positive_trials']} "
        "matching-positive proposals; "
        f"{candidate['hard_negative_proposals']}/{candidate['hard_negative_trials']} "
        "hard-negative proposals."
    )
    print(f"Wrote {output}; robot connections: 0.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
