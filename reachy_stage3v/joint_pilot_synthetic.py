"""Deterministic numeric fixtures for the frozen joint-pilot analyzer."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np

from .joint_instrument import JOINT_INSTRUMENT_SPEC_V1, JOINT_REQUIRED_COLUMNS
from .joint_pilot_execution import build_execution_payload, sha256_file
from .joint_pilot_protocol import joint_pilot_protocol_payload, randomized_joint_pilot_trials


def write_synthetic_joint_pilot(directory: Path) -> None:
    """Write a complete passing synthetic bundle without opening any device."""

    root = directory.resolve()
    root.mkdir(parents=True, exist_ok=True)
    protocol = joint_pilot_protocol_payload()
    execution = build_execution_payload()
    setup_path = root / "setup.json"
    setup_path.write_text(
        json.dumps(
            {
                "schema": "reachy-joint-shadow-pilot-synthetic-setup-v1",
                "status": "SEALED_BEFORE_TRIAL_1",
                "synthetic_fixture": True,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    manifest_path = root / "binding_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema": "reachy-joint-shadow-pilot-private-binding-manifest-v1",
                "status": "SEALED_BEFORE_TRIAL_1",
                "protocol_fingerprint": protocol["fingerprint"],
                "execution_fingerprint": execution["fingerprint"],
                "setup_sha256": sha256_file(setup_path),
                "synthetic_fixture": True,
                "contains_raw_media": False,
                "contains_identity": False,
                "contains_correspondence": False,
                "contains_approval_records": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    binding_manifest_sha256 = sha256_file(manifest_path)
    manifest_path.with_suffix(manifest_path.suffix + ".sha256").write_text(
        f"{binding_manifest_sha256}  {manifest_path.name}\n",
        encoding="ascii",
    )
    rng = np.random.default_rng(20260926)
    count = 201
    indices = np.arange(count, dtype=float)
    base = np.sin(2.0 * math.pi * indices / 25.0)
    interrupted = np.where((indices.astype(int) // 25) % 2 == 0, base, 0.0)

    for trial in randomized_joint_pilot_trials():
        condition = trial["condition_id"]
        if condition == "live_visible_interrupted":
            signal = interrupted
        else:
            signal = base
        audio = -42.0 + 4.0 * signal
        if condition in {"live_visible_continuous", "live_visible_interrupted"}:
            lip = 0.03 + 0.01 * signal
        elif condition == "silent_mouthing_unrelated_playback":
            lip = 0.03 + 0.008 * rng.normal(0.0, 1.0, count)
        else:
            lip = np.full(count, 0.03)
        visible = condition != "speech_without_usable_face"
        speech = condition != "visible_silence"
        doa_axis = 40.0 if condition == "spatial_conflict" else 90.0
        csv_path = root / f"{trial['trial_id']}.csv"
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=JOINT_REQUIRED_COLUMNS, lineterminator="\n")
            writer.writeheader()
            previous_lip = float(lip[0])
            for index in range(count):
                timestamp = index * 40.0
                current_lip = float(lip[index]) if visible else 0.0
                row = {column: "" for column in JOINT_REQUIRED_COLUMNS}
                row.update(
                    {
                        "timestamp_ms": timestamp,
                        "wall_time_iso": "2026-09-26T10:00:00.000Z",
                        "scheduler_lateness_ms": 1.0,
                        "sample_gap_ms": 0.0 if index == 0 else 40.0,
                        "audio_context_time_ms": timestamp,
                        "audio_dbfs": float(audio[index]) if speech else -70.0,
                        "face_count": 1 if visible else 0,
                        "face_center_x_norm": 0.5 if visible else "",
                        "face_center_y_norm": 0.5 if visible else "",
                        "face_heading_estimate_deg": 0.0 if visible else "",
                        "face_scale": 0.22 if visible else 0.0,
                        "lip_aperture": current_lip,
                        "lip_motion": abs(current_lip - previous_lip) if visible else 0.0,
                        "landmark_inference_ms": 18.0,
                        "video_frame_age_ms": 8.0,
                        "video_presented_frames": index,
                        "video_dropped_frames": 0,
                        "doa_valid": "true",
                        "doa_raw_angle_rad": math.radians(doa_axis),
                        "doa_axis_deg": doa_axis,
                        "doa_speech_detected": str(speech).lower(),
                        "doa_observed_ms": timestamp - 50.0,
                        "doa_received_ms": timestamp - 45.0,
                        "doa_age_ms": 50.0,
                        "doa_roundtrip_ms": 10.0,
                        "doa_clock_uncertainty_ms": 5.0,
                        "doa_robot_http_latency_ms": 4.0,
                        "doa_http_status": 200,
                        "doa_error_code": "",
                        "doa_poll_failures": 0,
                        "doa_poll_skips": 0,
                    }
                )
                writer.writerow(row)
                previous_lip = current_lip
        metadata = {
            "schema": "reachy-joint-shadow-pilot-trial-v1",
            "trial_id": trial["trial_id"],
            "protocol_fingerprint": JOINT_INSTRUMENT_SPEC_V1.payload()["fingerprint"],
            "instrument_fingerprint": JOINT_INSTRUMENT_SPEC_V1.payload()["fingerprint"],
            "pilot_protocol_fingerprint": protocol["fingerprint"],
            "execution_fingerprint": execution["fingerprint"],
            "binding_manifest_sha256": binding_manifest_sha256,
            "schedule_index": trial["schedule_index"],
            "repetition": trial["repetition"],
            "split": trial["split"],
            "condition_id": condition,
            "role": trial["role"],
            "duration_s": trial["duration_s"],
            "camera_horizontal_fov_deg_estimate": 60.0,
            "result": {"passed": True},
            "devices": [],
            "contains_pixels": False,
            "contains_waveform": False,
            "contains_transcript": False,
            "contains_identity_embedding": False,
            "uploads": 0,
            "actuation_commands": 0,
            "response_commands": 0,
            "claim_boundary": protocol["claim_boundary"],
        }
        (root / f"{trial['trial_id']}.metadata.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
