#!/usr/bin/env python3
"""Initialize, bind, inspect, or seal the private joint-pilot workspace."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reachy_stage3v.joint_pilot_private import (  # noqa: E402
    PRIVATE_ROOT,
    bind_marks,
    bind_stimulus,
    import_device_binding,
    initialize,
    preseal_status,
    seal,
    sealed_gate_status,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--initialize", action="store_true")
    group.add_argument("--bind-stimulus", type=Path)
    group.add_argument("--import-device-binding", type=Path)
    group.add_argument("--bind-marks", action="store_true")
    group.add_argument("--status", action="store_true")
    group.add_argument("--seal", action="store_true")
    parser.add_argument("--room-source", type=Path)
    parser.add_argument("--commissioning-metadata", type=Path)
    parser.add_argument(
        "--setup-source",
        type=Path,
        help="initialize v2 from a completed v1 setup without copying captures",
    )
    parser.add_argument("--phone-make-model")
    parser.add_argument("--volume-percent", type=int)
    parser.add_argument("--reachy-mark")
    parser.add_argument("--operator-mark")
    parser.add_argument("--phone-colocated-mark")
    parser.add_argument("--phone-conflict-mark")
    args = parser.parse_args()
    try:
        if args.initialize:
            initialize(
                room_source=args.room_source,
                commissioning_metadata=args.commissioning_metadata,
                setup_source=args.setup_source,
            )
        elif args.bind_stimulus is not None:
            if args.phone_make_model is None or args.volume_percent is None:
                parser.error("--bind-stimulus requires --phone-make-model and --volume-percent")
            bind_stimulus(
                args.bind_stimulus,
                phone_make_model=args.phone_make_model,
                volume_percent=args.volume_percent,
            )
        elif args.import_device_binding is not None:
            import_device_binding(args.import_device_binding)
        elif args.bind_marks:
            values = (
                args.reachy_mark,
                args.operator_mark,
                args.phone_colocated_mark,
                args.phone_conflict_mark,
            )
            if any(value is None for value in values):
                parser.error(
                    "--bind-marks requires --reachy-mark, --operator-mark, "
                    "--phone-colocated-mark, and --phone-conflict-mark"
                )
            bind_marks(
                reachy=str(args.reachy_mark),
                operator=str(args.operator_mark),
                phone_colocated=str(args.phone_colocated_mark),
                phone_conflict=str(args.phone_conflict_mark),
            )
        elif args.seal:
            seal()
        structural, missing = preseal_status()
        gate = sealed_gate_status()
        print(f"private_workspace={PRIVATE_ROOT}")
        print("schedule_rows=21")
        print(f"structural_issues={len(structural)}")
        print(f"missing_private_bindings={len(missing)}")
        print(f"collection_gate_status={gate['status']}")
        for issue in structural:
            print(f"FAIL: {issue}")
        for issue in missing:
            print(f"NEEDS INPUT: {issue}")
        return 0 if not structural and (not args.seal or gate["ready"]) else 1
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
