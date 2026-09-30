from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reachy_stage3v import joint_pilot_private as private


class JointPilotPrivateWorkspaceTests(unittest.TestCase):
    def workspace_patch(self, root: Path):
        return patch.multiple(
            private,
            PRIVATE_ROOT=root,
            SETUP=root / "setup.json",
            CAPTURES=root / "captures",
            LEDGER=root / "attempt_ledger.csv",
            SEALED_MANIFEST=root / "binding_manifest.json",
            GUIDE=root / "README.md",
        )

    def complete_setup(self, root: Path) -> None:
        path = root / "setup.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["room"] = {
            "opaque_room_id": "room_a",
            "approximate_dimensions_m": {"length": 5.0, "width": 4.0, "height": 2.4},
            "surface_and_furnishing_description": "mixed hard and soft surfaces",
            "background_audio_dbfs_10s": -56.64,
        }
        payload["marks"] = {
            "laptop": "desk mark",
            "reachy": "aligned robot mark",
            "operator": "one metre centre mark",
            "phone_colocated_with_face_within_10_deg": "colocated mark",
            "phone_spatial_conflict_at_least_45_deg": "right conflict mark",
        }
        payload["camera"] = {
            "horizontal_fov_deg_estimate": 60.0,
            "device_label": "test camera",
            "device_settings": {"width": 320, "height": 240},
        }
        payload["microphone"] = {
            "device_label": "test microphone",
            "device_settings": {"sampleRate": 48000},
        }
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def test_initialize_is_non_overwriting_and_reports_missing_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.workspace_patch(root):
                private.initialize()
                original = (root / "setup.json").read_bytes()
                private.initialize()
                unchanged = (root / "setup.json").read_bytes()
                structural, missing = private.preseal_status()
        self.assertEqual(original, unchanged)
        self.assertFalse(structural)
        self.assertTrue(any("recording_sha256" in item for item in missing))

    def test_stimulus_is_hashed_but_not_copied_and_complete_setup_seals(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "private"
            stimulus = Path(directory) / "voice.bin"
            stimulus.write_bytes(b"consented synthetic voice bytes")
            with self.workspace_patch(root):
                private.initialize()
                self.complete_setup(root)
                private.bind_stimulus(
                    stimulus,
                    phone_make_model="test phone",
                    volume_percent=40,
                )
                structural, missing = private.preseal_status()
                self.assertFalse(structural)
                self.assertFalse(missing)
                private.seal()
                gate = private.sealed_gate_status()
                setup = json.loads((root / "setup.json").read_text(encoding="utf-8"))
                manifest = json.loads((root / "binding_manifest.json").read_text(encoding="utf-8"))
            self.assertTrue(gate["ready"])
            self.assertEqual(gate["status"], "READY_FOR_COLLECTION")
            self.assertEqual(setup["playback"]["recording_bytes"], stimulus.stat().st_size)
            self.assertFalse((root / stimulus.name).exists())
            self.assertFalse(manifest["contains_identity"])
            self.assertFalse(manifest["contains_approval_record"])
            self.assertFalse(manifest["motion_authority"])

    def test_setup_change_after_seal_closes_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "private"
            stimulus = Path(directory) / "voice.bin"
            stimulus.write_bytes(b"voice")
            with self.workspace_patch(root):
                private.initialize()
                self.complete_setup(root)
                private.bind_stimulus(stimulus, phone_make_model="phone", volume_percent=40)
                private.seal()
                setup = json.loads((root / "setup.json").read_text(encoding="utf-8"))
                setup["playback"]["fixed_volume_percent"] = 41
                (root / "setup.json").write_text(json.dumps(setup), encoding="utf-8")
                gate = private.sealed_gate_status()
        self.assertFalse(gate["ready"])
        self.assertIn("PRIVATE_SETUP_CHANGED_AFTER_SEAL", gate["reasons"])

    def test_binding_manifest_sidecar_tamper_closes_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "private"
            stimulus = Path(directory) / "voice.bin"
            stimulus.write_bytes(b"voice")
            with self.workspace_patch(root):
                private.initialize()
                self.complete_setup(root)
                private.bind_stimulus(stimulus, phone_make_model="phone", volume_percent=40)
                private.seal()
                sidecar = root / "binding_manifest.json.sha256"
                sidecar.write_text(f"{'0' * 64}  binding_manifest.json\n", encoding="ascii")
                gate = private.sealed_gate_status()
        self.assertFalse(gate["ready"])
        self.assertIn("PRIVATE_BINDING_MANIFEST_HASH_INVALID", gate["reasons"])

    def test_device_binding_and_marks_import_without_media(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "private"
            binding = Path(directory) / "device.json"
            binding.write_text(
                json.dumps(
                    {
                        "schema": "reachy-joint-shadow-private-device-binding-v1",
                        "camera_horizontal_fov_deg_estimate": 60.0,
                        "devices": [
                            {"kind": "video", "label": "camera", "settings": {"width": 320}},
                            {"kind": "audio", "label": "microphone", "settings": {"sampleRate": 48000}},
                        ],
                        "contains_pixels": False,
                        "contains_waveform": False,
                    }
                ),
                encoding="utf-8",
            )
            with self.workspace_patch(root):
                private.initialize()
                private.import_device_binding(binding)
                private.bind_marks(
                    reachy="robot mark",
                    operator="operator mark",
                    phone_colocated="colocated mark",
                    phone_conflict="conflict mark",
                )
                setup = json.loads((root / "setup.json").read_text(encoding="utf-8"))
        self.assertEqual(setup["camera"]["device_label"], "camera")
        self.assertEqual(setup["microphone"]["device_label"], "microphone")
        self.assertEqual(setup["marks"]["reachy"], "robot mark")

    def test_initialize_v2_from_v1_setup_copies_bindings_but_not_seal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "private-v2"
            source = base / "setup-v1.json"
            source.write_text(
                json.dumps(
                    {
                        **private._blank_setup(),
                        "schema": "reachy-joint-shadow-pilot-private-setup-v1",
                        "status": "SEALED_BEFORE_TRIAL_1",
                        "opaque_setup_id": "room_a_joint_v1",
                    }
                ),
                encoding="utf-8",
            )
            with self.workspace_patch(root):
                private.initialize(setup_source=source)
                setup = json.loads((root / "setup.json").read_text(encoding="utf-8"))
        self.assertEqual(setup["schema"], "reachy-joint-shadow-pilot-private-setup-v2")
        self.assertEqual(setup["status"], "INCOMPLETE_DO_NOT_COLLECT")
        self.assertEqual(setup["opaque_setup_id"], "room_a_joint_v2")
        self.assertIn("No v1 capture", setup["revision_note"])


if __name__ == "__main__":
    unittest.main()
