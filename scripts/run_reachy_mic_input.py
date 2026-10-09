"""Prepared one-shot successor, missing-pair-v3-04. No standing live approval.

Default/help, --walkthrough and --inspect are offline. --run-once requires a separately
reviewed private authorization bound to this launcher and helper. It copies
new files, checks fresh preflight, then runs at most one interactive attempt.
--collect-only is remotely read-only and never resets either one-shot record.
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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import run_reachy_mic_diagnostic as legacy
from scripts.copy_reachy_mic_preflight import install_exact

SESSION = "missing-pair-v3-04"
LOCAL = ROOT / "data/private/mic_closeout" / SESSION
HELPER = ROOT / "tools/reachy_mic_health_input_run.py"
EXPECTED = "19e54ed1fae751b96565268688faa6048d11a8fac6e1336228efffd22c44d908"
SCHEMA = "reachy-mic-health-v3-session"
CANDIDATE_SHA = "cfa88aa8c30fb4a9f2d5b55f367117ceef6ab6a1cc5ea9e3acb90d72cb6dec87"
PRIOR_RECEIPT_SHA = "2118bf9284ff803d6e05c3eb20d65e3596a2b2038fe5b626cfb4fa4742d441f9"
PRIOR_PREFLIGHT_SHA = "1146870aabdf5a4bf557fec523af24deeacad85c919244901efb9552265de15f"
REMOTE = "/home/pollen/reachy_mic_health_input_v3_04.py"
REMOTE_AUTH = "/home/pollen/reachy_mic_input_v3_04_authorization.json"
REMOTE_ROOT = "/home/pollen/reachy-mic-health-runs-v2"
REMOTE_SCOPE = REMOTE_ROOT + "/run-" + SESSION
PRIOR_SCOPE = REMOTE_ROOT + "/run-vp38k4gc"
PREVIOUS_SCOPE = REMOTE_ROOT + "/run-two-pair-v3-01"
PREVIOUS_RECEIPT_SHA = "e218f2beb95b83185bfa03afa21ee0dc1b1b6ff6b47eaab77d419ac33158d6e8"
LATEST_SCOPE = REMOTE_ROOT + "/run-two-pair-v3-02"
LATEST_RECEIPT_SHA = "ef5355c2fed0484cc5610ebef1454c0157875e2f270f65eb163211e7cbd494ab"
RECENT_SCOPE = REMOTE_ROOT + "/run-two-pair-v3-03"
RECENT_RECEIPT_SHA = "89c3cda155ca80535c71280ed46d4897fd21c321c36ca01e3142d19bc0ced1fd"
PRECEDING_SCOPE = REMOTE_ROOT + "/run-two-pair-v3-04"
PRECEDING_RECEIPT_SHA = "1fd7869a6bfc8fadbbd48245f39303bc0b6196866fc93f80b0265a13422138b7"
LAST_SCOPE = REMOTE_ROOT + "/run-two-pair-v3-05"
LAST_RECEIPT_SHA = "d28a0cd6d44de0d9f3fa7bcfa83b8dc56ac7598f5218143c3374c1dc6582ee25"
REPAIRED_SCOPE = REMOTE_ROOT + "/run-missing-pair-v3-01"
REPAIRED_RECEIPT_SHA = "173d8a8f389654036ce748b66148d108e4c56a047cffc750858d9eec1169e965"
STIMULUS_SCOPE = REMOTE_ROOT + "/run-missing-pair-v3-02"
STIMULUS_RECEIPT_SHA = "6c0c129389ca1bdea876590f37dd2ae72dbc41efc3cbaa8d2faaa0d6b70d2e77"
ADAPTER_CANDIDATE_SHA = "f5145b92853e020b56e1635e905e760142d8563a153edb9dd7a0546ac01bdd62"
RECONCILIATION_SHA = "a59607be3a85474cf044b19e1e464f9a7495fe4c0288a34ab91eb660f37cccde"
INPUT_SCOPE = REMOTE_ROOT + "/run-missing-pair-v3-03"
INPUT_RECEIPT_SHA = "edf74fd7df7e32c4244204346f2952449d3f9cfd92ac732bcdbf9f38d9e5e74a"
INPUT_CANDIDATE_SHA = "a97f34778dda3f3f042d7a1f8493eedcc7de023953fd8bf5e46895f33dc0edff"
PREPARATION_REPORT = ROOT / "data/private/mic_input_preflight/20261008T181159-4bfae9cc/report.json"
PREPARATION_REPORT_SHA = "68a025b9e722ef9b6bf94bfdc46e15574030c000f88681fe758b5f98bdfb1450"
PREPARATION_LAUNCHER_SHA = "520f5a38b2b0eb2a990c0df9f231237d3b8310da3aa45d133b3122fe69504f98"
PYTHON = "/venvs/mini_daemon/bin/python"
ACK = ("APPROVE MIC INPUTS 2 AND 3 ONLY; NO OTHER AUDIO CLIENTS; RESTORE ROUTING; "
       "ACCEPT OS RESIDUALS; CHECK RUN FILES")
RECORD_KEYS = {name: set(keys) for name, keys in legacy.RECORD_KEYS.items()}
RECORD_KEYS["result.json"].add("failure_details")
read_regular = legacy.read_regular
write_new = legacy.write_new
local_inventory = legacy.local_inventory
utc_now = legacy.utc_now


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def private_local_directory(path):
    path = Path(path)
    info = path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or path.is_symlink()
            or getattr(info, "st_file_attributes", 0) & 0x400):
        raise RuntimeError("unsafe_local_directory")


def reviewed_input_preparation():
    """Saved source-bound prerequisite, never a substitute for fresh live checks."""
    payload = read_regular(PREPARATION_REPORT, 100000)
    if sha(payload) != PREPARATION_REPORT_SHA:
        raise RuntimeError("reviewed_input_preparation_changed")
    if sha(read_regular(ROOT / "scripts/prepare_reachy_mic_input.py", 100000)) != PREPARATION_LAUNCHER_SHA:
        raise RuntimeError("preparation_validator_changed")
    from scripts import prepare_reachy_mic_input as preparation
    preparation.sources()  # Pins the candidate, terminal check and transport dependencies.
    report = json.loads(payload)
    if (report.get("status") != "PREPARATION_OK_REVIEW_REQUIRED"
            or type(report.get("ssh_exit_code")) is not int or report["ssh_exit_code"] != 0
            or report.get("recording_authorized") is not False
            or report.get("candidate_sha256") != INPUT_CANDIDATE_SHA
            or report.get("launcher_sha256") != PREPARATION_LAUNCHER_SHA
            or not preparation.validate_report(report.get("remote"))):
        raise RuntimeError("reviewed_input_preparation_not_passed")
    return report


def prior_evidence():
    """Read only known numeric records; unknown entries are metadata only."""
    reviewed_input_preparation()
    root = ROOT / "data/private/mic_closeout"
    private_local_directory(root)
    entries = []
    with os.scandir(root) as scanned:
        for entry in scanned:
            if len(entries) >= 128:
                raise RuntimeError("local_run_registry_limit")
            entries.append(entry)
    for entry in entries:
        if entry.name == SESSION:
            continue
        directory = Path(entry.path)
        private_local_directory(directory)
        closed = json.loads(read_regular(directory / "closeout.json"))
        if (closed.get("status") not in ("CHECKED_NO_UNEXPECTED_FILES", "CLEANED_AND_RECHECKED")
                or closed.get("restoration_verified") is not True
                or closed.get("capture_exit_verified") is not True
                or closed.get("local_scope") != str(directory.resolve())):
            raise RuntimeError("previous_local_closeout_unresolved")
    receipts = {}
    for session, scope, expected_hash in (
            ("two-pair-v2-01", PRIOR_SCOPE, PRIOR_RECEIPT_SHA),
            ("two-pair-v3-01", PREVIOUS_SCOPE, PREVIOUS_RECEIPT_SHA),
            ("two-pair-v3-02", LATEST_SCOPE, LATEST_RECEIPT_SHA),
            ("two-pair-v3-03", RECENT_SCOPE, RECENT_RECEIPT_SHA),
            ("two-pair-v3-04", PRECEDING_SCOPE, PRECEDING_RECEIPT_SHA),
            ("two-pair-v3-05", LAST_SCOPE, LAST_RECEIPT_SHA),
            ("missing-pair-v3-01", REPAIRED_SCOPE, REPAIRED_RECEIPT_SHA),
            ("missing-pair-v3-02", STIMULUS_SCOPE, STIMULUS_RECEIPT_SHA),
            ("missing-pair-v3-03", INPUT_SCOPE, INPUT_RECEIPT_SHA)):
        prior = root / session
        private_local_directory(prior)
        payload = read_regular(prior / "closeout-final-v1.json")
        if sha(payload) != expected_hash:
            raise RuntimeError("reviewed_closeout_receipt_changed")
        receipt = json.loads(payload)
        rows = local_inventory(prior)
        expected_rows = receipt["local_after_check"]["inventory_at_check"]
        if [(r["name"], r["kind"]) for r in rows] != [(r["name"], r["kind"]) for r in expected_rows]:
            raise RuntimeError("previous_local_inventory_changed")
        # Each receipt's own after-check predates that receipt's final write.
        for actual, expected in zip(rows, expected_rows):
            if actual["name"] != "closeout-final-v1.json" and actual != expected:
                raise RuntimeError("previous_local_file_metadata_changed")
        closed = receipt["remote_closeout"]
        if (closed.get("scope") != scope
                or closed.get("status") not in ("CHECKED_NO_UNEXPECTED_FILES", "CLEANED_AND_RECHECKED")
                or closed.get("restoration_verified") is not True
                or closed.get("capture_exit_verified") is not True):
            raise RuntimeError("reviewed_remote_closeout_unresolved")
        inventory_key = "remote_after_inventory" if scope == REPAIRED_SCOPE else "remote_final_inventory"
        receipts[scope] = {"inventory": receipt[inventory_key], "closeout": closed}
    preflight = read_regular(ROOT / "data/private/mic_v3_preflight/two-pair-v2-01/report.json")
    if sha(preflight) != PRIOR_PREFLIGHT_SHA:
        raise RuntimeError("reviewed_candidate_preflight_changed")
    if sha(read_regular(ROOT / "tools/reachy_mic_health_v3.py", 100000)) != CANDIDATE_SHA:
        raise RuntimeError("preserved_candidate_changed")
    if sha(read_regular(ROOT / "tools/reachy_mic_health_missing_pair_fixed.py", 100000)) != ADAPTER_CANDIDATE_SHA:
        raise RuntimeError("repaired_adapter_candidate_changed")
    reconciliation = read_regular(ROOT / "data/private/mic_missing_pair_reconciliation/missing-pair-v3-01/report.json", 100000)
    if sha(reconciliation) != RECONCILIATION_SHA:
        raise RuntimeError("reviewed_reconciliation_changed")
    return receipts


def helper_namespace(path=HELPER):
    payload = read_regular(path, 100000)
    if sha(payload) != EXPECTED:
        raise RuntimeError("session_helper_changed")
    namespace = {"__name__": "verified_session_helper", "__file__": str(path)}
    exec(compile(payload, str(path), "exec"), namespace)
    return namespace


def approval_contract(directory):
    """Expected fields, NOT an approval generator. No CLI writes this file."""
    return {"schema": "reachy-mic-local-session-authorization-v1", "session": SESSION,
            "helper_sha256": EXPECTED, "launcher_sha256": sha(read_regular(Path(__file__), 100000)),
            "transport_dependencies": {p: sha(read_regular(ROOT / p, 100000)) for p in
                ("scripts/run_reachy_mic_diagnostic.py", "scripts/copy_reachy_mic_preflight.py")},
            "prior_closeout_sha256": PRIOR_RECEIPT_SHA, "prior_preflight_sha256": PRIOR_PREFLIGHT_SHA,
            "previous_session_closeout_sha256": PREVIOUS_RECEIPT_SHA,
            "latest_session_closeout_sha256": LATEST_RECEIPT_SHA,
            "recent_session_closeout_sha256": RECENT_RECEIPT_SHA,
            "preceding_session_closeout_sha256": PRECEDING_RECEIPT_SHA,
            "last_session_closeout_sha256": LAST_RECEIPT_SHA,
            "repaired_session_closeout_sha256": REPAIRED_RECEIPT_SHA,
            "stimulus_session_closeout_sha256": STIMULUS_RECEIPT_SHA,
            "input_session_closeout_sha256": INPUT_RECEIPT_SHA,
            "input_candidate_sha256": INPUT_CANDIDATE_SHA,
            "reviewed_input_preparation_sha256": PREPARATION_REPORT_SHA,
            "preparation_validator_sha256": PREPARATION_LAUNCHER_SHA,
            "adapter_candidate_sha256": ADAPTER_CANDIDATE_SHA,
            "reconciliation_report_sha256": RECONCILIATION_SHA,
            "local_scope": str(directory.resolve()), "remote_scope": REMOTE_SCOPE,
            "new_helper_path": REMOTE, "new_authorization_path": REMOTE_AUTH,
            "deployment_approved": True, "run_limit": 1,
            "session_authorization": helper_namespace()["required_authorization"]()}


def authorization(directory):
    private_local_directory(directory.parent)
    private_local_directory(directory)
    approved = json.loads(read_regular(directory / "authorization.json", 16384))
    required = approval_contract(directory)
    # JSON equality alone treats True as 1. Canonical text preserves types.
    if json.dumps(approved, sort_keys=True) != json.dumps(required, sort_keys=True):
        raise RuntimeError("matching_fresh_private_authorization_required")
    prior_evidence()
    return approved


def begin_local(directory):
    approved = authorization(directory)
    before = local_inventory(directory)
    if [(r["name"], r["kind"]) for r in before] != [("authorization.json", "file")]:
        raise RuntimeError("session_spent_or_unexpected_local_entry")
    write_new(directory / "closeout.json", {
        "schema": "reachy-mic-local-closeout-v1", "session": SESSION, "status": "PENDING",
        "reason": "one_shot_workflow_started_requires_after_review", "started_utc": utc_now(),
        "helper_sha256": EXPECTED, "local_scope": str(directory.resolve()),
        "remote_scope": REMOTE_SCOPE, "remote_root": REMOTE_ROOT, "local_before": before,
        "automatic_retry": False, "deleted_files": [], "forensic_erasure_claim": False})
    return approved


def remote_namespace():
    return helper_namespace(Path(REMOTE))


def remote_deploy():
    packet = json.loads(sys.stdin.buffer.read(150001))
    payload = base64.b64decode(packet["helper"], validate=True)
    if sha(payload) != EXPECTED:
        raise RuntimeError("helper_payload_changed")
    # Compile the verified standalone module without invoking any hardware mode.
    helper = {"__name__": "checked_session", "__file__": REMOTE}
    exec(compile(payload, REMOTE, "exec"), helper)
    helper["require_robot_account"]()
    helper["private_directory"](Path(REMOTE_ROOT))
    if Path(REMOTE_SCOPE).exists() or Path(REMOTE_SCOPE).is_symlink():
        raise RuntimeError("remote_session_already_spent")
    if helper["pending_runs"]():
        raise RuntimeError("previous_remote_closeout_unresolved")
    if set(packet["prior_runs"]) != {PRIOR_SCOPE, PREVIOUS_SCOPE, LATEST_SCOPE, RECENT_SCOPE, PRECEDING_SCOPE, LAST_SCOPE, REPAIRED_SCOPE, STIMULUS_SCOPE, INPUT_SCOPE}:
        raise RuntimeError("previous_remote_scope_mismatch")
    for scope in (PRIOR_SCOPE, PREVIOUS_SCOPE, LATEST_SCOPE, RECENT_SCOPE, PRECEDING_SCOPE, LAST_SCOPE, REPAIRED_SCOPE, STIMULUS_SCOPE, INPUT_SCOPE):
        prior = Path(scope)
        helper["private_directory"](prior)
        reviewed = packet["prior_runs"][scope]
        if (helper["inventory"](prior) != reviewed["inventory"]
                or json.loads(read_regular(prior / "closeout.json")) != reviewed["closeout"]):
            raise RuntimeError("previous_remote_closeout_changed")
    install_exact(REMOTE, payload, EXPECTED)
    helper = remote_namespace()
    report = helper["preflight_report"]()
    # Preflight failure never installs the session capability or starts a guard.
    if report["machine_checks_passed"] is True:
        required = helper["required_authorization"]()
        if json.dumps(packet["authorization"], sort_keys=True) != json.dumps(required, sort_keys=True):
            raise RuntimeError("remote_approval_mismatch")
        approval = json.dumps(required, sort_keys=True).encode()
        install_exact(REMOTE_AUTH, approval, sha(approval))
        helper["require_execution_authorization"]()
    print(json.dumps(report, allow_nan=False), flush=True)


def remote_run():
    helper = remote_namespace()
    helper["require_execution_authorization"]()
    helper["private_directory"](Path(REMOTE_ROOT))
    if Path(REMOTE_SCOPE).exists() or Path(REMOTE_SCOPE).is_symlink():
        raise RuntimeError("remote_session_already_spent")
    if helper["pending_runs"]():
        raise RuntimeError("previous_remote_closeout_unresolved")
    os.execv(PYTHON, [PYTHON, "-I", "-B", REMOTE, "--execute"])


def remote_collect():
    helper = remote_namespace()
    helper["require_robot_account"]()
    helper["private_directory"](Path(REMOTE_ROOT))
    directory = Path(REMOTE_SCOPE)
    run = None
    if directory.exists() or directory.is_symlink():
        helper["private_directory"](directory)
        run = export_records(directory, helper)
    print(json.dumps({"schema": "reachy-mic-session-export-v1", "session": SESSION,
                      "helper_sha256": EXPECTED, "root": REMOTE_ROOT, "run": run,
                      "checked_utc": utc_now(), "audio_exported": False, "deletion_performed": False,
                      "fresh_read_only_preflight": helper["preflight_report"]()}, allow_nan=False))


def remote_source(mode):
    if mode not in ("deploy", "run", "collect"):
        raise ValueError("invalid_remote_mode")
    constants = {key: globals()[key] for key in (
        "EXPECTED", "SESSION", "SCHEMA", "REMOTE", "REMOTE_AUTH", "REMOTE_ROOT",
        "REMOTE_SCOPE", "PRIOR_SCOPE", "PREVIOUS_SCOPE", "LATEST_SCOPE", "RECENT_SCOPE", "PRECEDING_SCOPE", "LAST_SCOPE", "REPAIRED_SCOPE", "STIMULUS_SCOPE", "INPUT_SCOPE", "PYTHON", "ACK", "RECORD_KEYS")}
    source = ("import base64, hashlib, json, os, re, stat, sys\nfrom pathlib import Path\n"
              "from datetime import datetime, timezone\n")
    source += "\n".join(key + " = " + repr(value) for key, value in constants.items()) + "\n"
    functions = (sha, read_regular, utc_now, install_exact, remote_namespace)
    source += "\n".join(inspect.getsource(f) for f in functions) + "\n"
    # Explicitly rebind the default: no laptop path in the transported function.
    source += inspect.getsource(helper_namespace).replace("path=HELPER", "path=REMOTE") + "\n"
    if mode == "collect":
        source += inspect.getsource(legacy.export_records).replace("reachy-mic-health-v2", SCHEMA) + "\n"
    action = {"deploy": remote_deploy, "run": remote_run, "collect": remote_collect}[mode]
    return source + inspect.getsource(action) + "\n" + action.__name__ + "()\n"


def ssh_command(mode):
    encoded = base64.b64encode(remote_source(mode).encode()).decode("ascii")
    remote = shlex.join([PYTHON, "-I", "-B", "-c", "import base64;exec(base64.b64decode('" + encoded + "'))"])
    return ["ssh", "-t" if mode == "run" else "-T", "-o", "StrictHostKeyChecking=yes",
            "-o", "ConnectTimeout=10", "-o", "ConnectionAttempts=1", "-o",
            "NumberOfPasswordPrompts=1", "-o", "ServerAliveInterval=15", "-o",
            "ServerAliveCountMax=4", "pollen@192.168.1.251", remote]


def validate_preflight(payload):
    if len(payload) > 262144:
        raise RuntimeError("oversized_preflight")
    report = json.loads(payload)
    if (report.get("schema") != SCHEMA or report.get("helper_sha256") != EXPECTED
            or report.get("mode") != "READ_ONLY" or report.get("execution_authorized") is not False
            or report.get("consumer_isolation_verified") is not False
            or not isinstance(report.get("checks"), list) or len(report["checks"]) != 17
            or report.get("machine_checks_passed") is not True
            or any(item.get("ok") is not True for item in report["checks"])):
        raise RuntimeError("fresh_preflight_not_passed_no_execution")
    return report


def collect(directory, runner=subprocess.run):
    private_local_directory(directory)
    record = json.loads(read_regular(directory / "closeout.json"))
    if (record.get("session") != SESSION or record.get("helper_sha256") != EXPECTED
            or record.get("remote_scope") != REMOTE_SCOPE):
        raise RuntimeError("missing_matching_local_run_record")
    print("Read-only collection of this exact run's numeric files and metadata. No retry or deletion.", flush=True)
    outcome = runner(ssh_command("collect"), stdout=subprocess.PIPE, timeout=120)
    if outcome.returncode or len(outcome.stdout) > 2 * 1024 * 1024:
        raise RuntimeError("collection_failed_closeout_pending")
    bundle = json.loads(outcome.stdout)
    if (bundle.get("schema") != "reachy-mic-session-export-v1" or bundle.get("session") != SESSION
            or bundle.get("helper_sha256") != EXPECTED or bundle.get("root") != REMOTE_ROOT
            or bundle.get("audio_exported") is not False or bundle.get("deletion_performed") is not False
            or (bundle.get("run") is not None and bundle["run"].get("directory") != REMOTE_SCOPE)):
        raise RuntimeError("unexpected_export_scope")
    bundle["local_inventory_before_export"] = local_inventory(directory)
    path = directory / ("review-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8] + ".json")
    write_new(path, bundle)
    print("REVIEW REPORT SAVED: " + str(path), flush=True)
    print("Close-out remains PENDING review. Do not repeat or resume the pilot.", flush=True)
    return path


def walkthrough():
    """Offline overview, not live cues. No input, connection or file changes."""
    print("OVERVIEW ONLY - keep the phone PAUSED. This overview does not request playback.")
    print("Use the SAME EXISTING CLIP at its beginning, volume 50%, at the front mark, one metre away, microphone height.")
    print("Before this command, verify the clip is audible from the PHONE BUILT-IN SPEAKER; disconnect headphones, then rewind and PAUSE. Keep it paused now.")
    print("The existing live start confirmation also confirms that speaker check; no extra timed prompt is added.")
    print("After login and fresh checks, one explicit start confirmation begins quiet measurement for inputs 2 and 3 ONLY.")
    print("There is no READY prompt, no extra Enter to start quiet, and NO second pair.")
    print("Only at the LIVE cue: first tap Play on the phone, then IMMEDIATELY press Enter ONCE in PowerShell within 10 seconds.")
    print("Phone playback alone is not confirmation. Do not wait for the clip to finish. The live run will acknowledge ENTER RECEIVED.")
    print("STAY IN POWERSHELL until the final report; send screenshots only after the attempt ends.")
    print("After this single quiet/playback measurement, pause the phone at the PAUSE cue. No between-pair action is needed.")
    print("Otherwise do not press Enter. Keep the clip playing until the live pause instruction.")
    print("An interrupted attempt remains spent. Pause playback, preserve the report, and do not rerun or reboot.")


def run_once(directory, runner=subprocess.run):
    if not sys.stdin.isatty():
        raise RuntimeError("interactive_PowerShell_required")
    approved = begin_local(directory)  # Check spent/approval before any overview; durable before SSH.
    walkthrough()  # Informational only; the robot-side start acknowledgement is the sole Pair-1 start input.
    receipts = prior_evidence()
    packet = {"helper": base64.b64encode(read_regular(HELPER, 100000)).decode("ascii"),
              "authorization": approved["session_authorization"],
              "prior_runs": receipts}
    print("ONE missing-pair-only attempt: inputs 2 and 3 (" + SESSION + "). Old helpers and records are preserved.", flush=True)
    print("Keep apps/pages closed, head resting and phone paused. No motion commands.", flush=True)
    print("SSH may request your password for deployment, the run, and read-only collection.", flush=True)
    print("Follow the phone prompts; do not press Enter early. On disconnect, do not reboot or retry.", flush=True)
    stage = "deployment_preflight"
    try:
        deployed = runner(ssh_command("deploy"), input=json.dumps(packet).encode(), stdout=subprocess.PIPE, timeout=120)
        # Preserve numeric report even on a failed machine check; no audio output on this connection.
        raw = deployed.stdout or b""
        if len(raw) <= 262144:
            try:
                parsed = json.loads(raw)
            except (ValueError, UnicodeError):
                parsed = None
        else:
            parsed = None
        write_new(directory / "deployment.json", {"session": SESSION, "utc": utc_now(),
            "ssh_exit_code": deployed.returncode, "report": parsed, "output_unavailable": parsed is None})
        if deployed.returncode:
            raise RuntimeError("deployment_failed_no_execution")
        validate_preflight(raw)
        stage = "interactive_execution"
        outcome = runner(ssh_command("run"), timeout=300)
        write_new(directory / "execution-exit.json", {"session": SESSION, "utc": utc_now(),
            "ssh_run_exit_code": outcome.returncode})
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        write_new(directory / "interrupted.json", {"session": SESSION, "utc": utc_now(), "stage": stage,
            "error_type": type(error).__name__, "outcome": "REVIEW_REQUIRED", "automatic_retry": False})
        raise
    collect(directory, runner)
    return outcome.returncode


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--inspect", action="store_true", help="offline provenance check; does not approve or start")
    modes.add_argument("--walkthrough", action="store_true", help="offline phone-cue walkthrough; no files or connection")
    modes.add_argument("--run-once", action="store_true")
    modes.add_argument("--collect-only", action="store_true")
    args = parser.parse_args(argv)
    if args.walkthrough:
        walkthrough()
        return 0
    if args.inspect:
        prior_evidence()
        helper_namespace()
        print(json.dumps({"session": SESSION, "mode": "OFFLINE_PREPARATION", "helper_sha256": EXPECTED,
                          "authorization_present": (LOCAL / "authorization.json").exists(),
                          "execution_authorized": False, "remote_scope": REMOTE_SCOPE,
                          "local_scope": str(LOCAL)}, indent=2))
        return 0
    if args.collect_only:
        collect(LOCAL)
        return 0
    if args.run_once:
        return run_once(LOCAL)
    parser.print_help()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        print("STOP: " + (str(error) or type(error).__name__), file=sys.stderr)
        print("No automatic retry. Preserve records; keep phone paused and apps closed for review.", file=sys.stderr)
        print("Private close-out scope: " + str(LOCAL), file=sys.stderr)
        raise SystemExit(2)
