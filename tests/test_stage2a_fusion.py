import time
import unittest

from reachy_doa.policies import PolicyDecision
from reachy_stage2a.fusion import fuse_passive_evidence
from reachy_stage2a.models import FaceObservation


def acoustic(**overrides):
    values = {
        "policy": "test",
        "sequence": 1,
        "elapsed_ms": 1000.0,
        "state": "TRACKING_AXIS",
        "axis_deg": 90.0,
        "hypothesis_a_deg": 0.0,
        "hypothesis_b_deg": 180.0,
        "confidence": 0.85,
        "valid_rate": 1.0,
        "speech_evidence": 0.7,
        "stability": 0.9,
        "reliability_prior": 0.8,
        "p95_latency_ms": 5.0,
        "front_back_ambiguous": True,
        "would_attend_axis": True,
        "would_propose_physical_target": False,
        "reason": "test",
    }
    values.update(overrides)
    return PolicyDecision(**values)


def face(now, **overrides):
    values = {
        "client_time_iso": "2026-08-24T12:00:00+01:00",
        "captured_monotonic": now,
        "detected": True,
        "face_count": 1,
        "center_x_norm": 0.5,
        "center_y_norm": 0.5,
        "heading_deg": 3.0,
        "detector_confidence": 0.9,
        "detector_score_raw": 4.0,
        "processing_ms": 4.0,
        "valid": True,
        "error_code": "",
    }
    values.update(overrides)
    return FaceObservation(**values)


class FusionTests(unittest.TestCase):
    def test_visual_agreement_selects_exactly_one_hypothesis(self):
        now = time.perf_counter()
        decision = fuse_passive_evidence(acoustic(), face(now), now_monotonic=now)
        self.assertEqual(decision.state, "CONFIRMED")
        self.assertEqual(decision.confirmed_heading_deg, 0.0)
        self.assertAlmostEqual(decision.agreement_error_deg, 3.0)

    def test_disagreement_withholds(self):
        now = time.perf_counter()
        decision = fuse_passive_evidence(
            acoustic(), face(now, heading_deg=90.0), now_monotonic=now
        )
        self.assertEqual(decision.reason_code, "ACOUSTIC_VISUAL_DISAGREEMENT")
        self.assertIsNone(decision.confirmed_heading_deg)

    def test_no_face_withholds(self):
        now = time.perf_counter()
        decision = fuse_passive_evidence(
            acoustic(), face(now, detected=False, face_count=0, heading_deg=None),
            now_monotonic=now,
        )
        self.assertEqual(decision.reason_code, "NO_FACE")

    def test_multiple_faces_withhold(self):
        now = time.perf_counter()
        decision = fuse_passive_evidence(
            acoustic(), face(now, face_count=2), now_monotonic=now
        )
        self.assertEqual(decision.reason_code, "MULTIPLE_FACES")

    def test_low_face_confidence_withholds(self):
        now = time.perf_counter()
        decision = fuse_passive_evidence(
            acoustic(), face(now, detector_confidence=0.2), now_monotonic=now
        )
        self.assertEqual(decision.reason_code, "FACE_LOW_CONFIDENCE")

    def test_stale_camera_observation_withholds(self):
        now = time.perf_counter()
        decision = fuse_passive_evidence(
            acoustic(), face(now - 2.0), now_monotonic=now
        )
        self.assertEqual(decision.reason_code, "CAMERA_OBSERVATION_STALE")

    def test_weak_acoustic_state_withholds_before_visual_selection(self):
        now = time.perf_counter()
        decision = fuse_passive_evidence(
            acoustic(confidence=0.3), face(now), now_monotonic=now
        )
        self.assertEqual(decision.reason_code, "ACOUSTIC_LOW_CONFIDENCE")

    def test_non_tracking_acoustic_state_withholds(self):
        now = time.perf_counter()
        decision = fuse_passive_evidence(
            acoustic(would_attend_axis=False), face(now), now_monotonic=now
        )
        self.assertEqual(decision.reason_code, "ACOUSTIC_NOT_TRACKING")


if __name__ == "__main__":
    unittest.main()
