from __future__ import annotations

import unittest

from reachy_stage3v.robustness import build_robustness_report, load_public_trials, wilson_interval


class Stage3VRobustnessTests(unittest.TestCase):
    def test_wilson_intervals_expose_small_denominators(self) -> None:
        self.assertAlmostEqual(wilson_interval(0, 6)[1], 0.3903342879)
        self.assertAlmostEqual(wilson_interval(12, 12)[0], 0.7575059933)

    def test_public_loader_uses_exactly_the_accepted_trials(self) -> None:
        trials = load_public_trials()
        self.assertEqual(len(trials), 18)
        self.assertEqual([trial.step.index for trial in trials], list(range(1, 19)))
        self.assertEqual(len({trial.sha256 for trial in trials}), 18)

    def test_report_reproduces_frozen_result_and_diagnostic_failures(self) -> None:
        report = build_robustness_report()
        by_name = {item["policy"]: item for item in report["ablations"]}
        frozen = by_name["full_frozen_v3"]
        self.assertEqual(frozen["positive_trials_with_proposal"], 12)
        self.assertEqual(frozen["hard_negative_trials_with_proposal"], 0)
        self.assertEqual(by_name["single_frame_audio_visual"]["hard_negative_trials_with_proposal"], 2)
        self.assertEqual(by_name["visual_only_temporal"]["hard_negative_trials_with_proposal"], 6)
        self.assertEqual(by_name["audio_only_front_hypothesis"]["hard_negative_trials_with_proposal"], 4)
        self.assertEqual(len(report["one_at_a_time_sensitivity"]), 33)
        self.assertEqual(len(report["risk_coverage_operating_points"]), 25)
        self.assertEqual(len(report["leave_one_trial_out"]), 18)

    def test_report_is_deterministic(self) -> None:
        self.assertEqual(build_robustness_report(), build_robustness_report())


if __name__ == "__main__":
    unittest.main()

