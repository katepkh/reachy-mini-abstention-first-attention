import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reachy_doa.decisions import completed_prefix, disposition_for, reopen_accepted_step


LEDGER = {
    "version": 1,
    "plans": {
        "direction-calibration": {
            "1": {"accepted_file": "accepted.csv", "superseded_files": ["old.csv"]},
            "2": {"accepted_file": "second.csv", "superseded_files": []},
        }
    },
}


class DecisionTests(unittest.TestCase):
    @patch("reachy_doa.decisions.load_decisions", return_value=LEDGER)
    def test_dispositions(self, _mock) -> None:
        self.assertEqual(disposition_for("accepted.csv"), "accepted")
        self.assertEqual(disposition_for("old.csv"), "superseded")
        self.assertEqual(disposition_for("other.csv"), "standalone")

    @patch("reachy_doa.decisions.load_decisions", return_value=LEDGER)
    def test_completed_prefix(self, _mock) -> None:
        self.assertEqual(completed_prefix("direction-calibration"), 2)

    def test_reopen_preserves_file_as_superseded(self) -> None:
        with tempfile.TemporaryDirectory():
            with (
                patch("reachy_doa.decisions.load_decisions", return_value=LEDGER),
                patch("reachy_doa.decisions._save") as save,
            ):
                reopen_accepted_step("direction-calibration", 2)
            payload = save.call_args.args[0]
            decision = payload["plans"]["direction-calibration"]["2"]
            self.assertIsNone(decision["accepted_file"])
            self.assertIn("second.csv", decision["superseded_files"])


if __name__ == "__main__":
    unittest.main()
