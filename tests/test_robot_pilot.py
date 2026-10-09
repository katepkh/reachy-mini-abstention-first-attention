"""Synthetic fixtures only; no sensors, network or private operator files."""
import csv
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from reachy_stage3v.robot_pilot_protocol import protocol, fingerprint
from reachy_stage3v.robot_pilot_analysis import quality, timing_series, select_development, validate_once
from reachy_stage3v.robot_camera_commissioning import robot_camera_execution_payload
from reachy_stage3v import robot_pilot_store as store
from tests.test_robot_camera_http import running_server, request, FakeBridge
from scripts.run_robot_camera_pilot import PilotHandler

def synthetic_config():
    """Build metadata without ignored models or any private operator setup.

    These tests exercise numeric analysis and accounting, not model inference.
    Only public manifest path names are reused; every file contains dummy bytes.
    """
    manifest = json.loads(store.MANIFEST.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        for name in manifest["files_sha256"]:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"synthetic offline test fixture\n")
        return robot_camera_execution_payload(root)


CONFIG = synthetic_config()
MIC = {"label": "synthetic", "settings": {"sampleRate": 48000, "channelCount": 2,
       "echoCancellation": False, "noiseSuppression": False, "autoGainControl": False}}


def fixture(path, card):
    fields = CONFIG["required_columns"] + CONFIG["diagnostic_columns"]
    rng = np.random.default_rng(909 + card["schedule_index"])
    noise = rng.normal(0, 0.02, 300)
    rows = []
    for i in range(251):
        t = i * 40
        seq = int(i * 2 / 3) + 1
        receipt = (seq - 1) * 60 - 20
        condition = card["condition_id"]
        visible = condition != "speech_without_usable_face"
        speech = condition != "visible_silence"
        moving = condition.startswith("live_visible")
        lip = 0.06 + 0.03 * math.sin(receipt / 250) if moving else 0.06
        if condition == "silent_mouthing_unrelated_playback":
            lip += noise[seq]
        row = {f: "0" for f in fields}
        row.update(timestamp_ms=str(t), robot_frame_sequence=str(seq),
                   robot_transport_frames=str(int(i * 1.2) + 1), robot_analysis_frames=str(seq),
                   robot_frame_duplicate=str(i > 0 and seq == int((i - 1) * 2 / 3) + 1).lower(),
                   robot_frame_age_ms=str(t - receipt), face_observation_age_ms="10",
                   robot_camera_status="RECEIVING", landmark_error_code="", doa_error_code="",
                   landmark_backend="GPU", landmark_inference_ms="30", face_count="1" if visible else "0",
                   face_scale="0.1" if visible else "0", face_heading_robot_deg="0" if visible else "",
                   lip_aperture=str(lip if visible else 0),
                   audio_dbfs=str(-40 + 5 * math.sin((t - 1024 * 1000 / 48000) / 250) if speech else -70),
                   doa_valid="true", doa_speech_detected=str(speech).lower(), doa_age_ms="100",
                   doa_axis_deg="30" if condition == "spatial_conflict" else "90",
                   robot_frame_source_width_px="1280", robot_frame_source_height_px="720",
                   robot_frame_width_px="640", robot_frame_height_px="360")
        rows.append(row)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return rows


