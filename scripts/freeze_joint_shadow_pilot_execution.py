#!/usr/bin/env python3
"""Write or verify the content-addressed joint-pilot execution contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reachy_stage3v.joint_pilot_execution import (  # noqa: E402
    EXECUTION_MANIFEST,
    build_execution_payload,
)


def render() -> bytes:
    return json.dumps(build_execution_payload(), indent=2, sort_keys=True).encode("utf-8") + b"\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = render()
    if args.write:
        EXECUTION_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        EXECUTION_MANIFEST.write_bytes(expected)
        print(f"wrote={EXECUTION_MANIFEST.relative_to(ROOT)}")
        return 0
    if not EXECUTION_MANIFEST.is_file() or EXECUTION_MANIFEST.read_bytes() != expected:
        print("FAIL: joint-pilot execution manifest is missing or stale.", file=sys.stderr)
        return 1
    print("PASS: joint-pilot execution manifest is current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
