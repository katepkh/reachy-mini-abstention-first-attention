from __future__ import annotations

import hashlib
import unittest

import numpy as np

from reachy_stage2a.face_detector import FacePositionDetector


class YuNetFaceDetectorTests(unittest.TestCase):
    def test_local_model_has_frozen_hash(self) -> None:
        model_bytes = FacePositionDetector.MODEL_PATH.read_bytes()
        self.assertEqual(
            hashlib.sha256(model_bytes).hexdigest(),
            FacePositionDetector.MODEL_SHA256,
        )

    def test_blank_frame_does_not_invent_a_face(self) -> None:
        blank = np.full((480, 640, 3), 127, dtype=np.uint8)
        observation = FacePositionDetector().observe(blank)
        self.assertTrue(observation.valid)
        self.assertFalse(observation.detected)
        self.assertEqual(observation.face_count, 0)
        self.assertIsNone(observation.heading_deg)

    def test_detector_reduces_yunet_eye_landmarks_to_numeric_midpoint(self) -> None:
        class FakeYuNet:
            def setInputSize(self, _size):
                return None

            def detect(self, _frame):
                # bbox; right eye; left eye; nose; mouth corners; score
                return 1, np.array([[
                    10, 20, 100, 120,
                    30, 50, 70, 54,
                    50, 76, 35, 105, 65, 106,
                    0.99,
                ]], dtype=np.float32)

        detector = FacePositionDetector()
        detector._classifier = FakeYuNet()
        observation = detector.observe(np.zeros((200, 320, 3), dtype=np.uint8))
        self.assertTrue(observation.valid)
        self.assertEqual(observation.face_count, 1)
        self.assertAlmostEqual(observation.eye_midpoint_x_norm or 0.0, 50.0 / 320.0)
        self.assertAlmostEqual(observation.eye_midpoint_y_norm or 0.0, 52.0 / 200.0)
        self.assertEqual(observation.frame_width_px, 320)
        self.assertEqual(observation.frame_height_px, 200)


if __name__ == "__main__":
    unittest.main()
