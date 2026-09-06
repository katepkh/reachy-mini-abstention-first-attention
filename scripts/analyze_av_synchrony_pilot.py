#!/usr/bin/env python3
"""Analyze twelve laptop-only synchrony pilot CSVs without contacting a robot."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from reachy_avsync.pilot import analyze_pilot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Directory containing the twelve exact trial CSV filenames.")
    parser.add_argument("--output", type=Path, required=True, help="Development-only JSON report to write.")
    args = parser.parse_args()
    report = analyze_pilot(args.input)
    content = json.dumps(report, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(content)
    sidecar = output.with_suffix(output.suffix + ".sha256")
    sidecar.write_text(f"{hashlib.sha256(content).hexdigest()}  {output.name}\n", encoding="ascii")
    if report["selection_succeeded"]:
        selected = report["selected_candidate"]
        assert selected is not None
        print(
            "Development candidate found: "
            f"{selected['matching_positive_candidates']}/6 positive and "
            f"{selected['hard_negative_candidates']}/6 hard-negative candidates."
        )
        print("It is not frozen and is not confirmation evidence.")
    else:
        print("No threshold candidate met the predeclared pilot selection rule.")
    print(f"Wrote {output} and SHA-256 sidecar; robot connections: 0.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

