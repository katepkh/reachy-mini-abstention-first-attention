"""Immutable Stage 2A transport, fusion and storage limits."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STAGE2A_DATA_DIR = (PROJECT_ROOT / "data" / "stage2a").resolve()

SIGNALLING_SCHEME = "ws"
CAMERA_PROXY_HOST = "127.0.0.1"
SIGNALLING_PORT = 8443
PRODUCER_NAME = "reachymini"
OUTBOUND_MESSAGE_TYPES = frozenset({"list", "startSession", "peer", "endSession"})

DEFAULT_ROBOT_IP = "192.168.1.251"
DEFAULT_POLL_HZ = 5
MAX_CAMERA_RUNTIME_SECONDS = 15 * 60
# A receive-only WebRTC track must keep delivering frames.  Without this
# watchdog, aiortc can remain blocked in ``track.recv()`` after Reachy Control's
# localhost bridge or the robot disappears, leaving the dashboard labelled
# RECEIVING while it repeatedly reuses an old numeric observation.
VIDEO_FRAME_TIMEOUT_SECONDS = 15.0
# Reachy's producer can deliver a short negotiation burst and then pause for
# about ten seconds before steady video begins.  Keep that same track alive
# during startup; after a one-second steady burst the shorter watchdog applies.
VIDEO_STARTUP_FRAME_TIMEOUT_SECONDS = 15.0
VIDEO_STARTUP_GRACE_SECONDS = 20.0
MAX_FACE_AGE_MS = 750.0
MIN_FACE_CONFIDENCE = 0.55
MIN_ACOUSTIC_CONFIDENCE = 0.60
MAX_FUSION_ERROR_DEG = 20.0

# Official Reachy Mini Wireless calibration is specified at 3840 x 2592.
CALIBRATION_WIDTH = 3840.0
CALIBRATION_HEIGHT = 2592.0
CALIBRATION_FX = 2001.8076426486707
CALIBRATION_FY = 2003.0778885944105
CALIBRATION_CX = 1905.876059826701
CALIBRATION_CY = 1328.3239717935594
