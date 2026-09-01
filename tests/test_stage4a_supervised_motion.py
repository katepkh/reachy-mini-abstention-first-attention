import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from reachy_stage4.config import ARM_PHRASE
from reachy_stage4.pilot import _status_ready, accept_trial, execute_trial, run_preflight
from reachy_stage4.protocol import PILOT_STEPS, protocol_payload
from reachy_stage4.safety import (
    relative_target_pose,
    rigid_pose,
    rotation_distance_deg,
    target_point,
    validate_host,
)


def pose_for_point(point):
    x, y, z = point
    angle = math.atan2(math.hypot(y, z), x)
    pose = np.eye(4)
    if z:
        sign = 1.0 if z > 0 else -1.0
        c, s = math.cos(sign * angle), math.sin(sign * angle)
        pose[:3, :3] = [[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]]
    elif y:
        sign = 1.0 if y > 0 else -1.0
        c, s = math.cos(sign * angle), math.sin(sign * angle)
        pose[:3, :3] = [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]
    return pose


class FakeAdapter:
    command_log = []

    def __init__(self, host):
        self.host = host
        self.pose = np.eye(4)
        self.disconnected = False

    def status(self):
        return {
            "state": "running",
            "backend_ready": False,
            "motor_control_mode": "enabled",
            "error": None,
            "simulation_enabled": False,
            "mockup_sim_enabled": False,
            "daemon_version": "1.9.0",
            "robot_name": "reachy_mini",
            "control_loop_frequency_hz": 50.0,
            "control_loop_max_interval_s": 0.02,
            "control_loop_error_count": 0,
            "motor_controller_status": "healthy",
            "head_pose_age_s": 0.01,
            "daemon_status_age_s": 0.01,
        }

    def current_pose(self):
        return self.pose.copy()

    def target_pose(self, point):
        return pose_for_point(point)

    def goto_head_only(self, pose, duration_s):
        self.pose = np.asarray(pose).copy()
        self.command_log.append((self.pose.copy(), duration_s))

    def disconnect(self):
        self.disconnected = True


class LaggedAdapter(FakeAdapter):
    latest = None

    def __init__(self, host):
        super().__init__(host)
        self.pending = None
        LaggedAdapter.latest = self

    def goto_head_only(self, pose, duration_s):
        self.pending = np.asarray(pose).copy()
        self.command_log.append((self.pending.copy(), duration_s))

    def settle(self):
        if self.pending is not None:
            self.pose = self.pending
            self.pending = None


