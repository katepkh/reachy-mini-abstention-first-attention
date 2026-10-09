"""Private, append-only attempt accounting and content-addressed pilot gates.

No sensor or network access. Files are written only by explicit CLI operations.
"""
from __future__ import annotations

import json
import shutil
import sys
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path

from .joint_pilot_execution import sha256_file
from .robot_camera_commissioning import robot_camera_execution_payload
from .robot_pilot_protocol import fingerprint, protocol

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "data/private/robot_camera_pilot_v1"
MANIFEST = ROOT / "evidence/manifests/robot_camera_pilot_execution_v1.json"
PROTOCOL_MANIFEST = ROOT / "evidence/manifests/robot_camera_pilot_protocol_v1.json"
NEW_FILES = (
    "reachy_stage3v/robot_pilot_protocol.py", "reachy_stage3v/robot_pilot_analysis.py",
    "reachy_stage3v/robot_pilot_store.py", "scripts/robot_camera_pilot.py",
    "scripts/run_robot_camera_pilot.py", "tools/robot_camera_pilot.html",
    "tools/robot_pilot_ui.mjs", "start_robot_camera_pilot.cmd",
    "reachy_stage3v/joint_pilot_protocol.py", "reachy_stage3v/joint_pilot_analysis.py",
    "reachy_stage3v/joint_pilot_execution.py", "reachy_stage3v/joint_instrument.py",
    "reachy_avsync/synchrony.py", "reachy_stage2a/calibration.py",
    "reachy_doa/angles.py", "reachy_doa/client.py", "reachy_doa/models.py",
    "reachy_doa/config.py", "reachy_stage2a/config.py",
)
MIC_KEYS = ("sampleRate", "channelCount", "echoCancellation", "noiseSuppression", "autoGainControl")


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_new(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n")


def execution():
    base = robot_camera_execution_payload(ROOT)
    hashes = {**base["execution_build"]["files_sha256"],
              **{name: sha256_file(ROOT / name) for name in NEW_FILES}}
    dependencies = {}
    for package in ("numpy", "requests", "websockets", "aiortc", "av", "opencv-python", "opencv-python-headless"):
        try:
            dependencies[package] = version(package)
        except PackageNotFoundError:
            dependencies[package] = None
    core = {"schema": "reachy-camera-pilot-execution-v1",
            "protocol_fingerprint": protocol()["fingerprint"],
            "commissioned_build_fingerprint": base["execution_build"]["fingerprint"],
            "files_sha256": hashes, "python_version": sys.version.split()[0],
            "dependency_versions": dependencies, "motion_authority": False, "response_authority": False}
    return {**core, "fingerprint": fingerprint(core)}


def mic_binding(label, settings):
    return {"label": label, "settings": {key: settings.get(key) for key in MIC_KEYS}}


def initialize(old_setup: Path, stimulus: Path, *, volume: int, confirmed: bool):
    if not confirmed or not 0 <= volume <= 100:
        raise ValueError("Explicit unchanged-marks confirmation and fixed volume required")
    if PRIVATE.exists():
        raise ValueError("Private pilot workspace already exists; refusing to overwrite")
    prior = read(old_setup)
    if sha256_file(stimulus) != prior["playback"]["recording_sha256"]:
        raise ValueError("Playback file does not match the previously bound stimulus")
    setup = {"schema": "reachy-camera-pilot-setup-v1", "status": "SEALED_BEFORE_TRIAL_1",
             "room": prior["room"], "marks": dict(prior["marks"]),
             "camera": {"source": "Reachy Mini Wireless", "source_width": 1280, "source_height": 720,
                        "processed_width": 640, "processed_height": 360,
                        "projection": "Pollen normalized Wireless intrinsics; no fitted offset"},
             "microphone": mic_binding(prior["microphone"]["device_label"], prior["microphone"]["device_settings"]),
             "playback": {**prior["playback"], "fixed_volume_percent": volume,
                          "start_instruction": "Restart from beginning immediately before capture; keep playback running throughout ten seconds. Manual onset offset is not measured."},
             "reachy": prior["reachy"],
             "sensor_boundary": "Reachy video and DoA; external laptop microphone; no laptop video",
             "historical_volume_percent": prior["playback"]["fixed_volume_percent"]}
    setup["marks"]["laptop"] = "Laptop at the unchanged marked desk position; external microphone only, laptop camera unused."
    setup["marks"]["reachy"] = "Reachy fixed at its unchanged mark, camera facing the one-metre front operator mark. No movement."
    expected = execution()
    if not MANIFEST.is_file() or read(MANIFEST) != expected:
        raise ValueError("Freeze the tested execution manifest before sealing")
    write_new(PRIVATE / "setup.json", setup)
    (PRIVATE / "attempts").mkdir()
    core = {"schema": "reachy-camera-pilot-binding-v1", "setup_sha256": sha256_file(PRIVATE / "setup.json"),
            "protocol_fingerprint": protocol()["fingerprint"], "execution_fingerprint": expected["fingerprint"],
            "microphone_fingerprint": fingerprint(setup["microphone"]),
            "contains_raw_media": False, "motion_authority": False, "response_authority": False}
    write_new(PRIVATE / "binding.json", {**core, "fingerprint": fingerprint(core)})


def verify_document(document):
    core = {k: v for k, v in document.items() if k != "fingerprint"}
    if document.get("fingerprint") != fingerprint(core):
        raise ValueError("Content-addressed document fingerprint mismatch")


def records():
    result = []
    for folder in sorted((PRIVATE / "attempts").glob("*")):
        if not folder.is_dir() or not (folder / "assessment.json").is_file():
            raise ValueError("Incomplete attempt archive; inspect before continuing")
        item = read(folder / "assessment.json")
        verify_document(item)
        for name, expected in item["source_hashes"].items():
            if sha256_file(folder / name) != expected:
                raise ValueError("An archived attempt changed")
        result.append((folder, item))
    return result


def accepted_sources():
    return [{"attempt": folder.name, **item["source_hashes"]}
            for folder, item in records() if item["quality"]["passed"]]


def verify_seal():
    if not PROTOCOL_MANIFEST.is_file() or read(PROTOCOL_MANIFEST) != protocol():
        raise ValueError("Protocol manifest missing or stale")
    expected = execution()
    if not MANIFEST.is_file() or read(MANIFEST) != expected:
        raise ValueError("Execution manifest missing or stale")
    seal = read(PRIVATE / "binding.json")
    verify_document(seal)
    if (seal["execution_fingerprint"] != expected["fingerprint"] or
        seal["protocol_fingerprint"] != protocol()["fingerprint"] or
        seal["setup_sha256"] != sha256_file(PRIVATE / "setup.json")):
        raise ValueError("Private setup or execution changed after sealing")
    return expected, seal


def collection_state():
    expected, seal = verify_seal()
    schedule = protocol()["schedule"]
    entries = records()
    next_index = 0
    attempts = 0
    for _, item in entries:
        if next_index >= 21 or item["trial_id"] != schedule[next_index]["trial_id"]:
            raise ValueError("Attempt order differs from the frozen schedule")
        attempts += 1
        if attempts > 2:
            raise ValueError("Attempt budget exceeded")
        if item["quality"]["passed"]:
            next_index += 1
            attempts = 0
    if attempts >= 2:
        raise ValueError("Two failed attempts: stop for repair/new protocol, do not keep repeating")
    if next_index >= 14:
        development = read(PRIVATE / "development.json")
        verify_document(development)
        if (development.get("source_hashes") != accepted_sources()[:14] or
            development.get("execution_fingerprint") != expected["fingerprint"] or
            not development.get("validation_open")):
            raise ValueError("Development setting is not sealed for validation")
    return {"ready": next_index < 21, "next_trial": schedule[next_index] if next_index < 21 else None,
            "attempt_number": attempts + 1, "binding_fingerprint": seal["fingerprint"],
            "execution_fingerprint": expected["fingerprint"],
            "microphone_fingerprint": seal["microphone_fingerprint"],
            "microphone": read(PRIVATE / "setup.json")["microphone"],
            "accepted_count": next_index, "reason": "Complete" if next_index == 21 else ""}


def safe_state():
    try:
        return collection_state()
    except (ValueError, KeyError, FileNotFoundError) as error:
        return {"ready": False, "next_trial": None, "reason": str(error)}


def import_attempt(csv_path: Path, metadata_path: Path):
    from .robot_pilot_analysis import quality
    state = collection_state()
    if not state["ready"]:
        raise ValueError("Collection is closed")
    card = state["next_trial"]
    metadata = read(metadata_path)
    expected = {"schema": "reachy-camera-pilot-capture-v1",
                "pilot_protocol_fingerprint": protocol()["fingerprint"],
                "pilot_execution_fingerprint": state["execution_fingerprint"],
                "binding_fingerprint": state["binding_fingerprint"],
                "microphone_fingerprint": state["microphone_fingerprint"],
                "csv_sha256": sha256_file(csv_path), "attempt_number": state["attempt_number"],
                **{k: card[k] for k in ("trial_id", "condition_id", "schedule_index", "role", "split", "repetition")}}
    for key, value in expected.items():
        if metadata.get(key) != value:
            raise ValueError(f"Capture metadata mismatch: {key}")
    for key in ("motion_commands", "response_commands", "uploads"):
        if metadata.get(key) != 0:
            raise ValueError(f"Nonzero or missing authority/privacy field: {key}")
    for key in ("contains_pixels", "contains_waveform", "contains_transcript", "contains_identity_embedding"):
        if metadata.get(key) is not False:
            raise ValueError(f"Invalid privacy declaration: {key}")
    base = robot_camera_execution_payload(ROOT)
    if (metadata.get("execution_build") != base["execution_build"] or
        metadata.get("instrument_fingerprint") != base["fingerprint"] or
        metadata.get("pipeline_diagnostics") != base["pipeline_diagnostics"]):
        raise ValueError("Commissioned sensor build/timing identity mismatch")
    report, rows = quality(csv_path, card)
    if metadata.get("sample_count") != len(rows):
        raise ValueError("Metadata/CSV sample count mismatch")
    if metadata.get("microphone") != state["microphone"]:
        raise ValueError("Microphone binding mismatch")
    if metadata.get("microphone_uninterrupted") is not True:
        report["failures"].append("MICROPHONE_INTERRUPTED")
    if metadata.get("audio_context_sample_rate_hz") != state["microphone"]["settings"]["sampleRate"]:
        report["failures"].append("AUDIO_CLOCK_RATE_MISMATCH")
    expected_size = read(PRIVATE / "setup.json")["camera"]
    for row in rows:
        if any(float(row[key] or 0) != expected_size[setting] for key, setting in (
                ("robot_frame_source_width_px", "source_width"),
                ("robot_frame_source_height_px", "source_height"),
                ("robot_frame_width_px", "processed_width"),
                ("robot_frame_height_px", "processed_height"))):
            report["failures"].append("CAMERA_RESOLUTION_CHANGED")
            break
    report["passed"] = not report["failures"]
    folder = PRIVATE / "attempts" / f'{card["schedule_index"]:02d}-{state["attempt_number"]:02d}'
    folder.mkdir()  # exclusive; never overwrite a previous attempt
    shutil.copyfile(csv_path, folder / "capture.csv")
    shutil.copyfile(metadata_path, folder / "metadata.json")
    core = {"trial_id": card["trial_id"], "quality": report,
            "source_hashes": {"capture.csv": sha256_file(folder / "capture.csv"),
                              "metadata.json": sha256_file(folder / "metadata.json")}}
    write_new(folder / "assessment.json", {**core, "fingerprint": fingerprint(core)})
    return report


def load_split(split):
    from .robot_pilot_analysis import quality
    by_id = {c["trial_id"]: c for c in protocol()["schedule"]}
    loaded = []
    for folder, assessment in records():
        card = by_id[assessment["trial_id"]]
        if assessment["quality"]["passed"] and card["split"] == split:
            report, rows = quality(folder / "capture.csv", card)
            meta = read(folder / "metadata.json")
            loaded.append((card, report, rows, float(meta["microphone"]["settings"]["sampleRate"])))
    return loaded


def freeze_development():
    from .robot_pilot_analysis import select_development
    if (PRIVATE / "development.json").exists():
        raise ValueError("Development has already been evaluated and frozen")
    verify_seal()
    # Do not require collection_state(), which deliberately blocks at this boundary.
    if len(accepted_sources()) != 14 or any(not item["quality"]["passed"]
            for _, item in records()[-1:]):
        raise ValueError("Exactly fourteen accepted development trials required")
    core = {**select_development(load_split("development")),
            "source_hashes": accepted_sources(), "execution_fingerprint": execution()["fingerprint"]}
    write_new(PRIVATE / "development.json", {**core, "fingerprint": fingerprint(core)})
    return core


def finish_validation():
    from .robot_pilot_analysis import validate_once
    if (PRIVATE / "validation.json").exists():
        raise ValueError("Internal validation has already been evaluated once")
    state = collection_state()
    if state["accepted_count"] != 21:
        raise ValueError("All twenty-one trials required")
    core = {**validate_once(load_split("internal_validation"), read(PRIVATE / "development.json")),
            "source_hashes": accepted_sources(), "execution_fingerprint": execution()["fingerprint"]}
    write_new(PRIVATE / "validation.json", {**core, "fingerprint": fingerprint(core)})
    return core


def record_abort():
    """Explicit operator-reported abort with no downloadable pair; counts as an attempt."""
    state = collection_state()
    if not state["ready"]:
        raise ValueError("No open trial")
    card = state["next_trial"]
    folder = PRIVATE / "attempts" / f'{card["schedule_index"]:02d}-{state["attempt_number"]:02d}'
    folder.mkdir()
    core = {"trial_id": card["trial_id"], "quality": {"passed": False,
            "failures": ["OPERATOR_REPORTED_ABORT_NO_DOWNLOAD"]}, "source_hashes": {}}
    write_new(folder / "assessment.json", {**core, "fingerprint": fingerprint(core)})
    return core
