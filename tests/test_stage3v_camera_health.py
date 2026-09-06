import unittest

from reachy_stage2a.models import FaceObservation
from reachy_stage3v.camera_health import (
    CameraHealthGate,
    CAMERA_HEALTH_MIN_READY_FRACTION,
    CAMERA_START_GRACE_SECONDS,
    CAMERA_STALE_RECONNECT_SECONDS,
    STAGE3V_MAX_FACE_AGE_MS,
    camera_health_reason,
    camera_detector_reason,
    camera_transport_reason,
    face_detection_status,
    observation_is_fresh_single_face,
    row_has_fresh_single_face,
    stable_face_observation,
)


def observation(*, captured: float, count: int = 1) -> FaceObservation:
    return FaceObservation(
        client_time_iso="2026-08-25T12:00:00+01:00",
        captured_monotonic=captured,
        detected=count > 0,
        face_count=count,
        center_x_norm=0.5 if count else None,
        center_y_norm=0.5 if count else None,
        heading_deg=0.0 if count else None,
        detector_confidence=0.9 if count else 0.0,
        detector_score_raw=None,
        processing_ms=5.0,
        valid=True,
        error_code="",
    )


class Stage3VCameraHealthTests(unittest.TestCase):
    def test_start_grace_allows_slow_local_webrtc_first_frame(self):
        # The physical setup has measured first-frame delays above eight seconds.
        # The app must not restart a healthy negotiation before that frame arrives.
        self.assertGreaterEqual(CAMERA_START_GRACE_SECONDS, 12.0)

    def test_start_grace_covers_measured_post_negotiation_frame_gap(self):
        # Reachy can send one frame and then pause for roughly ten seconds while
        # its steady stream warms up; five seconds caused an endless reconnect.
        self.assertGreaterEqual(CAMERA_START_GRACE_SECONDS, 20.0)

    def test_stale_reconnect_window_is_longer_than_freshness_gate(self):
        # Recording locks at 750 ms, while transport restart waits long enough
        # to avoid a reconnect loop on a brief detector pause.
        self.assertGreaterEqual(CAMERA_STALE_RECONNECT_SECONDS, 15.0)

    def test_stage3v_freshness_covers_measured_one_second_cadence(self):
        self.assertGreaterEqual(STAGE3V_MAX_FACE_AGE_MS, 1500.0)
        face = observation(captured=10.0)
        self.assertTrue(observation_is_fresh_single_face(face, now_monotonic=11.2))

    def test_recent_single_face_bridges_one_no_face_detection(self):
        no_face = observation(captured=11.0, count=0)
        last_face = observation(captured=10.0)
        self.assertIs(
            stable_face_observation(no_face, last_face, now_monotonic=11.2),
            last_face,
        )

    def test_multiple_faces_never_fall_back_to_old_single_face(self):
        multiple = observation(captured=11.0, count=2)
        last_face = observation(captured=10.0)
        self.assertIs(
            stable_face_observation(multiple, last_face, now_monotonic=11.2),
            multiple,
        )

    def test_fresh_single_face_is_ready(self):
        face = observation(captured=10.0)
        self.assertTrue(observation_is_fresh_single_face(face, now_monotonic=10.2))
        self.assertEqual(
            camera_health_reason(status="RECEIVING", observation=face, now_monotonic=10.2),
            "READY",
        )

    def test_stale_observation_fails_closed(self):
        face = observation(captured=10.0)
        self.assertFalse(observation_is_fresh_single_face(face, now_monotonic=12.0))
        self.assertEqual(
            camera_health_reason(status="RECEIVING", observation=face, now_monotonic=12.0),
            "CAMERA_OBSERVATION_STALE",
        )

    def test_stopped_transport_never_reuses_face(self):
        face = observation(captured=10.0)
        self.assertEqual(
            camera_health_reason(status="STOPPED", observation=face, now_monotonic=10.1),
            "CAMERA_STOPPED",
        )

    def test_transport_error_is_reported_instead_of_face_state(self):
        face = observation(captured=10.0)
        self.assertEqual(
            camera_health_reason(
                status="ERROR",
                observation=face,
                now_monotonic=20.0,
                error_code="VIDEO_FRAME_TIMEOUT",
            ),
            "VIDEO_FRAME_TIMEOUT",
        )

    def test_saved_row_requires_numeric_fresh_age(self):
        self.assertTrue(row_has_fresh_single_face({"face_count": 1, "face_age_ms": 20.0}))
        self.assertFalse(row_has_fresh_single_face({"face_count": 1, "face_age_ms": 20_000.0}))
        self.assertFalse(row_has_fresh_single_face({"face_count": 1, "face_age_ms": ""}))

    def test_no_face_is_healthy_transport_but_separate_detection_status(self):
        no_face = observation(captured=10.0, count=0)
        self.assertEqual(
            camera_transport_reason(
                status="RECEIVING",
                observation=no_face,
                now_monotonic=10.1,
                frames_received=5,
                last_frame_received_monotonic=10.1,
            ),
            "READY",
        )
        self.assertEqual(
            face_detection_status(no_face, now_monotonic=10.1),
            "NO_FACE",
        )

    def test_transport_health_does_not_depend_on_detector_freshness(self):
        stale_face = observation(captured=1.0)
        self.assertEqual(
            camera_transport_reason(
                status="RECEIVING",
                observation=stale_face,
                now_monotonic=10.0,
                frames_received=5,
                last_frame_received_monotonic=10.0,
            ),
            "READY",
        )
        self.assertEqual(
            camera_detector_reason(stale_face, now_monotonic=10.0),
            "CAMERA_OBSERVATION_STALE",
        )

    def test_health_gate_requires_time_and_distinct_observations(self):
        gate = CameraHealthGate(
            duration_seconds=1.0,
            minimum_observations=3,
            minimum_samples=3,
        )
        for now in (10.0, 10.4):
            gate.update(
                status="RECEIVING",
                observation=observation(captured=now, count=0),
                now_monotonic=now,
                frames_received=10,
                last_frame_received_monotonic=now,
            )
        self.assertFalse(gate.passed)
        gate.update(
            status="RECEIVING",
            observation=observation(captured=11.0, count=0),
            now_monotonic=11.0,
            frames_received=20,
            last_frame_received_monotonic=11.0,
        )
        self.assertTrue(gate.passed)
        self.assertEqual(gate.unique_observations, 3)

    def test_one_transient_failure_does_not_erase_rolling_progress(self):
        gate = CameraHealthGate(
            duration_seconds=1.0,
            minimum_observations=5,
            minimum_samples=10,
            minimum_ready_fraction=CAMERA_HEALTH_MIN_READY_FRACTION,
        )
        for index in range(11):
            now = index / 10.0
            last_frame = now - 3.0 if index == 5 else now
            gate.update(
                status="RECEIVING",
                observation=observation(captured=now),
                now_monotonic=now,
                frames_received=index + 1,
                last_frame_received_monotonic=last_frame,
            )
        self.assertTrue(gate.passed)
        self.assertEqual(gate.failure_count, 1)
        self.assertGreaterEqual(gate.ready_fraction, 0.90)
        self.assertEqual(gate.last_failure_reason, "CAMERA_FRAME_STALE")

    def test_sustained_failures_keep_rolling_gate_locked(self):
        gate = CameraHealthGate(
            duration_seconds=1.0,
            minimum_observations=3,
            minimum_samples=10,
            minimum_ready_fraction=0.90,
        )
        for index in range(11):
            now = index / 10.0
            last_frame = now if index < 5 else now - 3.0
            gate.update(
                status="RECEIVING",
                observation=observation(captured=now),
                now_monotonic=now,
                frames_received=index + 1,
                last_frame_received_monotonic=last_frame,
            )
        self.assertFalse(gate.passed)
        self.assertLess(gate.ready_fraction, 0.90)
        self.assertEqual(gate.last_reason, "CAMERA_FRAME_STALE")


if __name__ == "__main__":
    unittest.main()
