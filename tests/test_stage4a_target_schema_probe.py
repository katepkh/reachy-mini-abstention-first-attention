import ast
import inspect
import unittest
from pathlib import Path

from reachy_stage4 import target_schema_probe
from reachy_stage4.target_schema_probe import (
    TARGET_FIELDS,
    compare_schema_serialization,
)


ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "patches/reachy-mini-v1.9.0-target-state-observability.patch"


def payload(pose):
    return {
        "head_pose": pose,
        "target_head_pose": pose,
        "head_joints": [0.0] * 7,
        "target_head_joints": [0.1] * 7,
        "body_yaw": 0.0,
        "target_body_yaw": 0.1,
        "antennas_position": [-0.1, 0.1],
        "target_antennas_position": [-0.2, 0.2],
    }


class TargetSchemaProbeTests(unittest.TestCase):
    def test_released_model_drops_and_patched_model_preserves_all_route_fields(self):
        result = compare_schema_serialization(
            payload({"x": 0.0, "y": 0.0, "z": 0.0, "roll": 0.0, "pitch": 0.0, "yaw": 0.0})
        )
        self.assertEqual(result["released_target_fields_present"], [])
        self.assertEqual(result["patched_target_fields_present"], sorted(TARGET_FIELDS))
        self.assertEqual(result["patched_payload"]["target_head_joints"], [0.1] * 7)
        self.assertEqual(result["robot_commands_authorized"], 0)

    def test_matrix_and_xyz_rpy_target_poses_survive(self):
        matrix = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
        for pose in (
            {"m": matrix},
            {"x": 0.0, "y": 0.0, "z": 0.0, "roll": 0.0, "pitch": 0.0, "yaw": 0.0},
        ):
            with self.subTest(pose=pose):
                result = compare_schema_serialization(payload(pose))
                self.assertEqual(result["patched_payload"]["target_head_pose"], pose)

    def test_omitted_target_flags_do_not_create_values(self):
        result = compare_schema_serialization({"body_yaw": 0.0})
        self.assertEqual(result["patched_target_fields_present"], [])

    def test_patch_declares_exactly_the_four_route_produced_fields(self):
        additions = {
            line.split(":", 1)[0].lstrip("+").strip()
            for line in PATCH.read_text(encoding="utf-8").splitlines()
            if line.startswith("+    target_")
        }
        self.assertEqual(additions, set(TARGET_FIELDS))

    def test_probe_has_no_network_or_robot_command_surface(self):
        source = inspect.getsource(target_schema_probe)
        tree = ast.parse(source)
        forbidden_roots = {"requests", "websockets", "socket", "reachy_mini"}
        imported_roots = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertTrue(forbidden_roots.isdisjoint(imported_roots))
        forbidden_calls = {"send", "post", "put", "patch", "delete", "goto", "connect"}
        used_calls = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertTrue(forbidden_calls.isdisjoint(used_calls), used_calls & forbidden_calls)


if __name__ == "__main__":
    unittest.main()
