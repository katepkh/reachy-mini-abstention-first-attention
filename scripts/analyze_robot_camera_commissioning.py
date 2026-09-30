#!/usr/bin/env python
"""Assess one derived-numeric Reachy-camera commissioning CSV."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reachy_stage3v.robot_camera_commissioning import (  # noqa: E402
    assess_robot_camera_commissioning,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = assess_robot_camera_commissioning(args.csv)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.write_text(rendered, encoding="utf-8")
        print(args.output.resolve())
    return 0 if result["checks_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
