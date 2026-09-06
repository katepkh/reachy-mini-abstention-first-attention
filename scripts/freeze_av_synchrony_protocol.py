#!/usr/bin/env python3
"""Write/check the future audio–mouth synchrony study-design manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from reachy_avsync.protocol import protocol_payload


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = PROJECT_ROOT / "evidence" / "manifests" / "av_synchrony_falsification_protocol_v1.json"
SIDECAR = OUTPUT.with_suffix(OUTPUT.suffix + ".sha256")


def render() -> bytes:
    return json.dumps(protocol_payload(), indent=2, sort_keys=True).encode("utf-8") + b"\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = render()
    sidecar = f"{hashlib.sha256(content).hexdigest()}  {OUTPUT.name}\n".encode("ascii")
    if args.write:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_bytes(content)
        SIDECAR.write_bytes(sidecar)
        print(f"Wrote {OUTPUT.relative_to(PROJECT_ROOT)} and SHA-256 sidecar.")
        return 0
    if not OUTPUT.is_file() or OUTPUT.read_bytes() != content:
        print("FAIL: audio–mouth synchrony protocol manifest is missing or stale.")
        return 1
    if not SIDECAR.is_file() or SIDECAR.read_bytes() != sidecar:
        print("FAIL: audio–mouth synchrony protocol sidecar is missing or stale.")
        return 1
    print("PASS: audio–mouth synchrony protocol manifest is current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

