import ast
from pathlib import Path
import tempfile
import unittest

import reachy_stage4.offline_fault_rehearsal as rehearsal
from reachy_stage4.offline_fault_rehearsal import (
    SCENARIOS,
    rehearse_scenario,
    run_offline_fault_rehearsal,
)


class OfflineFaultRehearsalTests(unittest.TestCase):
    def test_all_fixed_scenarios_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            report = run_offline_fault_rehearsal(
                Path(directory),
                timeout_seconds=1.5,
            )
        self.assertEqual(report["status"], "PASS_OFFLINE_MOCK_ONLY")
        self.assertEqual(report["scenario_count"], 4)
        self.assertEqual(
            [item["scenario"] for item in report["scenarios"]],
            list(SCENARIOS),
        )
        for result in report["scenarios"]:
            self.assertEqual(result["result"], "PASS")
            self.assertTrue(result["duplicate_start_blocked"])
            self.assertTrue(
                result["restoration_blocked_while_mock_active_or_lease_held"]
            )
            self.assertTrue(result["mock_process_exit_confirmed"])
            self.assertFalse(result["hardware_restoration_authorized"])
            self.assertEqual(result["robot_connections"], 0)
            self.assertEqual(result["robot_commands_sent"], 0)

    def test_start_failure_is_observed_without_timeout(self):
        with tempfile.TemporaryDirectory() as directory:
            result = rehearse_scenario(
                "start_failure",
                Path(directory),
                timeout_seconds=1.5,
            )
        self.assertEqual(result["mock_returncode"], 17)
        self.assertFalse(result["mock_timed_out"])
        self.assertEqual(result["events"], ["MOCK_START_REJECTED"])

    def test_unknown_scenario_cannot_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "Unknown rehearsal scenario"):
                rehearse_scenario("real-daemon", Path(directory))

    def test_harness_has_no_robot_or_network_import(self):
        tree = ast.parse(Path(rehearsal.__file__).read_text(encoding="utf-8"))
        imported_roots = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported_roots.update(
            (node.module or "").split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.level == 0
        )
        self.assertTrue(
            imported_roots.isdisjoint(
                {"reachy_mini", "requests", "socket", "websockets", "aiohttp"}
            )
        )
        self.assertNotIn("socket", rehearsal.MOCK_WORKER_SOURCE)
        self.assertNotIn("reachy", rehearsal.MOCK_WORKER_SOURCE.lower())
        self.assertIn("-I", rehearsal.rehearse_scenario.__code__.co_consts)


if __name__ == "__main__":
    unittest.main()
