import ast
from pathlib import Path
import unittest

import reachy_stage4.failure_response as failure_response
from reachy_stage4.failure_response import classify_failure


class FailureResponseTests(unittest.TestCase):
    def test_observation_failure_depends_on_disabled_torque(self):
        result = classify_failure(
            "observation_only",
            "health_failure",
            daemon_responsive=True,
            telemetry_fresh=True,
            torque_expected_disabled=True,
        )
        self.assertEqual(
            result["response"],
            "STOP_TEMPORARY_DAEMON_PRESERVE_EVIDENCE_REVIEW_ROLLBACK",
        )
        self.assertFalse(result["automatic_return"])

    def test_responsive_fresh_failure_selects_only_preapproved_stop(self):
        result = classify_failure(
            "target",
            "unexpected_motion",
            daemon_responsive=True,
            telemetry_fresh=True,
            torque_expected_disabled=False,
        )
        self.assertEqual(
            result["response"],
            "PREAPPROVED_SUPPORTED_STOP_OR_DISABLE_NO_RETURN",
        )

    def test_daemon_loss_never_selects_software_return(self):
        result = classify_failure(
            "return",
            "timeout",
            daemon_responsive=False,
            telemetry_fresh=False,
            torque_expected_disabled=False,
        )
        self.assertIn("PHYSICAL_DEENERGIZATION", result["response"])
        self.assertFalse(result["normal_daemon_shutdown_assumed_safe"])
        self.assertFalse(result["hard_power_removal_assumed_safe"])

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