class Stage4ASupervisedMotionTests(unittest.TestCase):
    def setUp(self):
        FakeAdapter.command_log.clear()
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.sessions = root / "sessions"
        self.progress = root / "progress.json"
        self.patches = [
            patch("reachy_stage4.pilot.SESSIONS_DIR", self.sessions),
            patch("reachy_stage4.pilot.PROGRESS_PATH", self.progress),
            patch(
                "reachy_stage4.pilot.verify_prerequisites",
                return_value={"pilot_protocol": {"fingerprint": protocol_payload()["fingerprint"]}},
            ),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temporary.cleanup()

    def test_frozen_protocol_is_four_one_shot_three_degree_directions(self):
        payload = protocol_payload()
        self.assertEqual([step.direction for step in PILOT_STEPS], ["UP", "DOWN", "LEFT", "RIGHT"])
        self.assertEqual(payload["motion_envelope"]["captured_baseline_relative_increment_deg"], 3.0)
        self.assertTrue(payload["motion_envelope"]["command_poses_projected_to_nearest_rigid_transform"])
        self.assertTrue(payload["motion_envelope"]["maximum_one_target_per_preflight_session"])
        self.assertTrue(payload["prohibited"]["continuous_control"])
        self.assertTrue(payload["prohibited"]["body_yaw_command"])

    def test_target_points_follow_official_x_forward_y_left_z_up_frame(self):
        self.assertGreater(target_point("UP")[2], 0.0)
        self.assertLess(target_point("DOWN")[2], 0.0)
        self.assertGreater(target_point("LEFT")[1], 0.0)
        self.assertLess(target_point("RIGHT")[1], 0.0)
        for direction in ("UP", "DOWN", "LEFT", "RIGHT"):
            self.assertAlmostEqual(np.linalg.norm(target_point(direction)), 1.0)
            self.assertAlmostEqual(
                rotation_distance_deg(np.eye(4), pose_for_point(target_point(direction))),
                3.0,
                places=6,
            )

    def test_relative_target_is_exactly_three_degrees_from_a_noisy_baseline(self):
        baseline = pose_for_point((1.0, 0.01, -0.005))
        baseline[:3, :3] *= 1.0001
        target = relative_target_pose(baseline, "UP")
        self.assertAlmostEqual(rotation_distance_deg(baseline, target), 3.0, places=6)
        projected = rigid_pose(baseline)
        np.testing.assert_allclose(target[:3, 3], projected[:3, 3])
        np.testing.assert_allclose(target[:3, :3].T @ target[:3, :3], np.eye(3), atol=1e-10)

    def test_host_is_locked_to_audited_private_reachy(self):
        self.assertEqual(validate_host("192.168.1.251"), "192.168.1.251")
        for host in ("127.0.0.1", "192.168.1.250", "8.8.8.8"):
            with self.assertRaises(ValueError):
                validate_host(host)

    def test_preflight_is_read_only_and_trial_is_exactly_target_plus_restore(self):
        preflight = run_preflight(adapter_factory=FakeAdapter)
        self.assertEqual(preflight["robot_commands"], 0)
        self.assertEqual(preflight["direction"], "UP")
        result = execute_trial(
            preflight["session_id"],
            "UP",
            ARM_PHRASE,
            adapter_factory=FakeAdapter,
            sleep=lambda _: None,
        )
        self.assertTrue(result["mechanical_gate_passed"])
        self.assertEqual(result["actuation_commands"], 2)
        self.assertEqual(result["body_yaw_commands"], 0)
        self.assertEqual(result["antenna_commands"], 0)
        self.assertEqual(len(FakeAdapter.command_log), 2)
        self.assertAlmostEqual(rotation_distance_deg(np.eye(4), FakeAdapter.command_log[0][0]), 3.0)
        np.testing.assert_allclose(FakeAdapter.command_log[1][0], np.eye(4))

    def test_v19_false_serialized_ready_is_replaced_by_live_health_evidence(self):
        status = FakeAdapter("unused").status()
        self.assertFalse(status["backend_ready"])
        self.assertTrue(_status_ready(status))
        for field, unsafe in (
            ("control_loop_frequency_hz", 0.0),
            ("control_loop_max_interval_s", 0.2),
            ("control_loop_error_count", 1),
            ("head_pose_age_s", 3.0),
            ("daemon_status_age_s", 3.0),
        ):
            changed = {**status, field: unsafe}
            self.assertFalse(_status_ready(changed), field)

    def test_consumed_preflight_cannot_be_replayed(self):
        preflight = run_preflight(adapter_factory=FakeAdapter)
        execute_trial(
            preflight["session_id"],
            "UP",
            ARM_PHRASE,
            adapter_factory=FakeAdapter,
            sleep=lambda _: None,
        )
        with self.assertRaisesRegex(ValueError, "already been consumed"):
            execute_trial(
                preflight["session_id"],
                "UP",
                ARM_PHRASE,
                adapter_factory=FakeAdapter,
                sleep=lambda _: None,
            )

    def test_target_and_restore_are_measured_only_after_settling(self):
        preflight = run_preflight(adapter_factory=LaggedAdapter)

        def settle(_):
            assert LaggedAdapter.latest is not None
            LaggedAdapter.latest.settle()

        result = execute_trial(
            preflight["session_id"],
            "UP",
            ARM_PHRASE,
            adapter_factory=LaggedAdapter,
            sleep=settle,
        )
        self.assertTrue(result["mechanical_gate_passed"])
        self.assertAlmostEqual(result["commanded_increment_deg"], 3.0, places=6)
        self.assertAlmostEqual(result["target_error_deg"], 0.0, places=6)
        self.assertAlmostEqual(result["restore_error_deg"], 0.0, places=6)

    def test_operator_review_is_required_before_progress_advances(self):
        preflight = run_preflight(adapter_factory=FakeAdapter)
        execute_trial(
            preflight["session_id"],
            "UP",
            ARM_PHRASE,
            adapter_factory=FakeAdapter,
            sleep=lambda _: None,
        )
        with self.assertRaises(ValueError):
            accept_trial(preflight["session_id"], {
                "correct_direction": True,
                "smooth_motion": True,
                "no_abnormal_noise_or_heat": False,
                "returned_to_start": True,
            })
        progress = accept_trial(preflight["session_id"], {
            "correct_direction": True,
            "smooth_motion": True,
            "no_abnormal_noise_or_heat": True,
            "returned_to_start": True,
        })
        self.assertEqual(progress["accepted_steps"], 1)
        self.assertEqual(progress["status"], "IN_PROGRESS")


if __name__ == "__main__":
    unittest.main()
