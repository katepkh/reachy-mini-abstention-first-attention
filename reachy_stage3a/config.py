"""Paths and immutable defaults for the offline Stage 3A shadow."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "stage2a"
ANALYSIS_DIR = PROJECT_ROOT / "data" / "analysis"
MANIFEST_PATH = PROJECT_ROOT / "data" / "manifests" / "stage2a_tournament_split_v1.json"

SUMMARY_JSON_PATH = ANALYSIS_DIR / "stage3a_motion_shadow_v1.json"
TRIAL_CSV_PATH = ANALYSIS_DIR / "stage3a_motion_shadow_trials_v1.csv"
REPORT_PATH = ANALYSIS_DIR / "stage3a_motion_shadow_v1.md"
