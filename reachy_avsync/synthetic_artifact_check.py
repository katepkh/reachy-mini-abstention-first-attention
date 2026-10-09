"""Compare frozen synthetic reports across numerical library builds."""

from __future__ import annotations

import json
import math
from typing import Any


ROUNDOFF_TOLERANCE = 1e-12


def matches_frozen_report(
    stored: bytes, regenerated: bytes, *, roundoff_fields: frozenset[str]
) -> bool:
    """Require exact structure and decisions, allowing only named float roundoff."""

    if stored == regenerated:
        return True
    try:
        saved_report = json.loads(stored)
        current_report = json.loads(regenerated)
    except (UnicodeDecodeError, ValueError):
        return False

    def matches(saved: Any, current: Any, field: str | None = None) -> bool:
        if type(saved) is not type(current):
            return False
        if isinstance(saved, dict):
            return saved.keys() == current.keys() and all(
                matches(saved[key], current[key], key) for key in saved
            )
        if isinstance(saved, list):
            return len(saved) == len(current) and all(
                matches(left, right) for left, right in zip(saved, current)
            )
        if type(saved) is float and field in roundoff_fields:
            return (
                math.isfinite(saved)
                and math.isfinite(current)
                and math.isclose(
                    saved, current, rel_tol=0.0, abs_tol=ROUNDOFF_TOLERANCE
                )
            )
        return saved == current

    return matches(saved_report, current_report)
