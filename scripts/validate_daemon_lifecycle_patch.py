#!/usr/bin/env python3
"""Validate the lifecycle patch against exact Reachy Mini v1.9.0 source.

This offline validator copies source to a temporary directory, applies the
repository patch there, compiles the two changed Python files, and verifies the
new option is threaded from CLI to backend construction and retained on daemon
restart.  It never starts a daemon or opens a robot/network connection.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATCH = PROJECT_ROOT / "patches/reachy-mini-v1.9.0-observation-lifecycle.patch"
EXPECTED_SOURCE_HASHES = {
    "src/reachy_mini/daemon/app/main.py": "99988d983b374a83e689ebd5fa75289034a00fc3b1c68553a1afc678228705fb",
    "src/reachy_mini/daemon/daemon.py": "24af8189b83eb07a56a1753a9a9f76e31061026a1bf691368498059a7896d156",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(source_root: Path, patch: Path = DEFAULT_PATCH) -> dict:
    source_root = source_root.resolve()
    patch = patch.resolve()
    pyproject = source_root / "pyproject.toml"
    if 'version = "1.9.0"' not in pyproject.read_text(encoding="utf-8"):
        raise ValueError("source_root is not Reachy Mini v1.9.0 source.")

    observed_hashes = {
        relative: _sha256(source_root / relative)
        for relative in EXPECTED_SOURCE_HASHES
    }
    if observed_hashes != EXPECTED_SOURCE_HASHES:
        raise AssertionError("v1.9.0 lifecycle source bytes do not match the reviewed tag archive.")

    with tempfile.TemporaryDirectory(prefix="reachy-lifecycle-patch-") as directory:
        patched_root = Path(directory) / "reachy_mini-1.9.0"
        shutil.copytree(source_root, patched_root)
        apply = subprocess.run(
            ["git", "-C", str(patched_root), "apply", "--check", str(patch)],
            capture_output=True,
            text=True,
        )
        if apply.returncode != 0:
            raise AssertionError(f"Patch does not apply cleanly:\n{apply.stderr}")
        subprocess.run(
            ["git", "-C", str(patched_root), "apply", str(patch)],
            check=True,
            capture_output=True,
            text=True,
        )

        main_path = patched_root / "src/reachy_mini/daemon/app/main.py"
        daemon_path = patched_root / "src/reachy_mini/daemon/daemon.py"
        main_source = main_path.read_text(encoding="utf-8")
        daemon_source = daemon_path.read_text(encoding="utf-8")
        compile(main_source, str(main_path), "exec")
        compile(daemon_source, str(daemon_path), "exec")

        required_main = (
            "reflash_motors_on_start: bool = True",
            '"--no-reflash-motors-on-start"',
            "reflash_motors_on_start=args.reflash_motors_on_start",
            '"--no-startup-app"',
            "args.autostart and args.startup_app_enabled and startup_app",
            '"--no-mdns"',
            "if args.mdns_enabled:",
        )
        required_daemon = (
            "reflash_motors_on_start: bool = True",
            "reflash_motors_on_start=reflash_motors_on_start",
            '"reflash_motors_on_start": reflash_motors_on_start',
            'self._start_params["reflash_motors_on_start"]',
            "if reflash_motors_on_start:",
            "reflash_motors_if_needed(serialport, dont_light_up=True)",
        )
        missing = [item for item in required_main if item not in main_source]
        missing += [item for item in required_daemon if item not in daemon_source]
        if missing:
            raise AssertionError(f"Patched lifecycle plumbing is incomplete: {missing}")

        reverse = subprocess.run(
            ["git", "-C", str(patched_root), "apply", "--reverse", "--check", str(patch)],
            capture_output=True,
            text=True,
        )
        if reverse.returncode != 0:
            raise AssertionError(f"Patched source does not reverse-check:\n{reverse.stderr}")

    return {
        "schema": "reachy-stage4a-observation-lifecycle-patch-validation-v1",
        "result": "PASS",
        "upstream_version": "1.9.0",
        "source_hashes": observed_hashes,
        "patch_sha256": _sha256(patch),
        "patch_applies": True,
        "patched_files_compile": True,
        "cli_to_backend_plumbing_verified": True,
        "restart_preserves_no_reflash_setting": True,
        "daemon_started": False,
        "robot_connections": 0,
        "robot_commands_sent": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--patch", type=Path, default=DEFAULT_PATCH)
    args = parser.parse_args()
    print(json.dumps(validate(args.source_root, args.patch), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
