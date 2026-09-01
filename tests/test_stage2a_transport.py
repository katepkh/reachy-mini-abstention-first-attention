import asyncio
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from reachy_stage2a.config import OUTBOUND_MESSAGE_TYPES
from reachy_stage2a.stream_client import (
    LocalVideoSession,
    LocalStreamRejected,
    _send_allowed,
    camera_connector_error_code,
    local_signalling_url,
)


class HangingVideoTrack:
    async def recv(self):
        await asyncio.sleep(60)


class FakeFrame:
    def to_ndarray(self, *, format):
        self.format = format
        return object()


class BurstThenEndTrack:
    def __init__(self, frames: int) -> None:
        self.remaining = frames

    async def recv(self):
        from aiortc.mediastreams import MediaStreamError

        if self.remaining <= 0:
            raise MediaStreamError
        self.remaining -= 1
        await asyncio.sleep(0)
        return FakeFrame()


class FakeWebSocket:
    def __init__(self):
        self.messages = []

    async def send_json(self, message):
        self.messages.append(message)


class TransportTests(unittest.TestCase):
    def test_windows_socket_denial_is_not_mislabeled_as_proxy_unavailable(self):
        denied = SimpleNamespace(
            os_error=SimpleNamespace(winerror=10013, errno=None)
        )
        self.assertEqual(
            camera_connector_error_code(denied),
            "CAMERA_NETWORK_ACCESS_DENIED",
        )

    def test_ordinary_connector_failure_remains_proxy_unavailable(self):
        unavailable = SimpleNamespace(
            os_error=SimpleNamespace(winerror=10061, errno=None)
        )
        self.assertEqual(
            camera_connector_error_code(unavailable),
            "CAMERA_PROXY_UNAVAILABLE",
        )

    def test_signalling_url_is_fixed_loopback_proxy(self):
        self.assertEqual(local_signalling_url(), "ws://127.0.0.1:8443")

    def test_private_lan_signalling_target_is_allowed(self):
        self.assertEqual(
            local_signalling_url("192.168.1.251"),
            "ws://192.168.1.251:8443",
        )

    def test_public_signalling_target_is_rejected(self):
        with self.assertRaises(LocalStreamRejected):
            local_signalling_url("8.8.8.8")

    def test_outbound_message_allowlist_is_exact(self):
        self.assertEqual(
            OUTBOUND_MESSAGE_TYPES,
            {"list", "startSession", "peer", "endSession"},
        )

    def test_unknown_outbound_message_is_rejected(self):
        socket = FakeWebSocket()
        with self.assertRaises(LocalStreamRejected):
            asyncio.run(_send_allowed(socket, {"type": "unexpected"}))
        self.assertEqual(socket.messages, [])

    def test_frozen_video_track_reports_timeout_instead_of_staying_receiving(self):
        statuses = []
        session = LocalVideoSession()
        with (
            patch("reachy_stage2a.stream_client.VIDEO_FRAME_TIMEOUT_SECONDS", 0.01),
            patch(
                "reachy_stage2a.stream_client.VIDEO_STARTUP_FRAME_TIMEOUT_SECONDS",
                0.01,
            ),
        ):
            asyncio.run(
                session._consume_video(
                    HangingVideoTrack(),
                    lambda _pixels: None,
                    lambda status, error: statuses.append((status, error)),
                )
            )
        self.assertEqual(statuses[-1], ("ERROR", "VIDEO_STARTUP_FRAME_TIMEOUT"))

    def test_slow_face_analysis_does_not_block_transport_frame_draining(self):
        statuses = []
        transport_frames = []
        analysis_calls = []
        session = LocalVideoSession(detection_hz=1000)

        def slow_analysis(_pixels):
            analysis_calls.append(1)
            time.sleep(0.2)

        started = time.perf_counter()
        asyncio.run(
            session._consume_video(
                BurstThenEndTrack(20),
                slow_analysis,
                lambda status, error: statuses.append((status, error)),
                lambda received_at: transport_frames.append(received_at),
            )
        )
        elapsed = time.perf_counter() - started

        self.assertEqual(len(transport_frames), 20)
        self.assertLess(elapsed, 0.6)
        self.assertEqual(len(analysis_calls), 1)
        self.assertEqual(statuses[-1], ("ERROR", "VIDEO_TRACK_ENDED"))


if __name__ == "__main__":
    unittest.main()
