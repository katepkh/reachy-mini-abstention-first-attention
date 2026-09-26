"""No-side-effect integration state machine for the intended interaction.

The state machine connects fused selection, a separately reported orientation
outcome, bounded attention hold, and a deterministic acknowledgement *in
shadow*.  It emits no robot or audio command and has no automatic recovery.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .attention_hold import AttentionHoldResult
from .fused_shadow import ShadowDecision


@dataclass(frozen=True, slots=True)
class InteractionShadowOutput:
    state: str
    reason: str
    selected_face_track_id: str | None
    candidate_heading_deg: float | None
    would_orient: bool = False
    would_respond: bool = False
    response_text: str | None = None
    motion_authorized: bool = False
    response_authorized: bool = False
    actuation_commands: int = 0
    response_commands: int = 0

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


class InteractionShadowController:
    """Pure sequential contract with a latched fault and explicit outcomes."""

    VALID_STATES = frozenset(
        {"OBSERVE", "WOULD_ORIENT", "ATTEND", "WOULD_RESPOND", "COMPLETE", "FAULT"}
    )

    def __init__(self, acknowledgement: str = "I heard you.") -> None:
        if not acknowledgement.strip():
            raise ValueError("The deterministic acknowledgement cannot be empty.")
        self.acknowledgement = acknowledgement
        self.state = "OBSERVE"
        self.selected_face_track_id: str | None = None
        self.candidate_heading_deg: float | None = None
        self._fault_reason: str | None = None

    def _output(self, reason: str, *, would_orient: bool = False, would_respond: bool = False) -> InteractionShadowOutput:
        return InteractionShadowOutput(
            state=self.state,
            reason=reason,
            selected_face_track_id=self.selected_face_track_id,
            candidate_heading_deg=self.candidate_heading_deg,
            would_orient=would_orient,
            would_respond=would_respond,
            response_text=self.acknowledgement if would_respond else None,
        )

    def fault(self, reason: str) -> InteractionShadowOutput:
        self.state = "FAULT"
        self._fault_reason = str(reason or "UNSPECIFIED_FAULT")
        return self._output(self._fault_reason)

    def observe_selection(self, decision: ShadowDecision) -> InteractionShadowOutput:
        if self.state == "FAULT":
            return self._output(self._fault_reason or "FAULT_LATCHED")
        if self.state != "OBSERVE":
            return self.fault("SELECTION_RECEIVED_OUTSIDE_OBSERVE")
        if decision.state == "HOLD":
            return self._output(f"PERCEPTION_HOLD:{decision.reason}")
        if decision.state == "ABSTAIN":
            return self._output(f"PERCEPTION_ABSTAIN:{decision.reason}")
        if (
            decision.state != "SELECT"
            or not decision.candidate_face_track_id
            or decision.candidate_heading_deg is None
        ):
            return self.fault("INVALID_SELECTION")
        if decision.motion_authorized or decision.response_authorized:
            return self.fault("UPSTREAM_SIDE_EFFECT_AUTHORITY_FORBIDDEN")
        self.selected_face_track_id = decision.candidate_face_track_id
        self.candidate_heading_deg = float(decision.candidate_heading_deg)
        self.state = "WOULD_ORIENT"
        return self._output("SHADOW_ORIENTATION_PROPOSED", would_orient=True)

    def report_orientation(self, *, succeeded: bool, fresh_and_healthy: bool) -> InteractionShadowOutput:
        if self.state == "FAULT":
            return self._output(self._fault_reason or "FAULT_LATCHED")
        if self.state != "WOULD_ORIENT":
            return self.fault("ORIENTATION_RESULT_OUTSIDE_ORIENTATION_STATE")
        if not succeeded or not fresh_and_healthy:
            return self.fault("ORIENTATION_FAILED_OR_UNHEALTHY")
        self.state = "ATTEND"
        return self._output("ORIENTATION_REPORTED_SUCCESSFUL_ATTENTION_PENDING")

    def observe_attention(self, result: AttentionHoldResult) -> InteractionShadowOutput:
        if self.state == "FAULT":
            return self._output(self._fault_reason or "FAULT_LATCHED")
        if self.state != "ATTEND":
            return self.fault("ATTENTION_RESULT_OUTSIDE_ATTEND_STATE")
        if result.motion_authorized or result.response_authorized:
            return self.fault("ATTENTION_SIDE_EFFECT_AUTHORITY_FORBIDDEN")
        if result.state == "ABORT":
            return self.fault(f"ATTENTION_ABORT:{result.reason}")
        if result.state != "HELD":
            return self._output(f"ATTENTION_PENDING:{result.reason}")
        self.state = "WOULD_RESPOND"
        return self._output(
            "DETERMINISTIC_ACKNOWLEDGEMENT_PROPOSED",
            would_respond=True,
        )

    def report_response(self, *, succeeded: bool) -> InteractionShadowOutput:
        if self.state == "FAULT":
            return self._output(self._fault_reason or "FAULT_LATCHED")
        if self.state != "WOULD_RESPOND":
            return self.fault("RESPONSE_RESULT_OUTSIDE_RESPONSE_STATE")
        if not succeeded:
            return self.fault("RESPONSE_FAILED")
        self.state = "COMPLETE"
        return self._output("SHADOW_INTERACTION_COMPLETE")
