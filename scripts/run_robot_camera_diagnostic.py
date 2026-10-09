#!/usr/bin/env python
"""Separate receive-only playback diagnostic; never imports or advances a pilot."""
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
from reachy_stage3v.robot_camera_commissioning import robot_camera_execution_payload
from reachy_stage3v import robot_pilot_store as store
from reachy_stage3v.robot_pilot_protocol import fingerprint
from reachy_doa.client import ReadOnlyDoAClient

DIAGNOSTIC_FILES = (
    "scripts/run_robot_camera_diagnostic.py", "tools/robot_camera_diagnostic.html",
    "tools/robot_diagnostic_ui.mjs", "start_robot_camera_diagnostic.cmd",
)
DIAGNOSTIC_COLUMNS = (
    "diagnostic_doa_fresh", "diagnostic_direction_usable", "diagnostic_direction_error_deg",
    "diagnostic_warning_codes", "pilot_condition_failures", "microphone_continuous",
)


def diagnostic_config():
    # Read-only verification: do not reseal, write attempts or call collection_state.
    expected, seal = store.verify_seal()
    setup = store.read(store.PRIVATE / "setup.json")
    base = robot_camera_execution_payload(ROOT)
    core = {"schema": "reachy-playback-diagnostic-build-v1",
            "frozen_pilot_execution_fingerprint": expected["fingerprint"],
            "files_sha256": {p: store.sha256_file(ROOT / p) for p in DIAGNOSTIC_FILES},
            "motion_authority": False, "response_authority": False}
    return {**base, "diagnostic": {
        "schema": "reachy-playback-diagnostic-v1", "purpose": "DIAGNOSTIC_NOT_PILOT",
        "build": {**core, "fingerprint": fingerprint(core)},
        "binding_fingerprint": seal["fingerprint"],
        "microphone": setup["microphone"], "playback_volume_percent": setup["playback"]["fixed_volume_percent"],
        "stimulus_sha256": setup["playback"]["recording_sha256"],
        "extra_columns": list(DIAGNOSTIC_COLUMNS),
        "capture_seconds": 10,
        "claim_boundary": "Debugging only; excluded from pilot fitting, acceptance and validation. No robot action.",
        "start_gate": "Initialized model, fresh usable camera/face and processing, matching active microphone, operator playback confirmation. Speech, direction, and missing/stale DoA are observations, not start gates.",
        "instruction": "Stay silent at the one-metre front mark, face visible. Keep the single iPhone at the existing 60-degree mark to Reachy's right. Restart the fixed recording before Record and let it play throughout. Do not change the marks or volume.",
    }}


class DiagnosticHandler(RobotCameraCommissioningHandler):
    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/reachy-camera/config":
            try:
                config = diagnostic_config()
            except (ValueError, KeyError, OSError) as error:
                self._json({"error": f"Diagnostic binding verification failed: {error}"}, HTTPStatus.CONFLICT)
                return
            self.camera_bridge.start()
            self._json(config)
        elif path in {"/api/reachy-camera/frame.jpg", "/api/reachy-camera/status", "/api/reachy-camera/doa"}:
            super().do_GET()
        elif path in {"/tools/robot_camera_diagnostic.html", "/tools/robot_diagnostic_ui.mjs", "/tools/robot_pilot_ui.mjs"}:
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
    parser.add_argument("--port", type=int, default=8769)
    args = parser.parse_args()
    try:
        diagnostic_config()
    except (ValueError, KeyError, OSError) as error:
        print(f"Diagnostic unavailable: {error}")
        return 2
    client = ReadOnlyDoAClient(args.robot_ip)
    bridge = RobotCameraFrameBridge(analysis_hz=60.0)
    DiagnosticHandler.doa_client = client
    DiagnosticHandler.camera_bridge = bridge
    try:
        server = BoundedHTTPServer(("127.0.0.1", args.port), partial(DiagnosticHandler, directory=str(ROOT)))
    except Exception:
        client.close()
        raise
    print(f"Playback diagnostic: http://127.0.0.1:{args.port}/tools/robot_camera_diagnostic.html", flush=True)
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
