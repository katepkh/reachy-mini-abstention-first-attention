"""Stage 3V passive validation and command-free fused shadow interface."""

from .fused_shadow import (
    FUSED_SHADOW_SPEC_V1,
    ShadowDecision,
    ShadowFusionSpec,
    ShadowObservation,
    SpatialEvidence,
    SynchronyEvidence,
    fuse_shadow_observation,
    spatial_from_revised,
    synchrony_from_decision,
)

__all__ = [
    "FUSED_SHADOW_SPEC_V1",
    "ShadowDecision",
    "ShadowFusionSpec",
    "ShadowObservation",
    "SpatialEvidence",
    "SynchronyEvidence",
    "fuse_shadow_observation",
    "spatial_from_revised",
    "synchrony_from_decision",
]
