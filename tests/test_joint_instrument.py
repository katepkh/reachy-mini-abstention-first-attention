from __future__ import annotations

import ast
import math
import unittest
from pathlib import Path

from reachy_doa.models import DoAReading
from reachy_stage3v.joint_instrument import (
    JOINT_CONDITIONS,
    JOINT_INSTRUMENT_SPEC_V1,
    JOINT_REQUIRED_COLUMNS,
    doa_bridge_payload,
    joint_static_path_allowed,
)


ROOT = Path(__file__).resolve().parents[1]


class JointInstrumentContractTests(unittest.TestCase):
    def reading(self, **changes: object) -> DoAReading:
        values: dict[str, object] = {
            "client_time_iso": "2026-09-26T10:00:00.000+01:00",
            "captured_monotonic": 10.0,
            "raw_angle_rad": math.pi / 2.0,
            "speech_detected": True,
            "http_latency_ms": 12.0,
            "http_status": 200,
            "valid": True,
            "error": "",
        }
        values.update(changes)
        return DoAReading(**values)  # type: ignore[arg-type]

    def test_protocol_is_command_free_and_privacy_minimal(self) -> None:
        payload = JOINT_INSTRUMENT_SPEC_V1.payload()
        self.assertFalse(payload["motion_authority"])
        self.assertFalse(payload["response_authority"])
        self.assertEqual(payload["robot_mutating_requests"], 0)
        self.assertFalse(payload["raw_media_saved"])
        self.assertFalse(payload["raw_media_uploaded"])
        self.assertEqual(len(str(payload["fingerprint"])), 64)

    def test_conditions_include_primary_and_synchrony_hard_negatives(self) -> None:
        by_id = {item["id"]: item for item in JOINT_CONDITIONS}
        self.assertEqual(by_id["silent_face_phone_playback"]["role"], "primary_hard_negative")
        self.assertEqual(
            by_id["silent_mouthing_unrelated_playback"]["role"],
            "synchrony_hard_negative",
        )

    def test_required_columns_expose_availability_and_timing_quality(self) -> None:
        required = set(JOINT_REQUIRED_COLUMNS)
        self.assertTrue(
            {
                "audio_dbfs",
                "lip_aperture",
                "face_heading_estimate_deg",
                "doa_axis_deg",
                "doa_valid",
                "doa_age_ms",
                "doa_clock_uncertainty_ms",
                "video_frame_age_ms",
                "sample_gap_ms",
            }.issubset(required)
        )

    def test_valid_bridge_payload_remains_numeric_and_read_only(self) -> None:
        payload = doa_bridge_payload(
            self.reading(),
            bridge_request_started_monotonic=20.0,
            bridge_response_ready_monotonic=20.02,
        )
        self.assertTrue(payload["valid"])
        self.assertAlmostEqual(float(payload["axis_deg"]), 90.0)
        self.assertTrue(payload["speech_detected"])
        self.assertFalse(payload["motion_authorized"])
        self.assertEqual(payload["robot_mutating_requests"], 0)

    def test_invalid_bridge_payload_does_not_retain_an_angle_or_speech(self) -> None:
        payload = doa_bridge_payload(
            self.reading(valid=False, raw_angle_rad=None, speech_detected=None, error="timeout"),
            bridge_request_started_monotonic=20.0,
            bridge_response_ready_monotonic=20.01,
        )
        self.assertFalse(payload["valid"])
        self.assertIsNone(payload["axis_deg"])
        self.assertIsNone(payload["speech_detected"])
        self.assertEqual(payload["error_code"], "timeout")

    def test_invalid_bridge_timing_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            doa_bridge_payload(
                self.reading(),
                bridge_request_started_monotonic=21.0,
                bridge_response_ready_monotonic=20.0,
            )

    def test_static_server_exposes_only_instrument_assets(self) -> None:
        self.assertTrue(joint_static_path_allowed("/tools/joint_shadow_recorder.html"))
        self.assertTrue(joint_static_path_allowed("/tools/joint_pilot_quality.mjs"))
        self.assertTrue(
            joint_static_path_allowed("/models/avsync_v2/runtime/vision_bundle.mjs")
        )
        self.assertFalse(joint_static_path_allowed("/data/private/bindings.json"))
        self.assertFalse(joint_static_path_allowed("/.git/config"))
        self.assertFalse(joint_static_path_allowed("/tools/../data/private/file"))

    def test_browser_recorder_uses_local_assets_and_numeric_downloads(self) -> None:
        source = (ROOT / "tools" / "joint_shadow_recorder.html").read_text(encoding="utf-8")
        self.assertIn("/api/joint-shadow/doa", source)
        self.assertIn("/api/joint-shadow/pilot", source)
        self.assertIn("joint-shadow-pilot-v2-[0-9]{2}", source)
        self.assertIn("reachy-joint-shadow-pilot-trial-v2", source)
        self.assertIn("reachy-joint-shadow-no-motion-pilot-v2", source)
        self.assertIn('import { assessPilotQuality } from "./joint_pilot_quality.mjs"', source)
        self.assertIn("assessPilotQuality(pilotTrial, rows, pilot.quality_gates)", source)
        self.assertIn('id="faceScaleMetric"', source)
        self.assertIn("minimum ${pilotScaleMinimum.toFixed(4)}", source)
        self.assertIn("REQUIRED_DOA_STREAK = 5", source)
        self.assertIn("SPEECH_REQUIRED_CONDITIONS", source)
        self.assertIn("pilot preflight is not stable", source)
        self.assertIn("Keep them stable throughout the capture", source)
        quality_source = (ROOT / "tools" / "joint_pilot_quality.mjs").read_text(
            encoding="utf-8"
        )
        self.assertIn("minimum_median_face_scale_when_required", quality_source)
        self.assertIn("SINGLE_FACE_FRACTION_TOO_LOW", quality_source)
        self.assertIn("pilot_protocol_fingerprint", source)
        self.assertIn("binding_manifest_sha256", source)
        self.assertIn("execution_fingerprint", source)
        self.assertIn("pilot trial ID and condition do not match", source)
        self.assertIn('pilot?.collection_gate?.status !== "READY_FOR_COLLECTION"', source)
        self.assertIn("reachy-joint-shadow-private-device-binding-v1", source)
        self.assertIn("Download private device binding", source)
        self.assertIn("navigator.mediaDevices.getUserMedia", source)
        self.assertIn("Numeric audio level", source)
        self.assertNotIn("fetch(\"http", source)
        self.assertNotIn("WebSocket", source)

    def test_contract_module_has_no_network_media_or_robot_sdk_import(self) -> None:
        path = ROOT / "reachy_stage3v" / "joint_instrument.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertTrue(
            imported.isdisjoint({"requests", "aiohttp", "cv2", "sounddevice", "reachy_mini"})
        )


if __name__ == "__main__":
    unittest.main()
