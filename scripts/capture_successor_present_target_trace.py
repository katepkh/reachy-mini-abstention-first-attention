#!/usr/bin/env python3
"""Capture a bounded receive-only present/target trace after owner approval."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REVIEW_MANIFEST = PROJECT_ROOT / "docs/SUCCESSOR_REVIEW_MANIFEST.json"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from reachy_stage4.config import REACHY_HOST
from reachy_stage4.external_records import (
    require_independent_protocol_approval,
    require_owner_observability_scope,
)
from reachy_stage4.successor_trace import capture_receive_only_trace


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-scope-record", required=True, type=Path)
    parser.add_argument("--independent-review-record", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--duration-s", type=float, default=10.0)
    parser.add_argument("--frequency-hz", type=float, default=20.0)
    args = parser.parse_args()
    require_owner_observability_scope(args.owner_scope_record)
    require_independent_protocol_approval(
        args.independent_review_record,
        review_manifest_path=REVIEW_MANIFEST,
    )
    report, digest = capture_receive_only_trace(
        REACHY_HOST,
        duration_s=args.duration_s,
        frequency_hz=args.frequency_hz,
        output=args.output,
    )
    print(f"Captured {report['frame_count']} receive-only frames; SHA-256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
