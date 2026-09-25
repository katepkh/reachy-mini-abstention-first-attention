import ast
from copy import deepcopy
from pathlib import Path
import unittest

import reachy_stage4.observation_executor as observation_executor
from reachy_stage4.observation_executor import run_offline_observation_rehearsal


def probe(*, temporary, mode="disabled"):
    status = {
        "version": "1.9.0",
        "state": "running",
        "error": None,
        "wireless_version": not temporary,
        "no_media": temporary,
        "backend_status": {
            "error": None,
            "ready": False,
            "last_alive": None,
            "motor_control_mode": mode,
            "control_loop_stats": {
                "mean_control_loop_frequency": 50.0,
                "max_control_loop_interval": 0.02,
                "nb_error": 0,
            },
        },
    }
    state_before = {
        "timestamp": "2026-09-18T12:00:00Z",
        "control_mode": mode,
        "head_pose": {"m": [1.0, 0.0, 0.0, 0.0] * 4},
        "head_joints": [0.0] * 7,
        "body_yaw": 0.0,
    }
    state_after = deepcopy(state_before)
    state_after["timestamp"] = "2026-09-18T12:00:01Z"
    return {
        "status_before": deepcopy(status),
        "state_before": state_before,
        "status_after": deepcopy(status),
        "state_after": state_after,
        "app_lock": {"state": "free", "holder_name": None},
        "current_app": None,
    }


class FakeAdapter:
    offline_only = True

    def __init__(self):
        self.calls = []
        self.release = {
            "process_exited": True,
            "serial_owner_count": 0,
            "listener_count": 0,
        }
        self.terminal = {
            "daemon_responsive": True,
            "telemetry_fresh": True,
            "motor_mode": "disabled",
        }
        self.capture_error = False
        self.start_error = False
        self.terminal_error = False

    def baseline_probe(self):
        self.calls.append("baseline_probe")
        return probe(temporary=False)

    def stop_stock(self):
        self.calls.append("stop_stock")
        return dict(self.release)

    def start_temporary(self):
        self.calls.append("start_temporary")
        if self.start_error:
            raise RuntimeError("synthetic start fault")
        return {
            "bind_host": "127.0.0.1",
            "reflash_suppressed": True,
            "pid_gain_writes_declared": True,
            "experimental_motion_requests": 0,
            "torque_enable_requests": 0,
            "probe": probe(temporary=True),
        }

    def capture(self, requirement):
        self.calls.append(f"capture:{requirement}")
        if self.capture_error:
            raise RuntimeError("synthetic trace fault")
        return {
            "frame_count": 5,
            "target_requirement": requirement,
            "target_inference_performed": False,
            "transport": {
                "client_application_messages_sent": 0,
                "robot_commands_sent": 0,
            },
        }

    def terminal_state(self):
        self.calls.append("terminal_state")
        if self.terminal_error:
            raise RuntimeError("synthetic terminal fault")
        return dict(self.terminal)

    def safety_disable(self):
        self.calls.append("safety_disable")
        self.terminal["motor_mode"] = "disabled"

    def stop_temporary(self):
        self.calls.append("stop_temporary")
        return dict(self.release)

    def restore_stock(self):
        self.calls.append("restore_stock")
        return probe(temporary=False)


class ObservationExecutorTests(unittest.TestCase):
    def test_happy_path_rehearses_exact_order_and_restores_stock(self):
        adapter = FakeAdapter()
        report = run_offline_observation_rehearsal(adapter)
        self.assertEqual(report["status"], "PASS_OFFLINE_MOCK_ONLY")
        self.assertTrue(report["rollback_completed"])
        self.assertEqual(
            adapter.calls,
            [
                "baseline_probe",
                "stop_stock",
                "start_temporary",
                "capture:ALLOW_UNSET",
                "terminal_state",
                "stop_temporary",
                "restore_stock",
            ],
        )
        self.assertFalse(report["hardware_execution_authorized"])
        self.assertEqual(report["robot_commands_sent"], 0)

    def test_non_offline_adapter_is_refused_before_any_method(self):
        adapter = FakeAdapter()
        adapter.offline_only = False
        with self.assertRaisesRegex(PermissionError, "OFFLINE_ONLY"):
            run_offline_observation_rehearsal(adapter)
        self.assertEqual(adapter.calls, [])

    def test_stock_release_failure_never_starts_temporary(self):
        adapter = FakeAdapter()
        adapter.release["serial_owner_count"] = 1
        report = run_offline_observation_rehearsal(adapter)
        self.assertEqual(report["blocked_phase"], "STOCK_RELEASE")
        self.assertNotIn("start_temporary", adapter.calls)

    def test_capture_fault_rolls_back_when_terminal_state_is_fresh_disabled(self):
        adapter = FakeAdapter()
        adapter.capture_error = True
        report = run_offline_observation_rehearsal(adapter)
        self.assertEqual(report["status"], "BLOCKED_OFFLINE_MOCK_ONLY")
        self.assertIn("TRACE_CAPTURE_FAILED", report["reasons"])
        self.assertTrue(report["rollback_completed"])
        self.assertIn("restore_stock", adapter.calls)

    def test_ambiguous_terminal_state_requires_power_off_and_never_restores(self):
        adapter = FakeAdapter()
        adapter.capture_error = True
        adapter.terminal["telemetry_fresh"] = False
        report = run_offline_observation_rehearsal(adapter)
        self.assertTrue(report["physical_power_off_required"])
        self.assertFalse(report["rollback_completed"])
        self.assertNotIn("stop_temporary", adapter.calls)
        self.assertNotIn("restore_stock", adapter.calls)

    def test_missing_terminal_probe_requires_power_off_and_never_restores(self):
        adapter = FakeAdapter()
        adapter.terminal_error = True
        report = run_offline_observation_rehearsal(adapter)
        self.assertIn("TERMINAL_STATE_UNAVAILABLE", report["reasons"])
        self.assertTrue(report["physical_power_off_required"])
        self.assertNotIn("restore_stock", adapter.calls)

    def test_partial_start_failure_is_treated_as_ambiguous(self):
        adapter = FakeAdapter()
        adapter.start_error = True
        report = run_offline_observation_rehearsal(adapter)
        self.assertEqual(report["blocked_phase"], "TEMPORARY_START")
        self.assertTrue(report["physical_power_off_required"])
        self.assertNotIn("capture:ALLOW_UNSET", adapter.calls)
        self.assertNotIn("restore_stock", adapter.calls)

    def test_enabled_terminal_state_rehearses_one_safety_disable(self):
        adapter = FakeAdapter()
        adapter.terminal["motor_mode"] = "enabled"
        report = run_offline_observation_rehearsal(adapter)
        self.assertEqual(report["status"], "PASS_OFFLINE_MOCK_ONLY")
        self.assertEqual(adapter.calls.count("safety_disable"), 1)
        self.assertLess(adapter.calls.index("safety_disable"), adapter.calls.index("stop_temporary"))

    def test_module_has_no_transport_process_or_robot_import(self):
        tree = ast.parse(Path(observation_executor.__file__).read_text(encoding="utf-8"))
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertTrue(
            imports.isdisjoint(
                {"socket", "subprocess", "requests", "aiohttp", "websockets", "reachy_mini"}
            )
        )


if __name__ == "__main__":
    unittest.main()
