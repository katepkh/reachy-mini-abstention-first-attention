import csv
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

import scripts.prepare_av_synchrony_confirmation_workspace as workspace


class ConfirmationWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        private_root = Path(self.temporary.name)
        self.originals = {
            "PRIVATE_ROOT": workspace.PRIVATE_ROOT,
            "RECORDS": workspace.RECORDS,
            "CAPTURES": workspace.CAPTURES,
            "LEDGER": workspace.LEDGER,
            "SEALED_MANIFEST": workspace.SEALED_MANIFEST,
            "GUIDE": workspace.GUIDE,
        }
        workspace.PRIVATE_ROOT = private_root
        workspace.RECORDS = private_root / "bindings"
        workspace.CAPTURES = private_root / "captures"
        workspace.LEDGER = private_root / "attempt_ledger.csv"
        workspace.SEALED_MANIFEST = private_root / "binding_manifest.json"
        workspace.GUIDE = private_root / "README.md"

    def tearDown(self) -> None:
        for name, value in self.originals.items():
            setattr(workspace, name, value)
        self.temporary.cleanup()

    def test_initialization_creates_exact_schedule_and_no_capture(self) -> None:
        workspace.initialize("Test Browser 1")
        with workspace.LEDGER.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 54)
        self.assertTrue(all(row["capture_status"] == "NOT_STARTED" for row in rows))
        self.assertEqual(list(workspace.CAPTURES.iterdir()), [])
        self.assertTrue(workspace.GUIDE.is_file())
        structural, missing = workspace.status()
        self.assertEqual(structural, [])
        self.assertTrue(missing)

    def test_initialization_never_overwrites_a_binding(self) -> None:
        workspace.initialize("Test Browser 1")
        room = workspace.RECORDS / "room_a.json"
        room.write_text("preserved\n", encoding="utf-8")
        workspace.initialize("Test Browser 2")
        self.assertEqual(room.read_text(encoding="utf-8"), "preserved\n")

    def test_seal_refuses_incomplete_records(self) -> None:
        workspace.initialize("Test Browser 1")
        with redirect_stderr(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, "incomplete"):
                workspace.seal()
        self.assertFalse(workspace.SEALED_MANIFEST.exists())

    def test_seal_marks_complete_records_and_binds_execution(self) -> None:
        workspace.initialize("Test Browser 1")
        device = json.loads((workspace.RECORDS / "device.json").read_text(encoding="utf-8"))
        device.update(
            {
                "camera_make_model": "Test Camera",
                "microphone_make_model": "Test Microphone",
                "audio_input_selected": "Test Microphone",
                "media_device_settings": "fixed test settings",
                "headset_rule_acknowledged": True,
            }
        )
        (workspace.RECORDS / "device.json").write_text(
            json.dumps(device), encoding="utf-8"
        )
        for room_id in ("room_a", "room_b", "room_c"):
            path = workspace.RECORDS / f"{room_id}.json"
            room = json.loads(path.read_text(encoding="utf-8"))
            room.update(
                {
                    "confirmation_not_v2_pilot_room": True,
                    "approximate_dimensions_m": {"length": 1, "width": 1, "height": 1},
                    "dominant_surface_and_furnishing_description": "test room",
                    "background_audio_dbfs_10s": -50,
                    "camera_mark": "fixed",
                    "microphone_mark": "fixed",
                    "visible_person_marks": {"-20": "left", "0": "centre", "20": "right"},
                    "playback_marks": {"-20": "left", "0": "centre", "20": "right"},
                }
            )
            path.write_text(json.dumps(room), encoding="utf-8")
        for voice_id in ("voice_a", "voice_b"):
            path = workspace.RECORDS / f"{voice_id}.json"
            voice = json.loads(path.read_text(encoding="utf-8"))
            voice.update(
                {
                    "consent_basis": "test consent",
                    "recording_sha256": "0" * 64,
                    "clip_duration_s": 10,
                    "spoken_language": "English",
                    "playback_device_make_model": "Test speaker",
                    "fixed_volume_setting": "50%",
                }
            )
            path.write_text(json.dumps(voice), encoding="utf-8")
        workspace.seal()
        sealed = json.loads(workspace.SEALED_MANIFEST.read_text(encoding="utf-8"))
        self.assertIn("execution_fingerprint", sealed)
        completed = json.loads(
            (workspace.RECORDS / "device.json").read_text(encoding="utf-8")
        )
        self.assertEqual(completed["status"], "COMPLETE_BEFORE_FIRST_PREVIEW_OR_CAPTURE")


if __name__ == "__main__":
    unittest.main()
