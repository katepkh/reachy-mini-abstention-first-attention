#!/usr/bin/env python3
"""Analyze a complete joint-shadow pilot bundle entirely offline."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reachy_stage3v.joint_pilot_analysis import analyze_joint_pilot  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = analyze_joint_pilot(args.input)
    content = json.dumps(report, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(content)
    output.with_suffix(output.suffix + ".sha256").write_text(
        f"{hashlib.sha256(content).hexdigest()}  {output.name}\n",
        encoding="ascii",
    )
    print(f"status={report['status']}")
    print(
        "eligible_development_settings="
        f"{report['eligible_development_candidate_count']}/{report['candidate_count']}"
    )
    print(f"internal_validation_passed={str(report['internal_validation_passed']).lower()}")
    print(f"wrote={output}")
    print("robot_connections=0 actuation_commands=0 response_commands=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
