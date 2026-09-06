"""Offline-only Stage 3P V6 association repair candidate.

V6 keeps the V5 bounded relative eye-error controller unchanged.  It only
revises the conservative repeated-speech association fallback exposed by the
frozen failed V5 result.  This module consumes saved numeric rows and has no
network, media, robot SDK, or actuation capability.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from .policy_v5 import Stage3PVisualServoPolicyV5, Stage3PVisualServoV5Spec


@dataclass(frozen=True, slots=True)
class Stage3PVisualServoV6Spec(Stage3PVisualServoV5Spec):
    source_failed_v5_result_bundle_sha256: str
    association_revision: str

    def payload(self) -> dict[str, Any]:
        core = asdict(self)
        encoded = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return {**core, "fingerprint": hashlib.sha256(encoded).hexdigest()}


def candidate_v6_spec(
    base: Stage3PVisualServoV5Spec,
    *,
    failed_v5_result_bundle_sha256: str,
    fallback_geometry_error_deg: float,
    fallback_speech_onset_window_ms: float,
    association_consensus_hits: int,
) -> Stage3PVisualServoV6Spec:
    fields = asdict(base)
    fields.update(
        {
            "name": (
                "Stage 3P V6 bounded relative eye-error servo with disclosed "
                f"association repair geometry<={fallback_geometry_error_deg:g}deg "
                f"speech-window<={fallback_speech_onset_window_ms:g}ms "
                f"hits={association_consensus_hits}"
            ),
            "status": (
                "OFFLINE_DEVELOPMENT_CANDIDATE_NOT_HELD_OUT_"
                "NOT_AUTHORISED_FOR_ACTUATION"
            ),
            "fallback_geometry_error_deg": float(fallback_geometry_error_deg),
            "fallback_speech_onset_window_ms": float(fallback_speech_onset_window_ms),
            "association_consensus_hits": int(association_consensus_hits),
        }
    )
    return Stage3PVisualServoV6Spec(
        **fields,
        source_failed_v5_result_bundle_sha256=failed_v5_result_bundle_sha256,
        association_revision=(
            "DISCLOSED_POST_V5_REPEATED_SPEECH_ASSOCIATION_REPAIR_"
            "CONTROL_LAW_AND_FACE_FAULT_BOUNDARIES_UNCHANGED"
        ),
    )


class Stage3PVisualServoPolicyV6(Stage3PVisualServoPolicyV5):
    """V5 control law with only the selected V6 association parameters."""

    def __init__(self, spec: Stage3PVisualServoV6Spec) -> None:
        super().__init__(spec)
        self.spec = spec
