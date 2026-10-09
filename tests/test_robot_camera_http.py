"""Real loopback HTTP with synthetic sensors only; never contacts Reachy."""
from __future__ import annotations

import json
import math
import socket
import threading
import time
import unittest
from contextlib import contextmanager
from http.client import HTTPConnection, RemoteDisconnected
from http.server import BaseHTTPRequestHandler
from types import SimpleNamespace
from unittest.mock import patch

from reachy_doa.models import DoAReading
from reachy_stage2a.stream_client import FramePreparationTiming
from reachy_stage3v.bounded_http import BoundedHTTPServer
from reachy_stage3v.robot_camera_bridge import RobotCameraFrameBridge
from scripts.run_robot_camera_commissioning import RobotCameraCommissioningHandler


@contextmanager
def running_server(handler):
    server = BoundedHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)


def request(server, path, method="GET"):
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
    try:
        connection.request(method, path)
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


class FakeDoa:
    def __init__(self):
        self.entered, self.release = threading.Event(), threading.Event()
        self.calls = 0

    def read(self):
        self.calls += 1
        self.entered.set()
        if not self.release.wait(3):
            raise AssertionError("Fake DoA was not released")
        return DoAReading("synthetic", time.perf_counter(), math.pi / 2,
                          True, 150, 200, True, "")


class FakeBridge:
    def snapshot(self):
        received = time.perf_counter() - 0.005
        return SimpleNamespace(
            latest_jpeg=b"synthetic", latest_received_monotonic=received,
            latest_sequence=1, transport_frames=1, analysis_frames=1,
            width_px=640, height_px=360, encode_ms=2,
            preparation=FramePreparationTiming(received, received + 0.001, received + 0.003, None),
            bridge_total_ms=5, publish_interval_ms=None, source_width_px=1280, source_height_px=720)


def make_handler():
    class Handler(RobotCameraCommissioningHandler):
        doa_client = FakeDoa()
        camera_bridge = FakeBridge()
        doa_read_lock = threading.Lock()

        def log_message(self, *_args):
            pass
    return Handler


