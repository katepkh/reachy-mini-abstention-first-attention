"""Validate and compare content-addressed borrowed-condition inventories."""

from __future__ import annotations

import re
from typing import Any, Mapping


SCHEMA_VERSION = "reachy-stage4a-borrowed-condition-inventory-v1"
REQUIRED_SURFACES = (
    "physical_exterior",
    "robot_identity",
    "operating_system_release",
    "installed_reachy_package_tree",
    "daemon_service_unit",
    "daemon_launcher",
    "hardware_configuration",
    "mini_daemon_environment",
    "apps_environment",
    "restore_environment",
    "startup_apps_configuration",
    "bluetooth_service_configuration",
    "asoundrc_state",
    "enabled_services",
    "nonsecret_network_configuration",
    "robot_status",
    "startup_behavior",
)


def _validate_inventory(inventory: Mapping[str, Any]) -> dict[str, str]:
    if inventory.get("schema") != SCHEMA_VERSION:
        raise ValueError("Unknown inventory schema.")
    surfaces = inventory.get("surfaces")
    if not isinstance(surfaces, Mapping):
        raise ValueError("Inventory surfaces are missing.")
    missing = sorted(set(REQUIRED_SURFACES) - set(surfaces))
    extra = sorted(set(surfaces) - set(REQUIRED_SURFACES))
    if missing or extra:
        raise ValueError(f"Inventory surface mismatch; missing={missing}, extra={extra}")

    result: dict[str, str] = {}
    for name in REQUIRED_SURFACES:
        digest = surfaces[name]
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"{name} must be a SHA-256 digest of a canonical private record.")
        result[name] = digest
    return result


def compare_borrowed_condition(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare exact reviewed surfaces without touching either filesystem."""

    baseline = _validate_inventory(before)
    restored = _validate_inventory(after)
    differences = [
        {"surface": name, "before_sha256": baseline[name], "after_sha256": restored[name]}
        for name in REQUIRED_SURFACES
        if baseline[name] != restored[name]
    ]
    return {
        "schema": "reachy-stage4a-borrowed-condition-comparison-v1",
        "status": "MATCH" if not differences else "DIFFERENCE_REQUIRES_OWNER_REVIEW",
        "differences": differences,
        "all_reviewed_surfaces_match": not differences,
        "practical_equivalence_established": False,
        "literal_identity_claimed": False,
        "next_requirement": (
            "resolve every difference and obtain owner acceptance of the complete "
            "software, status, startup, and physical comparison"
        ),
        "excluded_residuals": ["logs", "timestamps", "ordinary_storage_writes", "physical_wear"],
        "robot_connections": 0,
        "robot_commands_sent": 0,
    }
