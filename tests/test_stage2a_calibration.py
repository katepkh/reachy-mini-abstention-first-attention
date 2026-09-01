import unittest

from reachy_stage2a.calibration import (
    circular_distance_degrees,
    face_center_to_heading,
)


class CalibrationTests(unittest.TestCase):
    def test_principal_point_is_camera_front(self):
        principal_x = 1905.876059826701 / 3840.0
        self.assertAlmostEqual(face_center_to_heading(principal_x), 0.0, places=7)

    def test_image_right_is_positive_heading(self):
        self.assertGreater(face_center_to_heading(0.75), 0.0)

    def test_image_left_is_negative_heading(self):
        self.assertLess(face_center_to_heading(0.25), 0.0)

    def test_invalid_normalized_coordinate_is_rejected(self):
        with self.assertRaises(ValueError):
            face_center_to_heading(1.1)

    def test_circular_distance_wraps(self):
        self.assertAlmostEqual(circular_distance_degrees(179.0, -179.0), 2.0)


if __name__ == "__main__":
    unittest.main()
