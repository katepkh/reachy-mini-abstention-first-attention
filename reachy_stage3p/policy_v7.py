"""Offline-only post-V6 association candidate.

The candidate keeps every V6 geometry, face-fault, pitch-control and actuation
boundary unchanged.  It may vary only the repeated-speech memory and the
number of fallback geometry rows required after two distinct speech onsets.
This module has no network, media, robot SDK, or actuation capability.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from .policy_v6 import Stage3PVisualServoPolicyV6, Stage3PVisualServoV6Spec


@dataclass(frozen=True, slots=True)
class Stage3PVisualServoV7Spec(Stage3PVisualServoV6Spec):
    source_failed_v6_result_bundle_sha256: str
    post_v6_association_revision: str

    def payload(self) -> dict[str, Any]:
        core = asdict(self)
        encoded = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return {**core, "fingerprint": hashlib.sha256(encoded).hexdigest()}


def candidate_v7_spec(
    base: Stage3PVisualServoV6Spec,
    *,
    failed_v6_result_bundle_sha256: str,
    fallback_speech_onset_window_ms: float,
    association_consensus_hits: int,
) -> Stage3PVisualServoV7Spec:
    fields = asdict(base)
    fields.update(
        {
            "name": (
                "Stage 3P post-V6 bounded relative eye-error candidate with "
                f"speech-window<={fallback_speech_onset_window_ms:g}ms "
                f"fallback-geometry-hits={association_consensus_hits}"
            ),
            "status": (
                "OFFLINE_DISCLOSED_DEVELOPMENT_CANDIDATE_NOT_HELD_OUT_"
                "NOT_AUTHORISED_FOR_ACTUATION"
            ),
            "fallback_speech_onset_window_ms": float(fallback_speech_onset_window_ms),
            "association_consensus_hits": int(association_consensus_hits),
        }
    )
    return Stage3PVisualServoV7Spec(
        **fields,
        source_failed_v6_result_bundle_sha256=failed_v6_result_bundle_sha256,
        post_v6_association_revision=(
            "DISCLOSED_POST_V6_TEMPORAL_ASSOCIATION_REPAIR_"
            "GEOMETRY_FACE_FAULT_PITCH_CONTROL_AND_RECENT_SPEECH_BOUNDARIES_UNCHANGED"
        ),
    )


class Stage3PVisualServoPolicyV7(Stage3PVisualServoPolicyV6):
    """V6 behavior with only the disclosed association timing candidate."""

    def __init__(self, spec: Stage3PVisualServoV7Spec) -> None:
        super().__init__(spec)
        self.spec = spec
