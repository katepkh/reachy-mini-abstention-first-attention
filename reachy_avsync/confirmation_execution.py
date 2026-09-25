"""Content-addressed execution contract for the frozen confirmation design."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .confirmation_protocol import confirmation_protocol_payload


IMPLEMENTATION_PATHS = (
    "reachy_avsync/synchrony.py",
    "reachy_avsync/confirmation_analysis.py",
    "scripts/analyze_av_synchrony_confirmation.py",
    "tools/avsync_confirmation_recorder.html",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def confirmation_execution_payload(project_root: Path) -> dict[str, Any]:
    project_root = project_root.resolve()
    protocol = confirmation_protocol_payload()
    implementation_files = []
    for relative in IMPLEMENTATION_PATHS:
        path = project_root / relative
        if not path.is_file():
            raise FileNotFoundError(f"Missing confirmation implementation: {relative}")
        implementation_files.append({"path": relative, "sha256": _sha256(path)})
    model = project_root / "models/avsync_v2/face_landmarker.task"
    if not model.is_file():
        raise FileNotFoundError("Pinned face-landmarker model is missing.")
    core: dict[str, Any] = {
        "schema": "reachy-av-synchrony-confirmation-execution-v1",
        "status": "FROZEN_BEFORE_FIRST_CONFIRMATION_PREVIEW_OR_CAPTURE",
        "protocol_fingerprint": protocol["fingerprint"],
        "protocol_file_sha256": _sha256(
            project_root
            / "evidence"
            / "manifests"
            / "av_synchrony_confirmation_protocol_v1.json"
        ),
        "sample_period_ms": 40,
        "required_columns": [
            "timestamp_ms",
            "audio_dbfs",
            "lip_aperture",
            "face_scale",
            "face_count",
        ],
        "quality_gates": protocol["quality_gates"],
        "randomized_schedule": protocol["randomization"]["schedule"],
        "instrument": {
            "runtime": "@mediapipe/tasks-vision",
            "runtime_version": "1.0.1",
            "runtime_tarball_sha256": (
                "ee318eaa3d42230aa10910d114faf2a488c577c4e4d33c7cb04126924aca505f"
            ),
            "model_path": "models/avsync_v2/face_landmarker.task",
            "model_sha256": _sha256(model),
            "delegate": "GPU",
            "running_mode": "VIDEO",
            "maximum_faces": 2,
            "capture_width": 320,
            "capture_height": 240,
            "scheduler": "deadline-anchored 40 ms cadence",
            "audio_processing": {
                "echoCancellation": False,
                "noiseSuppression": False,
                "autoGainControl": False,
            },
            "audio_definition": "20*log10(max(local microphone RMS, 1e-6))",
            "lip_aperture_definition": (
                "distance(landmarks 13,14) / distance(landmarks 33,263)"
            ),
        },
        "instrument_preflight": {
            "preview_measurements": 25,
            "maximum_median_landmark_inference_ms": 45.0,
            "failure_rule": "do not capture when the bound local instrument is too slow",
        },
        "candidate_scoring": {
            "unit": "one complete quality-passing ten-second trial",
            "method": "identical full-trial scoring path used for V2 candidate selection",
            "moving_average_samples": protocol["frozen_candidate"]["moving_average_samples"],
            "minimum_correlation": protocol["frozen_candidate"]["min_correlation"],
            "maximum_absolute_lag_ms": protocol["frozen_candidate"]["max_abs_lag_ms"],
            "retuning": "PROHIBITED",
        },
        "predeclared_baselines": {
            "acoustic_only_activity": "proposal iff full-trial audio dBFS SD is at least 0.5 dB",
            "visual_only_mouth_motion": (
                "proposal iff full-trial single-face lip-aperture SD is at least 0.002"
            ),
            "non_abstaining": "proposal on every accepted trial",
            "spatial_design_proxy": (
                "exploratory protocol-geometry proxy; not a replay of Stage 3V"
            ),
        },
        "analysis_opening_rule": (
            "do not run candidate or baseline analysis until all 54 canonical files exist, "
            "all pass frozen quality gates, and every attempt is retained"
        ),
        "known_identifiability_boundary": (
            "The five-column laptop instrument contains no acoustic direction or Stage 3V "
            "policy input fields. Therefore the frozen Stage 3V comparator, independently "
            "measured heading errors, wrong-sign outcomes, and streaming first-proposal "
            "latency are not identifiable from these captures. Report them as unresolved; "
            "do not replace them with the exploratory design proxy."
        ),
        "implementation_files": implementation_files,
        "privacy": {
            "uploads": 0,
            "raw_audio_saved": False,
            "pixels_saved": False,
            "transcripts_saved": False,
            "public_identifiers_saved": False,
        },
        "robot_scope": {
            "robot_connections": 0,
            "actuation_commands": 0,
            "required_robot_state": "powered off",
        },
    }
    encoded = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**core, "fingerprint": hashlib.sha256(encoded).hexdigest()}


__all__ = ["IMPLEMENTATION_PATHS", "confirmation_execution_payload"]
