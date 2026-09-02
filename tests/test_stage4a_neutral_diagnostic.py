import ast
import hashlib
import inspect
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from reachy_stage4 import neutral_diagnostic
from reachy_stage4.neutral_diagnostic import (
    ReadOnlyReachyState,
    capture_neutral_diagnostic,
    euler_xyz,
    matrix_pose,
    normalize_startup_context,
    write_immutable_capture,
    xyzrpy_pose,
)
from reachy_stage4.safety import look_at_world_pose


class FakeResponse:
    def __init__(self, value):
        self.value = value

    def raise_for_status(self):
        return None

    def json(self):
        return self.value


class FakeGetOnlySession:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def get(self, url, *, params, timeout):
        self.calls.append((url, params, timeout))
        return FakeResponse(next(self.responses))


class FakeReceiveOnlySocket:
    def __init__(self, frames):
        self.frames = iter(frames)
        self.receive_count = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def recv(self, *, timeout):
        self.receive_count += 1
        return json.dumps(next(self.frames))


def status():
    return {
        "state": "running",
        "version": "1.9.0",
        "robot_name": "reachy_mini",
        "simulation_enabled": False,
        "mockup_sim_enabled": False,
        "backend_status": {"ready": True, "motor_control_mode": "enabled"},
        "error": None,
    }


def matrix_payload(pose):
    return {"m": np.asarray(pose).reshape(-1).tolist()}


def euler_payload(pose):
    roll, pitch, yaw = euler_xyz(np.asarray(pose))
    return {
        "x": float(pose[0, 3]),
        "y": float(pose[1, 3]),
        "z": float(pose[2, 3]),
        "roll": roll,
        "pitch": pitch,
        "yaw": yaw,
    }


class Stage4ANeutralDiagnosticTests(unittest.TestCase):
    def test_startup_context_is_explicit_and_validated(self):
        context = normalize_startup_context(
            {
                "startup_kind": "physical_power_cycle",
                "startup_index": 2,
                "startup_age_seconds": 45,
                "wake_animation_observed": "yes",
                "startup_app_observed": "no",
                "controller_touched_since_start": "no",
            }
        )
        self.assertEqual(context["startup_index"], 2)
        self.assertEqual(context["controller_touched_since_start"], "no")
        with self.assertRaisesRegex(ValueError, "startup_index"):
            normalize_startup_context({"startup_index": 0})

    def test_matrix_and_euler_representations_round_trip(self):
        pose = look_at_world_pose((0.99, 0.08, 0.11))
        pose[:3, 3] = [0.001, -0.002, 0.003]
        np.testing.assert_allclose(matrix_pose(matrix_payload(pose)), pose, atol=1e-12)
        np.testing.assert_allclose(xyzrpy_pose(euler_payload(pose)), pose, atol=1e-12)

    def test_capture_uses_get_and_receive_only_state_stream(self):
        pose = look_at_world_pose((0.999, 0.0, 0.044))
        responses = [
            status(),
            {"startup_app": None},
            None,
            matrix_payload(pose),
            euler_payload(pose),
            matrix_payload(pose),
            euler_payload(pose),
            status(),
        ]
        session = FakeGetOnlySession(responses)
        stream_frames = [
            {
                "head_pose": matrix_payload(pose),
                "head_joints": [0.0] * 7,
                "body_yaw": 0.0,
                "antennas_position": [0.0, 0.0],
                "control_mode": "enabled",
                "timestamp": f"t{index}",
            }
            for index in range(3)
        ]
        socket = FakeReceiveOnlySocket(stream_frames)
        ws_calls = []

        def receive_only_factory(url, *, open_timeout):
            ws_calls.append((url, open_timeout))
            return socket

        client = ReadOnlyReachyState(
            session=session,
            websocket_factory=receive_only_factory,
        )
        record = capture_neutral_diagnostic(client, frame_count=3, frequency_hz=5.0)

        self.assertEqual(len(session.calls), 8)
        self.assertTrue(all(call[0].startswith("http://192.168.1.251:8000/api/") for call in session.calls))
        self.assertEqual(len(ws_calls), 1)
        self.assertIn("/api/state/ws/full?", ws_calls[0][0])
        self.assertEqual(socket.receive_count, 3)
        self.assertEqual(record["transport_audit"]["http_methods"], ["GET"])
        self.assertEqual(record["transport_audit"]["websocket_messages_sent"], 0)
        self.assertEqual(record["transport_audit"]["robot_commands_sent"], 0)
        self.assertEqual(
            record["app_context"],
            {"configured_startup_app": None, "current_app_status": None},
        )
        self.assertEqual(
            record["operator_annotation"]["startup_context"]["startup_kind"],
            "not_a_startup_capture",
        )
        self.assertAlmostEqual(
            record["summary"]["rest_matrix_vs_euler_rotation_gap_deg"]["before"],
            0.0,
            places=7,
        )

    def test_transport_module_has_no_write_capable_call_surface(self):
        tree = ast.parse(inspect.getsource(neutral_diagnostic))
        forbidden = {"send", "post", "put", "patch", "delete", "goto", "move", "set_target"}
        used = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertTrue(forbidden.isdisjoint(used), used & forbidden)

    def test_capture_is_immutable_and_checksum_matches(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "capture.json"
            path, checksum_path, digest = write_immutable_capture({"b": 2, "a": 1}, output)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
            self.assertEqual(checksum_path.read_text(encoding="utf-8"), f"{digest}  capture.json\n")
            with self.assertRaises(FileExistsError):
                write_immutable_capture({"a": 1}, output)

    def test_wrong_daemon_version_blocks_before_streaming(self):
        bad_status = status()
        bad_status["version"] = "1.8.0"
        session = FakeGetOnlySession([bad_status])
        client = ReadOnlyReachyState(
            session=session,
            websocket_factory=lambda *args, **kwargs: self.fail("stream must not open"),
        )
        with self.assertRaisesRegex(RuntimeError, "Expected daemon 1.9.0"):
            capture_neutral_diagnostic(client)

    def test_cli_reports_connection_failure_without_writing(self):
        with patch.object(
            neutral_diagnostic,
            "capture_neutral_diagnostic",
            side_effect=TimeoutError("offline"),
        ):
            with patch.object(neutral_diagnostic, "write_immutable_capture") as write_capture:
                result = neutral_diagnostic.main(["--frames", "1"])
        self.assertEqual(result, 2)
        write_capture.assert_not_called()


if __name__ == "__main__":
    unittest.main()
