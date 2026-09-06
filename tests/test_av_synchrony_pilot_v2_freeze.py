from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from reachy_avsync.pilot_v2_freeze import build_pilot_v2_candidate_freeze
from reachy_avsync.pilot_v2_protocol import pilot_v2_protocol_payload
from reachy_avsync.pilot_v2_synthetic import write_synthetic_pilot_v2


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class AudioMouthSynchronyPilotV2FreezeTests(unittest.TestCase):
    def test_passing_inputs_freeze_exact_candidate_and_assets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            input_dir = Path(directory)
            write_synthetic_pilot_v2(input_dir)
            payload = build_pilot_v2_candidate_freeze(input_dir, PROJECT_ROOT)
        self.assertEqual(payload["status"], "FROZEN_PILOT_CANDIDATE_NOT_CONFIRMATION")
        self.assertEqual(payload["protocol_fingerprint"], pilot_v2_protocol_payload()["fingerprint"])
        self.assertEqual(len(payload["sources"]), 12)
        self.assertTrue(payload["internal_validation_result"]["passed"])
        self.assertEqual(payload["scope"]["robot_connections"], 0)
        self.assertEqual(payload["scope"]["actuation_commands"], 0)
        self.assertEqual(len(payload["fingerprint"]), 64)


if __name__ == "__main__":
    unittest.main()