class RobotPilotTests(unittest.TestCase):
    def setUp(self):
        # Keep production build-identity comparisons intact, but bind this
        # numeric test suite to its generated fixture, never local model files.
        for module in ("reachy_stage3v.robot_pilot_analysis", "reachy_stage3v.robot_pilot_store"):
            fixture = patch(f"{module}.robot_camera_execution_payload", return_value=CONFIG)
            fixture.start()
            self.addCleanup(fixture.stop)

    def test_separate_balanced_schedule_and_no_authority(self):
        p = protocol()
        self.assertEqual(len(p["schedule"]), 21)
        self.assertEqual(len({x["trial_id"] for x in p["schedule"]}), 21)
        self.assertEqual(p["schedule"][0]["condition_id"], "spatial_conflict")
        for block in (1, 2, 3):
            self.assertEqual(len({c["condition_id"] for c in p["schedule"] if c["repetition"] == block}), 7)
        self.assertTrue(all(v == 0 for v in p["authority"].values()))
        self.assertEqual(p["fingerprint"], fingerprint({k: v for k, v in p.items() if k != "fingerprint"}))

    def test_all_seven_condition_quality_checks(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "trial.csv"
            for card in protocol()["schedule"][:7]:
                fixture(path, card)
                report, rows = quality(path, card)
                self.assertTrue(report["passed"], (card["condition_id"], report["failures"]))
                self.assertEqual(len(rows), 251)
                self.assertEqual(report["robot_observability"]["unique_analyzed_frame_fps"], 16.7)

    def test_duplicates_not_counted_as_new_lip_observations_and_gaps_not_filled(self):
        with tempfile.TemporaryDirectory() as d:
            card = next(c for c in protocol()["schedule"] if c["condition_id"] == "live_visible_continuous")
            rows = fixture(Path(d) / "t.csv", card)
            series, reason = timing_series(rows, 48000, 1)
            self.assertIsNone(reason)
            self.assertLess(len(series[0].values), 251)
            # Remove a real chunk of observations; interpolation must not hide it.
            damaged = [r for r in rows if not 2000 <= float(r["timestamp_ms"]) < 2300]
            self.assertIsNone(timing_series(damaged, 48000, 1)[0])

    def test_development_and_validation_are_separate(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "trial.csv"
            loaded = []
            for card in protocol()["schedule"]:
                fixture(path, card)
                report, rows = quality(path, card)
                loaded.append((card, report, rows, 48000))
            dev = select_development(loaded[:14])
            self.assertTrue(dev["validation_open"], dev["status"])
            self.assertEqual(dev["candidate_count"], 300)
            self.assertTrue(validate_once(loaded[14:], dev)["passed"])
            with self.assertRaises(ValueError):
                select_development(loaded)
            with self.assertRaises(ValueError):
                validate_once(loaded[:7], dev)

    def test_quality_keeps_robot_rate_gate(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "trial.csv"
            card = protocol()["schedule"][0]
            rows = fixture(path, card)
            for row in rows:
                row["robot_frame_sequence"] = str(int(float(row["timestamp_ms"]) / 100) + 1)
            with path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader(); writer.writerows(rows)
            report, _ = quality(path, card)
            self.assertIn("ROBOT_CAMERA_ANALYSIS_RATE_TOO_LOW", report["failures"])

    def test_append_only_import_seal_tamper_and_order(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            private = root / "private"
            manifest = root / "execution.json"
            fake_execution = {"fingerprint": "e" * 64}
            with patch.object(store, "PRIVATE", private), patch.object(store, "MANIFEST", manifest), patch.object(store, "PROTOCOL_MANIFEST", root / "protocol.json"), patch.object(store, "execution", return_value=fake_execution):
                store.write_new(manifest, fake_execution)
                store.write_new(root / "protocol.json", protocol())
                stimulus = root / "synthetic.dat"; stimulus.write_bytes(b"synthetic only")
                old = root / "old.json"
                store.write_new(old, {"room": {}, "marks": {}, "reachy": {},
                    "microphone": {"device_label": MIC["label"], "device_settings": MIC["settings"]},
                    "playback": {"recording_sha256": store.sha256_file(stimulus), "fixed_volume_percent": 80}})
                store.initialize(old, stimulus, volume=50, confirmed=True)
                self.assertEqual(store.read(old)["playback"]["fixed_volume_percent"], 80)
                self.assertEqual(store.read(private / "setup.json")["playback"]["fixed_volume_percent"], 50)
                state = store.collection_state(); card = state["next_trial"]
                csv_path = root / "trial.csv"; fixture(csv_path, card)
                meta = {"schema": "reachy-camera-pilot-capture-v1",
                    **{k: card[k] for k in ("trial_id", "condition_id", "schedule_index", "role", "split", "repetition")},
                    "attempt_number": 1, "sample_count": 251,
                    "pilot_protocol_fingerprint": protocol()["fingerprint"],
                    "pilot_execution_fingerprint": state["execution_fingerprint"],
                    "binding_fingerprint": state["binding_fingerprint"],
                    "microphone_fingerprint": state["microphone_fingerprint"], "microphone": MIC,
                    "microphone_uninterrupted": True, "audio_context_sample_rate_hz": 48000,
                    "csv_sha256": store.sha256_file(csv_path), "motion_commands": 0, "response_commands": 0,
                    "uploads": 0, "contains_pixels": False, "contains_waveform": False,
                    "contains_transcript": False, "contains_identity_embedding": False,
                    "instrument_fingerprint": CONFIG["fingerprint"], "execution_build": CONFIG["execution_build"],
                    "pipeline_diagnostics": CONFIG["pipeline_diagnostics"]}
                metadata = root / "meta.json"; store.write_new(metadata, meta)
                with patch.object(store, "robot_camera_execution_payload", return_value={
                    **CONFIG, "execution_build": {"fingerprint": "different-build"}
                }):
                    with self.assertRaisesRegex(ValueError, "sensor build/timing identity mismatch"):
                        store.import_attempt(csv_path, metadata)
                self.assertEqual(store.collection_state()["accepted_count"], 0)
                report = store.import_attempt(csv_path, metadata)
                self.assertTrue(report["passed"])
                self.assertEqual(store.collection_state()["accepted_count"], 1)
                with self.assertRaises(ValueError):
                    store.import_attempt(csv_path, metadata)
                with self.assertRaises(ValueError):
                    store.freeze_development()
                setup = private / "setup.json"
                setup.write_text(setup.read_text() + " ")
                self.assertFalse(store.safe_state()["ready"])
                self.assertEqual(len(list((private / "attempts").iterdir())), 1)

    def test_loopback_handler_no_mutations_or_private_static_files(self):
        class Bridge(FakeBridge):
            starts = 0
            def start(self): self.starts += 1
        class Handler(PilotHandler):
            camera_bridge = Bridge()
            def log_message(self, *_): pass
        with patch("scripts.run_robot_camera_pilot.pilot_config", return_value={"pilot_state": {"ready": False}}):
            with running_server(Handler) as server:
                self.assertEqual(request(server, "/api/reachy-camera/config")[0], 200)
                self.assertEqual(Handler.camera_bridge.starts, 0)
                for method in ("POST", "PUT", "DELETE", "PATCH", "HEAD"):
                    self.assertEqual(request(server, "/api/reachy-camera/config", method)[0], 405)
                for path in ("/data/private/robot_camera_pilot_v1/setup.json", "/tools/../AGENTS.md", "/tools/robot_camera_commissioning.html"):
                    self.assertEqual(request(server, path)[0], 404)

    def test_aborts_consume_budget_and_terminal_evaluations_are_not_repeated(self):
        with tempfile.TemporaryDirectory() as d:
            private = Path(d)
            (private / "attempts").mkdir()
            store.write_new(private / "setup.json", {"microphone": MIC})
            seal = {"fingerprint": "b", "microphone_fingerprint": "m"}
            with patch.object(store, "PRIVATE", private), patch.object(store, "verify_seal", return_value=({"fingerprint": "e"}, seal)):
                store.record_abort()
                self.assertEqual(store.collection_state()["attempt_number"], 2)
                store.record_abort()
                self.assertFalse(store.safe_state()["ready"])
                self.assertEqual(len(store.records()), 2)
                store.write_new(private / "development.json", {})
                store.write_new(private / "validation.json", {})
                with patch("reachy_stage3v.robot_pilot_analysis.select_development") as fit:
                    with self.assertRaisesRegex(ValueError, "already"):
                        store.freeze_development()
                    fit.assert_not_called()
                with patch("reachy_stage3v.robot_pilot_analysis.validate_once") as evaluate:
                    with self.assertRaisesRegex(ValueError, "already"):
                        store.finish_validation()
                    evaluate.assert_not_called()

    def test_collection_block_three_requires_matching_development_sources(self):
        with tempfile.TemporaryDirectory() as d:
            private = Path(d)
            (private / "attempts").mkdir()
            store.write_new(private / "setup.json", {"microphone": MIC})
            for card in protocol()["schedule"][:14]:
                core = {"trial_id": card["trial_id"], "quality": {"passed": True}, "source_hashes": {}}
                store.write_new(private / "attempts" / f'{card["schedule_index"]:02d}-01' / "assessment.json",
                                {**core, "fingerprint": fingerprint(core)})
            seal = {"fingerprint": "b", "microphone_fingerprint": "m"}
            with patch.object(store, "PRIVATE", private), patch.object(store, "verify_seal", return_value=({"fingerprint": "e"}, seal)):
                self.assertFalse(store.safe_state()["ready"])
                dev = {"validation_open": True, "execution_fingerprint": "e", "source_hashes": store.accepted_sources()}
                store.write_new(private / "development.json", {**dev, "fingerprint": fingerprint(dev)})
                self.assertEqual(store.collection_state()["next_trial"]["schedule_index"], 15)
                dev["source_hashes"] = []
                (private / "development.json").write_text(json.dumps({**dev, "fingerprint": fingerprint(dev)}))
                self.assertFalse(store.safe_state()["ready"])


if __name__ == "__main__":
    unittest.main()
