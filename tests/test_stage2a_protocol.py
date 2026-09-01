import unittest

from reachy_stage2a.protocol import (
    MATRIX_STEPS,
    matrix_quality_issues,
    summarise_matrix_rows,
)


class Stage2AProtocolTests(unittest.TestCase):
    def test_matrix_has_five_conditions_and_three_repetitions(self):
        self.assertEqual(len(MATRIX_STEPS), 15)
        conditions = {}
        for step in MATRIX_STEPS:
            conditions.setdefault(step.condition_id, []).append(step.repetition)
            self.assertEqual(step.countdown_s, 5)
            self.assertEqual(step.duration_s, 20)
        self.assertEqual(len(conditions), 5)
        self.assertTrue(all(repetitions == [1, 2, 3] for repetitions in conditions.values()))

    def test_run_ids_are_unique_and_filename_safe(self):
        run_ids = [step.run_id("2026-08-25") for step in MATRIX_STEPS]
        self.assertEqual(len(run_ids), len(set(run_ids)))
        self.assertTrue(all(" " not in run_id and "/" not in run_id for run_id in run_ids))

    def test_summary_is_transparent(self):
        rows = [
            {
                "http_status": 200,
                "http_latency_ms": 10.0,
                "speech_detected": True,
                "face_count": 1,
                "fusion_state": "CONFIRMED",
            },
            {
                "http_status": None,
                "http_latency_ms": 1000.0,
                "speech_detected": False,
                "face_count": 2,
                "fusion_state": "WITHHELD",
            },
        ]
        summary = summarise_matrix_rows(rows)
        self.assertEqual(summary["samples"], 2)
        self.assertEqual(summary["valid"], 1)
        self.assertEqual(summary["valid_pct"], 50.0)
        self.assertEqual(summary["speech_positive"], 1)
        self.assertEqual(summary["no_face"], 0)
        self.assertEqual(summary["single_face"], 1)
        self.assertEqual(summary["multiple_faces"], 1)
        self.assertEqual(summary["confirmed"], 1)
        self.assertEqual(summary["median_latency_ms"], 10.0)

    def test_quality_gate_checks_protocol_observability_not_outcome(self):
        matching = next(
            step for step in MATRIX_STEPS
            if step.condition_id == "matching-face-speech"
        )
        summary = {
            "samples": 40,
            "valid_pct": 100.0,
            "single_face": 40,
            "no_face": 0,
            "speech_positive": 8,
            "confirmed": 0,
        }
        self.assertEqual(matrix_quality_issues(matching, summary), ())

    def test_no_face_control_rejects_visible_face_contamination(self):
        no_face = next(
            step for step in MATRIX_STEPS
            if step.condition_id == "speech-no-visible-face"
        )
        summary = {
            "samples": 40,
            "valid_pct": 100.0,
            "single_face": 20,
            "no_face": 20,
            "speech_positive": 8,
        }
        issues = matrix_quality_issues(no_face, summary)
        self.assertTrue(any("no-face control" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()
