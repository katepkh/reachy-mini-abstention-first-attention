#!/usr/bin/env python
"""Serve the local joint recorder and a GET-only Reachy DoA bridge."""

from __future__ import annotations

import argparse
import json
import sys
import time
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reachy_doa.client import ReadOnlyDoAClient  # noqa: E402
from reachy_stage3v.joint_instrument import (  # noqa: E402
    JOINT_INSTRUMENT_SPEC_V1,
    doa_bridge_payload,
    joint_static_path_allowed,
)


class JointInstrumentHandler(SimpleHTTPRequestHandler):
    """Static localhost server with two explicit read-only JSON endpoints."""

    doa_client: ReadOnlyDoAClient

    def _json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
        path = urlsplit(self.path).path
        if path == "/api/joint-shadow/config":
            self._json(JOINT_INSTRUMENT_SPEC_V1.payload())
            return
        if path == "/api/joint-shadow/doa":
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
        if not joint_static_path_allowed(path):
            self._json({"error": "NOT_FOUND"}, HTTPStatus.NOT_FOUND)
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler contract
        self._json(
            {
                "error": "READ_ONLY_SERVER",
                "motion_authorized": False,
                "response_authorized": False,
                "robot_mutating_requests": 0,
            },
            HTTPStatus.METHOD_NOT_ALLOWED,
        )

    def end_headers(self) -> None:
        self.send_header("Permissions-Policy", "geolocation=(), payment=(), usb=()")
        super().end_headers()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--robot-ip", default="192.168.1.251")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--bind", default="127.0.0.1", choices=("127.0.0.1", "localhost"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client = ReadOnlyDoAClient(args.robot_ip)
    JointInstrumentHandler.doa_client = client
    handler = partial(JointInstrumentHandler, directory=str(ROOT))
    server = ThreadingHTTPServer((args.bind, args.port), handler)
    url = f"http://127.0.0.1:{args.port}/tools/joint_shadow_recorder.html"
    print(f"Joint shadow instrument: {url}")
    print("GET-only Reachy endpoint bridge; no motion or response authority.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
