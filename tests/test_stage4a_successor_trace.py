import ast
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

import reachy_stage4.successor_trace as successor_trace
from reachy_stage4.successor_trace import (
    build_receive_only_url,
    capture_receive_only_trace,
    parse_full_state_frame,
)


def valid_frame() -> dict:
    identity = np.eye(4).reshape(-1).tolist()
    return {
        "control_mode": "enabled",
        "head_pose": {"m": identity},
        "target_head_pose": {"m": identity},
        "head_joints": [0.0] * 7,
        "target_head_joints": [0.1] * 7,
        "body_yaw": 0.0,
        "target_body_yaw": 0.0,
        "timestamp": "2026-09-02T12:00:00Z",
    }


class FakeSocket:
    def __init__(self, messages):
        self.messages = iter(messages)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def recv(self, *, timeout):
        self.last_timeout = timeout
        return json.dumps(next(self.messages))


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        self.value += 0.2
        return self.value


class SuccessorTraceTests(unittest.TestCase):
    def test_url_requests_present_and_target_fields_without_command_route(self):
        url = build_receive_only_url("192.168.1.251", 20.0)
        self.assertIn("/api/state/ws/full?", url)
        self.assertIn("with_target_head_pose=true", url)
        self.assertIn("with_target_head_joints=true", url)
        self.assertIn("use_pose_matrix=true", url)
        self.assertNotIn("/ws/sdk", url)

    def test_released_schema_without_targets_fails_closed(self):
        frame = valid_frame()
        frame.pop("target_head_pose")
        with self.assertRaisesRegex(ValueError, "TARGET_STATE_UNAVAILABLE"):
            parse_full_state_frame(
                frame,
                received_monotonic_s=1.0,
                received_at_utc="2026-09-02T12:00:00Z",
            )

    def test_valid_frame_retains_present_and_target_state(self):
        parsed = parse_full_state_frame(
            valid_frame(),
            received_monotonic_s=1.0,
            received_at_utc="2026-09-02T12:00:00Z",
        )
        self.assertEqual(len(parsed["present_head_joints_rad"]), 7)
        self.assertEqual(len(parsed["target_head_joints_rad"]), 7)
        self.assertEqual(parsed["target_head_joints_rad"], [0.1] * 7)

    def test_malformed_pose_fails_with_stable_validation_error(self):
        frame = valid_frame()
        frame["target_head_pose"] = {"unexpected": "mapping"}
        with self.assertRaisesRegex(ValueError, "INVALID_TARGET_HEAD_POSE"):
            parse_full_state_frame(
                frame,
                received_monotonic_s=1.0,
                received_at_utc="2026-09-02T12:00:00Z",
            )

    def test_fake_capture_writes_hash_and_sends_zero_commands(self):
        clock = FakeClock()
        socket = FakeSocket([valid_frame()] * 10)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "trace.json"
            report, digest = capture_receive_only_trace(
                "192.168.1.251",
                duration_s=1.0,
                frequency_hz=10.0,
                output=output,
                connector=lambda *_args, **_kwargs: socket,
                monotonic=clock,
            )
            self.assertGreaterEqual(report["frame_count"], 2)
            self.assertEqual(report["transport"]["client_application_messages_sent"], 0)
            self.assertEqual(report["transport"]["robot_commands_sent"], 0)
            self.assertTrue(output.is_file())
            self.assertIn(digest, output.with_suffix(".json.sha256").read_text())

    def test_module_has_no_application_send_or_command_surface(self):
        tree = ast.parse(Path(successor_trace.__file__).read_text(encoding="utf-8"))
        called_attributes = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertNotIn("send", called_attributes)
        self.assertTrue(
            called_attributes.isdisjoint(
                {"post", "put", "patch", "delete", "goto", "set_target"}
            )
        )

    def test_capture_cli_requires_owner_and_independent_records(self):
        script = (
            Path(successor_trace.__file__).resolve().parents[1]
            / "scripts/capture_successor_present_target_trace.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"--owner-scope-record"', script)
        self.assertIn('"--independent-review-record"', script)
        self.assertIn("require_owner_observability_scope", script)
        self.assertIn("require_independent_protocol_approval", script)

    def test_capture_cli_has_no_command_call(self):
        script_path = (
            Path(successor_trace.__file__).resolve().parents[1]
            / "scripts/capture_successor_present_target_trace.py"
        )
        tree = ast.parse(script_path.read_text(encoding="utf-8"))
        called_attributes = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertTrue(
            called_attributes.isdisjoint(
                {"send", "post", "put", "patch", "delete", "goto", "set_target"}
            )
        )


if __name__ == "__main__":
    unittest.main()
