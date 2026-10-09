"""One operator-approved two-pair run, then read-only private result collection.

No helper deployment or modification. Default: help, with no connection.
--collect-only cannot start capture, change routing, or clear the one-run latch.
Passwords and the interactive diagnostic go directly through the SSH console.
"""

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys
import uuid


ROOT = Path(__file__).resolve().parents[1]
SESSION = "two-pair-v2-01"
LOCAL = ROOT / "data/private/mic_closeout" / SESSION
EXPECTED = "01b14cb7ac76c67c81bba12a11509dafc97c8eac8b28ceada0982cf1a8bc0e7d"
PREFLIGHT = "reachy-mic-preflight-v2-2026-10-02T10-01-37-055700Z-7a1e3f49.json"
PREFLIGHT_HASH = "86c2d6425456fe2d575c21220ff370185851033158c7d72aff3c431e021214f5"
REMOTE = "/home/pollen/reachy_mic_health_v2.py"
REMOTE_ROOT = "/home/pollen/reachy-mic-health-runs-v2"
PYTHON = "/venvs/mini_daemon/bin/python"
ACK = ("APPROVE TWO MIC PAIRS; NO OTHER AUDIO CLIENTS; RESTORE ROUTING; "
       "ACCEPT OS RESIDUALS; CHECK RUN FILES")
