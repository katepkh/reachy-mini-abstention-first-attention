import unittest
from unittest.mock import patch

from reachy_stage2a.camera_worker import (
    CameraWorker,
    is_expected_aioice_shutdown_race,
)


class CameraWorkerLifecycleTests(unittest.TestCase):
    @staticmethod
    def _wait_until_stopped(worker: CameraWorker) -> None:
        worker._stop.wait(5.0)

    def test_only_one_receiver_can_own_the_camera_and_stop_releases_it(self):
        first = CameraWorker()
        second = CameraWorker()
        first._thread_main = lambda: self._wait_until_stopped(first)
        second._thread_main = lambda: self._wait_until_stopped(second)
        try:
            first.start()
            with self.assertRaisesRegex(RuntimeError, "CAMERA_RECEIVER_ALREADY_ACTIVE"):
                second.start()
            self.assertTrue(first.stop())
            second.start()
            self.assertTrue(second.stop())
        finally:
            first.stop()
            second.stop()

    def test_reload_adopts_the_existing_process_receiver(self):
        first = CameraWorker()
        first._thread_main = lambda: self._wait_until_stopped(first)
        try:
            first.start()
            adopted = CameraWorker.acquire()
            self.assertIs(adopted, first)
        finally:
            first.stop()

    def test_stage3v_entry_point_is_fixed_to_the_loopback_proxy(self):
        sentinel = object()
        with patch.object(CameraWorker, "acquire", return_value=sentinel) as acquire:
            result = CameraWorker.acquire_local_proxy(detection_hz=7.0)
        self.assertIs(result, sentinel)
        acquire.assert_called_once_with(
            detection_hz=7.0,
            camera_host="127.0.0.1",
        )

    def test_only_the_known_aioice_callback_is_suppressed_during_stop(self):
        class RetryHandle:
            def __repr__(self) -> str:
                return "<TimerHandle Transaction.__retry()>"

        context = {
            "exception": __import__("asyncio").InvalidStateError(),
            "handle": RetryHandle(),
        }
        self.assertTrue(
            is_expected_aioice_shutdown_race(context, stop_requested=True)
        )
        self.assertFalse(
            is_expected_aioice_shutdown_race(context, stop_requested=False)
        )
        self.assertFalse(
            is_expected_aioice_shutdown_race(
                {"exception": RuntimeError(), "handle": RetryHandle()},
                stop_requested=True,
            )
        )


if __name__ == "__main__":
    unittest.main()
