import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reachy_stage3v.protocol import VALIDATION_STEPS
from reachy_stage3v.recorder import save_trial, trial_payloads


class Stage3VRecorderTests(unittest.TestCase):
    def test_browser_payload_has_numeric_schema_and_no_media(self):
        step = VALIDATION_STEPS[0]
        names = trial_payloads("trial", [{"sequence": 1, "speech_detected": True}], step)
        self.assertTrue(names[0].endswith(".csv"))
        self.assertTrue(names[2].endswith("_metadata.json"))
        rows = list(csv.DictReader(io.StringIO(names[1].decode("utf-8"))))
        self.assertEqual(rows[0]["sequence"], "1")
        metadata = json.loads(names[3])
        self.assertFalse(metadata["contains_pixels"])
        self.assertFalse(metadata["contains_audio"])
        self.assertFalse(metadata["contains_transcript"])
        self.assertEqual(metadata["actuation_commands"], 0)

    def test_local_save_stays_inside_stage3v_folder(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            with patch("reachy_stage3v.recorder.DATA_DIR", root):
                csv_path, metadata_path = save_trial("safe trial", [], VALIDATION_STEPS[0])
            self.assertEqual(csv_path.parent, root)
            self.assertEqual(metadata_path.parent, root)


if __name__ == "__main__":
    unittest.main()