RECORD_KEYS = {
    "baseline.json": {"asoundrc_sha256", "mixer_sha256", "parameters", "helper_sha256", "privacy_profile"},
    "approval.json": {"scope", "helper_sha256"},
    "guard.json": {"schema", "baseline", "events", "dirty", "terminal", "restoration"},
    "result.json": {"schema", "pair_results", "status", "helper_sha256", "retains_raw_media",
                    "privacy_profile", "os_residuals_possible", "error_type", "reason",
                    "route_restoration", "ordinary_file_closeout"},
    "closeout.json": {"schema", "run_id", "started_utc", "scope", "helper_sha256", "privacy_profile",
                      "before", "status", "reason", "restoration_verified", "capture_exit_verified",
                      "content_inspected", "forensic_erasure_claim", "deleted_files", "checked_utc",
                      "after", "unexpected"},
}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def read_regular(path, limit=262144):
    """Bounded regular-file read; refuse links/reparse points and changed files."""
    path = Path(path)
    before = path.lstat()
    if (not stat.S_ISREG(before.st_mode) or path.is_symlink()
            or getattr(before, "st_file_attributes", 0) & 0x400 or before.st_size > limit):
        raise RuntimeError("unsafe_or_oversized_file")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as source:
        info = os.fstat(source.fileno())
        if (not stat.S_ISREG(info.st_mode) or (info.st_dev, info.st_ino) != (before.st_dev, before.st_ino)
                or (hasattr(os, "getuid") and info.st_uid != os.getuid())):
            raise RuntimeError("file_identity_or_owner_changed")
        payload = source.read(limit + 1)
        after = os.fstat(source.fileno())
    if len(payload) > limit or (info.st_size, info.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError("file_changed_or_oversized")
    return payload


def verified_helper(path):
    payload = read_regular(path, 100000)
    if hashlib.sha256(payload).hexdigest() != EXPECTED:
        raise RuntimeError("helper_hash_changed_no_execution")
    namespace = {"__name__": "verified_mic_helper", "__file__": str(path)}
    # The pinned module's import path is standard-library-only and has no I/O.
    exec(compile(payload, str(path), "exec"), namespace)
    return namespace


def export_records(directory, helper):
    """Only known numeric/control JSON; unexpected entries get metadata only."""
    before = helper["inventory"](directory)
    records, errors = {}, []
    for row in before:
        name = row["name"]
        if name not in RECORD_KEYS or row["kind"] != "file":
            continue
        try:
            item = json.loads(read_regular(directory / name))
            if not isinstance(item, dict) or not set(item) <= RECORD_KEYS[name]:
                raise ValueError("record_shape")
            if name in ("baseline.json", "approval.json", "result.json", "closeout.json"):
                if item.get("helper_sha256") != EXPECTED:
                    raise ValueError("record_identity")
            if name == "approval.json" and item != {"scope": ACK, "helper_sha256": EXPECTED}:
                raise ValueError("approval_identity")
            if name in ("result.json", "guard.json") and item.get("schema") != "reachy-mic-health-v2":
                raise ValueError("record_schema")
            if name == "closeout.json" and (
                    item.get("schema") != "reachy-mic-closeout-v1"
                    or item.get("scope") != str(directory) or item.get("run_id") != directory.name):
                raise ValueError("closeout_scope")
            records[name] = item
        except (OSError, ValueError, RuntimeError):
            errors.append({"file": name, "reason": "record_unavailable_or_invalid"})
    after = helper["inventory"](directory)
    return {"directory": str(directory), "inventory": after, "records": records,
            "record_errors": errors, "stable_inventory": before == after,
            "missing_records": sorted(set(RECORD_KEYS) - set(records))}


def remote_main(mode):
    helper = verified_helper(REMOTE)
    helper["require_robot_account"]()
    root = Path(REMOTE_ROOT)
    if root.exists() or root.is_symlink():
        helper["private_directory"](root)
        with os.scandir(root) as entries:
            names = []
            for entry in entries:
                if len(names) >= 2:
                    raise RuntimeError("unexpected_multiple_runs_review_required")
                names.append(entry.name)
    else:
        names = []
    if mode == "run":
        # This authorization covers the FIRST run only; never silently repeat.
        if names:
            raise RuntimeError("run_root_not_empty_no_new_attempt")
        print("Verified helper; robot run-folder baseline is empty. No capture yet.", flush=True)
        os.execv(PYTHON, [PYTHON, "-I", "-B", REMOTE, "--execute"])
        return
    if mode != "collect":
        raise RuntimeError("invalid_mode")
    if len(names) > 1 or any(not re.fullmatch(r"run-[a-zA-Z0-9_-]{1,64}", name) for name in names):
        raise RuntimeError("ambiguous_run_scope_review_required")
    bundle = {"schema": "reachy-mic-run-export-v1", "checked_utc": utc_now(),
              "helper_sha256": EXPECTED, "root": REMOTE_ROOT, "run": None,
              "audio_exported": False, "deletion_performed": False}
    if names:
        directory = root / names[0]
        helper["private_directory"](directory)
        bundle["run"] = export_records(directory, helper)
    # Fresh status/configuration reads only; never opens capture or USB control.
    bundle["fresh_read_only_preflight"] = helper["preflight_report"]()
    print(json.dumps(bundle, allow_nan=False))


def remote_source(mode):
    if mode not in ("run", "collect"):
        raise ValueError("invalid_mode")
    constants = {"EXPECTED": EXPECTED, "REMOTE": REMOTE, "REMOTE_ROOT": REMOTE_ROOT,
                 "PYTHON": PYTHON, "ACK": ACK, "RECORD_KEYS": RECORD_KEYS}
    source = ("import os, sys, stat, json, hashlib, re\nfrom pathlib import Path\n"
              "from datetime import datetime, timezone\n")
    source += "\n".join(key + " = " + repr(value) for key, value in constants.items()) + "\n"
    source += "\n".join(inspect.getsource(function) for function in
                        (utc_now, read_regular, verified_helper, export_records, remote_main))
    return source + "\nremote_main(" + repr(mode) + ")\n"


def ssh_command(mode):
    encoded = base64.b64encode(remote_source(mode).encode()).decode("ascii")
    code = "import base64;exec(base64.b64decode('" + encoded + "'))"
    remote = shlex.join([PYTHON, "-I", "-B", "-c", code])
    return ["ssh", "-t" if mode == "run" else "-T", "-o", "StrictHostKeyChecking=yes",
            "-o", "ConnectTimeout=10", "-o", "ConnectionAttempts=1", "-o",
            "NumberOfPasswordPrompts=1", "-o", "ServerAliveInterval=15", "-o",
            "ServerAliveCountMax=4", "pollen@192.168.1.251", remote]


def local_inventory(directory):
    rows = []
    with os.scandir(directory) as entries:
        for entry in entries:
            if len(rows) >= 128:
                raise RuntimeError("local_inventory_limit")
            info = entry.stat(follow_symlinks=False)
            kind = ("link" if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400
                    else "file" if stat.S_ISREG(info.st_mode) else "other")
            rows.append({"name": entry.name, "kind": kind, "bytes": info.st_size, "mtime_ns": info.st_mtime_ns})
    return sorted(rows, key=lambda row: row["name"])


def write_new(path, value):
    with Path(path).open("x", encoding="utf-8") as output:
        json.dump(value, output, indent=2, allow_nan=False)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())


def authorization(directory):
    # No command-line bypass or authorization generation in this launcher.
    for parent in (directory, directory.parent):
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400 or parent.is_symlink():
            raise RuntimeError("unsafe_local_scope")
    approved = json.loads(read_regular(directory / "authorization.json", 8192))
    required = {"schema": "reachy-mic-operator-authorization-v1", "session": SESSION,
                "helper_sha256": EXPECTED, "preflight_sha256": PREFLIGHT_HASH,
                "run_limit": 1, "remote_inventory_root": REMOTE_ROOT,
                "local_inventory_scope": str(directory.resolve()),
                "routing_and_transient_capture_approved": True, "consumer_isolation_confirmed": True,
                "physical_setup_confirmed": True, "os_residuals_accepted": True,
                "metadata_inventory_approved": True}
    if any(type(approved.get(key)) is not type(value) or approved.get(key) != value
           for key, value in required.items()):
        raise RuntimeError("matching_private_approval_required")
    if hashlib.sha256(read_regular(ROOT / "tools/reachy_mic_health.py", 100000)).hexdigest() != EXPECTED:
        raise RuntimeError("local_helper_changed")
    payload = read_regular(ROOT / "data/private/mic_preflight" / PREFLIGHT)
    if hashlib.sha256(payload).hexdigest() != PREFLIGHT_HASH or json.loads(payload).get("machine_checks_passed") is not True:
        raise RuntimeError("reviewed_preflight_changed")
    return approved


