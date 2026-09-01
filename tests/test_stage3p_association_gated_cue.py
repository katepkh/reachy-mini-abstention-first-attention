import unittest
from types import SimpleNamespace

from reachy_stage3p.association_gated_cue import (
    AssociationGatedCueSpec,
    AssociationGatedMoveCue,
)


def evidence(*, confirmed=False, target_pitch_deg=None):
    return SimpleNamespace(confirmed=confirmed, target_pitch_deg=target_pitch_deg)


class Stage3PAssociationGatedCueTests(unittest.TestCase):
    def test_three_consecutive_center_confirmations_emit_one_visual_cue(self):
        gate = AssociationGatedMoveCue()
        self.assertEqual(gate.process(1000.0, evidence(confirmed=True, target_pitch_deg=0.0)).action, "WAIT")
        self.assertEqual(gate.process(1200.0, evidence(confirmed=True, target_pitch_deg=0.0)).action, "WAIT")
        decision = gate.process(1400.0, evidence(confirmed=True, target_pitch_deg=0.0))
        self.assertEqual(decision.action, "MOVE_CUE")
        self.assertEqual(decision.ready_streak, 3)
        self.assertEqual(
            gate.process(1600.0, evidence(confirmed=True, target_pitch_deg=0.0)).action,
            "HOLD",
        )

    def test_fault_or_noncenter_row_resets_streak(self):
        gate = AssociationGatedMoveCue()
        gate.process(1000.0, evidence(confirmed=True, target_pitch_deg=0.0))
        gate.process(1200.0, evidence(confirmed=True, target_pitch_deg=0.0))
        reset = gate.process(1400.0, evidence(confirmed=False, target_pitch_deg=None))
        self.assertEqual(reset.action, "WAIT")
        self.assertEqual(reset.ready_streak, 0)
        self.assertEqual(
            gate.process(1600.0, evidence(confirmed=True, target_pitch_deg=3.0)).ready_streak,
            0,
        )

    def test_timeout_aborts_without_move_cue_and_stays_aborted(self):
        gate = AssociationGatedMoveCue(
            AssociationGatedCueSpec(maximum_wait_ms=12000.0)
        )
        decision = gate.process(12000.1, evidence(confirmed=True, target_pitch_deg=0.0))
        self.assertEqual(decision.action, "ABORT")
        self.assertEqual(decision.reason, "ASSOCIATION_READY_TIMEOUT")
        self.assertEqual(
            gate.process(12200.0, evidence(confirmed=True, target_pitch_deg=0.0)).action,
            "ABORT",
        )

    def test_invalid_gate_configuration_is_rejected(self):
        with self.assertRaises(ValueError):
            AssociationGatedMoveCue(
                AssociationGatedCueSpec(minimum_consecutive_confirmed_center_rows=0)
            )
        with self.assertRaises(ValueError):
            AssociationGatedMoveCue(AssociationGatedCueSpec(maximum_wait_ms=0.0))


if __name__ == "__main__":
    unittest.main()
