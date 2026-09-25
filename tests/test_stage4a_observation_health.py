import ast
from copy import deepcopy
from pathlib import Path
import unittest

import reachy_stage4.observation_health as observation_health
from reachy_stage4.observation_health import evaluate_observation_health


def state(timestamp="2026-09-18T12:00:00Z", mode="disabled"):
    return {
        "timestamp": timestamp,
        "control_mode": mode,
        "head_pose": {"m": [1.0, 0.0, 0.0, 0.0] * 4},
        "head_joints": [0.0] * 7,
        "body_yaw": 0.0,
    }


def status(*, temporary=True, mode="disabled"):
    return {
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


def evaluate(*, temporary=True, mode="disabled"):
    context = "TEMPORARY_OBSERVATION" if temporary else "STOCK_BASELINE"
    sample = status(temporary=temporary, mode=mode)
    return evaluate_observation_health(
        context=context,
        status_before=deepcopy(sample),
        state_before=state("2026-09-18T12:00:00Z", mode),
        status_after=deepcopy(sample),
        state_after=state("2026-09-18T12:00:01Z", mode),
        app_lock={"state": "free", "holder_name": None},
        current_app=None,
        required_motor_mode=mode,
    )


class ObservationHealthTests(unittest.TestCase):
    def test_exact_v190_health_uses_advancing_state_not_broken_serialized_fields(self):
        report = evaluate()
        self.assertTrue(report["accepted"])
        self.assertFalse(report["evidence"]["serialized_backend_ready_observed"])
        self.assertIsNone(report["evidence"]["serialized_last_alive_observed"])
        self.assertTrue(
            report["evidence"][
                "serialized_ready_and_last_alive_excluded_for_exact_v1_9_0"
            ]
        )

    def test_stock_context_requires_wireless_and_media_defaults(self):
        self.assertTrue(evaluate(temporary=False)["accepted"])

    def test_non_advancing_timestamp_fails_closed(self):
        sample = status()
        report = evaluate_observation_health(
            context="TEMPORARY_OBSERVATION",
            status_before=sample,
            state_before=state(),
            status_after=sample,
            state_after=state(),
            app_lock={"state": "free", "holder_name": None},
            current_app=None,
            required_motor_mode="disabled",
        )
        self.assertIn("STATE_TIMESTAMP_NOT_ADVANCING", report["reasons"])

    def test_loop_faults_and_mode_disagreement_are_rejected(self):
        before = status()
        after = deepcopy(before)
        after["backend_status"]["motor_control_mode"] = "enabled"
        after["backend_status"]["control_loop_stats"] = {
            "mean_control_loop_frequency": 20.0,
            "max_control_loop_interval": 0.2,
            "nb_error": 1,
        }
        report = evaluate_observation_health(
            context="TEMPORARY_OBSERVATION",
            status_before=before,
            state_before=state(),
            status_after=after,
            state_after=state("2026-09-18T12:00:01Z"),
            app_lock={"state": "free", "holder_name": None},
            current_app=None,
            required_motor_mode="disabled",
        )
        for reason in (
            "MOTOR_MODE_DISAGREEMENT",
            "CONTROL_LOOP_FREQUENCY_OUT_OF_RANGE",
            "CONTROL_LOOP_INTERVAL_TOO_LARGE",
            "CONTROL_LOOP_ERRORS_PRESENT",
        ):
            self.assertIn(reason, report["reasons"])

    def test_active_application_and_bad_version_are_rejected(self):
        sample = status()
        sample["version"] = "1.10.0"
        report = evaluate_observation_health(
            context="TEMPORARY_OBSERVATION",
            status_before=sample,
            state_before=state(),
            status_after=sample,
            state_after=state("2026-09-18T12:00:01Z"),
            app_lock={"state": "held", "holder_name": "demo"},
            current_app="demo",
            required_motor_mode="disabled",
        )
        self.assertIn("DAEMON_VERSION_MISMATCH", report["reasons"])
        self.assertIn("ROBOT_APP_LOCK_NOT_FREE", report["reasons"])
        self.assertIn("APPLICATION_ACTIVE", report["reasons"])

    def test_module_has_no_transport_or_command_surface(self):
        tree = ast.parse(Path(observation_health.__file__).read_text(encoding="utf-8"))
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
