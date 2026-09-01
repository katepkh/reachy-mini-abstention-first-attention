"""Immutable local paths for passive Stage 3V and Stage 3P profiles."""

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STUDY_PROFILE = os.environ.get("REACHY_STAGE3V_PROFILE", "original").strip().lower()
if STUDY_PROFILE not in {
    "original", "confirmation", "confirmation_v2", "confirmation_v3", "stage3p_development",
    "stage3p_calibration", "stage3p_vad_diagnostic", "stage3p_confirmation",
    "stage3p_confirmation_v2", "stage3p_confirmation_v3", "stage3p_confirmation_v5",
    "stage3p_confirmation_v6",
    "stage3p_cue_confirmation",
}:
    raise ValueError(f"Unknown passive study profile: {STUDY_PROFILE}")

_DATA_DIR_NAMES = {
    "original": "stage3v",
    "confirmation": "stage3v_confirmation",
    "confirmation_v2": "stage3v_confirmation_v2",
    "confirmation_v3": "stage3v_confirmation_v3",
    "stage3p_development": "stage3p_development",
    "stage3p_calibration": "stage3p_calibration",
    "stage3p_vad_diagnostic": "stage3p_vad_diagnostic",
    "stage3p_confirmation": "stage3p_confirmation",
    "stage3p_confirmation_v2": "stage3p_confirmation_v2",
    "stage3p_confirmation_v3": "stage3p_confirmation_v3",
    "stage3p_confirmation_v5": "stage3p_confirmation_v5",
    "stage3p_confirmation_v6": "stage3p_confirmation_v6",
    "stage3p_cue_confirmation": "stage3p_cue_confirmation_v1",
}
_MANIFEST_NAMES = {
    "original": "stage3v_off_axis_protocol_v3.json",
    "confirmation": "stage3v_confirmation_protocol_v1.json",
    "confirmation_v2": "stage3v_confirmation_protocol_v2.json",
    "confirmation_v3": "stage3v_confirmation_protocol_v3.json",
    "stage3p_development": "stage3p_vertical_design_v1.json",
    "stage3p_calibration": "stage3p_calibration_pilot_v1.json",
    "stage3p_vad_diagnostic": "stage3p_silent_vad_diagnostic_v1.json",
    "stage3p_confirmation": "stage3p_confirmation_protocol_v1.json",
    "stage3p_confirmation_v2": "stage3p_confirmation_protocol_v2.json",
    "stage3p_confirmation_v3": "stage3p_confirmation_protocol_v3.json",
    "stage3p_confirmation_v5": "stage3p_confirmation_protocol_v5.json",
    "stage3p_confirmation_v6": "stage3p_confirmation_protocol_v6.json",
    "stage3p_cue_confirmation": "stage3p_association_gated_cue_confirmation_v1.json",
}
_RESULT_STEMS = {
    "original": "stage3v_off_axis_validation_v1",
    "confirmation": "stage3v_confirmation_validation_v1",
    "confirmation_v2": "stage3v_confirmation_validation_v2",
    "confirmation_v3": "stage3v_confirmation_validation_v3",
    "stage3p_development": "stage3p_development_validation_v1",
    "stage3p_calibration": "stage3p_calibration_pilot_v1",
    "stage3p_vad_diagnostic": "stage3p_silent_vad_diagnostic_v1",
    "stage3p_confirmation": "stage3p_confirmation_validation_v1",
    "stage3p_confirmation_v2": "stage3p_confirmation_validation_v2",
    "stage3p_confirmation_v3": "stage3p_confirmation_validation_v3",
    "stage3p_confirmation_v5": "stage3p_confirmation_validation_v5",
    "stage3p_confirmation_v6": "stage3p_confirmation_validation_v6",
    "stage3p_cue_confirmation": "stage3p_association_gated_cue_confirmation_v1",
}

DATA_DIR = (PROJECT_ROOT / "data" / _DATA_DIR_NAMES[STUDY_PROFILE]).resolve()
ANALYSIS_DIR = (PROJECT_ROOT / "data" / "analysis").resolve()
MANIFEST_PATH = (PROJECT_ROOT / "data" / "manifests" / _MANIFEST_NAMES[STUDY_PROFILE]).resolve()
PROGRESS_PATH = (DATA_DIR / "progress.json").resolve()
_RESULT_STEM = _RESULT_STEMS[STUDY_PROFILE]
RESULT_JSON_PATH = (ANALYSIS_DIR / f"{_RESULT_STEM}.json").resolve()
RESULT_CSV_PATH = (ANALYSIS_DIR / f"{_RESULT_STEM}_trials.csv").resolve()
REPORT_PATH = (ANALYSIS_DIR / f"{_RESULT_STEM}.md").resolve()

AUDIT_DIR = (
    PROJECT_ROOT
    / "data"
    / (
        "stage3p_confirmation_v6_audit"
        if STUDY_PROFILE == "stage3p_confirmation_v6"
        else "stage3p_cue_confirmation_v1_audit"
        if STUDY_PROFILE == "stage3p_cue_confirmation"
        else "stage3p_confirmation_v5_audit"
        if STUDY_PROFILE == "stage3p_confirmation_v5"
        else "stage3p_confirmation_v3_audit"
        if STUDY_PROFILE == "stage3p_confirmation_v3"
        else "stage3p_calibration_audit"
        if STUDY_PROFILE == "stage3p_calibration"
        else "stage3p_confirmation_v2_audit"
        if STUDY_PROFILE == "stage3p_confirmation_v2"
        else "stage3p_confirmation_audit"
        if STUDY_PROFILE == "stage3p_confirmation"
        else "stage3p_vad_audit"
        if STUDY_PROFILE == "stage3p_vad_diagnostic"
        else "stage3p_audit"
        if STUDY_PROFILE == "stage3p_development"
        else "stage3v_audit"
    )
).resolve()
