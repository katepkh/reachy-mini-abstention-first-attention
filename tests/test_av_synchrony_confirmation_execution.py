import unittest
from pathlib import Path

from reachy_avsync.confirmation_execution import confirmation_execution_payload


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class AVSynchronyConfirmationExecutionTests(unittest.TestCase):
    def test_execution_contract_binds_collector_analysis_and_baselines(self) -> None:
        payload = confirmation_execution_payload(PROJECT_ROOT)
        self.assertEqual(len(payload["randomized_schedule"]), 54)
        self.assertEqual(payload["sample_period_ms"], 40)
        self.assertEqual(payload["candidate_scoring"]["retuning"], "PROHIBITED")
        self.assertEqual(
            set(payload["predeclared_baselines"]),
            {
                "acoustic_only_activity",
                "visual_only_mouth_motion",
                "non_abstaining",
                "spatial_design_proxy",
            },
        )
        self.assertIn("not identifiable", payload["known_identifiability_boundary"])
        self.assertEqual(payload["robot_scope"]["actuation_commands"], 0)

    def test_recorder_has_binding_gate_and_no_network_upload(self) -> None:
        source = (PROJECT_ROOT / "tools" / "avsync_confirmation_recorder.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("binding_manifest.json", source)
        self.assertIn("SEALED_BEFORE_FIRST_PREVIEW_OR_CAPTURE", source)
        self.assertIn("schedule.length !== 54", source)
        self.assertNotIn("XMLHttpRequest", source)
        self.assertNotIn("WebSocket", source)
        self.assertNotIn("fetch(\"http", source)


if __name__ == "__main__":
    unittest.main()
