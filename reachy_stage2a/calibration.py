"""Approximate image-to-heading projection using Pollen camera intrinsics."""

from __future__ import annotations

import math

from reachy_doa.angles import wrap_degrees

from .config import CALIBRATION_CX, CALIBRATION_FX, CALIBRATION_WIDTH


def face_center_to_heading(center_x_norm: float) -> float:
    """Map normalized image x to a physical heading relative to camera front.

    Positive values are camera-right. The computation scales Pollen's official
    intrinsic matrix into normalized coordinates. Lens distortion is not
    inverted, so this is an approximate bearing and is labelled as such in UI.
    """
    x = float(center_x_norm)
    if not math.isfinite(x) or not 0.0 <= x <= 1.0:
        raise ValueError("Face centre must be a finite normalized x coordinate.")
    fx_norm = CALIBRATION_FX / CALIBRATION_WIDTH
    cx_norm = CALIBRATION_CX / CALIBRATION_WIDTH
    return wrap_degrees(math.degrees(math.atan((x - cx_norm) / fx_norm)))


def circular_distance_degrees(first: float, second: float) -> float:
    """Smallest unsigned distance between two headings."""
    return abs(wrap_degrees(float(first) - float(second)))
