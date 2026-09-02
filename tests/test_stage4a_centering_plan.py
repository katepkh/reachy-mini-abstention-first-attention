import ast
import inspect
import unittest

import numpy as np

from reachy_stage4 import centering_plan
from reachy_stage4.centering_plan import (
    MAX_PLANNED_STEP_DEG,
    STATUS_REVIEWED_REJECTED,
    assess_measured_step,
    draft_centering_plan,
    one_step_toward_identity,
)
from reachy_stage4.safety import rotation_distance_deg, translation_distance_mm


def axis_pose(axis, angle_deg, translation=(0.0, 0.0, 0.0)):
    axis = np.asarray(axis, dtype=np.float64)
    axis /= np.linalg.norm(axis)
    angle = np.deg2rad(angle_deg)
    x, y, z = axis
    skew = np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])
    rotation = np.eye(3) + np.sin(angle) * skew + (1.0 - np.cos(angle)) * (skew @ skew)
    pose = np.eye(4)
    pose[:3, :3] = rotation
    pose[:3, 3] = translation
    return pose


class Stage4ACenteringPlanTests(unittest.TestCase):
    def test_live_like_pose_gets_one_bounded_geodesic_waypoint(self):
        baseline = axis_pose((0.7, 0.5, -0.2), 4.182681, (-0.00256, 0.00161, -0.00218))
        plan = draft_centering_plan(baseline)
        waypoint = np.asarray(plan["waypoint_pose"])
        self.assertEqual(plan["authorization_status"], STATUS_REVIEWED_REJECTED)
        self.assertEqual(plan["decision"], "INDEPENDENT_REVIEW_REQUIRED")
        self.assertEqual(plan["review_verdict"]["hardware_execution"], "REJECT")
        self.assertEqual(plan["review_verdict"]["maximum_commands_authorized_by_this_artifact"], 0)
        self.assertAlmostEqual(rotation_distance_deg(baseline, waypoint), MAX_PLANNED_STEP_DEG)
        self.assertAlmostEqual(
            rotation_distance_deg(waypoint, np.eye(4)),
            4.182681 - MAX_PLANNED_STEP_DEG,
            places=6,
        )
        self.assertAlmostEqual(translation_distance_mm(baseline, waypoint), 0.0, places=9)
        self.assertEqual(plan["command_boundary"]["planner_robot_commands"], 0)
        self.assertEqual(plan["command_boundary"]["hardware_execution_commands_authorized"], 0)
        self.assertFalse(plan["command_boundary"]["automatic_chaining"])
        self.assertFalse(plan["command_boundary"]["automatic_return"])

    def test_pose_inside_gate_needs_no_waypoint(self):
        plan = draft_centering_plan(axis_pose((0.0, 1.0, 0.0), 0.8))
        self.assertEqual(plan["decision"], "NO_COMMAND_NEEDED")
        self.assertIsNone(plan["waypoint_pose"])

    def test_same_measured_pose_has_same_review_fingerprint(self):
        baseline = axis_pose((0.3, -0.6, 0.2), 4.2, (0.001, -0.002, 0.003))
        first = draft_centering_plan(baseline)
        second = draft_centering_plan(baseline.copy())
        self.assertEqual(first, second)
        self.assertEqual(len(first["plan_fingerprint"]), 64)

    def test_ineligible_rotation_or_translation_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Start rotation"):
            draft_centering_plan(axis_pose((1.0, 0.0, 0.0), 6.1))
        with self.assertRaisesRegex(ValueError, "Start translation"):
            draft_centering_plan(axis_pose((1.0, 0.0, 0.0), 2.0, (0.009, 0.0, 0.0)))

    def test_exact_waypoint_passes_endpoint_bounds_but_never_authorizes_next(self):
        baseline = axis_pose((0.2, 0.8, -0.1), 4.0)
        plan = draft_centering_plan(baseline)
        result = assess_measured_step(plan, np.asarray(plan["waypoint_pose"]))
        self.assertTrue(result["endpoint_bounds_pass"])
        self.assertEqual(result["operator_review"], "REQUIRED")
        self.assertFalse(result["automatic_next_command_authorized"])

    def test_overshoot_fails_endpoint_bounds(self):
        baseline = axis_pose((0.0, 1.0, 0.0), 4.0)
        plan = draft_centering_plan(baseline)
        measured = axis_pose((0.0, 1.0, 0.0), 1.0)
        result = assess_measured_step(plan, measured)
        self.assertAlmostEqual(result["metrics"]["measured_step_deg"], 3.0, places=6)
        self.assertFalse(result["endpoint_bounds_pass"])
        self.assertEqual(result["operator_review"], "NOT_ELIGIBLE")

    def test_planner_has_no_transport_or_command_call_surface(self):
        source = inspect.getsource(centering_plan)
        tree = ast.parse(source)
        imported_roots = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertTrue({"requests", "websockets", "socket"}.isdisjoint(imported_roots))
        forbidden_calls = {"send", "post", "put", "patch", "delete", "goto", "connect"}
        used_calls = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertTrue(forbidden_calls.isdisjoint(used_calls), used_calls & forbidden_calls)
        self.assertNotIn("reachy_stage4.runtime", source)


if __name__ == "__main__":
    unittest.main()
