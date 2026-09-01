"""Offline Stage 3A motion-shadow package.

This package transforms frozen, numeric Stage 2A evidence into hypothetical
head-motion decisions.  It has no robot, network, camera, media or actuation
capability.
"""

from .controller import MotionEnvelope, MotionShadowController, MotionShadowDecision

__all__ = ["MotionEnvelope", "MotionShadowController", "MotionShadowDecision"]
