import math
import unittest

from reachy_doa.angles import (
    circular_mean_degrees,
    doa_mean_degrees,
    doa_radians_to_degrees,
    doa_to_physical_hypotheses,
    percentile,
    physical_heading_to_expected_doa,
    radians_to_degrees,
    wrap_degrees,
)


class AngleTests(unittest.TestCase):
    def test_wraps_degrees(self) -> None:
        self.assertAlmostEqual(wrap_degrees(181), -179)
        self.assertAlmostEqual(wrap_degrees(-181), 179)
        self.assertAlmostEqual(wrap_degrees(360), 0)

    def test_radians_conversion(self) -> None:
        self.assertAlmostEqual(radians_to_degrees(math.pi / 2), 90)
        self.assertAlmostEqual(radians_to_degrees(3 * math.pi / 2), -90)

    def test_doa_conversion_preserves_right_edge(self) -> None:
        self.assertAlmostEqual(doa_radians_to_degrees(0), 0)
        self.assertAlmostEqual(doa_radians_to_degrees(math.pi / 2), 90)
        self.assertAlmostEqual(doa_radians_to_degrees(math.pi), 180)

    def test_doa_mean_preserves_right_edge(self) -> None:
        self.assertAlmostEqual(doa_mean_degrees([180, 180]), 180)

    def test_physical_heading_folds_front_back(self) -> None:
        expected = {
            -135: 135, -90: 180, -45: 135, 0: 90,
            45: 45, 90: 0, 135: 45, 180: 90,
        }
        for heading, doa in expected.items():
            with self.subTest(heading=heading):
                self.assertAlmostEqual(physical_heading_to_expected_doa(heading), doa)

    def test_doa_inverse_preserves_front_back_hypotheses(self) -> None:
        self.assertEqual(doa_to_physical_hypotheses(45), (45.0, 135.0))
        self.assertEqual(doa_to_physical_hypotheses(90), (0.0, -180.0))
        self.assertEqual(doa_to_physical_hypotheses(135), (-45.0, -135.0))
        self.assertEqual(doa_to_physical_hypotheses(0), (90.0,))
        self.assertEqual(doa_to_physical_hypotheses(180), (-90.0,))

    def test_doa_inverse_rejects_non_sensor_angles(self) -> None:
        with self.assertRaises(ValueError):
            doa_to_physical_hypotheses(181)

    def test_circular_mean_crosses_boundary(self) -> None:
        result = circular_mean_degrees([179, -179])
        self.assertIsNotNone(result)
        self.assertAlmostEqual(abs(result), 180, places=6)

    def test_circular_mean_empty(self) -> None:
        self.assertIsNone(circular_mean_degrees([]))

    def test_percentile_interpolates(self) -> None:
        self.assertAlmostEqual(percentile([10, 20, 30, 40], 0.5), 25)
        self.assertAlmostEqual(percentile([10, 20, 30, 40], 0.95), 38.5)


if __name__ == "__main__":
    unittest.main()
