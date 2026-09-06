import csv
import io
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


if __name__ == "__main__":
    unittest.main()
