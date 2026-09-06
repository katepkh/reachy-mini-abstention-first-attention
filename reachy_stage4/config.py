"""Fixed paths and bounds for the supervised Stage 4A motion pilot."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = (PROJECT_ROOT / "data/stage4a_supervised_motion_pilot_v4").resolve()
SESSIONS_DIR = (DATA_DIR / "sessions").resolve()
PROGRESS_PATH = (DATA_DIR / "progress.json").resolve()
MANIFEST_PATH = (
    PROJECT_ROOT / "data/manifests/stage4a_supervised_motion_pilot_v4.json"
).resolve()
TARGETED_FREEZE_PATH = (
    PROJECT_ROOT
    / "data/manifests/stage3p_association_gated_cue_confirmation_result_v1_freeze.json"
).resolve()
HORIZONTAL_FREEZE_PATH = (
    PROJECT_ROOT / "data/manifests/stage3v_confirmation_result_v3_freeze.json"
).resolve()
ACTUATION_PYTHON = (
    PROJECT_ROOT / ".venv/Scripts/python.exe"
).resolve()

REACHY_HOST = "192.168.1.251"
REACHY_PORT = 8000
OFFICIAL_PROTOCOL_VERSION = "1.9.0"
PILOT_PORT = 8528
MOVE_ANGLE_DEG = 3.0
MOVE_DURATION_S = 2.0
DWELL_S = 0.75
RESTORE_SETTLE_S = 0.75
RESTORE_DURATION_S = 2.0
SESSION_MAX_AGE_S = 600.0
BASELINE_NEUTRAL_LIMIT_DEG = 1.0
BASELINE_RECHECK_LIMIT_DEG = 1.0
TARGET_ERROR_LIMIT_DEG = 1.5
RESTORE_ERROR_LIMIT_DEG = 1.0
TRANSLATION_LIMIT_MM = 8.0
MIN_CONTROL_LOOP_HZ = 40.0
MAX_CONTROL_LOOP_HZ = 60.0
MAX_CONTROL_LOOP_INTERVAL_S = 0.1
MAX_TELEMETRY_AGE_S = 2.0
ARM_PHRASE = "MOVE REACHY 3 DEGREES AND RETURN"