class RobotCameraHTTPTests(unittest.TestCase):
    def test_frame_headers_report_pre_conversion_age_and_missing_first_interval(self):
        with running_server(make_handler()) as server:
            status, headers, _ = request(server, "/api/reachy-camera/frame.jpg")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(float(headers["X-Reachy-Frame-Age-Ms"]), 5)
        self.assertAlmostEqual(float(headers["X-Reachy-Conversion-Queue-Ms"]), 1, places=4)
        self.assertAlmostEqual(float(headers["X-Reachy-Conversion-Ms"]), 2, places=4)
        self.assertEqual(float(headers["X-Reachy-Bridge-Total-Ms"]), 5)
        self.assertEqual(float(headers["X-Reachy-Source-Width"]), 1280)
        self.assertNotIn("X-Reachy-Receive-Interval-Ms", headers)
        self.assertNotIn("X-Reachy-Bridge-Publish-Interval-Ms", headers)

    def test_frames_complete_while_doa_remains_blocked(self):
        handler = make_handler()
        with running_server(handler) as server:
            outcome = []
            reader = threading.Thread(target=lambda: outcome.append(
                request(server, "/api/reachy-camera/doa")))
            reader.start()
            try:
                self.assertTrue(handler.doa_client.entered.wait(1))
                code, headers, body = request(server, "/api/reachy-camera/frame.jpg")
                self.assertEqual((code, body), (200, b"synthetic"))
                self.assertFalse(handler.doa_client.release.is_set())
                self.assertTrue(reader.is_alive())
                self.assertGreaterEqual(float(headers["X-Reachy-Server-Queue-Ms"]), 0)
                self.assertGreaterEqual(float(headers["X-Reachy-Server-Handler-Ms"]), 0)
                self.assertIn("camera=()", headers["Permissions-Policy"])
                code, _, body = request(server, "/api/reachy-camera/doa")
                self.assertEqual(code, 503)
                self.assertEqual(json.loads(body)["error_code"], "DOA_READ_IN_PROGRESS")
                self.assertFalse(json.loads(body)["valid"])
                self.assertEqual(handler.doa_client.calls, 1)
            finally:
                handler.doa_client.release.set()
                reader.join(2)
            self.assertEqual(outcome[0][0], 200)
            self.assertTrue(json.loads(outcome[0][2])["valid"])

    def test_doa_exception_releases_single_flight_lock(self):
        handler = make_handler()
        with running_server(handler) as server:
            with patch.object(handler.doa_client, "read", side_effect=OSError("simulated")):
                with self.assertRaises((RemoteDisconnected, ConnectionResetError, ConnectionAbortedError)):
                    request(server, "/api/reachy-camera/doa")
            self.assertFalse(handler.doa_read_lock.locked())
            handler.doa_client.release.set()
            self.assertEqual(request(server, "/api/reachy-camera/doa")[0], 200)

    def test_pool_keeps_get_allowlist_and_rejects_mutations(self):
        handler = make_handler()
        with running_server(handler) as server:
            for method in ("POST", "PUT", "PATCH", "DELETE"):
                code, _, body = request(server, "/api/reachy-camera/frame.jpg", method)
                self.assertEqual(code, 405)
                self.assertFalse(json.loads(body)["motion_authorized"])
            self.assertEqual(request(server, "/api/motors/enable")[0], 404)
            self.assertEqual(request(server, "/data/private/setup.json")[0], 404)
            self.assertEqual(handler.doa_client.calls, 0)

    def test_pool_reuses_two_threads_and_closes_overload(self):
        release, both_running = threading.Event(), threading.Event()
        ids, lock = set(), threading.Lock()

        class BlockedHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                with lock:
                    ids.add(threading.get_ident())
                    if len(ids) == 2:
                        both_running.set()
                release.wait(3)
                self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *_args):
                pass

        clients = []
        with running_server(BlockedHandler) as server:
            try:
                for _ in range(6):
                    client = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
                    client.request("GET", "/")
                    clients.append(client)
                self.assertTrue(both_running.wait(1))
                deadline = time.monotonic() + 1
                while time.monotonic() < deadline:
                    with server._pending_lock:
                        if len(server._pending) == 6:
                            break
                    time.sleep(0.005)
                with server._pending_lock:
                    self.assertEqual(len(server._pending), 6)
                with self.assertRaises((RemoteDisconnected, ConnectionResetError, ConnectionAbortedError)):
                    request(server, "/")
                self.assertEqual(len(ids), 2)
                self.assertEqual(len(server._pool._threads), 2)
            finally:
                release.set()
                for client in clients:
                    try:
                        self.assertEqual(client.getresponse().status, 200)
                    finally:
                        client.close()
            for _ in range(100):
                self.assertEqual(request(server, "/")[0], 200)
            self.assertEqual(len(ids), 2)
            self.assertEqual(len(server._pool._threads), 2)
        self.assertTrue(all(not t.is_alive() for t in server._pool._threads))

    def test_shutdown_wakes_incomplete_http_request(self):
        with running_server(make_handler()) as server:
            client = socket.create_connection(("127.0.0.1", server.server_port), timeout=1)
            try:
                client.sendall(b"GET /api/reachy-camera/frame.jpg HTTP/1.0\r\n")
                deadline = time.monotonic() + 1
                while not server._pool._threads and time.monotonic() < deadline:
                    time.sleep(0.005)
                server.shutdown()
                started = time.monotonic()
                server.server_close()
                # Windows may finish a socket read at its existing IO timeout
                # even after shutdown; it must still be bounded and joined.
                self.assertLess(time.monotonic() - started, 3)
                self.assertTrue(all(not t.is_alive() for t in server._pool._threads))
            finally:
                client.close()

    def test_concurrent_config_starts_only_one_camera_thread(self):
        bridge = RobotCameraFrameBridge()
        entered, calls = threading.Event(), []

        def fake_run():
            calls.append(1)
            entered.set()
            bridge._stop.wait(2)

        with patch.object(bridge, "_thread_main", side_effect=fake_run):
            starters = [threading.Thread(target=bridge.start) for _ in range(8)]
            try:
                for starter in starters:
                    starter.start()
                for starter in starters:
                    starter.join(1)
                self.assertTrue(entered.wait(1))
                self.assertEqual(len(calls), 1)
            finally:
                self.assertTrue(bridge.stop())


if __name__ == "__main__":
    unittest.main()
