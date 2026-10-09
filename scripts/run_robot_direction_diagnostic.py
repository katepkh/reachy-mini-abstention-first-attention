#!/usr/bin/env python
"""Separate three-position direction diagnostic; no pilot changes or commands."""
from __future__ import annotations

import argparse
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.run_robot_camera_commissioning import RobotCameraCommissioningHandler
from reachy_stage3v.bounded_http import BoundedHTTPServer
from reachy_stage3v.robot_camera_bridge import RobotCameraFrameBridge
from reachy_stage3v import robot_pilot_store as store
from reachy_stage3v.robot_pilot_protocol import fingerprint
from reachy_doa.client import ReadOnlyDoAClient

from scripts.run_robot_camera_diagnostic import diagnostic_config as playback_config

DIRECTION_FILES = (
    "scripts/run_robot_direction_diagnostic.py", "tools/robot_direction_diagnostic.html",
    "tools/robot_direction_ui.mjs", "start_robot_direction_diagnostic.cmd",
)
POSITIONS = [
    {"id": "front", "label": "FRONT", "heading_left_positive_deg": 0, "expected_axis_deg": 90},
    {"id": "left60", "label": "60° to Reachy's LEFT", "heading_left_positive_deg": 60, "expected_axis_deg": 30},
    {"id": "right60", "label": "60° to Reachy's RIGHT", "heading_left_positive_deg": -60, "expected_axis_deg": 150},
]


def direction_config():
    base = playback_config()  # Seal verification only; never collection_state.
    parent = base["diagnostic"]
    if parent["playback_volume_percent"] != 50:
        raise ValueError("This direction diagnostic requires the existing 50% playback binding.")
    core = {"schema": "reachy-direction-diagnostic-build-v1",
            "parent_diagnostic_build": parent["build"],
            "files_sha256": {p: store.sha256_file(ROOT / p) for p in DIRECTION_FILES},
            "positions": POSITIONS,
            "motion_authority": False, "response_authority": False}
    return {**base, "diagnostic": {
        **parent, "schema": "reachy-direction-diagnostic-v1",
        "build": {**core, "fingerprint": fingerprint(core)},
        "positions": POSITIONS,
        "extra_columns": [
            "position_id", "expected_axis_deg", "phone_heading_left_positive_deg",
            "direction_doa_fresh", "direction_usable", "direction_bearing_left_positive_deg",
            "expected_axis_error_deg", "face_sound_separation_deg", "direction_warning_codes",
            "microphone_continuous",
        ],
        "coordinate_contract": {
            "frame": "Head-relative horizontal bearing; front=0, robot-left positive, robot-right negative.",
            "camera": "Unmirrored image-right is camera-right; stored face bearing negates camera-right.",
            "doa": "Raw axis 0=left, 90=front/back, 180=right. Front-hemisphere bearing = 90 minus raw axis.",
            "ambiguity": "Front/back ambiguity remains; both hypotheses used for face separation.",
            "expected": "Nominal values from operator-confirmed marks, not measured ground truth or a fitted correction.",
            "erratum": "Inherited commissioning metadata said robot-right positive; this diagnostic corrects the description only. Numeric pipeline is unchanged.",
        },
        "instruction": (
            "Keep Reachy, its head and the laptop fixed. Remain silent with your face visible at the usual front mark. "
            "Use ONE iPhone and the SAME recording at 50%. Use the existing right-hand phone mark's horizontal "
            "distance for all three positions. Keep the phone speaker level with Reachy's head/microphones "
            "for this diagnostic. Add temporary front and left marks without changing "
            "the existing marks. Keep the phone speaker directed toward Reachy. Stop playback while moving "
            "the phone; restart the recording from its beginning immediately before each Record."
        ),
        "start_gate": "Same camera/face/processing and microphone readiness, position confirmation and measured phone distance. No speech or direction start gate.",
        "claim_boundary": "Three-position diagnostic only; not pilot evidence, calibration certification, fitted offset, permission to retry, or robot action.",
    }}


class DirectionHandler(RobotCameraCommissioningHandler):
    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/reachy-camera/config":
            try:
                config = direction_config()
            except (ValueError, KeyError, OSError) as error:
                self._json({"error": f"Diagnostic binding verification failed: {error}"}, HTTPStatus.CONFLICT)
                return
            self.camera_bridge.start()
            self._json(config)
        elif path in {"/api/reachy-camera/frame.jpg", "/api/reachy-camera/status", "/api/reachy-camera/doa"}:
            super().do_GET()
        elif path in {"/tools/robot_direction_diagnostic.html", "/tools/robot_direction_ui.mjs", "/tools/robot_diagnostic_ui.mjs", "/tools/robot_pilot_ui.mjs"}:
            SimpleHTTPRequestHandler.do_GET(self)
        elif path in {"/tools/robot_camera_pipeline.mjs", "/tools/robot_camera_landmarks_worker.js"} or (
            path.startswith("/models/avsync_v2/") and ".." not in path and "\\" not in path and "%" not in path
        ):
            super().do_GET()
        else:
            self._json({"error": "NOT_FOUND"}, HTTPStatus.NOT_FOUND)

    do_HEAD = RobotCameraCommissioningHandler._reject_mutation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--robot-ip", default="192.168.1.251")
    parser.add_argument("--port", type=int, default=8770)
    args = parser.parse_args()
    try:
        direction_config()
    except (ValueError, KeyError, OSError) as error:
        print(f"Diagnostic unavailable: {error}")
        return 2
    client = ReadOnlyDoAClient(args.robot_ip)
    bridge = RobotCameraFrameBridge(analysis_hz=60.0)
    DirectionHandler.doa_client = client
    DirectionHandler.camera_bridge = bridge
    try:
        server = BoundedHTTPServer(("127.0.0.1", args.port), partial(DirectionHandler, directory=str(ROOT)))
    except Exception:
        client.close()
        raise
    print(f"Three-position direction diagnostic: http://127.0.0.1:{args.port}/tools/robot_direction_diagnostic.html", flush=True)
    print("NOT a pilot trial. No motion or response. Numeric files only. Keep this window open.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        bridge.stop()
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
