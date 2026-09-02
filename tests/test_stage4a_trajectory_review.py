import unittest

import numpy as np
from scipy.spatial.transform import Rotation

from reachy_stage4.trajectory_review import (
    JOINT_NAMES,
    analyze_joint_margins,
    interpolate_pose_v190,
    minimum_jerk_progress,
    reconstruct_ideal_leg_v190,
)


class TrajectoryReviewTests(unittest.TestCase):
    def test_minimum_jerk_endpoints_and_midpoint(self):
        self.assertEqual(minimum_jerk_progress(0.0), 0.0)
        self.assertEqual(minimum_jerk_progress(0.5), 0.5)
        self.assertEqual(minimum_jerk_progress(1.0), 1.0)
        with self.assertRaises(ValueError):
            minimum_jerk_progress(1.01)

    def test_pose_interpolation_retains_endpoints(self):
        start = np.eye(4)
        start[:3, :3] = Rotation.from_euler("xyz", [2, -1, 3], degrees=True).as_matrix()
        target = np.eye(4)
        target[:3, :3] = Rotation.from_euler("xyz", [-2, 4, -5], degrees=True).as_matrix()
        target[:3, 3] = [0.001, -0.002, 0.003]
        np.testing.assert_allclose(interpolate_pose_v190(start, target, 0.0), start, atol=1e-12)
        np.testing.assert_allclose(interpolate_pose_v190(start, target, 1.0), target, atol=1e-12)

    def test_ideal_grid_is_inclusive_and_minimum_jerk(self):
        start = np.eye(4)
        target = np.eye(4)
        target[:3, :3] = Rotation.from_euler("y", 3, degrees=True).as_matrix()
        leg = reconstruct_ideal_leg_v190(
            start,
            target,
            start_body_yaw=0.1,
            target_body_yaw=0.1,
            duration_s=2.0,
            sample_hz=100.0,
        )
        self.assertEqual(leg["sample_count_including_endpoint"], 201)
        self.assertEqual(float(leg["times_s"][-1]), 2.0)
        self.assertEqual(float(leg["progress"][100]), 0.5)

    def test_joint_margin_reports_limiting_joint_and_bound_violation(self):
        leg = reconstruct_ideal_leg_v190(
            np.eye(4),
            np.eye(4),
            start_body_yaw=0.0,
            target_body_yaw=0.0,
            duration_s=1.0,
            sample_hz=2.0,
        )
        counter = {"index": 0}

        def fake_ik(_pose, _body_yaw):
            index = counter["index"]
            counter["index"] += 1
            row = np.zeros(7)
            row[3] = [0.0, 0.5, 1.1][index]
            return row

        bounds = {name: (-1.0, 1.0) for name in JOINT_NAMES}
        result = analyze_joint_margins(
            leg, inverse_kinematics=fake_ik, joint_bounds_rad=bounds
        )
        self.assertFalse(result["within_all_supplied_joint_bounds"])
        self.assertEqual(result["limiting_joint"], "stewart_3")
        self.assertAlmostEqual(result["minimum_margin_rad"], -0.1)


if __name__ == "__main__":
    unittest.main()
