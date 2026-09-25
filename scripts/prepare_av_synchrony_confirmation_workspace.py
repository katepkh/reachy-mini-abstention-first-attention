#!/usr/bin/env python3
"""Initialize, inspect, or seal the private AV-synchrony confirmation workspace.

Initialization is local and non-acquiring: it opens no camera, microphone,
network, or robot connection.  Existing private records are never overwritten.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import platform
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "evidence" / "manifests" / "av_synchrony_confirmation_protocol_v1.json"
EXECUTION = ROOT / "evidence" / "manifests" / "av_synchrony_confirmation_execution_v1.json"
PRIVATE_ROOT = ROOT / "data" / "private" / "avsync_confirmation_v1"
RECORDS = PRIVATE_ROOT / "bindings"
CAPTURES = PRIVATE_ROOT / "captures"
LEDGER = PRIVATE_ROOT / "attempt_ledger.csv"
SEALED_MANIFEST = PRIVATE_ROOT / "binding_manifest.json"
GUIDE = PRIVATE_ROOT / "README.md"

ROOM_FIELDS = (
    "confirmation_not_v2_pilot_room",
    "approximate_dimensions_m.length",
    "approximate_dimensions_m.width",
    "approximate_dimensions_m.height",
    "dominant_surface_and_furnishing_description",
    "background_audio_dbfs_10s",
    "camera_mark",
    "microphone_mark",
    "visible_person_marks.-20",
    "visible_person_marks.0",
    "visible_person_marks.20",
    "playback_marks.-20",
    "playback_marks.0",
    "playback_marks.20",
)
VOICE_FIELDS = (
    "consent_basis",
    "recording_sha256",
    "clip_duration_s",
    "spoken_language",
    "playback_device_make_model",
    "fixed_volume_setting",
)
DEVICE_FIELDS = (
    "computer_os_and_build",
    "browser_and_version",
    "camera_make_model",
    "microphone_make_model",
    "audio_input_selected",
    "media_device_settings",
    "recorder_sha256",
    "model_sha256",
    "runtime_tarball_sha256",
)

LEDGER_FIELDS = (
    "schedule_index",
    "trial_id",
    "room",
    "visible_heading_deg",
    "condition_id",
    "role",
    "duration_s",
    "playback_voice_id",
    "playback_heading_deg",
    "attempt_number",
    "capture_status",
    "objective_exclusion_reason",
    "output_file",
    "output_sha256",
    "operator_note",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_once(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        return
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def blank_room(room_id: str) -> dict[str, Any]:
    return {
        "schema": "reachy-avsync-confirmation-room-binding-v1",
        "opaque_room_id": room_id,
        "status": "INCOMPLETE_DO_NOT_COLLECT",
        "confirmation_not_v2_pilot_room": None,
        "approximate_dimensions_m": {"length": None, "width": None, "height": None},
        "dominant_surface_and_furnishing_description": None,
        "background_audio_dbfs_10s": None,
        "camera_mark": None,
        "microphone_mark": None,
        "visible_person_marks": {"-20": None, "0": None, "20": None},
        "playback_marks": {"-20": None, "0": None, "20": None},
        "private_location_note": None,
    }


def blank_voice(voice_id: str) -> dict[str, Any]:
    return {
        "schema": "reachy-avsync-confirmation-voice-binding-v1",
        "opaque_voice_id": voice_id,
        "status": "INCOMPLETE_DO_NOT_COLLECT",
        "consent_basis": None,
        "recording_sha256": None,
        "clip_duration_s": None,
        "spoken_language": None,
        "playback_device_make_model": None,
        "fixed_volume_setting": None,
        "private_identity_note": None,
    }


def blank_device(browser: str | None) -> dict[str, Any]:
    return {
        "schema": "reachy-avsync-confirmation-device-binding-v1",
        "status": "INCOMPLETE_DO_NOT_COLLECT",
        "computer_os_and_build": platform.platform(),
        "browser_and_version": browser,
        "camera_candidates_observed_without_capture": ["HP HD Camera", "HP IR Camera"],
        "camera_make_model": None,
        "microphone_candidates_observed_without_capture": [
            "Microphone (Conexant ISST Audio) [started]",
            "Headset (AirPods Pro) [disconnected at inventory]",
        ],
        "microphone_make_model": None,
        "audio_input_selected": None,
        "media_device_settings": None,
        "playback_output_candidates_observed_without_playback": [
            "Speakers (Conexant ISST Audio) [started]",
            "Headphones (AirPods Pro) [disconnected at inventory]",
        ],
        "recorder_path": "tools/avsync_confirmation_recorder.html",
        "recorder_sha256": sha256_file(ROOT / "tools" / "avsync_confirmation_recorder.html"),
        "model_sha256": "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff",
        "runtime_tarball_sha256": "ee318eaa3d42230aa10910d114faf2a488c577c4e4d33c7cb04126924aca505f",
        "headset_rule_acknowledged": None,
    }


def render_ledger(protocol: dict[str, Any]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=LEDGER_FIELDS, lineterminator="\n")
    writer.writeheader()
    for index, card in enumerate(protocol["randomization"]["schedule"], start=1):
        writer.writerow(
            {
                "schedule_index": index,
                **card,
                "playback_voice_id": card["playback_voice_id"] or "",
                "playback_heading_deg": (
                    "" if card["playback_heading_deg"] is None else card["playback_heading_deg"]
                ),
                "attempt_number": 1,
                "capture_status": "NOT_STARTED",
            }
        )
    return stream.getvalue()


def initialize(browser: str | None) -> None:
    protocol = load_json(PROTOCOL)
    RECORDS.mkdir(parents=True, exist_ok=True)
    CAPTURES.mkdir(parents=True, exist_ok=True)
    write_json_once(RECORDS / "device.json", blank_device(browser))
    for room_id in ("room_a", "room_b", "room_c"):
        write_json_once(RECORDS / f"{room_id}.json", blank_room(room_id))
    for voice_id in ("voice_a", "voice_b"):
        write_json_once(RECORDS / f"{voice_id}.json", blank_voice(voice_id))
    if not LEDGER.exists():
        LEDGER.write_text(render_ledger(protocol), encoding="utf-8", newline="")
    if not GUIDE.exists():
        GUIDE.write_text(
            "# Private AV-synchrony confirmation bindings\n\n"
            "Status: **INCOMPLETE — DO NOT COLLECT** until `--status` reports "
            "`opening_gate_ready=true` and `--seal` succeeds.\n\n"
            "1. Complete `bindings/device.json` with the devices actually selected in the browser.\n"
            "2. Complete the three opaque room records; keep exact addresses out of them.\n"
            "3. Complete both voice records and hash each consented audio file.\n"
            "4. Keep `captures/` empty until sealing. Do not reuse any V1/V2 pilot capture.\n"
            "5. Run `python scripts/prepare_av_synchrony_confirmation_workspace.py --status`, "
            "then `--seal`.\n\n"
            "6. Serve the repository on localhost and use only "
            "`tools/avsync_confirmation_recorder.html`.\n\n"
            "Sealing freezes setup identity; it does not authorize robot activity.\n",
            encoding="utf-8",
        )


def nested_value(payload: dict[str, Any], dotted: str) -> Any:
    value: Any = payload
    for part in dotted.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def missing_required(path: Path, fields: tuple[str, ...]) -> list[str]:
    if not path.is_file():
        return [f"{path.name}: file missing"]
    payload = load_json(path)
    missing = []
    for field in fields:
        value = nested_value(payload, field)
        if value is None or value == "" or value == []:
            missing.append(f"{path.name}: {field}")
    return missing


def ledger_issues(protocol: dict[str, Any]) -> list[str]:
    if not LEDGER.is_file():
        return ["attempt_ledger.csv: file missing"]
    with LEDGER.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    schedule = protocol["randomization"]["schedule"]
    if len(rows) != len(schedule):
        return [f"attempt_ledger.csv: expected {len(schedule)} initial rows, found {len(rows)}"]
    issues = []
    for index, (row, card) in enumerate(zip(rows, schedule, strict=True), start=1):
        if row["schedule_index"] != str(index) or row["trial_id"] != card["trial_id"]:
            issues.append(f"attempt_ledger.csv: schedule mismatch at row {index}")
    return issues


def status() -> tuple[list[str], list[str]]:
    protocol = load_json(PROTOCOL)
    structural = ledger_issues(protocol)
    if not EXECUTION.is_file():
        structural.append("confirmation execution manifest: file missing")
    else:
        execution = load_json(EXECUTION)
        if execution.get("protocol_fingerprint") != protocol.get("fingerprint"):
            structural.append("confirmation execution manifest: protocol mismatch")
    if not CAPTURES.is_dir():
        structural.append("captures/: directory missing")
    elif any(CAPTURES.iterdir()):
        structural.append("captures/: must be empty before the opening gate")
    missing = missing_required(RECORDS / "device.json", DEVICE_FIELDS)
    for room_id in ("room_a", "room_b", "room_c"):
        missing.extend(missing_required(RECORDS / f"{room_id}.json", ROOM_FIELDS))
    for voice_id in ("voice_a", "voice_b"):
        missing.extend(missing_required(RECORDS / f"{voice_id}.json", VOICE_FIELDS))
    device_path = RECORDS / "device.json"
    if device_path.is_file():
        device = load_json(device_path)
        if device.get("headset_rule_acknowledged") is not True:
            missing.append("device.json: headset_rule_acknowledged")
        recorder_path = device.get("recorder_path")
        if recorder_path != "tools/avsync_confirmation_recorder.html":
            structural.append("device.json: recorder_path is not the confirmation recorder")
        else:
            expected = sha256_file(ROOT / recorder_path)
            if device.get("recorder_sha256") != expected:
                structural.append("device.json: recorder_sha256 is stale")
    return structural, missing


def seal() -> None:
    structural, missing = status()
    if structural or missing:
        for issue in (*structural, *missing):
            print(f"INCOMPLETE: {issue}", file=sys.stderr)
        raise RuntimeError("private bindings are incomplete; no manifest was sealed")
    for path in sorted(RECORDS.glob("*.json")):
        record = load_json(path)
        record["status"] = "COMPLETE_BEFORE_FIRST_PREVIEW_OR_CAPTURE"
        path.write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    files = [LEDGER, *(sorted(RECORDS.glob("*.json")))]
    payload = {
        "schema": "reachy-avsync-confirmation-private-binding-manifest-v1",
        "status": "SEALED_BEFORE_FIRST_PREVIEW_OR_CAPTURE",
        "protocol_fingerprint": load_json(PROTOCOL)["fingerprint"],
        "protocol_sha256": sha256_file(PROTOCOL),
        "execution_fingerprint": load_json(EXECUTION)["fingerprint"],
        "execution_sha256": sha256_file(EXECUTION),
        "files": [
            {"path": path.relative_to(PRIVATE_ROOT).as_posix(), "sha256": sha256_file(path)}
            for path in files
        ],
        "captures_directory_empty": True,
    }
    SEALED_MANIFEST.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    sidecar = SEALED_MANIFEST.with_suffix(SEALED_MANIFEST.suffix + ".sha256")
    sidecar.write_text(f"{sha256_file(SEALED_MANIFEST)}  {SEALED_MANIFEST.name}\n", encoding="ascii")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--initialize", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--seal", action="store_true")
    parser.add_argument("--browser", help="Observed browser name and version; does not launch it.")
    args = parser.parse_args()
    if sum((args.initialize, args.status, args.seal)) != 1:
        parser.error("choose exactly one of --initialize, --status, or --seal")
    try:
        if args.initialize:
            initialize(args.browser)
        if args.seal:
            seal()
        structural, missing = status()
        if structural:
            for issue in structural:
                print(f"FAIL: {issue}", file=sys.stderr)
            return 1
        print(f"Private workspace: {PRIVATE_ROOT}")
        print("schedule_rows=54")
        print("captures_directory_empty=true")
        print(f"missing_human_bindings={len(missing)}")
        print(f"opening_gate_ready={'true' if not missing else 'false'}")
        if missing:
            for issue in missing:
                print(f"NEEDS INPUT: {issue}")
        return 0
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
