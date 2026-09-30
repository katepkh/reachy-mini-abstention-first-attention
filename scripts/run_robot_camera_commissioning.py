#!/usr/bin/env python
"""Serve command-free Reachy-camera commissioning on localhost."""

from __future__ import annotations

import argparse
import json
import sys
import time
from functools import partial
from http import HTTPStatus
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reachy_doa.client import ReadOnlyDoAClient  # noqa: E402
from reachy_stage3v.joint_instrument import doa_bridge_payload  # noqa: E402
from reachy_stage3v.robot_camera_bridge import RobotCameraFrameBridge  # noqa: E402
from reachy_stage3v.robot_camera_commissioning import (  # noqa: E402
    ROBOT_CAMERA_COMMISSIONING_SPEC_V1,
    robot_camera_static_path_allowed,
)


class RobotCameraCommissioningHandler(SimpleHTTPRequestHandler):
    """Exact GET-only APIs plus allowlisted static assets."""

    doa_client: ReadOnlyDoAClient
    camera_bridge: RobotCameraFrameBridge

    def _json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _camera_status(self) -> dict[str, object]:
        snapshot = self.camera_bridge.snapshot()
        now = time.perf_counter()
        return {
            "schema": "reachy-robot-camera-bridge-status-v1",
            "status": snapshot.status,
            "error_code": snapshot.error_code,
            "transport_frames": snapshot.transport_frames,
            "analysis_frames": snapshot.analysis_frames,
            "latest_sequence": snapshot.latest_sequence,
            "transport_age_ms": (
                None
                if snapshot.last_transport_monotonic is None
                else max(0.0, 1000.0 * (now - snapshot.last_transport_monotonic))
            ),
            "latest_frame_age_ms": (
                None
                if snapshot.latest_encoded_monotonic is None
                else max(0.0, 1000.0 * (now - snapshot.latest_encoded_monotonic))
            ),
            "width_px": snapshot.width_px,
            "height_px": snapshot.height_px,
            "encode_ms": snapshot.encode_ms,
            "motion_authorized": False,
            "response_authorized": False,
            "robot_mutating_requests": 0,
        }

    def _frame(self) -> None:
        snapshot = self.camera_bridge.snapshot()
        if snapshot.latest_jpeg is None or snapshot.latest_encoded_monotonic is None:
            self._json(
                {
                    "error": snapshot.error_code or "ROBOT_FRAME_NOT_READY",
                    "camera_status": snapshot.status,
                },
                HTTPStatus.SERVICE_UNAVAILABLE,
            )
            return
        body = snapshot.latest_jpeg
        age_ms = max(0.0, 1000.0 * (time.perf_counter() - snapshot.latest_encoded_monotonic))
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Reachy-Frame-Sequence", str(snapshot.latest_sequence))
        self.send_header("X-Reachy-Transport-Frames", str(snapshot.transport_frames))
        self.send_header("X-Reachy-Analysis-Frames", str(snapshot.analysis_frames))
        self.send_header("X-Reachy-Frame-Age-Ms", f"{age_ms:.6f}")
        self.send_header("X-Reachy-Frame-Width", str(snapshot.width_px or 0))
        self.send_header("X-Reachy-Frame-Height", str(snapshot.height_px or 0))
        self.send_header("X-Reachy-Frame-Encode-Ms", f"{float(snapshot.encode_ms or 0.0):.6f}")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if path == "/api/reachy-camera/config":
            self._json(ROBOT_CAMERA_COMMISSIONING_SPEC_V1.payload())
            return
        if path == "/api/reachy-camera/status":
            self._json(self._camera_status())
            return
        if path == "/api/reachy-camera/frame.jpg":
            self._frame()
            return
        if path == "/api/reachy-camera/doa":
            started = time.perf_counter()
            reading = self.doa_client.read()
            ready = time.perf_counter()
            self._json(
                doa_bridge_payload(
                    reading,
                    bridge_request_started_monotonic=started,
                    bridge_response_ready_monotonic=ready,
                )
            )
            return
        if not robot_camera_static_path_allowed(path):
            self._json({"error": "NOT_FOUND"}, HTTPStatus.NOT_FOUND)
            return
        super().do_GET()

    def _reject_mutation(self) -> None:
        self._json(
            {
                "error": "READ_ONLY_SERVER",
                "motion_authorized": False,
                "response_authorized": False,
                "robot_mutating_requests": 0,
            },
            HTTPStatus.METHOD_NOT_ALLOWED,
        )

    do_POST = _reject_mutation
    do_PUT = _reject_mutation
    do_DELETE = _reject_mutation
    do_PATCH = _reject_mutation

    def log_message(self, format: str, *args: object) -> None:
        """Keep the high-rate receive-only endpoints out of the console log.

        The browser deliberately polls the latest transient frame many times per
        second.  Logging every successful poll can produce hundreds of thousands
        of terminal lines during one commissioning session and provides no useful
        evidence.  Errors and ordinary page/static requests remain visible.
        """

        path = urlsplit(self.path).path
        status = str(args[1]) if len(args) > 1 else ""
        if status == "200" and path in {
            "/api/reachy-camera/frame.jpg",
            "/api/reachy-camera/doa",
            "/api/reachy-camera/status",
        }:
            return
        super().log_message(format, *args)

    def end_headers(self) -> None:
        self.send_header("Permissions-Policy", "camera=(), geolocation=(), payment=(), usb=()")
        super().end_headers()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--robot-ip", default="192.168.1.251")
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--bind", default="127.0.0.1", choices=("127.0.0.1", "localhost"))
    parser.add_argument("--camera-analysis-hz", type=float, default=60.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client = ReadOnlyDoAClient(args.robot_ip)
    bridge = RobotCameraFrameBridge(analysis_hz=args.camera_analysis_hz)
    bridge.start()
    RobotCameraCommissioningHandler.doa_client = client
    RobotCameraCommissioningHandler.camera_bridge = bridge
    handler = partial(RobotCameraCommissioningHandler, directory=str(ROOT))
    # The recorder issues one awaited frame request at a time.  A single-threaded
    # loopback server is therefore sufficient and, unlike ThreadingHTTPServer,
    # cannot exhaust Windows worker threads during a long-open preview.
    server = HTTPServer((args.bind, args.port), handler)
    url = f"http://127.0.0.1:{args.port}/tools/robot_camera_commissioning.html"
    print(f"Reachy-camera commissioning: {url}")
    print("Receive-only camera + GET-only DoA; no motion or response authority.")
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