def begin_local(directory):
    authorization(directory)
    before = local_inventory(directory)
    if before and [(row["name"], row["kind"]) for row in before] != [("authorization.json", "file")]:
        raise RuntimeError("session_already_attempted_or_unexpected_file_do_not_repeat")
    record = {"schema": "reachy-mic-local-closeout-v1", "session": SESSION, "status": "PENDING",
              "reason": "execution_may_start_outcome_requires_review", "started_utc": utc_now(),
              "helper_sha256": EXPECTED, "local_scope": str(directory.resolve()),
              "remote_root": REMOTE_ROOT, "remote_scope": "one_new_run_directory",
              "local_before": before, "automatic_retry": False, "deleted_files": []}
    write_new(directory / "closeout.json", record)  # Durable BEFORE opening SSH.


def decode_export(payload):
    if len(payload) > 2 * 1024 * 1024:
        raise RuntimeError("oversized_export")
    bundle = json.loads(payload)
    if (not isinstance(bundle, dict) or bundle.get("schema") != "reachy-mic-run-export-v1"
            or bundle.get("helper_sha256") != EXPECTED or bundle.get("root") != REMOTE_ROOT
            or bundle.get("audio_exported") is not False or bundle.get("deletion_performed") is not False):
        raise RuntimeError("unexpected_export_contract")
    run = bundle.get("run")
    if run is not None and (not isinstance(run, dict) or not re.fullmatch(
            re.escape(REMOTE_ROOT) + r"/run-[a-zA-Z0-9_-]{1,64}", run.get("directory", ""))):
        raise RuntimeError("unexpected_remote_scope")
    return bundle


def collect(directory, runner=subprocess.run):
    # This mode is READ ONLY remotely and cannot reset the local one-run latch.
    record = json.loads(read_regular(directory / "closeout.json"))
    if record.get("session") != SESSION or record.get("helper_sha256") != EXPECTED:
        raise RuntimeError("missing_session_record")
    print("Collecting known numeric records and file metadata only. SSH may ask for the password again.", flush=True)
    outcome = runner(ssh_command("collect"), stdout=subprocess.PIPE, timeout=120)
    if outcome.returncode:
        raise RuntimeError("collection_failed_closeout_remains_pending")
    bundle = decode_export(outcome.stdout)
    exit_path = directory / "execution-exit.json"
    bundle["execution_exit"] = json.loads(read_regular(exit_path)) if exit_path.exists() else None
    bundle["local_inventory_before_export"] = local_inventory(directory)
    name = "review-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8] + ".json"
    target = directory / name
    write_new(target, bundle)
    # Preserve PENDING until the results, restoration, and both scopes are reviewed.
    print("REVIEW REPORT SAVED: " + str(target), flush=True)
    print("Close-out remains PENDING review. Do not repeat the run or resume the pilot.", flush=True)
    return target


def run_once(directory, runner=subprocess.run):
    if not sys.stdin.isatty():
        raise RuntimeError("interactive_PowerShell_console_required")
    begin_local(directory)
    print("ONE approved two-pair diagnostic. Keep all robot apps/pages closed and the phone paused.", flush=True)
    print("Follow the remote prompts; do not press Enter early. This is not a motion test.", flush=True)
    print("Password stays in SSH. A dropped connection is NOT proof of restoration; do not reboot or retry.", flush=True)
    # No stdout/stderr capture: remote PTY retains prompts, input and Ctrl+C behavior.
    try:
        outcome = runner(ssh_command("run"), timeout=300)
    except (OSError, subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        write_new(directory / "execution-interrupted.json", {
            "session": SESSION, "utc": utc_now(), "error_type": type(error).__name__,
            "outcome": "UNKNOWN", "restoration_verified": False, "automatic_retry": False})
        raise
    write_new(directory / "execution-exit.json", {"session": SESSION, "utc": utc_now(),
                                                 "ssh_run_exit_code": outcome.returncode})
    collect(directory, runner)
    return outcome.returncode


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--run-once", action="store_true")
    modes.add_argument("--collect-only", action="store_true")
    args = parser.parse_args(argv)
    if not args.run_once and not args.collect_only:
        parser.print_help()
        return 0
    if args.collect_only:
        collect(LOCAL)
        return 0
    return run_once(LOCAL)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        print("STOP: " + (str(error) or type(error).__name__), file=sys.stderr)
        print("Do not repeat acquisition or reboot. Keep the phone paused and apps closed.", file=sys.stderr)
        print("Private review/close-out folder: " + str(LOCAL), file=sys.stderr)
        raise SystemExit(2)
