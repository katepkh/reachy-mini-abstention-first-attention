#!/usr/bin/env python
"""Print the frozen command-free joint-shadow pilot schedule."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reachy_stage3v.joint_pilot_protocol import joint_pilot_protocol_payload  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print the complete protocol JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = joint_pilot_protocol_payload()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    print(f"protocol_fingerprint={payload['fingerprint']}")
    print("status=" + payload["status"])
    for trial in payload["randomized_schedule"]:
        print(
            f"{trial['schedule_index']:02d}  {trial['trial_id']}  "
            f"{trial['condition_id']}  [{trial['split']}]"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
