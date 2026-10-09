"""Offline-only robot-camera pilot checks and development-only selection."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from reachy_avsync.synchrony import NumericSeries, SynchronySpec, evaluate_synchrony
from .joint_pilot_analysis import (JointPilotInput, assess_joint_pilot_quality,
                                   joint_pilot_candidate_specs, _smooth, _metrics,
                                   _selection_key, VISIBLE_CONDITIONS,
                                   MOUTH_MOTION_REQUIRED_CONDITIONS)
from .robot_camera_commissioning import (assess_robot_camera_commissioning,
                                         robot_camera_execution_payload)
from .robot_pilot_protocol import protocol


def distinct(rows: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for row in rows:
        sequence = int(row["robot_frame_sequence"])
        if sequence not in seen:
            seen.add(sequence)
            result.append(row)
    return result


def quality(csv_path: Path, card: dict) -> tuple[dict, list[dict]]:
    """No outcomes are used to accept/retry captures."""
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        config = robot_camera_execution_payload(Path(__file__).resolve().parents[1])
        if reader.fieldnames != config["required_columns"] + config["diagnostic_columns"]:
            raise ValueError("CSV columns do not match the robot-camera instrument")
        rows = list(reader)
    translated = [{**row, "face_heading_estimate_deg": row["face_heading_robot_deg"]}
                  for row in rows]
    report = assess_joint_pilot_quality(card, JointPilotInput(tuple(translated), {}))
    robot = assess_robot_camera_commissioning(csv_path)
    # Commissioning expects continuous visible speech; controls deliberately do not.
    transport_failures = {"INSUFFICIENT_SAMPLES", "SPAN_TOO_SHORT", "SAMPLE_GAP_EXCESSIVE",
                          "ROBOT_CAMERA_TRANSPORT_RATE_TOO_LOW", "ROBOT_CAMERA_ANALYSIS_RATE_TOO_LOW",
                          "ROBOT_CAMERA_FRAME_AGE_TOO_HIGH", "ROBOT_CAMERA_DUPLICATE_FRACTION_TOO_HIGH",
                          "LANDMARK_INFERENCE_TOO_SLOW", "DOA_AVAILABILITY_TOO_LOW",
                          "DOA_AGE_TOO_HIGH", "LANDMARK_PROCESSING_ERROR"}
    report["failures"].extend(f for f in robot["failures"] if f in transport_failures)
    sequences = [int(row["robot_frame_sequence"]) for row in rows]
    if any(s <= 0 for s in sequences) or any(b < a for a, b in zip(sequences, sequences[1:])):
        report["failures"].append("FRAME_SEQUENCE_INVALID")
    if any(row["robot_camera_status"] != "RECEIVING" for row in rows):
        report["failures"].append("CAMERA_UNAVAILABLE")
    for key in ("robot_frame_age_ms", "landmark_inference_ms", "face_observation_age_ms"):
        if any(not row[key] or not np.isfinite(float(row[key])) or float(row[key]) < 0 for row in rows):
            report["failures"].append(f"INVALID_{key.upper()}")
    lips = [float(row["lip_aperture"]) for row in distinct(rows) if row["face_count"] == "1"]
    report["lip_aperture_std"] = float(np.std(lips)) if lips else 0.0
    report["failures"] = [f for f in report["failures"] if f != "LIP_DYNAMIC_RANGE_TOO_LOW"]
    if card["condition_id"] in MOUTH_MOTION_REQUIRED_CONDITIONS and report["lip_aperture_std"] < 0.002:
        report["failures"].append("LIP_DYNAMIC_RANGE_TOO_LOW")
    report["failures"] = sorted(set(report["failures"]))
    report["passed"] = not report["failures"]
    report["robot_observability"] = robot["observability"]
    return report, rows


def timing_series(rows: list[dict], sample_rate: float, smoothing: int):
    """Never treat stale repeated lip values as independently timed observations."""
    audio_t = np.array([float(r["timestamp_ms"]) - 1024 * 1000 / sample_rate for r in rows])
    audio_v = np.array([float(r["audio_dbfs"]) for r in rows])
    face = [r for r in distinct(rows) if r["face_count"] == "1"]
    mouth_t = np.array([float(r["timestamp_ms"]) - float(r["robot_frame_age_ms"]) for r in face])
    mouth_v = np.array([float(r["lip_aperture"]) for r in face])
    for times in (audio_t, mouth_t):
        if len(times) < 30 or not np.isfinite(times).all():
            return None, "INSUFFICIENT_DISTINCT_TIMED_OBSERVATIONS"
        gaps = np.diff(times)
        if (gaps <= 0).any() or (gaps > 160).any():
            return None, "TIMING_GAP_OR_NONMONOTONIC_RECEIPT"
    start = max(audio_t[0], mouth_t[0])
    end = min(audio_t[-1], mouth_t[-1])
    if end - start < 1200:
        return None, "INSUFFICIENT_COMMON_SUPPORT"
    grid = np.arange(start, end + 1e-6, 40.0)
    audio = NumericSeries.from_sequences(grid, _smooth(np.interp(grid, audio_t, audio_v), smoothing))
    mouth = NumericSeries.from_sequences(grid, _smooth(np.interp(grid, mouth_t, mouth_v), smoothing))
    return (audio, mouth), None


def evaluate(card, report, rows, sample_rate, spec, smoothing, spatial):
    usable = report["passed"] and report["single_face_fraction"] >= 0.95
    speech = report["doa_speech_fraction"] >= 0.25
    mouth = report["lip_aperture_std"] >= 0.002
    error = report["median_spatial_error_deg"]
    aligned = usable and error is not None and error <= spatial
    score = None
    reason = "QUALITY_OR_FACE_UNAVAILABLE"
    if usable:
        series, reason = timing_series(rows, sample_rate, smoothing)
        if series is not None:
            score = evaluate_synchrony(*series, spec)
            reason = score.reason
    synced = score is not None and score.status == "CANDIDATE"
    proposal = bool(usable and speech and aligned and synced)
    return {"trial_id": card["trial_id"], "condition_id": card["condition_id"],
            "split": card["split"], "role": card["role"],
            "expected_positive": card["role"] == "matching_positive", "proposal": proposal,
            "correlation": None if score is None else score.correlation,
            "lag_ms": None if score is None else score.lag_ms,
            "timing_reason": reason,
            "lag_at_boundary": bool(score is not None and score.lag_ms is not None and
                                    abs(score.lag_ms) >= spec.max_abs_lag_ms),
            "baselines": {"acoustic_only": bool(report["passed"] and speech),
                          "visual_activity_only": bool(usable and mouth),
                          "speech_plus_mouth_activity": bool(usable and speech and mouth),
                          "spatial_only": bool(aligned and speech), "synchrony_only": bool(usable and synced),
                          "non_abstaining_visible_face": bool(usable), "fused_abstaining": proposal}}


def evaluate_setting(loaded, spec, smoothing, spatial):
    trials = [evaluate(card, report, rows, rate, spec, smoothing, spatial)
              for card, report, rows, rate in loaded]
    positive = sum(t["proposal"] for t in trials if t["expected_positive"])
    negative = sum(t["proposal"] for t in trials if not t["expected_positive"])
    passed = all(report["passed"] for _, report, _, _ in loaded)
    return {"synchrony_spec": asdict(spec), "moving_average_samples": smoothing,
            "maximum_median_spatial_error_deg": spatial,
            "development_positive_proposals": positive, "development_negative_proposals": negative,
            "eligible": passed and positive >= 3 and negative == 0, "trials": trials}


def select_development(loaded):
    if len(loaded) != 14 or any(card["split"] != "development" for card, _, _, _ in loaded):
        raise ValueError("Selection requires exactly the fourteen development trials, never validation")
    expected = {c["trial_id"] for c in protocol()["schedule"][:14]}
    if {c["trial_id"] for c, _, _, _ in loaded} != expected:
        raise ValueError("Development trial set mismatch")
    settings = [evaluate_setting(loaded, spec, smooth, spatial)
                for spec, smooth, spatial in joint_pilot_candidate_specs()]
    eligible = [s for s in settings if s["eligible"]]
    selected = max(eligible, key=_selection_key) if eligible else None
    boundary = bool(selected and any(t["proposal"] and t["lag_at_boundary"] for t in selected["trials"]))
    return {"schema": "reachy-camera-pilot-development-v1", "protocol_fingerprint": protocol()["fingerprint"],
            "candidate_count": len(settings), "eligible_count": len(eligible), "selected": selected,
            "validation_open": selected is not None and not boundary,
            "status": "NO_QUALIFYING_SETTING" if selected is None else
                      "BOUNDARY_LAG_REQUIRES_TIMING_REVIEW" if boundary else "SETTING_FROZEN_FOR_VALIDATION",
            "baseline_metrics": None if selected is None else
                {name: _metrics(selected["trials"], name) for name in protocol()["baselines"]}}


def validate_once(loaded, development):
    if not development.get("validation_open") or len(loaded) != 7:
        raise ValueError("Validation is closed or incomplete")
    if {c["trial_id"] for c, _, _, _ in loaded} != {c["trial_id"] for c in protocol()["schedule"][14:]}:
        raise ValueError("Validation trial set mismatch")
    selected = development["selected"]
    result = evaluate_setting(loaded, SynchronySpec(**selected["synchrony_spec"]),
                              selected["moving_average_samples"], selected["maximum_median_spatial_error_deg"])
    passed = (all(q["passed"] for _, q, _, _ in loaded) and
              result["development_positive_proposals"] == 2 and result["development_negative_proposals"] == 0 and
              not any(t["proposal"] and t["lag_at_boundary"] for t in result["trials"]))
    return {"schema": "reachy-camera-pilot-validation-v1", "passed": passed,
            "trials": result["trials"], "baseline_metrics":
                {name: _metrics(result["trials"], name) for name in protocol()["baselines"]},
            "claim_boundary": protocol()["claim_boundary"]}
