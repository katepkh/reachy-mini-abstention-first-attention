import ast
from pathlib import Path
import unittest

import reachy_stage4.daemon_lifecycle as daemon_lifecycle
from reachy_stage4.daemon_lifecycle import (
    build_observation_daemon_plan,
    plan_observation_shutdown,
    stock_restart_acceptance,
)


class DaemonLifecyclePlanTests(unittest.TestCase):
    def test_plan_is_isolated_and_non_wireless(self):
        plan = build_observation_daemon_plan(
            "/opt/reachy-experiment/source",
            "/opt/reachy-experiment/session-001",
        )
        command = plan["command"]
        for flag in (
            "--no-media",
            "--no-wake-up-on-start",
            "--no-goto-sleep-on-stop",
            "--no-reflash-motors-on-start",
            "--no-startup-app",
            "--no-mdns",
            "--no-preload-datasets",
            "--timeout-health-check",
        ):
            self.assertIn(flag, command)
        self.assertNotIn("--wireless-version", command)
        self.assertEqual(command[command.index("--fastapi-host") + 1], "127.0.0.1")
        self.assertEqual(command[command.index("--dataset-update-interval") + 1], "0")
        self.assertEqual(command[command.index("--timeout-health-check") + 1], "60")
        self.assertEqual(
            command[command.index("--hardware-config-filepath") + 1],
            "/opt/reachy-experiment/source/src/reachy_mini/assets/config/hardware_config.yaml",
        )

    def test_plan_is_not_a_launcher(self):
        tree = ast.parse(Path(daemon_lifecycle.__file__).read_text(encoding="utf-8"))
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertTrue(
            imports.isdisjoint({"subprocess", "socket", "requests", "websockets", "aiohttp"})
        )

    def test_paths_must_be_absolute(self):
        with self.assertRaisesRegex(ValueError, "absolute POSIX"):
            build_observation_daemon_plan("relative", "/session")

    def test_fresh_disabled_shutdown_only_stops_and_verifies_release(self):
        plan = plan_observation_shutdown(
            daemon_responsive=True,
            telemetry_fresh=True,
            motor_mode="disabled",
        )
        self.assertEqual(plan["branch"], "ALREADY_DISABLED_STOP")
        self.assertEqual(plan["safety_disable_actions_planned"], 0)
        self.assertFalse(plan["automatic_return"])

    def test_fresh_enabled_shutdown_plans_one_safety_disable_only(self):
        plan = plan_observation_shutdown(
            daemon_responsive=True,
            telemetry_fresh=True,
            motor_mode="enabled",
        )
        self.assertEqual(plan["branch"], "SAFETY_DISABLE_THEN_STOP")
        self.assertEqual(plan["safety_disable_actions_planned"], 1)
        self.assertEqual(plan["experimental_commands_planned"], 0)
        self.assertEqual(plan["robot_commands_authorized"], 0)

    def test_unknown_or_unresponsive_state_selects_physical_power_off(self):
        for responsive, fresh, mode in (
            (False, True, "disabled"),
            (True, False, "disabled"),
            (True, True, "unknown"),
        ):
            with self.subTest(responsive=responsive, fresh=fresh, mode=mode):
                plan = plan_observation_shutdown(
                    daemon_responsive=responsive,
                    telemetry_fresh=fresh,
                    motor_mode=mode,
                )
                self.assertEqual(plan["branch"], "PHYSICAL_POWER_OFF")
                self.assertFalse(plan["replacement_daemon_before_terminal_verification"])
                self.assertEqual(plan["safety_disable_actions_planned"], 0)

    def test_unknown_motor_mode_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "Unknown motor mode"):
            plan_observation_shutdown(
                daemon_responsive=True,
                telemetry_fresh=True,
                motor_mode="limp-ish",
            )

    def test_stock_restart_requires_temp_exit_and_has_no_motion_authority(self):
        gate = stock_restart_acceptance()
        self.assertIn("temporary process is confirmed exited", gate["preconditions"])
        self.assertFalse(gate["automatic_motion_authorized"])
        self.assertEqual(gate["robot_commands_authorized"], 0)


if __name__ == "__main__":
    unittest.main()
