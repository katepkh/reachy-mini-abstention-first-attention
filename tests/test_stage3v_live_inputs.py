import unittest
from unittest.mock import Mock, patch

from reachy_doa.models import DoAReading
from reachy_stage2a.camera_worker import CameraSnapshot
from reachy_stage3v.live_inputs import (
    LiveInputStartupError,
    doa_failure_code,
    start_live_inputs,
)


def reading(*, valid: bool, error: str = "") -> DoAReading:
    return DoAReading(
        client_time_iso="2026-08-27T19:00:00+01:00",
        captured_monotonic=1.0,
        raw_angle_rad=0.0 if valid else None,
        speech_detected=False if valid else None,
        http_latency_ms=2.0,
        http_status=200 if valid else None,
        valid=valid,
        error=error,
    )


class Stage3VLiveInputTests(unittest.TestCase):
    def test_windows_10013_is_classified_as_process_network_denial(self):
        self.assertEqual(
            doa_failure_code("Failed to connect: [WinError 10013] access forbidden"),
            "NETWORK_ACCESS_DENIED",
        )

    @patch("reachy_stage3v.live_inputs.NumericSampler")
    @patch("reachy_stage3v.live_inputs.CameraWorker.acquire_local_proxy")
    @patch("reachy_stage3v.live_inputs.ReadOnlyDoAClient")
    def test_startup_proves_doa_frames_and_analysis_before_returning(
        self,
        client_factory,
        acquire_local_proxy,
        sampler_factory,
    ):
        client = Mock()
        client.read.return_value = reading(valid=True)
        client_factory.return_value = client
        worker = Mock()
        worker.snapshot.return_value = CameraSnapshot(
            status="RECEIVING",
            error_code="",
            observation=None,
            last_single_face_observation=None,
            frames_received=5,
            last_frame_received_monotonic=1.0,
            observations_processed=1,
        )
        acquire_local_proxy.return_value = worker
        sampler = Mock()
        sampler_factory.return_value = sampler

        result = start_live_inputs(
            "192.168.1.251",
            5.0,
            startup_timeout_seconds=0.1,
        )

        self.assertIs(result.client, client)
        self.assertIs(result.worker, worker)
        self.assertIs(result.sampler, sampler)
        acquire_local_proxy.assert_called_once_with(detection_hz=5.0)
        sampler.start.assert_called_once_with()

    @patch("reachy_stage3v.live_inputs.CameraWorker.acquire_local_proxy")
    @patch("reachy_stage3v.live_inputs.ReadOnlyDoAClient")
    def test_network_denial_blocks_before_starting_a_camera_receiver(
        self,
        client_factory,
        acquire_local_proxy,
    ):
        client = Mock()
        client.read.return_value = reading(
            valid=False,
            error="[WinError 10013] access forbidden",
        )
        client_factory.return_value = client

        with self.assertRaises(LiveInputStartupError) as raised:
            start_live_inputs("192.168.1.251", 5.0)

        self.assertEqual(raised.exception.code, "NETWORK_ACCESS_DENIED")
        acquire_local_proxy.assert_not_called()
        client.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
