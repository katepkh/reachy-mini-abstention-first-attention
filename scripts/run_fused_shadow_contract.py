#!/usr/bin/env python3
"""Write/check the deterministic M5 fused-shadow software contract rehearsal."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from reachy_stage3v.fused_shadow import (
    FUSED_SHADOW_SPEC_V1,
    ShadowObservation,
    SpatialEvidence,
    SynchronyEvidence,
    fuse_shadow_observation,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "evidence" / "analysis" / "fused_shadow_contract_v1.json"
SIDECAR = OUTPUT.with_suffix(OUTPUT.suffix + ".sha256")


def _spatial(status: str = "SUPPORTED", **changes: object) -> SpatialEvidence:
    values: dict[str, object] = {
        "status": status,
        "observed_ms": 900.0,
        "face_track_id": "visible-face-1",
        "heading_deg": 12.0,
        "reason": "TEMPORAL_CONSENSUS",
    }
    values.update(changes)
    return SpatialEvidence(**values)  # type: ignore[arg-type]


def _synchrony(status: str = "SUPPORTED", **changes: object) -> SynchronyEvidence:
    values: dict[str, object] = {
        "status": status,
        "observed_ms": 920.0,
        "face_track_id": "visible-face-1",
        "correlation": 0.72,
        "lag_ms": 40.0,
        "reason": "STABLE_SYNCHRONY_CANDIDATE_NOT_IDENTITY",
    }
    values.update(changes)
    return SynchronyEvidence(**values)  # type: ignore[arg-type]


def build_report() -> dict[str, object]:
    cases = (
        ("supported_same_visible_face", "SELECT", True, "READY", _spatial(), _synchrony()),
        ("spatial_pending", "HOLD", True, "READY", _spatial("PENDING"), _synchrony()),
        ("synchrony_pending", "HOLD", True, "READY", _spatial(), _synchrony("PENDING")),
        ("phone_like_synchrony_abstain", "ABSTAIN", True, "READY", _spatial(), _synchrony("ABSTAIN")),
        ("spatial_conflict", "ABSTAIN", True, "READY", _spatial("CONFLICT"), _synchrony()),
        (
            "face_track_mismatch",
            "ABSTAIN",
            True,
            "READY",
            _spatial(),
            _synchrony(face_track_id="visible-face-2"),
        ),
        (
            "stale_spatial_evidence",
            "ABSTAIN",
            True,
            "READY",
            _spatial(observed_ms=0.0),
            _synchrony(),
        ),
        (
            "invalid_heading",
            "ABSTAIN",
            True,
            "READY",
            _spatial(heading_deg=None),
            _synchrony(),
        ),
        ("unhealthy_runtime", "ABSTAIN", False, "STATE_STALE", _spatial(), _synchrony()),
        ("synchrony_unavailable", "ABSTAIN", True, "READY", _spatial(), _synchrony("UNAVAILABLE")),
    )
    results: list[dict[str, object]] = []
    for name, expected, healthy, health_reason, spatial, synchrony in cases:
        decision = fuse_shadow_observation(
            ShadowObservation(1000.0, healthy, health_reason, spatial, synchrony)
        )
        passed = (
            decision.state == expected
            and not decision.motion_authorized
            and not decision.response_authorized
            and decision.actuation_commands == 0
            and decision.response_commands == 0
        )
        results.append(
            {
                "name": name,
                "expected_state": expected,
                "observed_state": decision.state,
                "passed": passed,
                "decision": decision.as_dict(),
            }
        )
    return {
        "schema": "reachy-m5-fused-shadow-contract-v1",
        "status": "SYNTHETIC_SOFTWARE_CONTRACT_ONLY",
        "spec": FUSED_SHADOW_SPEC_V1.payload(),
        "cases": results,
        "all_passed": all(bool(item["passed"]) for item in results),
        "robot_connections": 0,
        "media_captures": 0,
        "actuation_commands": 0,
        "response_commands": 0,
        "claim_boundary": (
            "Exercises deterministic fusion branches only. It does not establish liveness, "
            "speaker identity, conversational intent, eye contact, robot motion, audible response, "
            "phone-playback rejection, or end-to-end performance."
        ),
    }


def render() -> bytes:
    report = build_report()
    if not report["all_passed"]:
        raise RuntimeError("The fused-shadow contract rehearsal failed.")
    return json.dumps(report, indent=2, sort_keys=True).encode("utf-8") + b"\n"


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
        print(f"Wrote {OUTPUT.relative_to(ROOT)} and SHA-256 sidecar.")
        return 0
    if not OUTPUT.is_file() or OUTPUT.read_bytes() != content:
        print("FAIL: fused-shadow contract artifact is missing or stale.")
        return 1
    if not SIDECAR.is_file() or SIDECAR.read_bytes() != sidecar:
        print("FAIL: fused-shadow contract SHA-256 sidecar is missing or stale.")
        return 1
    print("PASS: fused-shadow contract artifact is current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
