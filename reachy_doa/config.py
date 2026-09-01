"""Immutable network and data-safety settings."""

from pathlib import Path


DEFAULT_ROBOT_IP = "192.168.1.251"
ALLOWED_SCHEME = "http"
ALLOWED_PORT = 8000
ALLOWED_PATH = "/api/state/doa"
DEFAULT_POLL_HZ = 5
MIN_POLL_HZ = 1
MAX_POLL_HZ = 10
REQUEST_TIMEOUT_SECONDS = 1.0
HISTORY_SECONDS = 60.0
SMOOTHING_WINDOW = 8

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = (PROJECT_ROOT / "data").resolve()
