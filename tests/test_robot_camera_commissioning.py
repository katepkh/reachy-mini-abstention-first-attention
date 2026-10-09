from __future__ import annotations

import csv
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from reachy_stage3v.robot_camera_bridge import RobotCameraFrameBridge
from reachy_stage2a.stream_client import FramePreparationTiming
from reachy_stage3v.robot_camera_commissioning import (
    ROBOT_CAMERA_COMMISSIONING_SPEC_V1,
    ROBOT_CAMERA_REQUIRED_COLUMNS,
    assess_robot_camera_commissioning,
    robot_camera_static_path_allowed,
    robot_camera_execution_payload,
)


ROOT = Path(__file__).resolve().parents[1]


class RobotCameraCommissioningTests(unittest.TestCase):
    def test_contract_is_robot_camera_specific_command_free_and_numeric_only(self) -> None:
        payload = ROBOT_CAMERA_COMMISSIONING_SPEC_V1.payload()
        self.assertEqual(payload["status"], "COMMISSIONING_REQUIRED")
        self.assertFalse(payload["motion_authority"])
        self.assertFalse(payload["response_authority"])
        self.assertEqual(payload["robot_mutating_requests"], 0)
        self.assertFalse(payload["raw_media_saved"])
        self.assertFalse(payload["raw_media_uploaded"])
        self.assertEqual(len(payload["fingerprint"]), 64)
        self.assertIn("RTP packet-loss counters are not exposed", payload["timing_contract"]["frame_loss_boundary"])

    def test_static_allowlist_is_exact(self) -> None:
        self.assertTrue(robot_camera_static_path_allowed("/tools/robot_camera_commissioning.html"))
        self.assertTrue(robot_camera_static_path_allowed("/tools/robot_camera_pipeline.mjs"))
        self.assertTrue(robot_camera_static_path_allowed("/tools/robot_camera_landmarks_worker.js"))
        self.assertFalse(robot_camera_static_path_allowed("/tools/other_worker.js"))
        self.assertTrue(robot_camera_static_path_allowed("/models/avsync_v2/runtime/vision_bundle.mjs"))
        self.assertFalse(robot_camera_static_path_allowed("/tools/joint_shadow_recorder.html"))
        self.assertFalse(robot_camera_static_path_allowed("/data/private/setup.json"))
        self.assertFalse(robot_camera_static_path_allowed("/tools/../secret"))

    def test_browser_never_requests_laptop_video_or_mutating_robot_api(self) -> None:
        source = (ROOT / "tools" / "robot_camera_commissioning.html").read_text(encoding="utf-8")
        self.assertIn("/api/reachy-camera/frame.jpg", source)
        self.assertIn("/api/reachy-camera/doa", source)
        self.assertIn("camera_source: \"Reachy Mini receive-only local WebRTC stream\"", source)
        self.assertIn("getUserMedia({ video: false", source)
        self.assertNotIn("facingMode", source)
        self.assertNotIn("motion_authorized: true", source)
        self.assertNotIn("WebSocket", source)
        server = (ROOT / "scripts" / "run_robot_camera_commissioning.py").read_text(encoding="utf-8")
        self.assertIn("do_POST = _reject_mutation", server)
        self.assertIn("camera=()", server)

    def test_windows_launcher_is_receive_only_and_keeps_terminal_open(self) -> None:
        launcher = (ROOT / "start_robot_camera_commissioning.cmd").read_text(
            encoding="utf-8"
        )
        self.assertIn("run_robot_camera_commissioning.py", launcher)
        self.assertIn("--robot-ip 192.168.1.251", launcher)
        self.assertIn("pause", launcher.lower())
        self.assertNotIn("/api/move", launcher)
        self.assertNotIn("/api/motors", launcher)

    def test_loopback_server_cannot_spawn_one_thread_per_frame_request(self) -> None:
        server = (ROOT / "scripts" / "run_robot_camera_commissioning.py").read_text(encoding="utf-8")
        self.assertIn("server = BoundedHTTPServer((args.bind, args.port), handler)", server)
        self.assertNotIn("server = ThreadingHTTPServer", server)
        pool = (ROOT / "reachy_stage3v/bounded_http.py").read_text()
        self.assertIn("worker_count = 2", pool)
        self.assertIn("pending_capacity = 4", pool)
        self.assertIn("self._slots.acquire(blocking=False)", pool)

    def test_page_config_load_restarts_only_the_bounded_camera_bridge(self) -> None:
        server = (ROOT / "scripts" / "run_robot_camera_commissioning.py").read_text(encoding="utf-8")
        config_branch = server.split('if path == "/api/reachy-camera/config":', 1)[1].split(
            'if path == "/api/reachy-camera/status":', 1
        )[0]
        statements = [
            line.strip()
            for line in config_branch.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertEqual(
            statements,
            [
                "self.camera_bridge.start()",
                "self._json(robot_camera_execution_payload(ROOT))",
                "return",
            ],
        )

    def test_original_contract_fingerprint_is_unchanged(self) -> None:
        self.assertEqual(ROBOT_CAMERA_COMMISSIONING_SPEC_V1.payload()["fingerprint"],
                         "dbded406d1d271f69eb3652bc0b036cfe0deea734c4db2bf4f7a6979b2d3a95b")

    def test_execution_build_hashes_actual_sources_separately(self) -> None:
        import hashlib
        # CI does not ship the large ignored model/runtime assets. Build a
        # fixture tree without opening any sensor or downloading dependencies.
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            for name in [
                "tools/robot_camera_commissioning.html", "tools/robot_camera_pipeline.mjs",
                "tools/robot_camera_landmarks_worker.js", "scripts/run_robot_camera_commissioning.py",
                "reachy_stage3v/robot_camera_commissioning.py", "reachy_stage3v/robot_camera_bridge.py",
                "reachy_stage2a/stream_client.py", "models/avsync_v2/face_landmarker.task",
                "reachy_stage3v/bounded_http.py",
                "models/avsync_v2/runtime/vision_bundle.mjs", "models/avsync_v2/runtime/wasm/test.wasm",
            ]:
                file = fixture / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_bytes(name.encode())
            payload = robot_camera_execution_payload(fixture)
        self.assertEqual(payload["fingerprint"], ROBOT_CAMERA_COMMISSIONING_SPEC_V1.payload()["fingerprint"])
        build = payload["execution_build"]
        self.assertEqual(len(build["fingerprint"]), 64)
        name = "tools/robot_camera_landmarks_worker.js"
        self.assertEqual(build["files_sha256"][name], hashlib.sha256(name.encode()).hexdigest())
        self.assertEqual(payload["pipeline_diagnostics"]["http_workers"], 2)
        self.assertEqual(payload["pipeline_diagnostics"]["schema"], "reachy-camera-pipeline-timing-v2")
        self.assertEqual(build["schema"], "reachy-camera-bridge-timing-build-v3")
        self.assertEqual(payload["pipeline_diagnostics"]["conversion_jobs_in_flight"], 1)
        self.assertIn("robot_frame_conversion_ms", payload["diagnostic_columns"])
        self.assertIn("frame_pipeline_ms", payload["diagnostic_columns"])
        self.assertEqual(len(payload["diagnostic_columns"]), len(set(payload["diagnostic_columns"])))

    def test_worker_preserves_model_settings_and_does_not_request_media(self) -> None:
        source = (ROOT / "tools/robot_camera_landmarks_worker.js").read_text()
        self.assertIn('numFaces: 2', source)
        self.assertIn('minFaceDetectionConfidence: 0.5', source)
        self.assertIn('minFacePresenceConfidence: 0.5', source)
        self.assertIn('minTrackingConfidence: 0.5', source)
        self.assertNotIn('getUserMedia', source)
        page = (ROOT / "tools/robot_camera_commissioning.html").read_text(encoding="utf-8")
        self.assertNotIn('detectForVideo(', page)
        self.assertIn('remainingFrameDelay(started, performance.now(), period)', page)
        self.assertIn('latestFace = reply.face;\n            latestFrame = frame;', page)
        self.assertIn('processingError = error.message', page)

    def test_bridge_preserves_bounded_runtime_stop_reason(self) -> None:
        bridge = RobotCameraFrameBridge(maximum_width_px=320)
        bridge._set_status("AUTO_STOPPING", "MAX_RUNTIME_REACHED")
        bridge._set_status("STOPPED", "")
        snapshot = bridge.snapshot()
        self.assertEqual(snapshot.status, "STOPPED")
        self.assertEqual(snapshot.error_code, "MAX_RUNTIME_REACHED")

    def test_bridge_preserves_transport_failure_stop_reason(self) -> None:
        bridge = RobotCameraFrameBridge(maximum_width_px=320)
        bridge._set_status("ERROR", "VIDEO_FRAME_TIMEOUT")
        bridge._set_status("STOPPED", "")
        snapshot = bridge.snapshot()
        self.assertEqual(snapshot.status, "STOPPED")
        self.assertEqual(snapshot.error_code, "VIDEO_FRAME_TIMEOUT")

    def test_bridge_keeps_only_encoded_latest_frame(self) -> None:
        bridge = RobotCameraFrameBridge(maximum_width_px=320)
        pixels = np.zeros((480, 640, 3), dtype=np.uint8)
        bridge._set_status("RECEIVING", "")
        bridge._encode_frame(pixels)
        snapshot = bridge.snapshot()
        self.assertEqual(snapshot.analysis_frames, 1)
        self.assertEqual(snapshot.latest_sequence, 1)
        self.assertIsInstance(snapshot.latest_jpeg, bytes)
        self.assertTrue(snapshot.latest_jpeg.startswith(b"\xff\xd8"))
        self.assertEqual(snapshot.width_px, 320)
        self.assertEqual(snapshot.height_px, 240)
        self.assertFalse(any(isinstance(value, np.ndarray) for value in snapshot.__dict__.values()) if hasattr(snapshot, "__dict__") else False)

    def test_bridge_age_includes_dispatch_and_conversion_and_timing_matches_frame(self) -> None:
        bridge = RobotCameraFrameBridge(maximum_width_px=320)
        bridge._set_status("RECEIVING", "")
        pixels = np.zeros((480, 640, 3), dtype=np.uint8)
        first = FramePreparationTiming(10, 10.02, 10.10, None)
        with patch("reachy_stage3v.robot_camera_bridge.time.perf_counter", side_effect=[10.10, 10.105]):
            bridge._encode_frame(pixels, first)
        snapshot = bridge.snapshot()
        self.assertEqual(snapshot.latest_received_monotonic, 10)
        self.assertEqual(snapshot.preparation, first)
        self.assertAlmostEqual(snapshot.bridge_total_ms, 105)
        self.assertAlmostEqual(snapshot.encode_ms, 5)
        self.assertIsNone(snapshot.publish_interval_ms)
        self.assertEqual((snapshot.source_width_px, snapshot.source_height_px), (640, 480))
        self.assertEqual((snapshot.width_px, snapshot.height_px), (320, 240))
        second = FramePreparationTiming(10.2, 10.21, 10.22, 33)
        with patch("reachy_stage3v.robot_camera_bridge.time.perf_counter", side_effect=[10.22, 10.225]):
            bridge._encode_frame(pixels, second)
        snapshot = bridge.snapshot()
        self.assertEqual(snapshot.latest_sequence, 2)
        self.assertEqual(snapshot.preparation, second)
        self.assertAlmostEqual(snapshot.bridge_total_ms, 25)
        self.assertAlmostEqual(snapshot.publish_interval_ms, 120)

    def test_terminal_status_during_encoding_discards_late_jpeg(self) -> None:
        import cv2
        pixels = np.zeros((48, 64, 3), dtype=np.uint8)
        for status in ["ERROR", "STOPPING", "STOPPED", "AUTO_STOPPING"]:
            with self.subTest(status=status):
                bridge = RobotCameraFrameBridge()
                bridge._set_status("RECEIVING", "")
                bridge._encode_frame(pixels)
                original = cv2.imencode
                def finish_after_terminal(*args):
                    bridge._set_status(status, "TEST_STOP")
                    return original(*args)
                with patch("cv2.imencode", side_effect=finish_after_terminal):
                    bridge._encode_frame(pixels)
                snapshot = bridge.snapshot()
                self.assertIsNone(snapshot.latest_jpeg)
                self.assertIsNone(snapshot.latest_received_monotonic)
                self.assertIsNone(snapshot.preparation)
                self.assertEqual(snapshot.analysis_frames, 1)

    def test_explicit_stop_blocks_late_results_even_before_transport_status_changes(self) -> None:
        bridge = RobotCameraFrameBridge()
        bridge._set_status("RECEIVING", "")
        pixels = np.zeros((48, 64, 3), dtype=np.uint8)
        bridge._encode_frame(pixels)
        self.assertTrue(bridge.stop())
        bridge._encode_frame(pixels)
        self.assertIsNone(bridge.snapshot().latest_jpeg)
        self.assertEqual(bridge.snapshot().analysis_frames, 1)

    def _write_capture(self, path: Path, *, frozen_frames: bool = False) -> None:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=ROBOT_CAMERA_REQUIRED_COLUMNS)
            writer.writeheader()
            for index in range(201):
                phase = 2 * math.pi * index / 25.0
                sequence = 1 if frozen_frames else index + 1
                writer.writerow(
                    {
                        "timestamp_ms": index * 40.0,
                        "wall_time_iso": "2026-09-30T20:00:00+01:00",
                        "scheduler_lateness_ms": 0.5,
                        "sample_gap_ms": 0.0 if index == 0 else 40.0,
                        "audio_context_time_ms": index * 40.0,
                        "audio_dbfs": -35.0 + 3.0 * math.sin(phase),
                        "robot_camera_status": "RECEIVING",
                        "robot_frame_sequence": sequence,
                        "robot_transport_frames": index + 100,
                        "robot_analysis_frames": sequence,
                        "robot_frame_age_ms": 35.0,
                        "robot_frame_fetch_ms": 6.0,
                        "robot_frame_width_px": 640,
                        "robot_frame_height_px": 432,
                        "robot_frame_encode_ms": 4.0,
                        "robot_frame_duplicate": frozen_frames and index > 0,
                        "robot_frames_skipped_since_previous": 0,
                        "face_count": 1,
                        "face_center_x_norm": 0.4963,
                        "face_center_y_norm": 0.5,
                        "face_camera_right_deg": 0.0,
                        "face_heading_robot_deg": 0.0,
                        "face_scale": 0.10,
                        "lip_aperture": 0.04 + 0.01 * math.sin(phase),
                        "lip_motion": 0.004,
                        "landmark_inference_ms": 22.0,
                        "face_observation_age_ms": 40.0,
                        "doa_valid": True,
                        "doa_raw_angle_rad": math.pi / 2,
                        "doa_axis_deg": 90.0,
                        "doa_speech_detected": True,
                        "doa_age_ms": 90.0,
                        "doa_roundtrip_ms": 20.0,
                        "doa_robot_http_latency_ms": 12.0,
                        "doa_http_status": 200,
                        "doa_error_code": "",
                    }
                )

    def test_offline_checks_pass_only_as_commissioning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.csv"
            self._write_capture(path)
            result = assess_robot_camera_commissioning(path)
        self.assertTrue(result["checks_passed"])
        self.assertEqual(result["status"], "COMMISSIONING_CHECKS_PASSED")
        self.assertEqual(result["actuation_commands"], 0)
        self.assertIn("does not validate", result["claim_boundary"])
        diagnostics = result["diagnostics"]["pipeline_timing_distinct_frames"]
        self.assertEqual(diagnostics["landmark_inference_ms"]["observations"], 201)
        self.assertIsNone(diagnostics["frame_pipeline_ms"]["median_ms"])
        self.assertIsNone(diagnostics["robot_frame_conversion_ms"]["median_ms"])

    def test_frozen_frame_stream_fails_objectively(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "frozen.csv"
            self._write_capture(path, frozen_frames=True)
            result = assess_robot_camera_commissioning(path)
        self.assertFalse(result["checks_passed"])
        self.assertIn("ROBOT_CAMERA_ANALYSIS_RATE_TOO_LOW", result["failures"])
        self.assertIn("ROBOT_CAMERA_DUPLICATE_FRACTION_TOO_HIGH", result["failures"])

    def test_worker_error_fails_closed_even_when_numeric_gates_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "error.csv"
            self._write_capture(path)
            with path.open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            rows[100]["landmark_error_code"] = "LANDMARK_WORKER_TIMEOUT"
            with path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=[*ROBOT_CAMERA_REQUIRED_COLUMNS, "landmark_error_code"])
                writer.writeheader()
                writer.writerows(rows)
            result = assess_robot_camera_commissioning(path)
        self.assertEqual(result["failures"], ["LANDMARK_PROCESSING_ERROR"])
        self.assertEqual(result["diagnostics"]["processing_error_rows"], 1)


if __name__ == "__main__":
    unittest.main()
