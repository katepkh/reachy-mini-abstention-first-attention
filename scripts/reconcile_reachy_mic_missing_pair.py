"""Exact failed-run metadata reconciliation; never a microphone test.

Default: help. --review-local reads saved numeric evidence only.
--reconcile-once is operator-run SSH: fresh read-only checks, then update only
the reviewed run's closeout.json. No installation, audio, routing, motion,
deletion, lock changes, automatic retry or recording authorization.
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
from scripts import run_reachy_mic_diagnostic as records
from scripts.prepare_reachy_mic_v3 import diagnostic_processes
from tools import reachy_mic_startup_probe as probe

SCHEMA = "reachy-mic-missing-pair-reconciliation-v1"
SESSION = "missing-pair-v3-01"
LOCAL = ROOT / "data/private/mic_closeout" / SESSION
REPORT_NAME = "review-20261003T064943-f5405f79.json"
REPORT_SHA = "e21a94ced936cf862cbef5e0c8c9e0ac0463165b685a25213acd5bb3755fc83c"
EXPECTED = "2e18a7c7b706590ce726c00c3e6e2c87523d0b75ddc2eb069eeb139b6615303a"
HELPER = Path("/home/pollen/reachy_mic_health_missing_pair_v3_01.py")
REMOTE = "/home/pollen/reachy-mic-health-runs-v2/run-missing-pair-v3-01"
REVIEW = LOCAL / "closeout-review-v1.json"
OUTPUT = ROOT / "data/private/mic_missing_pair_reconciliation" / SESSION
LOCK = Path("/tmp/reachy-mic-health.lock")
RECORD_NAMES = {"approval.json", "baseline.json", "closeout.json", "guard.json", "result.json"}
LOCAL_PINS = {
    REPORT_NAME: REPORT_SHA,
    "authorization.json": "7c8c7149d9728e1249083d422445c8525d41fc76915582ce1d5d3cdd03f1fac6",
    "deployment.json": "94e1da2b4803a5e94f304c9d82fd3b6aec5cb96bc4539cf92a7fa15ff94c7e62",
    "execution-exit.json": "bdb8609b1c618f7c374e23aab610eb7706aa2d0f796999851900fcc3e00d2cd9",
    "closeout.json": "5d46b6153591279d79c7a9836daac6b50a96ab9cff4ac81bc9d972aa1b09e9e9",
}
DEPENDENCIES = {
    "tools/reachy_mic_health_missing_pair.py": EXPECTED,
    "tools/reachy_mic_startup_probe.py": "1fd10ec27fb2b35ab6bb09ba585dd6def626e29ee1c41c8bd3aac04732e51162",
    "scripts/run_reachy_mic_diagnostic.py": "d38f202b9375f8bf542f991bfebdc52e7f442b839f15939e9108488f46267d9c",
    "scripts/prepare_reachy_mic_v3.py": "049d701e5f9acbc2153956e4da944b8e0ada25ea7a0169ae410d76fe590e7301",
}


def pinned(path, expected):
    raw = records.read_regular(path, 2 * 1024 * 1024)
    if hashlib.sha256(raw).hexdigest() != expected:
        raise RuntimeError("pinned_evidence_or_source_changed")
    return raw


def local_review():
    for name, expected in DEPENDENCIES.items():
        pinned(ROOT / name, expected)
    rows = records.local_inventory(LOCAL)
    if ({row["name"] for row in rows} - {REVIEW.name} != set(LOCAL_PINS)
            or any(row["kind"] != "file" for row in rows)):
        raise RuntimeError("unexpected_or_missing_local_entries")
    saved = {name: json.loads(pinned(LOCAL / name, expected)) for name, expected in LOCAL_PINS.items()}
    report = saved[REPORT_NAME]
    run = report["run"]
    result = run["records"]["result.json"]
    checks = {item["name"]: item for item in report["fresh_read_only_preflight"]["checks"]}
    baseline = run["records"]["baseline.json"]
    if (run["directory"] != REMOTE or run["record_errors"] or run["missing_records"]
            or run["stable_inventory"] is not True or set(run["records"]) != RECORD_NAMES
            or {r["name"] for r in run["inventory"]} != RECORD_NAMES
            or any(r["kind"] != "file" for r in run["inventory"])
            or result["pair_results"] != [] or result["status"] != "RESTORATION_UNVERIFIED"
            or run["records"]["closeout.json"]["before"] != []
            or run["records"]["closeout.json"]["unexpected"] != []
            or run["records"]["closeout.json"]["capture_exit_verified"] is not True
            or len(checks) != 17
            or [k for k, v in checks.items() if not v["ok"]] != ["previous_closeout"]
            or checks["previous_closeout"]["value"] != ["run-" + SESSION]
            or checks["parameters"]["value"] != baseline["parameters"]
            or checks["asoundrc"]["value"]["sha256"] != baseline["asoundrc_sha256"]
            or checks["mixer"]["value"] != baseline["mixer_sha256"]):
        raise RuntimeError("saved_failed_run_review_does_not_match")
    expected_before = report["local_inventory_before_export"]
    if [row for row in rows if row["name"] not in (REPORT_NAME, REVIEW.name)] != expected_before:
        raise RuntimeError("local_preexisting_metadata_changed")
    return {"schema": "reachy-mic-closeout-review-v1", "session": SESSION,
            "reviewed_utc": records.utc_now(), "status": "PENDING",
            "review_status": "LOCAL_REVIEW_COMPLETE_REMOTE_RECONCILIATION_PENDING",
            "reason": "fresh_robot_metadata_reconciliation_not_yet_run",
            "local_scope": str(LOCAL), "remote_scope": REMOTE,
            "evidence_sha256": LOCAL_PINS, "source_sha256": DEPENDENCIES,
            "run_outcome": result, "original_failure_preserved": True,
            "root_cause": "single_pair_USBBoard_write_indexes_absent_PAIRS_1_before_control_transfer",
            "diagnostic_capture_started": False,
            "diagnostic_USB_OUT_issued": False,
            "no_capture_or_write_basis": "pinned_source_control_flow_and_offline_actual_adapter_reproduction_not_live_USB_trace",
            "saved_baseline_match_observed": True,
            "saved_baseline_checked_utc": report["fresh_read_only_preflight"]["checked_utc"],
            "remote_inventory_before": [], "remote_inventory_after": run["inventory"],
            "local_inventory_before": saved["closeout.json"]["local_before"],
            "local_inventory_at_review": [r for r in rows if r["name"] != REVIEW.name],
            "unexpected_files": [], "deleted_files": [], "deletion_approval": None,
            "forensic_erasure_claim": False, "robot_return_final_check_complete": False,
            "execution_authorized": False}


def reconcile_record(helper, directory, expected):
    if directory.as_posix() != REMOTE or expected["directory"] != REMOTE or set(expected["records"]) != RECORD_NAMES:
        raise ProbeError("wrong_reconciliation_scope")
    helper["private_directory"](directory.parent)
    helper["private_directory"](directory)
    baseline = expected["records"]["baseline.json"]
    for _ in range(2):
        rows = helper["inventory"](directory)
        if rows != expected["inventory"]:
            raise ProbeError("run_inventory_changed")
        current = {name: json.loads(read_regular(directory / name)) for name in sorted(RECORD_NAMES)}
        if current != expected["records"]:
            raise ProbeError("run_records_changed")
        if inspect_lock()["owners"] or diagnostic_processes():
            raise ProbeError("diagnostic_process_or_lock_owner_present")
        # Exclude only this reviewed pending record; all other run gates remain.
        if helper["snapshot"](directory) != baseline:
            raise ProbeError("fresh_baseline_mismatch")
    if inspect_lock()["owners"] or diagnostic_processes() or helper["inventory"](directory) != rows:
        raise ProbeError("state_changed_before_reconciliation")
    closed = helper["finish_closeout"](directory, expected["records"]["closeout.json"],
                                       restoration_verified=True, capture_exit_verified=True)
    after = helper["inventory"](directory)
    unchanged = lambda items: [row for row in items if row["name"] != "closeout.json"]
    if (closed.get("status") != "CHECKED_NO_UNEXPECTED_FILES"
            or unchanged(after) != unchanged(rows)
            or json.loads(read_regular(directory / "closeout.json")) != closed):
        raise ProbeError("closeout_write_or_readback_unverified")
    return {"before": rows, "after": after, "original_closeout": expected["records"]["closeout.json"],
            "updated_closeout": closed, "baseline_observed_equal_twice": True,
            "restoration_basis": "reviewed_prewrite_precapture_abort_and_fresh_baseline_not_fault_recovery_test",
            "complete_process_isolation_verified": False, "deleted_files": []}


def remote_main():
    def emit(event, **value):
        print(json.dumps({"schema": SCHEMA, "event": event, "execution_authorized": False,
                          **value}, allow_nan=False), flush=True)
    try:
        raw = sys.stdin.buffer.read(200001)
        if len(raw) > 200000 or hashlib.sha256(raw).hexdigest() != REPORT_SHA:
            raise ProbeError("wrong_reviewed_report")
        report = json.loads(raw)
        helper = load_helper()
        emit("checking")
        outcome = reconcile_record(helper, Path(REMOTE), report["run"])
        emit("closeout_reconciled", **outcome)
        # Exclude no runs here. This does not confer execution authority.
        emit("after_preflight", report=helper["preflight_report"]())
        emit("finished", status="REPORT_REVIEW_REQUIRED", audio_capture=False,
             routing_writes=False, deletion_performed=False, helper_installed=False)
        return 0
    except Exception as error:
        emit("failed", **error_details(error))
        return 2


def remote_source():
    for name, expected in DEPENDENCIES.items():
        pinned(ROOT / name, expected)
    # Only these audited functions are sent; no USB adapter, capture or installer.
    source = "import hashlib,json,os,re,stat,subprocess,sys,time\nfrom pathlib import Path\n"
    for name, value in (("SCHEMA", SCHEMA), ("REPORT_SHA", REPORT_SHA), ("EXPECTED", EXPECTED),
                        ("REMOTE", REMOTE), ("RECORD_NAMES", RECORD_NAMES)):
        rendered = "set(" + repr(sorted(value)) + ")" if isinstance(value, set) else repr(value)
        source += name + " = " + rendered + "\n"
    source += "HELPER = Path(" + repr(HELPER.as_posix()) + ")\nLOCK = Path(" + repr(LOCK.as_posix()) + ")\n"
    # Enumerate every checked-in helper filename and its deployed session variants.
    source += "DIAGNOSTIC_NAMES = " + repr(sorted({"arecord", "reachy_mic_health.py", "reachy_mic_health_v2.py",
        "reachy_mic_health_v3.py", "reachy_mic_health_v3_candidate.py", "reachy_mic_health_missing_pair_v3_01.py",
        *["reachy_mic_health_two_pair_v3_" + str(i).zfill(2) + ".py" for i in range(1, 6)],
        *[p.name for p in (ROOT / "tools").glob("reachy_mic_health*.py")]})) + "\n"
    for function in (probe.ProbeError, probe.error_details, probe.read_regular, probe.load_helper,
                     probe.inspect_lock, diagnostic_processes, reconcile_record, remote_main):
        source += inspect.getsource(function) + "\n"
    return source + "\nraise SystemExit(remote_main())\n"


def reconcile_once():
    if not sys.stdin.isatty():
        raise RuntimeError("interactive_PowerShell_required")
    reviewed = local_review()
    saved = json.loads(records.read_regular(REVIEW))
    stable = lambda value: {k: v for k, v in value.items() if k != "reviewed_utc"}
    if stable(saved) != stable(reviewed):
        raise RuntimeError("matching_local_review_required")
    source = remote_source()
    OUTPUT.mkdir(parents=True, exist_ok=False)  # One attempt, including connection failures.
    source_sha = hashlib.sha256(source.encode()).hexdigest()
    records.write_new(OUTPUT / "started.json", {"schema": SCHEMA, "utc": records.utc_now(),
        "source_sha256": source_sha, "launcher_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "report_sha256": REPORT_SHA, "remote_scope": REMOTE, "status": "PENDING",
        "execution_authorized": False, "automatic_retry": False})
    encoded = base64.b64encode(source.encode()).decode("ascii")
    remote = shlex.join([records.PYTHON, "-I", "-B", "-c", "import base64;exec(base64.b64decode('" + encoded + "'))"])
    command = ["ssh", "-T", "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=10",
        "-o", "ConnectionAttempts=1", "-o", "ServerAliveInterval=10", "-o", "ServerAliveCountMax=2",
        "-o", "NumberOfPasswordPrompts=1", "pollen@192.168.1.251", remote]
    print("ONE metadata close-out reconciliation. Keep Reachy apps closed and phone paused.", flush=True)
    print("No Play cue or timed Enter. Only the SSH password may be requested.", flush=True)
    print("Checks current state; updates ONLY this failed run's closeout.json. No recording, routing, motion or deletion.", flush=True)
    code, error, output = None, None, b""
    try:
        outcome = subprocess.run(command, input=pinned(LOCAL / REPORT_NAME, REPORT_SHA),
                                 stdout=subprocess.PIPE, timeout=120)
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
            event = json.loads(line)
            if event.get("schema") != SCHEMA or event.get("execution_authorized") is not False:
                raise ValueError("contract")
            events.append(event)
        except (ValueError, AttributeError):
            invalid += 1
    records.write_new(OUTPUT / "report.json", {"schema": SCHEMA, "utc": records.utc_now(),
        "source_sha256": source_sha, "events": events, "invalid_lines": invalid,
        "ssh_exit_code": code, "transport_error": error, "automatic_retry": False,
        "execution_authorized": False, "local_closeout_status": "PENDING_REPORT_REVIEW"})
    print("REPORT SAVED: " + str(OUTPUT / "report.json"), flush=True)
    print("Send the report for review. Do not rerun this command or start a microphone test.", flush=True)
    return 0 if code == 0 and error is None and not invalid and events and events[-1]["event"] == "finished" else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--review-local", action="store_true")
    modes.add_argument("--reconcile-once", action="store_true")
    args = parser.parse_args(argv)
    if args.review_local:
        print(json.dumps(local_review(), indent=2, allow_nan=False))
        return 0
    if args.reconcile_once:
        return reconcile_once()
    parser.print_help()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        print("STOP: " + type(error).__name__ + ". Preserve output; do not retry.", file=sys.stderr)
        raise SystemExit(2)
