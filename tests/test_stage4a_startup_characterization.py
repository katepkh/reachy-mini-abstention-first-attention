import ast
import hashlib
import inspect
import json
import tempfile
import unittest
from pathlib import Path

from reachy_stage4 import startup_characterization
from reachy_stage4.startup_characterization import (
    load_verified_capture,
    summarize_startup_captures,
    write_report,
)


def capture(index, mean, maximum, *, controller_touched="no", frames=20):
    return {
        "schema": "reachy-stage4-neutral-diagnostic-v2",
        "operator_annotation": {
            "startup_context": {
                "startup_kind": "physical_power_cycle",
                "startup_index": index,
                "startup_age_seconds": 30.0,
                "wake_animation_observed": "yes",
                "startup_app_observed": "no",
                "controller_touched_since_start": controller_touched,
            }
        },
        "transport_audit": {
            "http_methods": ["GET"],
            "websocket_messages_sent": 0,
            "robot_commands_sent": 0,
        },
        "daemon_status_after": {
            "version": "1.9.0",
            "simulation_enabled": False,
            "mockup_sim_enabled": False,
        },
        "app_context": {
            "configured_startup_app": None,
            "current_app_status": None,
        },
        "summary": {
            "stream_rotation_from_identity_deg": {
                "minimum": mean - 0.05,
                "mean": mean,
                "maximum": maximum,
            },
            "stream_rotation_drift_from_first_deg": {"maximum": 0.08},
        },
        "stream_frames": [{} for _ in range(frames)],
        "started_at_utc": f"t{index}",
        "_capture_file": f"capture-{index}.json",
        "_capture_sha256": str(index) * 64,
    }


class Stage4AStartupCharacterizationTests(unittest.TestCase):
    def test_three_controlled_starts_are_aggregated_without_authority(self):
        report = summarize_startup_captures(
            [capture(3, 1.4, 1.45), capture(1, 4.18, 4.22), capture(2, 1.3, 1.36)]
        )
        self.assertEqual(report["capture_count"], 3)
        self.assertTrue(report["controlled_start_count_sufficient"])
        self.assertEqual(report["diagnostic_status"], "START_STATE_OUTSIDE_GATE")
        self.assertAlmostEqual(report["capture_mean_rotation_deg"]["range"], 2.88)
        self.assertEqual(report["v4_commands_authorized"], 0)
        self.assertEqual([row["startup_index"] for row in report["captures"]], [1, 2, 3])

    def test_one_start_is_explicitly_insufficient(self):
        report = summarize_startup_captures([capture(1, 0.7, 0.8)])
        self.assertEqual(report["diagnostic_status"], "INSUFFICIENT_CONTROLLED_STARTS")
        self.assertFalse(report["controlled_start_count_sufficient"])

    def test_touched_controller_or_short_capture_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "untouched"):
            summarize_startup_captures([capture(1, 1.2, 1.3, controller_touched="yes")])
        with self.assertRaisesRegex(ValueError, "20 frames"):
            summarize_startup_captures([capture(1, 1.2, 1.3, frames=19)])

    def test_configured_or_running_app_is_rejected(self):
        configured = capture(1, 1.2, 1.3)
        configured["app_context"]["configured_startup_app"] = "some_app"
        with self.assertRaisesRegex(ValueError, "configured startup app"):
            summarize_startup_captures([configured])
        running = capture(1, 1.2, 1.3)
        running["app_context"]["current_app_status"] = {"name": "some_app"}
        with self.assertRaisesRegex(ValueError, "currently running app"):
            summarize_startup_captures([running])

    def test_verified_capture_and_immutable_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "capture.json"
            payload = (json.dumps(capture(1, 1.2, 1.3), sort_keys=True) + "\n").encode()
            path.write_bytes(payload)
            digest = hashlib.sha256(payload).hexdigest()
            path.with_suffix(".json.sha256").write_text(
                f"{digest}  capture.json\n", encoding="utf-8"
            )
            loaded = load_verified_capture(path)
            self.assertEqual(loaded["_capture_sha256"], digest)
            output = root / "report.json"
            written, sidecar, report_digest = write_report(
                summarize_startup_captures([loaded]), output
            )
            self.assertTrue(written.is_file())
            self.assertIn(report_digest, sidecar.read_text(encoding="utf-8"))
            with self.assertRaises(FileExistsError):
                write_report({}, output)

    def test_module_has_no_network_or_robot_command_surface(self):
        source = inspect.getsource(startup_characterization)
        tree = ast.parse(source)
        forbidden_roots = {"requests", "websockets", "socket"}
        imported_roots = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertTrue(forbidden_roots.isdisjoint(imported_roots))
        forbidden_calls = {"send", "post", "put", "patch", "delete", "goto", "connect"}
        used_calls = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertTrue(forbidden_calls.isdisjoint(used_calls), used_calls & forbidden_calls)


if __name__ == "__main__":
    unittest.main()
