import math
import unittest

from reachy_doa.confidence import ReliabilityEnvelope
from reachy_doa.policies import (
    ConfidenceAwarePolicy,
    INTENDED_TWO_DEGREE_RAD,
    PUBLISHED_THRESHOLD_RAD,
    ThresholdPolicy,
)
from reachy_doa.replay import ReplayObservation


def observation(sequence, elapsed, angle_deg=90.0, speech=True, valid=True, latency=20.0):
    return ReplayObservation(
        sequence=sequence,
        elapsed_ms=elapsed,
        angle_rad=math.radians(angle_deg) if valid else None,
        angle_deg=angle_deg if valid else None,
        speech_detected=speech if valid else None,
        latency_ms=latency,
        http_status=200 if valid else None,
        valid=valid,
        error="" if valid else "timeout",
    )


class PolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reliability = ReliabilityEnvelope(tuple((axis, 1.0) for axis in (0, 45, 90, 135, 180)))

    def test_threshold_comment_mismatch_changes_update_behaviour(self) -> None:
        published = ThresholdPolicy(PUBLISHED_THRESHOLD_RAD, "published")
        intended = ThresholdPolicy(INTENDED_TWO_DEGREE_RAD, "intended")
        for policy in (published, intended):
            policy.process(observation(1, 0, angle_deg=57.2958))
        published_second = published.process(observation(2, 200, angle_deg=58.4417))
        intended_second = intended.process(observation(2, 200, angle_deg=58.4417))
        self.assertGreater(published_second.axis_deg, intended_second.axis_deg)

    def test_confidence_policy_requires_persistence_and_withholds_ambiguous_target(self) -> None:
        policy = ConfidenceAwarePolicy(self.reliability)
        decisions = [
            policy.process(observation(index + 1, index * 200, angle_deg=90.0))
            for index in range(5)
        ]
        self.assertEqual(decisions[0].state, "CANDIDATE")
        self.assertEqual(decisions[-1].state, "TRACKING_AXIS")
        self.assertTrue(decisions[-1].front_back_ambiguous)
        self.assertTrue(decisions[-1].would_attend_axis)
        self.assertFalse(decisions[-1].would_propose_physical_target)

    def test_confidence_policy_detects_competing_clusters(self) -> None:
        policy = ConfidenceAwarePolicy(self.reliability)
        angles = [10, 12, 9, 160, 162, 158]
        decision = None
        for index, angle in enumerate(angles):
            decision = policy.process(observation(index + 1, index * 150, angle_deg=angle))
        self.assertIsNotNone(decision)
        self.assertEqual(decision.state, "COMPETING_SOURCES")
        self.assertFalse(decision.would_attend_axis)

    def test_confidence_policy_marks_repeated_network_failure(self) -> None:
        policy = ConfidenceAwarePolicy(self.reliability)
        policy.process(observation(1, 0))
        policy.process(observation(2, 200, valid=False))
        decision = policy.process(observation(3, 400, valid=False))
        self.assertEqual(decision.state, "NETWORK_DEGRADED")
        self.assertFalse(decision.would_attend_axis)


if __name__ == "__main__":
    unittest.main()
