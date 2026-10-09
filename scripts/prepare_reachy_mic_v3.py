"""Reviewed failed-run close-out, then candidate installation and read-only preflight.

Default is help. --review-local prints a local evidence review without writing.
--reconcile-preflight is one operator-run SSH action: recheck the exact failed
run, update only its numeric closeout.json, install the unreleased candidate at
a new path, and call preflight only. No capture, USB access, routing, movement,
service changes, deletion, acquisition release or automatic retry.
"""

import argparse
import base64
import hashlib
import inspect
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import check_reachy_mic_retry as retry
from scripts import copy_reachy_mic_preflight as copy_v2
from scripts import run_reachy_mic_diagnostic as original
from tools.reachy_mic_startup_probe import ProbeError, inspect_lock, load_helper, read_regular, validate_scope

SCHEMA = "reachy-mic-v3-preparation-v1"
CANDIDATE_HASH = "cfa88aa8c30fb4a9f2d5b55f367117ceef6ab6a1cc5ea9e3acb90d72cb6dec87"
RETRY_HASH = "3673c1ede23aff347cbc01c7a9ec0565cda4c1a98c08690be9205f8fe8f16919"
FAILURE_HASH = "0968e68faf985561891f56ffa4edf3535d10027a234a3958298a9ee37ec3d3d0"
FAILURE_NAME = "review-20261002T103734-3c855d5b.json"
REVIEW = original.LOCAL / "closeout-review-v1.json"
OUTPUT = ROOT / "data/private/mic_v3_preflight" / original.SESSION
DESTINATION = "/home/pollen/reachy_mic_health_v3_candidate.py"
DIAGNOSTIC_NAMES = {"reachy_mic_health.py", "reachy_mic_health_v2.py", "reachy_mic_health_v3.py",
                    "reachy_mic_health_v3_candidate.py", "arecord"}


def pinned_json(path, expected):
    raw = original.read_regular(path, 2 * 1024 * 1024)
    if hashlib.sha256(raw).hexdigest() != expected:
        raise RuntimeError("reviewed_evidence_changed")
    return json.loads(raw)


def local_review():
    """Review only known numeric records and immediate-child file metadata."""
    directory, bindings = retry.reviewed_failure()
    if bindings["failure_review_sha256"] != FAILURE_HASH:
        raise RuntimeError("different_failed_run")
    failed = pinned_json(original.LOCAL / FAILURE_NAME, FAILURE_HASH)
    report = pinned_json(retry.OUTPUT.with_name(retry.OUTPUT.name + "-connect-replacement-01") / "report.json", RETRY_HASH)
    if (report.get("schema") != retry.SCHEMA or report.get("ssh_exit_code") != 0
            or report.get("invalid_lines") != 0 or report.get("transport_error") is not None
            or report.get("execution_authorized") is not False):
        raise RuntimeError("completed_read_only_verification_required")
    source_hash = hashlib.sha256(retry.remote_source()).hexdigest()
    if report.get("source_sha256") != source_hash:
        raise RuntimeError("reader_source_changed")
    events = report["events"]
    stages = {row["stage"]: row for row in events if row["event"] == "stage_finished"}
    if (not events or events[-1].get("event") != "finished" or events[-1].get("unavailable_stages") != []
            or any(row.get("candidate_sha256") != CANDIDATE_HASH for row in events)
            or any(row.get("status") != "observed" for row in stages.values())):
        raise RuntimeError("incomplete_reader_verification")
    run = failed["run"]
    baseline = run["records"]["baseline.json"]
    for name in ("baseline_before", "baseline_after"):
        if stages[name]["value"] != {**baseline, "matches_failed_run_baseline": True}:
            raise RuntimeError("baseline_not_equal")
    for name in ("startup_platform_checks", "robot_state_after"):
        if not stages[name]["value"] or not all(row["ok"] for row in stages[name]["value"]):
            raise RuntimeError("platform_not_ready")
    for key in retry.candidate.ROUTES:
        value = stages["usb_read_" + key]["value"]
        if value["values"] != baseline["parameters"][key] or value["status_bytes"] != [64, 0]:
            raise RuntimeError("reviewed_retry_result_changed")
    if (stages["failed_run_records"]["value"]["inventory"] != run["inventory"]
            or stages["run_inventory_after"]["value"] != {"inventory": run["inventory"], "unchanged": True}
            or run.get("record_errors") != [] or run.get("stable_inventory") is not True
            or run["records"]["closeout.json"].get("unexpected") != []):
        raise RuntimeError("remote_inventory_review_failed")
    allowed = {"authorization.json", "closeout.json", "execution-exit.json", FAILURE_NAME, REVIEW.name}
    rows = original.local_inventory(original.LOCAL)
    if (any(row["kind"] != "file" or row["name"] not in allowed for row in rows)
            or not allowed - {REVIEW.name} <= {row["name"] for row in rows}):
        raise RuntimeError("local_unexpected_or_missing_files")
    return {"schema": "reachy-mic-closeout-review-v1", "session": original.SESSION,
            "reviewed_utc": original.utc_now(),
            "review_status": "REVIEW_COMPLETE", "status": "PENDING",
            "reason": "fresh_robot_reconciliation_and_preflight_not_yet_run",
            "local_scope": str(original.LOCAL), "remote_scope": directory,
            "evidence": {**bindings, "retry_report_sha256": RETRY_HASH,
                         "candidate_sha256": CANDIDATE_HASH, "source_sha256": source_hash},
            "run_outcome": run["records"]["result.json"],
            "remote_ordinary_file_review": {"status": "CHECKED_NO_UNEXPECTED_FILES",
                "checked_utc": report["utc"], "inventory": run["inventory"], "unexpected": []},
            "local_inventory_at_review": [row for row in rows if row["name"] != REVIEW.name],
            "baseline_match_observed_before_and_after": True,
            "restoration_tested_under_fault": False, "guard_journal_missing_preserved": True,
            "deleted_files": [], "deletion_approval": None, "forensic_erasure_claim": False,
            "robot_return_final_check_complete": False, "execution_authorized": False,
            "next_step": "fresh exact-run check, numeric close-out update, new-path candidate preflight only"}


