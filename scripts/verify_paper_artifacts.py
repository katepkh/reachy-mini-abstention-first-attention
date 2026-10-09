#!/usr/bin/env python3
"""Run the complete offline paper/evidence/software verification suite.

The command intentionally excludes live acquisition and hardware validators. It
opens no network, camera, microphone, or robot connection.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "requirements-test.lock"
LOG = ROOT / "evidence" / "analysis" / "paper_artifact_verification_v1.txt"
SIDECAR = LOG.with_suffix(LOG.suffix + ".sha256")
ENVIRONMENT = ROOT / "evidence" / "manifests" / "reproducibility_environment_v1.json"
ENVIRONMENT_SIDECAR = ENVIRONMENT.with_suffix(ENVIRONMENT.suffix + ".sha256")

CHECKS = (
    ("canonical project alignment", ("scripts/check_project_alignment.py",)),
    ("public frozen evidence", ("scripts/verify_results.py",)),
    ("generated public result summary", ("scripts/regenerate_public_results.py", "--check")),
    ("Stage 3V trial-level robustness", ("scripts/run_stage3v_robustness.py", "--check")),
    ("AV-synchrony falsification design", ("scripts/freeze_av_synchrony_protocol.py", "--check")),
    ("AV-synchrony synthetic faults", ("scripts/run_av_synchrony_faults.py", "--check")),
    ("AV-synchrony V1 pilot design", ("scripts/freeze_av_synchrony_pilot_protocol.py", "--check")),
    ("AV-synchrony V1 synthetic dry run", ("scripts/run_av_synchrony_pilot_dry_run.py", "--check")),
    ("AV-synchrony V2 pilot design", ("scripts/freeze_av_synchrony_pilot_v2_protocol.py", "--check")),
    ("AV-synchrony V2 synthetic dry run", ("scripts/run_av_synchrony_pilot_v2_dry_run.py", "--check")),
    ("AV-synchrony confirmation design", ("scripts/freeze_av_synchrony_confirmation_protocol.py", "--check")),
    ("M5 fused-shadow software contract", ("scripts/run_fused_shadow_contract.py", "--check")),
    ("joint-shadow pilot execution contract", ("scripts/freeze_joint_shadow_pilot_execution.py", "--check")),
    ("generated manuscript tables and figures", ("scripts/build_paper_artifacts.py", "--check")),
    ("temporary-daemon offline fault rehearsal", ("scripts/run_offline_fault_rehearsal.py", "--check")),
    ("Stage 4A successor review packet", ("scripts/build_successor_review_manifest.py", "--check")),
    ("curated software tests", ("-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py")),
)


def _normalised_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def verify_locked_environment() -> int:
    checked = 0
    for raw in LOCK.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "==" not in line:
            raise RuntimeError(f"Unpinned lock entry: {line}")
        name, expected = line.split("==", 1)
        observed = importlib.metadata.version(name)
        if observed != expected:
            raise RuntimeError(f"Dependency mismatch for {name}: expected {expected}, observed {observed}")
        checked += 1
    if checked < 20:
        raise RuntimeError("Dependency lock unexpectedly contains fewer than 20 packages.")
    return checked


def verify_environment_manifest(dependency_count: int) -> None:
    content = ENVIRONMENT.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    expected_sidecar = f"{digest}  {ENVIRONMENT.name}\n".encode("ascii")
    if ENVIRONMENT_SIDECAR.read_bytes() != expected_sidecar:
        raise RuntimeError("Reproducibility-environment SHA-256 sidecar changed.")
    payload = json.loads(content)
    lock = payload["dependency_lock"]
    if lock["sha256"] != hashlib.sha256(LOCK.read_bytes()).hexdigest():
        raise RuntimeError("Dependency lock does not match the environment manifest.")
    if lock["package_count"] != dependency_count:
        raise RuntimeError("Dependency count does not match the environment manifest.")
    project = payload["project_metadata"]
    if project["sha256"] != hashlib.sha256((ROOT / project["path"]).read_bytes()).hexdigest():
        raise RuntimeError("pyproject.toml does not match the environment manifest.")
    browser = payload["browser_instrument_assets"]
    if browser["protocol_manifest_sha256"] != hashlib.sha256(
        (ROOT / browser["protocol_manifest"]).read_bytes()
    ).hexdigest():
        raise RuntimeError("V2 browser protocol does not match the environment manifest.")


def run_checks() -> tuple[list[str], int]:
    # Runner patch releases vary; the locked dependencies and checks establish
    # whether this CPython minor release reproduces the public artifact suite.
    lines = [
        "reachy-paper-artifact-verification-v1",
        f"python={sys.version_info.major}.{sys.version_info.minor}",
        "network_connections=0",
        "robot_connections=0",
        "camera_or_microphone_capture=0",
    ]
    dependency_count = verify_locked_environment()
    verify_environment_manifest(dependency_count)
    lines.append(f"PASS locked dependency environment ({dependency_count} packages)")
    lines.append("PASS hardware/software reproducibility environment manifest")
    tests_run = 0
    for label, arguments in CHECKS:
        command = (sys.executable, *arguments)
        completed = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        output = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
        if completed.returncode:
            raise RuntimeError(
                f"{label} failed with exit code {completed.returncode}\n{output}"
            )
        match = re.search(r"Ran (\d+) tests? in", output)
        if match:
            tests_run = int(match.group(1))
            lines.append(f"PASS {label} ({tests_run} tests)")
        else:
            lines.append(f"PASS {label}")
    lines.append("all_checks_passed=true")
    return lines, tests_run


def render_log() -> bytes:
    lines, tests_run = run_checks()
    if tests_run == 0:
        raise RuntimeError("Software-test count was not observed in unittest output.")
    return ("\n".join(lines) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write-log", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        rendered = render_log()
        sidecar = f"{hashlib.sha256(rendered).hexdigest()}  {LOG.name}\n".encode("ascii")
        if args.write_log:
            LOG.parent.mkdir(parents=True, exist_ok=True)
            LOG.write_bytes(rendered)
            SIDECAR.write_bytes(sidecar)
            print(f"WROTE: {LOG.relative_to(ROOT)}")
            print(f"WROTE: {SIDECAR.relative_to(ROOT)}")
            print(rendered.decode("utf-8"), end="")
            return 0
        if not LOG.is_file() or LOG.read_bytes() != rendered:
            print("FAIL: committed paper verification log is missing or stale.", file=sys.stderr)
            return 1
        if not SIDECAR.is_file() or SIDECAR.read_bytes() != sidecar:
            print("FAIL: paper verification-log SHA-256 sidecar is missing or stale.", file=sys.stderr)
            return 1
        print(rendered.decode("utf-8"), end="")
        print("PASS: committed verification log and sidecar are current.")
        return 0
    except (OSError, RuntimeError, importlib.metadata.PackageNotFoundError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
