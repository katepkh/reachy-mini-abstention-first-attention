import unittest

from reachy_stage3v.analysis import evaluate_trial
from reachy_stage3v.protocol import VALIDATION_STEPS


def numeric_row(
    elapsed_ms: float,
    *,
    speech: bool,
    face_heading: float,
    hypothesis_a: float,
    hypothesis_b: float,
):
    return {
        "sequence": int(elapsed_ms // 200),
        "elapsed_ms": elapsed_ms,
        "http_status": 200,
        "raw_angle_rad": 1.0,
        "speech_detected": speech,
        "acoustic_state": "TRACKING_AXIS",
        "acoustic_confidence": 0.95,
        "hypothesis_a_deg": hypothesis_a,
        "hypothesis_b_deg": hypothesis_b,
        "face_count": 1,
        "face_heading_deg": face_heading,
        "face_confidence": 0.90,
        "face_age_ms": 20.0,
    }


class Stage3VAnalysisTests(unittest.TestCase):
    def test_matching_consensus_produces_correct_shadow_target(self):
        step = next(item for item in VALIDATION_STEPS if item.true_heading_deg == 10 and item.role == "matching_positive")
        rows = [
            numeric_row(index * 200.0, speech=True, face_heading=10.0, hypothesis_a=10.0, hypothesis_b=170.0)
            for index in range(8)
        ]
        result = evaluate_trial(step, rows)
        self.assertGreater(result["would_move_rows"], 0)
        self.assertEqual(result["first_target_yaw_deg"], 10.0)
        self.assertEqual(result["wrong_sign_moves"], 0)
        self.assertEqual(result["median_target_error_deg"], 0.0)

    def test_matching_target_is_bounded_at_twenty_degrees(self):
        step = next(item for item in VALIDATION_STEPS if item.true_heading_deg == 20 and item.role == "matching_positive")
        rows = [
            numeric_row(index * 200.0, speech=True, face_heading=20.0, hypothesis_a=20.0, hypothesis_b=160.0)
            for index in range(8)
        ]
        result = evaluate_trial(step, rows)
        self.assertEqual(result["first_target_yaw_deg"], 20.0)

    def test_mismatched_phone_and_face_fails_closed(self):
        step = next(item for item in VALIDATION_STEPS if item.condition_id.startswith("mismatch-"))
        rows = [
            numeric_row(
                index * 200.0,
                speech=True,
                face_heading=step.face_heading_deg,
                hypothesis_a=step.sound_heading_deg,
                hypothesis_b=160.0 if step.sound_heading_deg == 20.0 else -160.0,
            )
            for index in range(8)
        ]
        result = evaluate_trial(step, rows)
        self.assertEqual(result["would_move_rows"], 0)

    def test_silent_visible_face_produces_no_shadow_move(self):
        step = next(item for item in VALIDATION_STEPS if item.condition_id.startswith("silent-face"))
        rows = [
            numeric_row(
                index * 200.0,
                speech=False,
                face_heading=step.face_heading_deg,
                hypothesis_a=step.face_heading_deg,
                hypothesis_b=160.0,
            )
            for index in range(8)
        ]
        result = evaluate_trial(step, rows)
        self.assertEqual(result["would_move_rows"], 0)


if __name__ == "__main__":
    unittest.main()

