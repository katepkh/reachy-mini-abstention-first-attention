import ast
from pathlib import Path
import unittest

import reachy_stage4.failure_response as failure_response
from reachy_stage4.failure_response import classify_failure


class FailureResponseTests(unittest.TestCase):
    def test_observation_failure_with_confirmed_disabled_mode_stops_only(self):
        result = classify_failure(
            "observation_only",
            "health_failure",
            daemon_responsive=True,
            telemetry_fresh=True,
            motor_mode_confirmed_disabled=True,
        )
        self.assertEqual(
            result["response"],
            "STOP_TEMPORARY_DAEMON_VERIFY_EXIT_AND_SERIAL_RELEASE_NO_RETURN",
        )
        self.assertFalse(result["automatic_return"])

    def test_responsive_fresh_enabled_state_selects_one_safety_disable(self):
        result = classify_failure(
            "target",
            "unexpected_motion",
            daemon_responsive=True,
            telemetry_fresh=True,
            motor_mode_confirmed_disabled=False,
        )
        self.assertEqual(
            result["response"],
            "ISSUE_ONE_SAFETY_DISABLE_VERIFY_DISABLED_THEN_STOP_NO_RETURN",
        )
        self.assertEqual(result["safety_disable_actions_planned"], 1)
        self.assertEqual(result["experimental_commands_planned"], 0)

    def test_daemon_loss_or_stale_telemetry_selects_physical_power_off(self):
        for responsive, fresh in ((False, False), (True, False)):
            with self.subTest(responsive=responsive, fresh=fresh):
                result = classify_failure(
                    "return",
                    "timeout",
                    daemon_responsive=responsive,
                    telemetry_fresh=fresh,
                    motor_mode_confirmed_disabled=False,
                )
                self.assertIn("PHYSICAL_POWER_OFF", result["response"])
                self.assertTrue(result["platform_drop_zone_required"])
                self.assertFalse(result["normal_daemon_shutdown_assumed_safe"])
                self.assertFalse(result["hard_power_removal_assumed_safe"])
                self.assertFalse(result["automatic_return"])

    def test_module_has_no_command_or_transport_surface(self):
        tree = ast.parse(Path(failure_response.__file__).read_text(encoding="utf-8"))
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertTrue(imports.isdisjoint({"requests", "websockets", "socket", "subprocess"}))


if __name__ == "__main__":
    unittest.main()
