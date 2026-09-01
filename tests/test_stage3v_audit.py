import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from reachy_stage3v import audit
from reachy_stage3v.audit import decrypt_media_bytes, encrypt_media_file


class Stage3VAuditTests(unittest.TestCase):
    def test_atomic_audit_index_retries_a_transient_windows_share_violation(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "audit_index.json"
            original_replace = Path.replace
            attempts = 0

            def transient_replace(path, destination):
                nonlocal attempts
                attempts += 1
                if attempts < 3:
                    raise PermissionError(5, "temporarily locked")
                return original_replace(path, destination)

            with (
                patch.object(Path, "replace", transient_replace),
                patch("reachy_stage3v.audit.time.sleep"),
            ):
                audit._atomic_json(target, {"schema": "test"})

            self.assertEqual(attempts, 3)
            self.assertEqual(target.read_text(encoding="utf-8").strip(), '{\n  "schema": "test"\n}')

    def test_encrypted_clip_round_trip_and_wrong_passphrase_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "capture.mp4"
            encrypted = root / "capture.r3audit"
            source.write_bytes(b"synthetic-local-media" * 100)
            encrypt_media_file(
                source,
                encrypted,
                passphrase="correct horse battery staple",
                public_metadata={"clip_id": "clip-1", "trial_id": "trial-1"},
            )
            header, recovered = decrypt_media_bytes(
                encrypted,
                passphrase="correct horse battery staple",
            )
            self.assertEqual(header["cipher"], "AES-256-GCM")
            self.assertEqual(recovered, source.read_bytes())
            with self.assertRaises(Exception):
                decrypt_media_bytes(encrypted, passphrase="wrong password value")

    def test_short_passphrase_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "capture.mp4"
            source.write_bytes(b"media")
            with self.assertRaises(ValueError):
                encrypt_media_file(
                    source,
                    root / "capture.r3audit",
                    passphrase="short",
                    public_metadata={},
                )

    def test_external_clip_is_encrypted_indexed_reviewed_and_deleted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            with (
                patch.object(audit, "AUDIT_DIR", root),
                patch.object(audit, "INDEX_PATH", root / "audit_index.json"),
                patch.object(audit, "TEMP_DIR", root / ".plaintext_capture"),
            ):
                clip = audit.store_external_audit_bytes(
                    "trial-1",
                    b"synthetic-audit-media" * 100,
                    passphrase="correct horse battery staple",
                    retention_hours=1,
                )
                encrypted_path = root / clip.encrypted_file
                self.assertTrue(encrypted_path.is_file())
                self.assertNotIn(b"synthetic-audit-media", encrypted_path.read_bytes())
                self.assertEqual(len(audit.list_audit_clips()), 1)
                reviewed = audit.record_audit_review(clip.clip_id, "COMPLIANT")
                self.assertEqual(reviewed["review_verdict"], "COMPLIANT")
                self.assertTrue(audit.delete_audit_clip(clip.clip_id, reason="TEST_VERIFIED"))
                self.assertFalse(encrypted_path.exists())
                index = audit._load_index()
                self.assertEqual(index["clips"], [])
                self.assertTrue(index["deletion_log"][-1]["deleted"])

    def test_retention_expiry_purges_encrypted_clip(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            with (
                patch.object(audit, "AUDIT_DIR", root),
                patch.object(audit, "INDEX_PATH", root / "audit_index.json"),
            ):
                clip = audit.store_external_audit_bytes(
                    "trial-expiry",
                    b"synthetic-audit-media",
                    passphrase="correct horse battery staple",
                    retention_hours=1,
                )
                future = datetime.now(timezone.utc).astimezone() + timedelta(hours=2)
                self.assertEqual(audit.purge_expired_audit_clips(future), [clip.clip_id])
                self.assertFalse((root / clip.encrypted_file).exists())


if __name__ == "__main__":
    unittest.main()
