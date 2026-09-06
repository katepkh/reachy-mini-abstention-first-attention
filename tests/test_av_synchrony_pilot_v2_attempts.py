from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from reachy_avsync.pilot_v2_attempts import audit_pilot_v2_attempts
from reachy_avsync.pilot_v2_synthetic import write_synthetic_pilot_v2


class AudioMouthSynchronyPilotV2AttemptAuditTests(unittest.TestCase):
    def test_complete_synthetic_bundle_audits_without_robot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            input_dir = Path(directory)
            write_synthetic_pilot_v2(input_dir)
            payload = audit_pilot_v2_attempts(input_dir)
        self.assertEqual(payload["attempt_count"], 12)
        self.assertEqual(payload["canonical_count"], 12)
        self.assertEqual(payload["quality_failed_attempt_count"], 0)
        self.assertEqual(payload["robot_connections"], 0)
        self.assertEqual(payload["actuation_commands"], 0)


if __name__ == "__main__":
    unittest.main()
