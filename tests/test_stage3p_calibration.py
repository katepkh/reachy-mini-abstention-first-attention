import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from reachy_stage3p.calibration import pitch_to_center_y_norm
from reachy_stage3p.calibration_pilot import (
    CALIBRATION_STEPS,
    evaluate_calibration_trial,
    protocol_payload,
    quality_issues,
)
from reachy_stage3v.analysis import summarise_rows


ROOT = Path(__file__).resolve().parents[1]


def sample(index: int, pitch: float) -> dict[str, object]:
    y = pitch_to_center_y_norm(pitch)
    return {
        "elapsed_ms": index * 200.0,
        "http_status": 200,
        "face_count": 1,
        "face_age_ms": 20.0,
        "face_center_y_norm": y + 0.02,
        "face_eye_midpoint_y_norm": y,
        "speech_detected": False,
        "acoustic_state": "SEARCHING",
    }


class Stage3PCalibrationPilotTests(unittest.TestCase):
    def test_protocol_is_counterbalanced_passive_and_audited(self):
        self.assertEqual(len(CALIBRATION_STEPS), 9)
        self.assertEqual(
            [step.target_pitch_deg for step in CALIBRATION_STEPS],
            [0.0, -10.0, 10.0, 10.0, 0.0, -10.0, -10.0, 10.0, 0.0],
        )
        payload = protocol_payload()
        self.assertEqual(payload["required_data_mode"], "development_audit")
        self.assertEqual(payload["actuation_commands"], 0)
        self.assertEqual(payload["cloud_requests"], 0)

    def test_quality_requires_fresh_eye_landmarks(self):
        rows = [sample(index, 0.0) for index in range(40)]
        self.assertEqual(quality_issues(CALIBRATION_STEPS[0], summarise_rows(rows)), ())
        for row in rows[:8]:
            row["face_eye_midpoint_y_norm"] = None
        self.assertTrue(any(
            "eye landmarks" in issue
            for issue in quality_issues(CALIBRATION_STEPS[0], summarise_rows(rows))
        ))

    def test_trial_reports_eye_and_legacy_box_pitch_separately(self):
        rows = [sample(index, 10.0) for index in range(40)]
        result = evaluate_calibration_trial(CALIBRATION_STEPS[2], rows)
        self.assertAlmostEqual(result["eye_midpoint_pitch_median_deg"], 10.0)
        self.assertNotEqual(
            result["eye_midpoint_pitch_median_deg"], result["face_box_pitch_median_deg"]
        )
        self.assertEqual(result["would_adjust_rows"], 0)

    def test_profile_paths_are_isolated(self):
        environment = dict(os.environ)
        environment["REACHY_STAGE3V_PROFILE"] = "stage3p_calibration"
        code = (
            "import json; from reachy_stage3v.config import DATA_DIR,MANIFEST_PATH,RESULT_JSON_PATH,AUDIT_DIR; "
            "print(json.dumps({'data':DATA_DIR.name,'manifest':MANIFEST_PATH.name,"
            "'result':RESULT_JSON_PATH.name,'audit':AUDIT_DIR.name}))"
        )
        paths = json.loads(subprocess.check_output(
            [sys.executable, "-c", code], cwd=ROOT, env=environment, text=True
        ))
        self.assertEqual(paths["data"], "stage3p_calibration")
        self.assertEqual(paths["manifest"], "stage3p_calibration_pilot_v1.json")
        self.assertEqual(paths["result"], "stage3p_calibration_pilot_v1.json")
        self.assertEqual(paths["audit"], "stage3p_calibration_audit")


if __name__ == "__main__":
    unittest.main()
