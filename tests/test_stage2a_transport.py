import asyncio
import threading
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
    def test_robot_camera_commissioning_can_request_25_hz_without_changing_legacy_callers(self):
        self.assertAlmostEqual(LocalVideoSession(detection_hz=25).detection_period, 0.04)
        self.assertAlmostEqual(LocalVideoSession(detection_hz=1000).detection_period, 1 / 60)

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

        class StartedAnalysisTrack(BurstThenEndTrack):
            async def recv(self):
                if self.remaining == 19:
                    async def wait_started():
                        while not analysis_calls:
                            await asyncio.sleep(0.001)
                    await asyncio.wait_for(wait_started(), 1)
                return await super().recv()

        started = time.perf_counter()
        asyncio.run(
            session._consume_video(
                StartedAnalysisTrack(20),
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

    def test_blocked_conversion_does_not_block_draining_or_queue_more_conversions(self):
        entered, release = threading.Event(), threading.Event()
        conversion_threads, drained, callbacks = [], [], []
        loop_thread = threading.get_ident()

        class BlockingFrame:
            def to_ndarray(self, *, format):
                conversion_threads.append(threading.get_ident())
                entered.set()
                if not release.wait(1):
                    raise AssertionError("Receiver could not drain during conversion")
                return object()

        class Track(BurstThenEndTrack):
            async def recv(self):
                if self.remaining == 20:
                    self.remaining -= 1
                    return BlockingFrame()
                if self.remaining == 19:
                    async def wait_started():
                        while not entered.is_set():
                            await asyncio.sleep(0.001)
                    await asyncio.wait_for(wait_started(), 1)
                if self.remaining == 0:
                    self.assert_drained = len(drained)
                    release.set()
                return await super().recv()

        track = Track(20)
        try:
            asyncio.run(LocalVideoSession(detection_hz=60)._consume_video(
                track, callbacks.append, lambda *_: None, drained.append,
            ))
        finally:
            release.set()
        self.assertEqual(track.assert_drained, 20)
        self.assertEqual(len(conversion_threads), 1)
        self.assertNotEqual(conversion_threads[0], loop_thread)
        self.assertEqual(callbacks, [])  # track end discards late conversion

    def test_prepared_callback_receives_pre_conversion_timestamp_and_legacy_is_not_called(self):
        from av import VideoFrame
        import numpy as np

        observations, legacy = [], []
        rgb = np.zeros((48, 64, 3), dtype=np.uint8)
        rgb[:, :, 0] = 255
        native_frame = VideoFrame.from_ndarray(rgb, format="rgb24")

        class SlowFrame(FakeFrame):
            def to_ndarray(self, *, format):
                time.sleep(0.02)
                return native_frame.to_ndarray(format=format)

        class Track(BurstThenEndTrack):
            async def recv(self):
                if self.remaining:
                    self.remaining = 0
                    return SlowFrame()
                async def wait_callback():
                    while not observations:
                        await asyncio.sleep(0.001)
                await asyncio.wait_for(wait_callback(), 1)
                return await super().recv()

        asyncio.run(LocalVideoSession()._consume_video(
            Track(1), legacy.append, lambda *_: None,
            on_prepared_frame=lambda pixels, timing: observations.append((pixels, timing)),
        ))
        self.assertEqual(legacy, [])
        self.assertEqual(len(observations), 1)
        np.testing.assert_array_equal(observations[0][0], rgb[:, :, ::-1])
        timing = observations[0][1]
        self.assertLessEqual(timing.received_monotonic, timing.conversion_started_monotonic)
        self.assertGreaterEqual(timing.conversion_completed_monotonic - timing.conversion_started_monotonic, 0.019)
        self.assertIsNone(timing.receive_interval_ms)

    def test_conversion_exception_reports_failure(self):
        statuses = []

        class BrokenFrame:
            def to_ndarray(self, **_kwargs):
                raise ValueError("synthetic conversion failure")

        class Track:
            async def recv(self):
                await asyncio.sleep(0.02)
                return BrokenFrame()

        asyncio.run(LocalVideoSession(detection_hz=60)._consume_video(
            Track(), lambda _: self.fail("Broken pixels must not be published"),
            lambda *args: statuses.append(args),
        ))
        self.assertEqual(statuses[-1], ("ERROR", "VIDEO_TRACK_VALUEERROR"))

    def test_cancellation_waits_for_owned_conversion_but_discards_its_result(self):
        entered, release = threading.Event(), threading.Event()
        callbacks = []

        class Frame:
            def to_ndarray(self, **_kwargs):
                entered.set()
                if not release.wait(2):
                    raise AssertionError("Test did not release conversion")
                return object()

        class Track:
            async def recv(self):
                await asyncio.sleep(0.001)
                return Frame()

        async def run():
            task = asyncio.create_task(LocalVideoSession()._consume_video(
                Track(), callbacks.append, lambda *_: None,
            ))
            try:
                async def wait_started():
                    while not entered.is_set():
                        await asyncio.sleep(0.001)
                await asyncio.wait_for(wait_started(), 1)
                task.cancel()
                await asyncio.sleep(0.02)
                self.assertFalse(task.done())
            finally:
                release.set()
                with self.assertRaises(asyncio.CancelledError):
                    await task

        asyncio.run(run())
        self.assertEqual(callbacks, [])


if __name__ == "__main__":
    unittest.main()
