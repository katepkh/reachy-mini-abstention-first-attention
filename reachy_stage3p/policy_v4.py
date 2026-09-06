"""Pre-collection hardening of Stage 3P V3 association lifetime.

V4 changes one state-machine detail: a fresh, valid acoustic/visual
reconfirmation refreshes the existing ten-second maintenance lease.  The
lease therefore starts from the last trustworthy matching speech evidence,
not only from the first association.  Every V3 face fault still clears it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from statistics import median
from typing import Any

from reachy_stage3v.revised_policy_v3 import FROZEN_REVISED_POLICY_V3

from .policy import Stage3PEvidence
from .policy_v3 import (
    Stage3PCandidateV3Spec,
    Stage3PReplayPolicyV3,
    _number,
    _truth,
)


@dataclass(frozen=True, slots=True)
class Stage3PCandidateV4Spec(Stage3PCandidateV3Spec):
    source_superseded_policy_fingerprint: str
    refresh_maintenance_lease_on_valid_reconfirmation: bool

    def payload(self) -> dict[str, Any]:
        core = asdict(self)
        encoded = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return {**core, "fingerprint": hashlib.sha256(encoded).hexdigest()}


def candidate_v4_spec(
    base: Stage3PCandidateV3Spec,
    *,
    source_superseded_policy_fingerprint: str,
) -> Stage3PCandidateV4Spec:
    fields = asdict(base)
    fields["name"] = base.name.replace("Stage 3P V3", "Stage 3P V4") + " with renewable maintenance lease"
    fields["status"] = "PRECOLLECTION_HARDENED_CANDIDATE_NOT_HELD_OUT_NOT_AUTHORISED_FOR_ACTUATION"
    return Stage3PCandidateV4Spec(
        **fields,
        source_superseded_policy_fingerprint=source_superseded_policy_fingerprint,
        refresh_maintenance_lease_on_valid_reconfirmation=True,
    )


class Stage3PReplayPolicyV4(Stage3PReplayPolicyV3):
    """V3 policy with a lease refreshed only by valid matching evidence."""

    def __init__(
        self,
        spec: Stage3PCandidateV4Spec,
        *,
        allow_legacy_box_bridge: bool = False,
    ) -> None:
        super().__init__(spec, allow_legacy_box_bridge=allow_legacy_box_bridge)
        self.spec = spec

    def process(self, row: dict[str, Any]) -> Stage3PEvidence:
        elapsed = _number(row, "elapsed_ms") or 0.0
        speech = _truth(row.get("speech_detected"))
        if speech:
            self._last_speech_ms = elapsed
        if speech and not self._speech_was_positive:
            self._speech_onsets.append(elapsed)
        self._speech_was_positive = speech
        while (
            self._speech_onsets
            and elapsed - self._speech_onsets[0]
            > self.spec.fallback_speech_onset_window_ms
        ):
            self._speech_onsets.popleft()

        horizontal = self._yaw.process(row)
        face_reason = self._face_reason(row)
        if face_reason is not None:
            self._clear_association()
            return Stage3PEvidence(False, None, None, "UNASSOCIATED", face_reason)

        pitch = self._pitch(row)
        raw_yaw = _number(row, "face_heading_deg")
        if pitch is None or raw_yaw is None:
            self._clear_association()
            return Stage3PEvidence(False, None, None, "UNASSOCIATED", "FACE_GEOMETRY_UNAVAILABLE")

        self._pitch_hits.append((elapsed, pitch))
        while (
            self._pitch_hits
            and elapsed - self._pitch_hits[0][0] > self.spec.pitch_consensus_window_ms
        ):
            self._pitch_hits.popleft()

        source_association = bool(
            horizontal.confirmed
            and horizontal.agreement_error_deg is not None
            and float(horizontal.agreement_error_deg)
            <= self.spec.fallback_geometry_error_deg
        )
        fallback_association = False
        if not source_association and not self._associated:
            fallback_association = self._fallback_association(row, elapsed)

        if not self._associated and (source_association or fallback_association):
            self._associated = True
            self._acquired_at_ms = elapsed
        elif (
            self._associated
            and source_association
            and self.spec.refresh_maintenance_lease_on_valid_reconfirmation
        ):
            self._acquired_at_ms = elapsed

        if not self._associated:
            return Stage3PEvidence(False, None, None, "UNASSOCIATED", horizontal.reason)
        if elapsed - self._acquired_at_ms > self.spec.maximum_maintenance_ms:
            self._clear_association()
            return Stage3PEvidence(False, None, None, "EXPIRED", "SPEAKER_ASSOCIATION_EXPIRED")

        stable = [
            value
            for _, value in self._pitch_hits
            if abs(value - pitch) <= self.spec.pitch_consensus_tolerance_deg
        ]
        if len(stable) < self.spec.pitch_consensus_hits:
            return Stage3PEvidence(False, None, None, "ACQUISITION", "PITCH_CONSENSUS_PENDING")

        target_pitch = median(stable[-self.spec.pitch_consensus_hits :])
        target_pitch = max(
            -self.spec.maximum_abs_pitch_target_deg,
            min(self.spec.maximum_abs_pitch_target_deg, target_pitch),
        )
        target_yaw = (
            FROZEN_REVISED_POLICY_V3.face_heading_multiplier * raw_yaw
            + FROZEN_REVISED_POLICY_V3.face_heading_offset_deg
        )
        phase = "ACQUISITION" if horizontal.confirmed else "MAINTENANCE"
        return Stage3PEvidence(
            True,
            target_yaw,
            target_pitch,
            phase,
            "ANCHORED_RENEWABLE_COUPLED_TARGET_CONFIRMED",
        )
