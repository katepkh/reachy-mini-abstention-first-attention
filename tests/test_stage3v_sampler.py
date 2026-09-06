import time
import unittest

from reachy_doa.models import DoAReading
from reachy_stage3v.sampler import NumericSampler


class _FakeClient:
    def __init__(self) -> None:
        self.calls = 0

    def read(self) -> DoAReading:
        self.calls += 1
        captured = time.perf_counter()
        return DoAReading(
            client_time_iso=f"sample-{self.calls}",
            captured_monotonic=captured,
            raw_angle_rad=1.0,
            speech_detected=True,
            http_latency_ms=1.0,
            http_status=200,
            valid=True,
            error="",
        )


class _FakeCamera:
    def snapshot(self):
        return None


class Stage3VSamplerTests(unittest.TestCase):
    def test_background_sampler_runs_independently_of_ui_refresh(self):
        client = _FakeClient()
        sampler = NumericSampler(client, _FakeCamera(), poll_hz=20.0)
        started = time.perf_counter()
        sampler.start()
        time.sleep(0.28)
        ended = time.perf_counter()
        self.assertTrue(sampler.stop())

        snapshot = sampler.snapshot()
        self.assertGreaterEqual(snapshot.sample_count, 4)
        samples = sampler.samples_between(started, ended)
        self.assertGreaterEqual(len(samples), 4)
        self.assertEqual(
            [sample.sequence for sample in samples],
            sorted(sample.sequence for sample in samples),
        )
        self.assertEqual(client.calls, snapshot.sample_count)

    def test_invalid_rate_is_rejected(self):
        with self.assertRaises(ValueError):
            NumericSampler(_FakeClient(), None, poll_hz=0.0)


if __name__ == "__main__":
    unittest.main()
