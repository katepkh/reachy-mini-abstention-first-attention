from __future__ import annotations

import unittest

import numpy as np

from reachy_avsync import (
    NumericSeries,
    SynchronyConsensus,
    SynchronyDecision,
    SynchronySpec,
    audio_energy_envelope,
    evaluate_synchrony,
    mouth_motion_envelope,
    run_synthetic_fault_suite,
    select_face_candidate,
)
from reachy_avsync.protocol import confirmation_trials, protocol_payload, randomized_confirmation_trials


class AudioMouthSynchronyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = SynchronySpec()
        self.timestamps = np.arange(60, dtype=float) * self.spec.resample_period_ms
        self.signal = np.random.default_rng(87).normal(0.0, 1.0, 60)
        self.audio = NumericSeries.from_sequences(self.timestamps, self.signal)

    def test_aligned_signal_is_only_a_candidate(self) -> None:
        mouth = NumericSeries.from_sequences(self.timestamps, self.signal)
        result = evaluate_synchrony(self.audio, mouth, self.spec)
        self.assertEqual(result.status, "CANDIDATE")
        self.assertIn("NOT_IDENTITY", result.reason)
        self.assertAlmostEqual(result.correlation or 0.0, 1.0)

    def test_audio_energy_is_derived_without_capture(self) -> None:
        sample_rate = 1000.0
        time = np.arange(1000, dtype=float) / sample_rate
        waveform = np.sin(2.0 * np.pi * 25.0 * time)
        envelope = audio_energy_envelope(waveform, sample_rate)
        self.assertEqual(len(envelope.values), 25)
        self.assertTrue(all(value > 0.6 for value in envelope.values))

    def test_mouth_motion_is_scale_normalized(self) -> None:
        timestamps = [0.0, 40.0, 80.0]
        upper = [[0.0, 0.0]] * 3
        lower = [[0.0, 1.0], [0.0, 3.0], [0.0, 1.0]]
        motion = mouth_motion_envelope(timestamps, upper, lower, [10.0, 10.0, 10.0])
        self.assertEqual(motion.values[0], 0.0)
        self.assertAlmostEqual(motion.values[1], 0.2)
        self.assertAlmostEqual(motion.values[2], 0.2)

    def test_length_mismatch_abstains(self) -> None:
        mouth = NumericSeries.from_sequences(self.timestamps, self.signal[:-1])
        result = evaluate_synchrony(self.audio, mouth, self.spec)
        self.assertEqual(result.status, "ABSTAIN")
        self.assertEqual(result.reason, "MOUTH_LENGTH_MISMATCH")

    def test_close_face_scores_conflict(self) -> None:
        track = NumericSeries.from_sequences(self.timestamps, self.signal)
        decision = select_face_candidate(self.audio, {"a": track, "b": track}, self.spec)
        self.assertEqual(decision.status, "CONFLICT")
        self.assertIsNone(decision.candidate_face_id)

    def test_empty_face_set_abstains(self) -> None:
        decision = select_face_candidate(self.audio, {}, self.spec)
        self.assertEqual(decision.status, "ABSTAIN")
        self.assertEqual(decision.reason, "NO_FACE_TRACKS")

    def test_consensus_resets_on_face_switch(self) -> None:
        consensus = SynchronyConsensus(self.spec)
        face_a = SynchronyDecision("CANDIDATE", "test", "a", 0.9, 0.0)
        face_b = SynchronyDecision("CANDIDATE", "test", "b", 0.9, 0.0)
        self.assertEqual(consensus.update(0.0, face_a).stable_windows, 1)
        self.assertEqual(consensus.update(200.0, face_a).stable_windows, 2)
        switched = consensus.update(400.0, face_b)
        self.assertEqual(switched.status, "ABSTAIN")
        self.assertEqual(switched.stable_windows, 1)

    def test_consensus_never_calls_candidate_identity(self) -> None:
        consensus = SynchronyConsensus(self.spec)
        decision = SynchronyDecision("CANDIDATE", "test", "a", 0.9, 0.0)
        consensus.update(0.0, decision)
        consensus.update(200.0, decision)
        supported = consensus.update(400.0, decision)
        self.assertEqual(supported.status, "SUPPORTED_CANDIDATE")
        self.assertIn("NOT_IDENTITY", supported.reason)

    def test_synthetic_fault_suite_passes_every_declared_case(self) -> None:
        report = run_synthetic_fault_suite()
        self.assertTrue(report["all_passed"])
        self.assertEqual(len(report["cases"]), 9)
        self.assertEqual(report["robot_connections"], 0)
        self.assertEqual(report["actuation_commands"], 0)

    def test_future_protocol_has_frozen_trial_units_and_no_commands(self) -> None:
        trials = confirmation_trials()
        self.assertEqual(len(trials), 54)
        self.assertEqual(sum(item["role"] == "matching_positive" for item in trials), 18)
        self.assertEqual(sum(item["role"] == "hard_negative" for item in trials), 36)
        schedule = randomized_confirmation_trials()
        self.assertEqual(len({item["trial_id"] for item in schedule}), 54)
        self.assertNotEqual(schedule, trials)
        payload = protocol_payload()
        self.assertEqual(payload["robot_scope"]["actuation_commands"], 0)
        self.assertEqual(len(payload["fingerprint"]), 64)


if __name__ == "__main__":
    unittest.main()
