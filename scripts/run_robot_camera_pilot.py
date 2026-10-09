#!/usr/bin/env python
"""Loopback-only robot-camera pilot; same commissioned receive-only transport."""
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
from reachy_stage3v.robot_pilot_protocol import protocol
from reachy_stage3v.robot_pilot_store import safe_state
from reachy_doa.client import ReadOnlyDoAClient


def pilot_config():
    return {**robot_camera_execution_payload(ROOT), "pilot_protocol": protocol(), "pilot_state": safe_state()}


class PilotHandler(RobotCameraCommissioningHandler):
    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/reachy-camera/config":
            config = pilot_config()
            if config["pilot_state"]["ready"]:
                self.camera_bridge.start()
            self._json(config)
        elif path in {"/api/reachy-camera/frame.jpg", "/api/reachy-camera/status", "/api/reachy-camera/doa"}:
            super().do_GET()
        elif path in {"/tools/robot_camera_pilot.html", "/tools/robot_pilot_ui.mjs"}:
            SimpleHTTPRequestHandler.do_GET(self)
        elif path.startswith("/models/avsync_v2/") or path in {
                "/tools/robot_camera_pipeline.mjs", "/tools/robot_camera_landmarks_worker.js"}:
            super().do_GET()  # retain exact model/worker allowlist and traversal checks
        else:
            self._json({"error": "NOT_FOUND"}, HTTPStatus.NOT_FOUND)

    do_HEAD = RobotCameraCommissioningHandler._reject_mutation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--robot-ip", default="192.168.1.251")
    parser.add_argument("--port", type=int, default=8768)
    args = parser.parse_args()
    state = safe_state()
    if not state["ready"]:
        print(f'Collection gate closed: {state["reason"]}')
        return 2
    client = ReadOnlyDoAClient(args.robot_ip)
    bridge = RobotCameraFrameBridge(analysis_hz=60.0)
    PilotHandler.doa_client = client
    PilotHandler.camera_bridge = bridge
    try:
        server = BoundedHTTPServer(("127.0.0.1", args.port), partial(PilotHandler, directory=str(ROOT)))
    except Exception:
        client.close()
        raise
    print(f"Robot-camera pilot: http://127.0.0.1:{args.port}/tools/robot_camera_pilot.html")
    print("Receive-only Reachy video + GET-only DoA + external laptop microphone. NO motion or response.")
    print(f'Next: {state["next_trial"]["trial_id"]}. Keep this window open; send both downloads after one capture.')
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
