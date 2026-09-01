import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reachy_stage3v import compliance
from reachy_stage3v.confirmation_analysis import confirmation_quality_issues
from reachy_stage3v.confirmation_protocol import (
    CONFIRMATION_STEPS,
    confirmation_protocol_payload,
)
from reachy_stage3v.revised_policy import FROZEN_REVISED_POLICY


class Stage3VConfirmationTests(unittest.TestCase):
    def test_confirmation_is_new_data_only_and_fingerprints_frozen_policy(self):
        payload = confirmation_protocol_payload()
        self.assertTrue(payload["development_dataset_reuse_forbidden"])
        self.assertEqual(payload["policy"]["fingerprint"], FROZEN_REVISED_POLICY.payload()["fingerprint"])
        self.assertEqual(
            payload["fingerprint"],
            "247e7c4ef3ad72cf8155d8dc932ca58be37a92024cbb32c74a732fb9956aae92",
        )
        self.assertEqual(len(CONFIRMATION_STEPS), 18)
        self.assertEqual(payload["actuation_commands"], 0)
        self.assertEqual(payload["cloud_requests"], 0)

    def test_confirmation_requires_eighty_percent_of_nominal_samples(self):
        step = CONFIRMATION_STEPS[0]
        base = {
            "valid_pct": 100.0,
            "speech_positive": 5,
            "single_face": 47,
            "fresh_single_face_pct": 100.0,
        }
        self.assertTrue(any("48" in issue for issue in confirmation_quality_issues(step, {**base, "samples": 47})))
        self.assertEqual(confirmation_quality_issues(step, {**base, "samples": 48, "single_face": 48}), ())

    def test_audit_compliance_requires_a_reviewed_clip(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            csv_path = root / "trial.csv"
            csv_path.write_text("sample\n", encoding="utf-8")
            with patch.object(compliance, "DATA_DIR", root):
                path = compliance.save_compliance_review(
                    csv_path,
                    protocol_fingerprint="protocol",
                    step_index=1,
                    data_mode="development_audit",
                    position_followed=True,
                    speech_or_playback_followed=True,
                    audit_clip_id="clip-1",
                    audit_verdict="UNREVIEWED",
                )
                self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["verdict"], "NONCOMPLIANT")
                path = compliance.save_compliance_review(
                    csv_path,
                    protocol_fingerprint="protocol",
                    step_index=1,
                    data_mode="development_audit",
                    position_followed=True,
                    speech_or_playback_followed=True,
                    audit_clip_id="clip-1",
                    audit_verdict="COMPLIANT",
                )
                self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["verdict"], "COMPLIANT")


if __name__ == "__main__":
    unittest.main()
