import ast
from pathlib import Path
import unittest

import reachy_stage4.daemon_lifecycle as daemon_lifecycle
from reachy_stage4.daemon_lifecycle import build_observation_daemon_plan


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


if __name__ == "__main__":
    unittest.main()
