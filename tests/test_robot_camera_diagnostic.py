"""Synthetic-only diagnostic checks; no real sensor access or private writes."""
import json
from functools import partial
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from reachy_stage3v import robot_pilot_store as store
from reachy_stage3v.robot_pilot_protocol import protocol
from scripts.run_robot_camera_diagnostic import diagnostic_config, DiagnosticHandler, ROOT
from tests.test_robot_camera_http import FakeBridge, running_server, request

MIC = {"label": "synthetic", "settings": {"sampleRate": 48000}}


class DiagnosticTests(unittest.TestCase):
    def test_config_reads_seal_without_collection_or_mutation(self):
        setup = {"microphone": MIC, "playback": {"fixed_volume_percent": 50, "recording_sha256": "s" * 64}}
        with patch.object(store, "verify_seal", return_value=({"fingerprint": "e" * 64}, {"fingerprint": "b" * 64})), \
             patch.object(store, "read", return_value=setup), \
             patch.object(store, "collection_state", side_effect=AssertionError("Must not touch attempt accounting")), \
             patch.object(store, "write_new", side_effect=AssertionError("Must not write")):
            result = diagnostic_config()
        self.assertNotIn("pilot_state", result)
        self.assertEqual(result["diagnostic"]["purpose"], "DIAGNOSTIC_NOT_PILOT")
        self.assertEqual(result["diagnostic"]["microphone"], MIC)
        self.assertEqual(result["capture_seconds"], 10)
        self.assertFalse(result["motion_authority"])
        self.assertFalse(result["response_authority"])
        self.assertEqual(result["robot_mutating_requests"], 0)

    def test_diagnostic_schema_rejected_before_pilot_archive_write(self):
        with tempfile.TemporaryDirectory() as d:
            csv = Path(d) / "diagnostic.csv"
            csv.write_text("timestamp_ms\n0\n", encoding="utf-8")
            meta = Path(d) / "diagnostic.metadata.json"
            meta.write_text(json.dumps({"schema": "reachy-playback-diagnostic-capture-v1", "pilot_eligible": False}), encoding="utf-8")
            state = {"ready": True, "next_trial": protocol()["schedule"][0], "execution_fingerprint": "e",
                     "binding_fingerprint": "b", "microphone_fingerprint": "m", "attempt_number": 1}
            with patch.object(store, "collection_state", return_value=state), \
                 patch.object(store, "write_new", side_effect=AssertionError("Must not write")):
                with self.assertRaisesRegex(ValueError, "schema"):
                    store.import_attempt(csv, meta)

    def test_http_is_separate_loopback_get_only(self):
        class Bridge(FakeBridge):
            starts = 0
            def start(self): self.starts += 1
        class Handler(DiagnosticHandler):
            camera_bridge = Bridge()
            def log_message(self, *_): pass
        with patch("scripts.run_robot_camera_diagnostic.diagnostic_config", return_value={"diagnostic": {"purpose": "DIAGNOSTIC_NOT_PILOT"}}):
            with running_server(partial(Handler, directory=str(ROOT))) as server:
                self.assertEqual(request(server, "/api/reachy-camera/config")[0], 200)
                self.assertEqual(Handler.camera_bridge.starts, 1)
                self.assertEqual(request(server, "/tools/robot_camera_diagnostic.html")[0], 200)
                self.assertEqual(request(server, "/tools/robot_diagnostic_ui.mjs")[0], 200)
                self.assertEqual(request(server, "/api/reachy-camera/frame.jpg")[0], 200)
                for method in ("POST", "PUT", "PATCH", "DELETE", "HEAD"):
                    self.assertEqual(request(server, "/api/reachy-camera/frame.jpg", method)[0], 405)
                for path in ("/tools/robot_camera_pilot.html", "/tools/robot_camera_commissioning.html", "/data/private/robot_camera_pilot_v1/setup.json", "/api/motors/enable", "/models/avsync_v2/%2e%2e/private.json"):
                    self.assertEqual(request(server, path)[0], 404, path)

    def test_config_verification_failure_cannot_start_camera(self):
        class Handler(DiagnosticHandler):
            class camera_bridge:
                @staticmethod
                def start(): raise AssertionError("Must not start camera")
            def log_message(self, *_): pass
        with patch("scripts.run_robot_camera_diagnostic.diagnostic_config", side_effect=ValueError("Changed seal")):
            with running_server(Handler) as server:
                self.assertEqual(request(server, "/api/reachy-camera/config")[0], 409)


if __name__ == "__main__":
    unittest.main()
