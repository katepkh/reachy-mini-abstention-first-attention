"""Circular-angle calculations used by the dashboard."""

from __future__ import annotations

import math
from collections.abc import Iterable


def wrap_degrees(angle: float) -> float:
    """Wrap an angle to [-180, 180)."""
    wrapped = (float(angle) + 180.0) % 360.0 - 180.0
    return 0.0 if wrapped == -0.0 else wrapped


def radians_to_degrees(angle_radians: float) -> float:
    """Convert radians to wrapped degrees."""
    return wrap_degrees(math.degrees(float(angle_radians)))


def doa_radians_to_degrees(angle_radians: float) -> float:
    """Convert Reachy v1.9 DoA radians to its documented 0..180 degree axis.

    Reachy's linear microphone array reports 0=left, pi/2=front/back, and
    pi=right.  Unlike a generic heading, pi must remain +180 rather than wrap
    to -180.
    """
    degrees = math.degrees(float(angle_radians))
    if math.isclose(degrees, 0.0, abs_tol=1e-9):
        return 0.0
    if math.isclose(degrees, 180.0, abs_tol=1e-9):
        return 180.0
    return degrees


def doa_mean_degrees(angles: Iterable[float]) -> float | None:
    """Return a circular mean while preserving Reachy's +180 right edge."""
    result = circular_mean_degrees(angles)
    if result is not None and math.isclose(result, -180.0, abs_tol=1e-9):
        return 180.0
    return result


def physical_heading_to_expected_doa(heading_degrees: float) -> float:
    """Fold the displayed top-down diagram heading onto Reachy's DoA axis.

    Diagram headings use 0=front at page-bottom, +90=page-right,
    +/-180=back, and -90=page-left. With Reachy facing page-bottom,
    page-right corresponds to the microphone array's 0-degree side.
    """
    heading = math.radians(wrap_degrees(heading_degrees))
    return 90.0 - math.degrees(math.asin(math.sin(heading)))


def doa_to_physical_hypotheses(doa_degrees: float) -> tuple[float, ...]:
    """Invert a folded Reachy DoA into one or two diagram headings.

    The linear array cannot distinguish the two sides of its front/back plane.
    For example, 45 degrees can mean front-right (+45) or back-right (+135).
    At the lateral end-fire directions (0 and 180) the two hypotheses coincide.
    """
    doa = float(doa_degrees)
    if not math.isfinite(doa) or not 0.0 <= doa <= 180.0:
        raise ValueError("Reachy DoA must be finite and between 0 and 180 degrees.")
    first = wrap_degrees(90.0 - doa)
    second = wrap_degrees(180.0 - first)
    if math.isclose(first, second, abs_tol=1e-9):
        return (first,)
    return (first, second)


def circular_mean_degrees(angles: Iterable[float]) -> float | None:
    """Return the circular mean, correctly handling the +/-180 boundary."""
    values = [wrap_degrees(value) for value in angles if math.isfinite(float(value))]
    if not values:
        return None

    x = sum(math.cos(math.radians(value)) for value in values)
    y = sum(math.sin(math.radians(value)) for value in values)
    if math.isclose(x, 0.0, abs_tol=1e-12) and math.isclose(y, 0.0, abs_tol=1e-12):
        return None
    return wrap_degrees(math.degrees(math.atan2(y, x)))


def percentile(values: Iterable[float], quantile: float) -> float | None:
    """Compute a linearly interpolated percentile without third-party packages."""
    ordered = sorted(float(value) for value in values if math.isfinite(float(value)))
    if not ordered:
        return None
    if not 0.0 <= quantile <= 1.0:
        raise ValueError("quantile must be between 0 and 1")
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction
