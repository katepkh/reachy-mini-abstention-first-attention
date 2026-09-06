"""Offline audio–mouth synchrony research prototype."""

from .synchrony import (
    NumericSeries,
    SynchronyConsensus,
    SynchronyDecision,
    SynchronyScore,
    SynchronySpec,
    audio_energy_envelope,
    evaluate_synchrony,
    mouth_motion_envelope,
    run_synthetic_fault_suite,
    select_face_candidate,
)
from .protocol import confirmation_trials, protocol_payload, randomized_confirmation_trials
from .pilot import analyze_pilot, candidate_specs, load_numeric_trial
from .pilot_protocol import (
    canonical_pilot_trials,
    pilot_protocol_payload,
    randomized_pilot_trials,
)

__all__ = [
    "NumericSeries",
    "SynchronyConsensus",
    "SynchronyDecision",
    "SynchronyScore",
    "SynchronySpec",
    "audio_energy_envelope",
    "evaluate_synchrony",
    "mouth_motion_envelope",
    "run_synthetic_fault_suite",
    "select_face_candidate",
    "confirmation_trials",
    "protocol_payload",
    "randomized_confirmation_trials",
    "analyze_pilot",
    "candidate_specs",
    "load_numeric_trial",
    "canonical_pilot_trials",
    "pilot_protocol_payload",
    "randomized_pilot_trials",
]
