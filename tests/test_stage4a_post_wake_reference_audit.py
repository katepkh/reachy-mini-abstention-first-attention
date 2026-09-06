import ast
import inspect
import math
import unittest

from reachy_stage4 import post_wake_reference_audit
from reachy_stage4.post_wake_reference_audit import (
    IDENTITY_IK_JOINTS_DEG,
    audit_post_wake_reference,
)


def capture(index, joints_deg, pose_mean=2.7):
    frame = {"head_joints_rad": [math.radians(value) for value in joints_deg]}
    return {
        "schema": "reachy-stage4-neutral-diagnostic-v2",
        "operator_annotation": {
            "startup_context": {
                "startup_kind": "physical_power_cycle",
                "startup_index": index,
                "startup_age_seconds": 60.0,
                "wake_animation_observed": "yes",
                "startup_app_observed": "no",
                "controller_touched_since_start": "no",
            }
        },
        "transport_audit": {
            "http_methods": ["GET"],
            "websocket_messages_sent": 0,
            "robot_commands_sent": 0,
        },
        "daemon_status_after": {
            "version": "1.9.0",
            "simulation_enabled": False,
            "mockup_sim_enabled": False,
        },
        "app_context": {
            "configured_startup_app": None,
            "current_app_status": None,
        },
        "summary": {
            "stream_rotation_from_identity_deg": {
                "minimum": pose_mean - 0.05,
                "mean": pose_mean,
                "maximum": pose_mean + 0.05,
            },
            "stream_rotation_drift_from_first_deg": {"maximum": 0.1},
        },
        "stream_frames": [dict(frame) for _ in range(20)],
        "started_at_utc": f"t{index}",
        "_capture_file": f"capture-{index}.json",
        "_capture_sha256": str(index) * 64,
    }


class PostWakeReferenceAuditTests(unittest.TestCase):
    def test_identity_reference_is_source_pinned_and_zero_authority(self):
        observed = list(IDENTITY_IK_JOINTS_DEG)
        observed[5] -= 4.0
        observed[6] += 3.0
        report = audit_post_wake_reference(
            [capture(1, observed), capture(2, observed), capture(3, observed)]
        )
        self.assertEqual(report["daemon_version"], "1.9.0")
        self.assertEqual(report["source_defined_wake_endpoint"], "4x4 identity pose")
        self.assertAlmostEqual(
            report["per_joint_summary"]["stewart_5"][
                "mean_delta_from_rounded_identity_ik_deg"
            ],
            -4.0,
        )
        self.assertAlmostEqual(
            report["per_joint_summary"]["stewart_6"][
                "mean_delta_from_rounded_identity_ik_deg"
            ],
            3.0,
        )
        self.assertEqual(report["robot_commands_authorized"], 0)

    def test_between_start_joint_range_is_reported_without_a_pass_threshold(self):
        records = []
        for index, shift in enumerate((0.0, 0.2, -0.1), start=1):
            joints = list(IDENTITY_IK_JOINTS_DEG)
            joints[1] += shift
            records.append(capture(index, joints))
        report = audit_post_wake_reference(records)
        self.assertAlmostEqual(
            report["per_joint_summary"]["stewart_1"]["between_start_range_deg"],
            0.3,
        )
        self.assertNotIn("joint_repeatability_pass", report)

    def test_malformed_joint_frame_is_rejected(self):
        record = capture(1, IDENTITY_IK_JOINTS_DEG)
        record["stream_frames"][0]["head_joints_rad"] = [0.0] * 6
        with self.assertRaisesRegex(ValueError, "seven"):
            audit_post_wake_reference([record])

    def test_module_has_no_network_or_robot_command_surface(self):
        source = inspect.getsource(post_wake_reference_audit)
        tree = ast.parse(source)
        forbidden_roots = {"requests", "websockets", "socket"}
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
