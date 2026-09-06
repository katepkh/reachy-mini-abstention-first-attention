"""Camera-image vertical geometry for passive Stage 3P analysis."""

from __future__ import annotations

import math

from reachy_stage2a.config import CALIBRATION_CY, CALIBRATION_FY, CALIBRATION_HEIGHT


def face_center_to_pitch(center_y_norm: float) -> float:
    """Convert normalized image y to camera-relative pitch in degrees.

    Stage 3P defines positive pitch as up and negative pitch as down. Image y
    grows downward, hence the sign reversal around the calibrated principal
    point. The result is evidence only; it is never sent to the robot.
    """
    y = float(center_y_norm)
    if not math.isfinite(y) or not 0.0 <= y <= 1.0:
        raise ValueError("Face centre must be a finite normalized y coordinate.")
    fy_norm = CALIBRATION_FY / CALIBRATION_HEIGHT
    cy_norm = CALIBRATION_CY / CALIBRATION_HEIGHT
    return math.degrees(math.atan((cy_norm - y) / fy_norm))


def pitch_to_center_y_norm(pitch_deg: float) -> float:
    """Project a camera-relative pitch back to normalized image y."""
    pitch = float(pitch_deg)
    if not math.isfinite(pitch) or not -89.0 < pitch < 89.0:
        raise ValueError("Pitch must be finite and strictly between -89 and +89 degrees.")
    fy_norm = CALIBRATION_FY / CALIBRATION_HEIGHT
    cy_norm = CALIBRATION_CY / CALIBRATION_HEIGHT
    return cy_norm - fy_norm * math.tan(math.radians(pitch))


def vertical_offset_cm(pitch_deg: float, horizontal_distance_m: float = 1.0) -> float:
    """Return eye-height offset at a fixed horizontal camera distance."""
    distance = float(horizontal_distance_m)
    if not math.isfinite(distance) or distance <= 0.0:
        raise ValueError("Horizontal distance must be finite and positive.")
    return 100.0 * distance * math.tan(math.radians(float(pitch_deg)))

