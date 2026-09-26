"""Ignored private bindings and seal for the command-free joint pilot."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any

from .joint_pilot_execution import EXECUTION_MANIFEST, ROOT, build_execution_payload, sha256_file
from .joint_pilot_protocol import joint_pilot_protocol_payload, randomized_joint_pilot_trials


PRIVATE_ROOT = ROOT / "data" / "private" / "joint_shadow_pilot_v1"
SETUP = PRIVATE_ROOT / "setup.json"
CAPTURES = PRIVATE_ROOT / "captures"
LEDGER = PRIVATE_ROOT / "attempt_ledger.csv"
SEALED_MANIFEST = PRIVATE_ROOT / "binding_manifest.json"
GUIDE = PRIVATE_ROOT / "README.md"

SETUP_FIELDS = (
    "opaque_setup_id",
    "room.opaque_room_id",
    "room.approximate_dimensions_m.length",
    "room.approximate_dimensions_m.width",
    "room.approximate_dimensions_m.height",
    "room.surface_and_furnishing_description",
    "room.background_audio_dbfs_10s",
    "marks.laptop",
    "marks.reachy",
    "marks.operator",
    "marks.phone_colocated_with_face_within_10_deg",
    "marks.phone_spatial_conflict_at_least_45_deg",
    "camera.horizontal_fov_deg_estimate",
    "camera.device_label",
    "camera.device_settings",
    "microphone.device_label",
    "microphone.device_settings",
    "reachy.model",
    "reachy.daemon_version",
    "playback.recording_sha256",
    "playback.recording_bytes",
    "playback.recording_suffix",
    "playback.phone_make_model",
    "playback.fixed_volume_percent",
)

LEDGER_FIELDS = (
    "schedule_index",
    "trial_id",
    "condition_id",
    "role",
    "repetition",
    "split",
    "attempt_number",
    "capture_status",
    "objective_exclusion_reason",
    "csv_file",
    "csv_sha256",
    "metadata_file",
    "metadata_sha256",
    "operator_note",
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _nested(payload: dict[str, Any], dotted: str) -> Any:
    value: Any = payload
    for part in dotted.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _blank_setup() -> dict[str, Any]:
    return {
        "schema": "reachy-joint-shadow-pilot-private-setup-v1",
        "status": "INCOMPLETE_DO_NOT_COLLECT",
        "opaque_setup_id": "room_a_joint_v1",
        "room": {
            "opaque_room_id": "room_a",
            "approximate_dimensions_m": {"length": None, "width": None, "height": None},
            "surface_and_furnishing_description": None,
            "background_audio_dbfs_10s": None,
        },
        "marks": {
            "laptop": None,
            "reachy": None,
            "operator": None,
            "phone_colocated_with_face_within_10_deg": None,
            "phone_spatial_conflict_at_least_45_deg": None,
        },
        "camera": {
            "horizontal_fov_deg_estimate": None,
            "device_label": None,
            "device_settings": None,
        },
        "microphone": {"device_label": None, "device_settings": None},
        "reachy": {"model": "Reachy Mini Wireless", "daemon_version": "1.9.0"},
        "playback": {
            "recording_sha256": None,
            "recording_bytes": None,
            "recording_suffix": None,
            "phone_make_model": None,
            "fixed_volume_percent": None,
        },
        "privacy_note": (
            "No identity, consent correspondence, external approval record, address, "
            "raw audio, or raw image is stored in this binding."
        ),
    }


def _render_ledger() -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=LEDGER_FIELDS, lineterminator="\n")
    writer.writeheader()
    for trial in randomized_joint_pilot_trials():
        writer.writerow(
            {
                **{key: trial[key] for key in ("schedule_index", "trial_id", "condition_id", "role", "repetition", "split")},
                "attempt_number": 1,
                "capture_status": "NOT_STARTED",
            }
        )
    return stream.getvalue()


def initialize(*, room_source: Path | None = None, commissioning_metadata: Path | None = None) -> None:
    """Create ignored records without overwriting existing human bindings."""

    PRIVATE_ROOT.mkdir(parents=True, exist_ok=True)
    CAPTURES.mkdir(parents=True, exist_ok=True)
    if not SETUP.exists():
        setup = _blank_setup()
        if room_source is not None:
            room = _load(room_source.resolve())
            setup["room"]["opaque_room_id"] = room.get("opaque_room_id", "room_a")
            setup["room"]["approximate_dimensions_m"] = room.get("approximate_dimensions_m")
            setup["room"]["surface_and_furnishing_description"] = room.get(
                "dominant_surface_and_furnishing_description"
            )
            setup["room"]["background_audio_dbfs_10s"] = room.get("background_audio_dbfs_10s")
            setup["marks"]["laptop"] = room.get("camera_mark")
        if commissioning_metadata is not None:
            metadata = _load(commissioning_metadata.resolve())
            setup["camera"]["horizontal_fov_deg_estimate"] = metadata.get(
                "camera_horizontal_fov_deg_estimate"
            )
            for device in metadata.get("devices", []):
                kind = device.get("kind")
                if kind == "video":
                    setup["camera"]["device_label"] = device.get("label")
                    setup["camera"]["device_settings"] = device.get("settings")
                if kind == "audio":
                    setup["microphone"]["device_label"] = device.get("label")
                    setup["microphone"]["device_settings"] = device.get("settings")
        SETUP.write_text(json.dumps(setup, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not LEDGER.exists():
        LEDGER.write_text(_render_ledger(), encoding="utf-8", newline="")
    if not GUIDE.exists():
        GUIDE.write_text(
            "# Private joint-shadow pilot workspace\n\n"
            "Keep this directory private and ignored. Complete setup.json, then run "
            "`python scripts/prepare_joint_shadow_pilot_workspace.py --status`. "
            "Seal only before Trial 1. Sealing authorizes numeric collection only; "
            "it never authorizes motion or a response.\n",
            encoding="utf-8",
        )


def bind_stimulus(path: Path, *, phone_make_model: str, volume_percent: int) -> None:
    if not SETUP.is_file():
        raise RuntimeError("Initialize the private workspace first.")
    source = path.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if not phone_make_model.strip() or not 0 <= volume_percent <= 100:
        raise ValueError("Phone model is required and volume must be between 0 and 100.")
    setup = _load(SETUP)
    setup["playback"] = {
        "recording_sha256": sha256_file(source),
        "recording_bytes": source.stat().st_size,
        "recording_suffix": source.suffix.lower(),
        "phone_make_model": phone_make_model.strip(),
        "fixed_volume_percent": volume_percent,
    }
    SETUP.write_text(json.dumps(setup, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def import_device_binding(path: Path) -> None:
    if not SETUP.is_file():
        raise RuntimeError("Initialize the private workspace first.")
    binding = _load(path.resolve())
    if binding.get("schema") != "reachy-joint-shadow-private-device-binding-v1":
        raise ValueError("Unexpected device-binding schema.")
    devices = binding.get("devices")
    if not isinstance(devices, list):
        raise ValueError("Device binding has no device list.")
    setup = _load(SETUP)
    setup["camera"]["horizontal_fov_deg_estimate"] = binding.get(
        "camera_horizontal_fov_deg_estimate"
    )
    for device in devices:
        if device.get("kind") == "video":
            setup["camera"]["device_label"] = device.get("label")
            setup["camera"]["device_settings"] = device.get("settings")
        if device.get("kind") == "audio":
            setup["microphone"]["device_label"] = device.get("label")
            setup["microphone"]["device_settings"] = device.get("settings")
    SETUP.write_text(json.dumps(setup, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def bind_marks(*, reachy: str, operator: str, phone_colocated: str, phone_conflict: str) -> None:
    if not SETUP.is_file():
        raise RuntimeError("Initialize the private workspace first.")
    values = (reachy, operator, phone_colocated, phone_conflict)
    if any(not value.strip() for value in values):
        raise ValueError("Every physical mark description is required.")
    setup = _load(SETUP)
    setup["marks"].update(
        {
            "reachy": reachy.strip(),
            "operator": operator.strip(),
            "phone_colocated_with_face_within_10_deg": phone_colocated.strip(),
            "phone_spatial_conflict_at_least_45_deg": phone_conflict.strip(),
        }
    )
    SETUP.write_text(json.dumps(setup, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _ledger_issues() -> list[str]:
    if not LEDGER.is_file():
        return ["attempt_ledger.csv: file missing"]
    with LEDGER.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    schedule = randomized_joint_pilot_trials()
    if len(rows) != len(schedule):
        return [f"attempt_ledger.csv: expected 21 rows, found {len(rows)}"]
    issues = []
    for index, (row, trial) in enumerate(zip(rows, schedule, strict=True), start=1):
        if row.get("schedule_index") != str(index) or row.get("trial_id") != trial["trial_id"]:
            issues.append(f"attempt_ledger.csv: schedule mismatch at row {index}")
    return issues


def preseal_status() -> tuple[list[str], list[str]]:
    structural = _ledger_issues()
    expected_execution = build_execution_payload()
    if not EXECUTION_MANIFEST.is_file():
        structural.append("execution manifest: missing")
    elif _load(EXECUTION_MANIFEST) != expected_execution:
        structural.append("execution manifest: stale")
    if not CAPTURES.is_dir():
        structural.append("captures/: directory missing")
    elif any(CAPTURES.iterdir()):
        structural.append("captures/: must be empty before sealing")
    missing = []
    if not SETUP.is_file():
        missing.append("setup.json: file missing")
    else:
        setup = _load(SETUP)
        for field in SETUP_FIELDS:
            value = _nested(setup, field)
            if value is None or value == "" or value == [] or value == {}:
                missing.append(f"setup.json: {field}")
        volume = _nested(setup, "playback.fixed_volume_percent")
        if volume is not None and not 0 <= int(volume) <= 100:
            structural.append("setup.json: playback.fixed_volume_percent outside 0..100")
    return structural, missing


def seal() -> None:
    structural, missing = preseal_status()
    if structural or missing:
        raise RuntimeError("Private bindings are incomplete; no manifest was sealed.")
    setup = _load(SETUP)
    setup["status"] = "SEALED_BEFORE_TRIAL_1"
    SETUP.write_text(json.dumps(setup, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    execution = _load(EXECUTION_MANIFEST)
    payload = {
        "schema": "reachy-joint-shadow-pilot-private-binding-manifest-v1",
        "status": "SEALED_BEFORE_TRIAL_1",
        "opaque_setup_id": setup["opaque_setup_id"],
        "protocol_fingerprint": joint_pilot_protocol_payload()["fingerprint"],
        "execution_fingerprint": execution["fingerprint"],
        "setup_sha256": sha256_file(SETUP),
        "initial_ledger_sha256": sha256_file(LEDGER),
        "captures_directory_empty_at_seal": True,
        "contains_identity": False,
        "contains_external_correspondence": False,
        "contains_approval_record": False,
        "contains_raw_media": False,
        "motion_authority": False,
        "response_authority": False,
    }
    SEALED_MANIFEST.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    SEALED_MANIFEST.with_suffix(SEALED_MANIFEST.suffix + ".sha256").write_text(
        f"{sha256_file(SEALED_MANIFEST)}  {SEALED_MANIFEST.name}\n", encoding="ascii"
    )


def sealed_gate_status() -> dict[str, Any]:
    reasons: list[str] = []
    expected_execution = build_execution_payload()
    if not EXECUTION_MANIFEST.is_file() or _load(EXECUTION_MANIFEST) != expected_execution:
        reasons.append("EXECUTION_MANIFEST_MISSING_OR_STALE")
        execution = None
    else:
        execution = expected_execution
    if not SEALED_MANIFEST.is_file():
        reasons.append("PRIVATE_BINDING_MANIFEST_NOT_SEALED")
        manifest = None
    else:
        manifest = _load(SEALED_MANIFEST)
        sidecar = SEALED_MANIFEST.with_suffix(SEALED_MANIFEST.suffix + ".sha256")
        expected_sidecar = f"{sha256_file(SEALED_MANIFEST)}  {SEALED_MANIFEST.name}\n"
        if not sidecar.is_file() or sidecar.read_text(encoding="ascii") != expected_sidecar:
            reasons.append("PRIVATE_BINDING_MANIFEST_HASH_INVALID")
    if manifest is not None:
        if manifest.get("status") != "SEALED_BEFORE_TRIAL_1":
            reasons.append("PRIVATE_BINDING_STATUS_INVALID")
        if manifest.get("protocol_fingerprint") != joint_pilot_protocol_payload()["fingerprint"]:
            reasons.append("PRIVATE_BINDING_PROTOCOL_MISMATCH")
        if execution is None or manifest.get("execution_fingerprint") != execution.get("fingerprint"):
            reasons.append("PRIVATE_BINDING_EXECUTION_MISMATCH")
        if not SETUP.is_file() or manifest.get("setup_sha256") != sha256_file(SETUP):
            reasons.append("PRIVATE_SETUP_CHANGED_AFTER_SEAL")
    return {
        "status": "READY_FOR_COLLECTION" if not reasons else "COLLECTION_GATE_CLOSED",
        "ready": not reasons,
        "reasons": reasons,
        "execution_fingerprint": execution.get("fingerprint") if execution else None,
        "binding_manifest_sha256": sha256_file(SEALED_MANIFEST) if SEALED_MANIFEST.is_file() else None,
        "private_values_exposed": False,
        "motion_authority": False,
        "response_authority": False,
    }
