#!/usr/bin/env python
"""Explicit offline pilot operations; never opens a sensor or a robot connection."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reachy_stage3v import robot_pilot_store as store
from reachy_stage3v.robot_pilot_protocol import protocol


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser("status")
    actions.add_parser("freeze-execution")
    actions.add_parser("freeze-development")
    actions.add_parser("validate")
    actions.add_parser("record-abort")
    setup = actions.add_parser("seal-setup")
    setup.add_argument("--old-setup", type=Path, required=True)
    setup.add_argument("--stimulus", type=Path, required=True)
    setup.add_argument("--volume", type=int, required=True)
    setup.add_argument("--confirmed-unchanged-marks", action="store_true")
    incoming = actions.add_parser("import")
    incoming.add_argument("csv", type=Path)
    incoming.add_argument("metadata", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "freeze-execution":
            protocol_path = store.PROTOCOL_MANIFEST
            frozen_execution = store.execution()
            if protocol_path.exists() or store.MANIFEST.exists():
                raise ValueError("A frozen manifest already exists; use a new version, never overwrite")
            store.write_new(protocol_path, protocol())
            store.write_new(store.MANIFEST, frozen_execution)
            result = {"status": "DESIGN_AND_EXECUTION_FROZEN", "collection": store.safe_state()}
        elif args.action == "seal-setup":
            store.initialize(args.old_setup, args.stimulus, volume=args.volume,
                             confirmed=args.confirmed_unchanged_marks)
            result = store.safe_state()
        elif args.action == "import":
            result = store.import_attempt(args.csv, args.metadata)
        elif args.action == "freeze-development":
            result = store.freeze_development()
        elif args.action == "validate":
            result = store.finish_validation()
        elif args.action == "record-abort":
            result = store.record_abort()
        else:
            result = store.safe_state()
        print(json.dumps(result, indent=2, sort_keys=True))
    except (ValueError, OSError, KeyError) as error:
        print(json.dumps({"status": "GATE_CLOSED", "reason": str(error)}))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
