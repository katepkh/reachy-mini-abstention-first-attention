import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reachy_stage2a.models import STAGE2A_CSV_COLUMNS
from reachy_stage2a.recorder import numeric_session_downloads, save_numeric_session


class RecorderTests(unittest.TestCase):
    def test_browser_download_payloads_are_derived_metadata_only(self):
        row = {column: None for column in STAGE2A_CSV_COLUMNS}
        row.update({"sequence": 7, "face_count": 1, "face_confidence": 0.91})
        csv_name, csv_bytes, metadata_name, metadata_bytes = numeric_session_downloads(
            "../../unsafe session",
            [row],
            condition_code="single-consenting-operator",
        )
        self.assertNotIn("..", csv_name)
        self.assertTrue(csv_name.endswith(".csv"))
        self.assertTrue(metadata_name.endswith("_metadata.json"))
        decoded_rows = list(csv.DictReader(csv_bytes.decode("utf-8").splitlines()))
        self.assertEqual(decoded_rows[0]["sequence"], "7")
        metadata = json.loads(metadata_bytes.decode("utf-8"))
        self.assertEqual(metadata["row_count"], 1)
        self.assertFalse(metadata["contains_pixels"])
        self.assertFalse(metadata["contains_audio"])
        self.assertFalse(metadata["contains_transcript"])
        self.assertFalse(metadata["contains_identity_embedding"])

    def test_numeric_metadata_stays_in_constrained_folder(self):
        with tempfile.TemporaryDirectory() as temporary:
            data_dir = Path(temporary).resolve()
            row = {column: None for column in STAGE2A_CSV_COLUMNS}
            row.update({"sequence": 1, "face_count": 1, "face_confidence": 0.8})
            with patch("reachy_stage2a.recorder.STAGE2A_DATA_DIR", data_dir):
                csv_path, metadata_path = save_numeric_session(
                    "../../unsafe session",
                    [row],
                    condition_code="single-consenting-operator",
                )
            self.assertEqual(csv_path.parent, data_dir)
            self.assertEqual(metadata_path.parent, data_dir)
            with csv_path.open(encoding="utf-8", newline="") as handle:
                saved = list(csv.DictReader(handle))
            self.assertEqual(list(saved[0]), STAGE2A_CSV_COLUMNS)
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertFalse(metadata["contains_pixels"])
            self.assertFalse(metadata["contains_audio"])
            self.assertFalse(metadata["contains_transcript"])
            self.assertFalse(metadata["contains_identity_embedding"])


if __name__ == "__main__":
    unittest.main()
