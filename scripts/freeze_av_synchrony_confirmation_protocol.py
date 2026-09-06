#!/usr/bin/env python3
"""Write or verify the frozen AV-synchrony confirmation protocol."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reachy_avsync.confirmation_protocol import confirmation_protocol_payload  # noqa: E402


OUTPUT = ROOT / "evidence" / "manifests" / "av_synchrony_confirmation_protocol_v1.json"
SIDECAR = OUTPUT.with_suffix(OUTPUT.suffix + ".sha256")


def rendered_payload() -> str:
    return json.dumps(confirmation_protocol_payload(), indent=2, sort_keys=True) + "\n"


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
    if args.write:
        OUTPUT.write_text(payload, encoding="utf-8")
        SIDECAR.write_text(sidecar, encoding="utf-8")
        print(f"WROTE: {OUTPUT.relative_to(ROOT)}")
        print(f"WROTE: {SIDECAR.relative_to(ROOT)}")
        return 0

    if not OUTPUT.is_file() or not SIDECAR.is_file():
        print("FAIL: frozen confirmation protocol is missing.", file=sys.stderr)
        return 1
    if OUTPUT.read_text(encoding="utf-8") != payload:
        print("FAIL: confirmation protocol is stale.", file=sys.stderr)
        return 1
    if SIDECAR.read_text(encoding="utf-8") != sidecar:
        print("FAIL: confirmation protocol SHA-256 sidecar is stale.", file=sys.stderr)
        return 1
    print("PASS: frozen AV-synchrony confirmation protocol matches code.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
