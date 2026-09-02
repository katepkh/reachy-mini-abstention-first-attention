"""Aggregate verified, command-free Reachy startup captures.

This module reads private diagnostic JSON files from disk. It has no network,
robot transport, or actuation surface and never treats operator annotations as
robot telemetry.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .config import OFFICIAL_PROTOCOL_VERSION, PROJECT_ROOT
from .neutral_diagnostic import DEFAULT_OUTPUT_DIR, SCHEMA_VERSION as CAPTURE_SCHEMA_VERSION


SCHEMA_VERSION = "reachy-stage4-startup-characterization-v1"
NEUTRAL_GATE_DEG = 1.0
MINIMUM_CONTROLLED_STARTS = 3
DEFAULT_REPORT = PROJECT_ROOT / "data/private/stage4a_startup_characterization_v1/report.json"


def load_verified_capture(path: Path) -> dict[str, Any]:
    """Load a capture only when its adjacent SHA-256 sidecar matches."""

    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    sidecar = path.with_suffix(path.suffix + ".sha256")
    if not sidecar.is_file():
        raise ValueError(f"Missing checksum sidecar for {path.name}.")
    expected = sidecar.read_text(encoding="utf-8").strip().split()[0]
    if digest != expected:
        raise ValueError(f"Checksum mismatch for {path.name}.")
    value = json.loads(payload)
    if not isinstance(value, dict) or value.get("schema") != CAPTURE_SCHEMA_VERSION:
        raise ValueError(f"{path.name} is not a supported neutral diagnostic capture.")
    value["_capture_file"] = path.name
    value["_capture_sha256"] = digest
    return value


def _controlled_row(record: Mapping[str, Any]) -> dict[str, Any]:
    annotation = record.get("operator_annotation")
    context = annotation.get("startup_context") if isinstance(annotation, Mapping) else None
    if not isinstance(context, Mapping):
        raise ValueError("Capture lacks structured startup context.")
    if context.get("startup_kind") != "physical_power_cycle":
        raise ValueError("Characterization accepts physical_power_cycle captures only.")
    index = context.get("startup_index")
    if not isinstance(index, int) or index < 1:
        raise ValueError("Each capture requires a positive startup_index.")
    if context.get("controller_touched_since_start") != "no":
        raise ValueError("Controller must remain untouched before a controlled capture.")

    audit = record.get("transport_audit")
    if not isinstance(audit, Mapping):
        raise ValueError("Capture lacks a transport audit.")
    if audit.get("robot_commands_sent") != 0 or audit.get("websocket_messages_sent") != 0:
        raise ValueError("Characterization requires a zero-command capture.")
    if audit.get("http_methods") != ["GET"]:
        raise ValueError("Characterization requires GET-only HTTP access.")

    status = record.get("daemon_status_after")
    if not isinstance(status, Mapping):
        raise ValueError("Capture lacks final daemon status.")
    if str(status.get("version")) != OFFICIAL_PROTOCOL_VERSION:
        raise ValueError("Capture daemon version does not match the frozen protocol.")
    if status.get("simulation_enabled") is not False or status.get("mockup_sim_enabled") is not False:
        raise ValueError("Characterization requires physical-hardware captures.")

    app_context = record.get("app_context")
    if not isinstance(app_context, Mapping):
        raise ValueError("Capture lacks read-only app context.")
    if app_context.get("configured_startup_app") is not None:
        raise ValueError("Controlled starts require no configured startup app.")
    if app_context.get("current_app_status") is not None:
        raise ValueError("Controlled starts require no currently running app.")

    summary = record.get("summary")
    rotation = summary.get("stream_rotation_from_identity_deg") if isinstance(summary, Mapping) else None
    drift = summary.get("stream_rotation_drift_from_first_deg") if isinstance(summary, Mapping) else None
    frames = record.get("stream_frames")
    if not isinstance(rotation, Mapping) or not isinstance(drift, Mapping) or not isinstance(frames, list):
        raise ValueError("Capture lacks required stream summary fields.")
    if len(frames) < 20:
        raise ValueError("Controlled startup captures require at least 20 frames.")

    return {
        "startup_index": index,
        "capture_file": record.get("_capture_file"),
        "capture_sha256": record.get("_capture_sha256"),
        "started_at_utc": record.get("started_at_utc"),
        "startup_age_seconds": context.get("startup_age_seconds"),
        "wake_animation_observed": context.get("wake_animation_observed"),
        "startup_app_observed": context.get("startup_app_observed"),
        "configured_startup_app": app_context.get("configured_startup_app"),
        "current_app_status": app_context.get("current_app_status"),
        "rotation_minimum_deg": float(rotation["minimum"]),
        "rotation_mean_deg": float(rotation["mean"]),
        "rotation_maximum_deg": float(rotation["maximum"]),
        "maximum_drift_deg": float(drift["maximum"]),
        "all_frames_within_neutral_gate": float(rotation["maximum"]) <= NEUTRAL_GATE_DEG,
    }


def summarize_startup_captures(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Return a deterministic characterization that never authorizes movement."""

    rows = sorted((_controlled_row(record) for record in records), key=lambda row: row["startup_index"])
    if not rows:
        raise ValueError("At least one controlled startup capture is required.")
    indices = [row["startup_index"] for row in rows]
    if len(indices) != len(set(indices)):
        raise ValueError("startup_index values must be unique.")
    means = [row["rotation_mean_deg"] for row in rows]
    gate_passes = sum(bool(row["all_frames_within_neutral_gate"]) for row in rows)
    enough = len(rows) >= MINIMUM_CONTROLLED_STARTS
    return {
        "schema": SCHEMA_VERSION,
        "capture_count": len(rows),
        "minimum_controlled_starts": MINIMUM_CONTROLLED_STARTS,
        "controlled_start_count_sufficient": enough,
        "neutral_gate_deg": NEUTRAL_GATE_DEG,
        "all_frame_gate_pass_count": gate_passes,
        "all_frame_gate_fail_count": len(rows) - gate_passes,
        "capture_mean_rotation_deg": {
            "minimum": min(means),
            "mean": sum(means) / len(means),
            "maximum": max(means),
            "range": max(means) - min(means),
        },
        "captures": rows,
        "diagnostic_status": (
            "INSUFFICIENT_CONTROLLED_STARTS"
            if not enough
            else "START_STATE_OUTSIDE_GATE"
            if gate_passes != len(rows)
            else "START_STATE_WITHIN_GATE_IN_THIS_SMALL_SERIES"
        ),
        "claim_boundary": (
            "This is a small within-unit startup characterization, not calibration, "
            "repair validation, a population estimate, or hardware authorization."
        ),
        "v4_commands_authorized": 0,
    }


def write_report(report: Mapping[str, Any], output: Path) -> tuple[Path, Path, str]:
    """Write a deterministic report and checksum, refusing to overwrite."""

    path = output.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    sidecar = path.with_suffix(path.suffix + ".sha256")
    with path.open("xb") as stream:
        stream.write(payload)
    try:
        with sidecar.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(f"{digest}  {path.name}\n")
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return path, sidecar, digest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    records = [load_verified_capture(path) for path in args.capture]
    report = summarize_startup_captures(records)
    path, _, digest = write_report(report, args.output)
    print(f"Startup characterization: {path}")
    print(f"SHA-256: {digest}")
    print(f"Status: {report['diagnostic_status']}")
    print("Robot commands authorized: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