def diagnostic_processes(proc_root=Path("/proc")):
    """Bounded command-name check; export PIDs only, never command lines."""
    matches = []
    deadline = time.monotonic() + 3
    for count, entry in enumerate(proc_root.iterdir()):
        if count >= 4096 or time.monotonic() >= deadline:
            raise ProbeError("process_inventory_budget")
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            with (entry / "cmdline").open("rb") as stream:
                command = stream.read(65537)
        except (FileNotFoundError, ProcessLookupError):
            continue
        if len(command) > 65536:
            raise ProbeError("process_command_oversized")
        args = command.split(b"\0")
        if any(arg.decode("utf-8", "replace").rsplit("/", 1)[-1] in DIAGNOSTIC_NAMES for arg in args):
            matches.append(int(entry.name))
    return sorted(matches)


def fresh_failed_run(helper, directory, expected):
    baseline, rows = validate_scope(helper, directory)
    records = {name: json.loads(read_regular(directory / name)) for name in expected["records"]}
    if rows != expected["inventory"] or records != expected["records"] or baseline != expected["records"]["baseline.json"]:
        raise ProbeError("failed_run_changed")
    # Only the run being reviewed is omitted here; this does NOT clear a gate.
    # The final candidate preflight below omits no runs.
    if helper["snapshot"](directory) != baseline:
        raise ProbeError("fresh_baseline_mismatch")
    if inspect_lock()["owners"] or diagnostic_processes():
        raise ProbeError("diagnostic_process_or_lock_owner_present")
    if helper["inventory"](directory) != rows:
        raise ProbeError("inventory_changed_during_review")
    return baseline, rows


