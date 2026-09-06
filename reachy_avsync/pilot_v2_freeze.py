"""Build a content-addressed freeze for a successful V2 pilot candidate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .pilot_v2 import analyze_pilot_v2
from .pilot_v2_protocol import pilot_v2_protocol_payload


IMPLEMENTATION_PATHS = (
    "reachy_avsync/synchrony.py",
    "reachy_avsync/pilot_v2.py",
    "reachy_avsync/pilot_v2_protocol.py",
    "tools/avsync_pilot_recorder_v2.html",
    "scripts/fetch_av_synchrony_v2_assets.py",
    "evidence/manifests/av_synchrony_pilot_protocol_v2.json",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash_files(project_root: Path, relative_paths: tuple[str, ...]) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for relative in relative_paths:
        path = project_root / relative
        if not path.is_file():
            raise FileNotFoundError(f"Missing freeze input: {relative}")
        records.append({"path": relative, "sha256": _sha256(path)})
    return records


def build_pilot_v2_candidate_freeze(input_dir: Path, project_root: Path) -> dict[str, Any]:
    """Reanalyze private inputs and freeze only a fully passing pilot candidate."""

    project_root = project_root.resolve()
    report = analyze_pilot_v2(input_dir)
    protocol = pilot_v2_protocol_payload()
    if report["protocol_fingerprint"] != protocol["fingerprint"]:
        raise ValueError("Pilot result does not match the current frozen protocol.")
    if report["status"] != "DEVELOPMENT_CANDIDATE_AWAITS_SEPARATE_CODE_THRESHOLD_FREEZE":
        raise ValueError("Pilot did not nominate a candidate for freezing.")
    if not report["development_selection_succeeded"] or not report["internal_validation_passed"]:
        raise ValueError("Development selection and internal validation must both pass.")
    selected = report["selected_candidate"]
    if selected is None:
        raise ValueError("Passing pilot result has no selected candidate.")

    model_path = project_root / "models/avsync_v2/face_landmarker.task"
    if not model_path.is_file() or _sha256(model_path) != protocol["instrument"]["model_sha256"]:
        raise ValueError("Installed face-landmarker model does not match the protocol.")
    runtime_root = project_root / "models/avsync_v2/runtime"
    runtime_paths = tuple(
        path.relative_to(project_root).as_posix()
        for path in sorted(runtime_root.rglob("*"))
        if path.is_file()
    )
    if not runtime_paths:
        raise FileNotFoundError("No installed V2 runtime assets were found.")

    core: dict[str, Any] = {
        "schema": "reachy-av-synchrony-pilot-v2-candidate-freeze",
        "status": "FROZEN_PILOT_CANDIDATE_NOT_CONFIRMATION",
        "protocol_fingerprint": report["protocol_fingerprint"],
        "source_bundle_sha256": report["source_bundle_sha256"],
        "sources": report["sources"],
        "candidate": {
            "spec": selected["spec"],
            "moving_average_samples": selected["moving_average_samples"],
        },
        "development_result": {
            "eligible_candidate_count": report["eligible_development_candidate_count"],
            "candidate_count": report["candidate_count"],
            "matching_positive_candidates": selected[
                "development_matching_positive_candidates"
            ],
            "matching_positive_trials": selected[
                "development_matching_positive_trials"
            ],
            "hard_negative_candidates": selected[
                "development_hard_negative_candidates"
            ],
            "hard_negative_trials": selected["development_hard_negative_trials"],
            "all_quality_gates_passed": selected["development_quality_passed"],
        },
        "internal_validation_result": {
            key: report["internal_validation"][key]
            for key in (
                "quality_passed",
                "matching_positive_candidates",
                "matching_positive_trials",
                "hard_negative_candidates",
                "hard_negative_trials",
                "passed",
            )
        },
        "implementation_files": _hash_files(project_root, IMPLEMENTATION_PATHS),
        "model_asset": {
            "path": model_path.relative_to(project_root).as_posix(),
            "sha256": _sha256(model_path),
        },
        "runtime_assets": _hash_files(project_root, runtime_paths),
        "runtime_package": {
            "name": protocol["instrument"]["runtime"],
            "version": protocol["instrument"]["runtime_version"],
            "tarball_sha256": protocol["instrument"]["runtime_tarball_sha256"],
        },
        "scope": {
            "robot_connections": 0,
            "actuation_commands": 0,
            "confirmation_data_collected": False,
            "identity_or_authorization_validated": False,
        },
        "claim_boundary": (
            "This freezes one single-person, single-setup pilot candidate for a separate "
            "confirmation design. It is not confirmation, speaker identification, "
            "authorization, multi-speaker evidence, or robot evidence."
        ),
    }
    encoded = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**core, "fingerprint": hashlib.sha256(encoded).hexdigest()}
