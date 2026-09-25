#!/usr/bin/env python3
"""Write or verify the AV-synchrony confirmation execution contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reachy_avsync.confirmation_execution import confirmation_execution_payload  # noqa: E402


OUTPUT = ROOT / "evidence" / "manifests" / "av_synchrony_confirmation_execution_v1.json"
SIDECAR = OUTPUT.with_suffix(OUTPUT.suffix + ".sha256")


def rendered_payload() -> str:
    return json.dumps(confirmation_execution_payload(ROOT), indent=2, sort_keys=True) + "\n"


def rendered_sidecar(payload: str) -> str:
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"{digest}  {OUTPUT.name}\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = rendered_payload()
    sidecar = rendered_sidecar(payload)
    payload_bytes = payload.encode("utf-8")
    sidecar_bytes = sidecar.encode("ascii")
    if args.write:
        OUTPUT.write_bytes(payload_bytes)
        SIDECAR.write_bytes(sidecar_bytes)
        print(f"WROTE: {OUTPUT.relative_to(ROOT)}")
        print(f"WROTE: {SIDECAR.relative_to(ROOT)}")
        return 0
    if not OUTPUT.is_file() or not SIDECAR.is_file():
        print("FAIL: frozen confirmation execution contract is missing.", file=sys.stderr)
        return 1
    if OUTPUT.read_bytes() != payload_bytes:
        print("FAIL: confirmation execution contract is stale.", file=sys.stderr)
        return 1
    if SIDECAR.read_bytes() != sidecar_bytes:
        print("FAIL: confirmation execution SHA-256 sidecar is stale.", file=sys.stderr)
        return 1
    print("PASS: frozen AV-synchrony confirmation execution contract matches code.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