def reconcile_record(helper, directory, expected):
    baseline, rows = fresh_failed_run(helper, directory, expected)
    # The immutable local export already preserves the entire original PENDING
    # record. Never rewrite result.json, fabricate guard.json or remove locks.
    if helper["snapshot"](directory) != baseline:
        raise ProbeError("second_baseline_mismatch")
    if inspect_lock()["owners"] or diagnostic_processes() or helper["inventory"](directory) != rows:
        raise ProbeError("state_changed_before_reconciliation")
    closed = helper["finish_closeout"](directory, expected["records"]["closeout.json"],
                                       restoration_verified=True, capture_exit_verified=True)
    if closed.get("status") != "CHECKED_NO_UNEXPECTED_FILES":
        raise ProbeError("closeout_not_completed")
    after = helper["inventory"](directory)
    untouched = lambda items: [row for row in items if row["name"] != "closeout.json"]
    if untouched(after) != untouched(rows):
        raise ProbeError("non_closeout_file_changed")
    if json.loads(read_regular(directory / "closeout.json")) != closed:
        raise ProbeError("closeout_readback_mismatch")
    return {"before": rows, "after": after, "original_closeout": expected["records"]["closeout.json"],
            "updated_closeout": closed, "baseline_observed_equal": True,
            "restoration_basis": "reviewed_pre_capture_abort_and_fresh_baseline_checks_not_fault_recovery_test",
            "diagnostic_process_check": "none_observed", "deleted_files": []}


def remote_main():
    def emit(event, **value):
        print(json.dumps({"schema": PREPARATION_SCHEMA, "event": event,
                          "execution_authorized": False, **value}, allow_nan=False), flush=True)
    stage = "input"
    try:
        data = sys.stdin.buffer.read(200001)
        if len(data) > 200000:
            raise ProbeError("input_oversized")
        request = json.loads(data)
        payload = base64.b64decode(request["candidate"], validate=True)
        if hashlib.sha256(payload).hexdigest() != CANDIDATE_HASH:
            raise ProbeError("candidate_hash_changed")
        helper = load_helper()
        directory = Path(request["run"]["directory"])
        # Check the candidate before touching the close-out; never overwrite it.
        stage = "candidate_destination"
        target = Path(DESTINATION)
        if target.exists() or target.is_symlink():
            if hashlib.sha256(read_regular(target)).hexdigest() != CANDIDATE_HASH:
                raise ProbeError("candidate_destination_conflict")
        stage = "fresh_run_review_and_closeout"
        emit("stage_started", stage=stage)
        result = reconcile_record(helper, directory, request["run"])
        emit("closeout_reconciled", **result)
        stage = "candidate_installation"
        created = install_exact(DESTINATION, payload, CANDIDATE_HASH)
        verified = read_regular(Path(DESTINATION))
        if hashlib.sha256(verified).hexdigest() != CANDIDATE_HASH:
            raise ProbeError("installed_candidate_changed")
        namespace = {"__name__": "verified_candidate_preflight", "__file__": DESTINATION}
        exec(compile(verified, DESTINATION, "exec"), namespace)
        if namespace.get("EXECUTION_RELEASED") is not False:
            raise ProbeError("candidate_execution_release_changed")
        emit("candidate_installed", created=created, helper_sha256=CANDIDATE_HASH)
        stage = "candidate_preflight"
        report = namespace["preflight_report"]()
        emit("candidate_preflight", report=report)
        emit("finished", status="REVIEW_REQUIRED", closeout_record_reconciled=True,
             audio_capture=False, routing_writes=False, deletion_performed=False,
             candidate_execution_released=False)
        return 0
    except Exception as error:
        emit("failed", stage=stage, **error_details(error))
        return 2


def remote_source():
    base = (ROOT / "tools/reachy_mic_startup_probe.py").read_bytes()
    if hashlib.sha256(base).hexdigest() != retry.BASE_PROBE_HASH:
        raise RuntimeError("base_probe_source_changed")
    source = "import base64\n" + base.decode()
    source += "\n"  # Base module's main is inert under the namespace below.
    for key, value in (("PREPARATION_SCHEMA", SCHEMA), ("CANDIDATE_HASH", CANDIDATE_HASH),
                       ("DESTINATION", DESTINATION), ("DIAGNOSTIC_NAMES", sorted(DIAGNOSTIC_NAMES))):
        source += key + " = " + repr(value) + "\n"
    source += "\n".join(inspect.getsource(fn) for fn in
                         (copy_v2.install_exact, diagnostic_processes, fresh_failed_run, reconcile_record, remote_main))
    source += "\nraise SystemExit(remote_main())\n"
    return "exec(compile(" + repr(source) + ", '<reviewed-closeout-preflight>', 'exec'), {'__name__': 'reviewed_closeout_preflight'})"


def reconcile_preflight():
    if not sys.stdin.isatty():
        raise RuntimeError("interactive_PowerShell_required")
    review = local_review()
    stored = json.loads(original.read_regular(REVIEW))
    # Rechecking the same evidence later changes only this review's clock time.
    stable = lambda value: {key: item for key, item in value.items() if key != "reviewed_utc"}
    if not isinstance(stored.get("reviewed_utc"), str) or stable(stored) != stable(review):
        raise RuntimeError("matching_completed_local_review_required")
    failed = pinned_json(original.LOCAL / FAILURE_NAME, FAILURE_HASH)
    payload = original.read_regular(ROOT / "tools/reachy_mic_health_v3.py", 100000)
    if hashlib.sha256(payload).hexdigest() != CANDIDATE_HASH:
        raise RuntimeError("candidate_changed")
    source = remote_source()
    source_hash = hashlib.sha256(source.encode()).hexdigest()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    original.write_new(OUTPUT / "started.json", {"schema": SCHEMA, "utc": original.utc_now(),
        "source_sha256": source_hash, "review_sha256": hashlib.sha256(original.read_regular(REVIEW)).hexdigest(),
        "candidate_sha256": CANDIDATE_HASH, "execution_authorized": False, "automatic_retry": False,
        "status": "PENDING", "remote_scope": review["remote_scope"], "candidate_destination": DESTINATION})
    encoded = base64.b64encode(source.encode()).decode("ascii")
    remote = shlex.join([original.PYTHON, "-I", "-B", "-c", "import base64;exec(base64.b64decode('" + encoded + "'))"])
    command = ["ssh", "-T", "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=10", "-o",
               "ConnectionAttempts=1", "-o", "ServerAliveInterval=10", "-o", "ServerAliveCountMax=2",
               "-o", "NumberOfPasswordPrompts=1", "pollen@192.168.1.251", remote]
    print("ONE close-out reconciliation plus candidate preflight. Keep robot apps closed; phone paused.", flush=True)
    print("Writes only the reviewed run's numeric closeout.json and the new v3 candidate helper path.", flush=True)
    print("Original failure result/helper preserved. No audio, routing, motion, deletion or execution release.", flush=True)
    print("SSH password stays in the console. After any interruption, do not rerun; send the saved report.", flush=True)
    request = json.dumps({"run": failed["run"], "candidate": base64.b64encode(payload).decode("ascii")}).encode()
    code, error, output = None, None, b""
    try:
        outcome = subprocess.run(command, input=request, stdout=subprocess.PIPE, timeout=120)
        code, output = outcome.returncode, outcome.stdout
    except subprocess.TimeoutExpired as failure:
        error, output = "ssh_timeout", failure.output or b""
    except (OSError, KeyboardInterrupt) as failure:
        error = type(failure).__name__
    events, invalid = [], 0
    if len(output) > 2 * 1024 * 1024:
        error, output = "oversized_output", b""
    for line in output.splitlines():
        try:
            item = json.loads(line)
            if item.get("schema") != SCHEMA or item.get("execution_authorized") is not False:
                raise ValueError("contract")
            events.append(item)
        except (ValueError, UnicodeError, AttributeError):
            invalid += 1
    target = OUTPUT / "report.json"
    original.write_new(target, {"schema": SCHEMA, "utc": original.utc_now(), "source_sha256": source_hash,
        "events": events, "invalid_lines": invalid, "ssh_exit_code": code, "transport_error": error,
        "local_closeout_status": "PENDING_REPORT_REVIEW", "execution_authorized": False, "automatic_retry": False})
    print("REPORT SAVED: " + str(target), flush=True)
    print("Send the report for review. Do not repeat this command or start the two-pair diagnostic.", flush=True)
    return 0 if code == 0 and not invalid and events and events[-1].get("event") == "finished" else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--review-local", action="store_true")
    modes.add_argument("--reconcile-preflight", action="store_true")
    args = parser.parse_args(argv)
    if args.review_local:
        print(json.dumps(local_review(), indent=2, allow_nan=False))
        return 0
    if args.reconcile_preflight:
        return reconcile_preflight()
    parser.print_help()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        print("Preparation stopped: " + type(error).__name__ + ". Send output; do not retry.", file=sys.stderr)
        raise SystemExit(2)
