"""One automatic Linux-terminal self-check plus read-only microphone readiness.

--prepare-once copies only the execution-blocked candidate to a new fixed path.
No audio capture, route/motor/OS change, approval installation or deletion.
Phone stays paused. Only the SSH password may be requested; no timed Enter.
--inspect and default/help are offline. Results require review, not automatic
acquisition. Interrupted checks are preserved; there is no automatic retry.
"""

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import inspect
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import run_reachy_mic_missing_pair_speaker as prior
from scripts.copy_reachy_mic_preflight import install_exact
from scripts.check_reachy_keyboard import safe_local_directory

HELPER = ROOT / "tools/reachy_mic_health_input_candidate.py"
EXPECTED = "a97f34778dda3f3f042d7a1f8493eedcc7de023953fd8bf5e46895f33dc0edff"
SELFCHECK = ROOT / "tools/reachy_mic_input_selfcheck.py"
SELFCHECK_SHA = "3c76fa8a2a0d427a24d5592f6334a2c2626193a645426bcd11cdd2e02871e51a"
REMOTE = "/home/pollen/reachy_mic_health_input_candidate.py"
REMOTE_ROOT = "/home/pollen/reachy-mic-health-runs-v2"
LATEST_SCOPE = REMOTE_ROOT + "/run-missing-pair-v3-03"
LATEST_RECEIPT_SHA = "edf74fd7df7e32c4244204346f2952449d3f9cfd92ac732bcdbf9f38d9e5e74a"
LOCAL_ROOT = ROOT / "data/private/mic_input_preflight"
PYTHON = "/venvs/mini_daemon/bin/python"
PREFLIGHT_CHECKS = {
    "swap_metadata", "core_pattern", "tool_arecord", "tool_timeout", "tool_amixer", "tool_fuser",
    "audio_card", "asoundrc", "asoundrc_contract", "source_audio_doa.py", "source_audio_control_utils.py",
    "capture_owner", "robot_status", "current_app", "previous_closeout", "parameters", "mixer",
}
DEPENDENCIES = {
    "scripts/run_reachy_mic_missing_pair_speaker.py": "1bbdbd895322a71730da260b10d4ae1f628bd10f144f3b6021ad8e546c282f24",
    "scripts/run_reachy_mic_diagnostic.py": "d38f202b9375f8bf542f991bfebdc52e7f442b839f15939e9108488f46267d9c",
    "scripts/copy_reachy_mic_preflight.py": "0fef4e2647bf4b63a47ac6b80db6991baba9df072f7a8646a44ceb199ff60617",
    "scripts/check_reachy_keyboard.py": "88a7deed87ecbea663b054b5bdf5ce935593536ab7390c08ceb0c3612db582cc",
}
read_regular = prior.read_regular
write_new = prior.write_new
utc_now = prior.utc_now


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def sources():
    for relative, expected in DEPENDENCIES.items():
        if sha(read_regular(ROOT / relative, 100000)) != expected:
            raise RuntimeError("preparation_dependency_changed")
    helper = read_regular(HELPER, 100000)
    checker = read_regular(SELFCHECK, 20000)
    if sha(helper) != EXPECTED or sha(checker) != SELFCHECK_SHA:
        raise RuntimeError("preparation_source_changed")
    return helper, checker


def previous_runs():
    # All eight historical scopes plus the latest spent attempt, never just
    # absence of a pending file. All reads are known numeric records/metadata.
    records = prior.prior_evidence()
    directory = ROOT / "data/private/mic_closeout/missing-pair-v3-03"
    payload = read_regular(directory / "closeout-final-v1.json")
    if sha(payload) != LATEST_RECEIPT_SHA:
        raise RuntimeError("latest_closeout_receipt_changed")
    receipt = json.loads(payload)
    actual = prior.local_inventory(directory)
    expected = receipt["local_after_check"]["inventory_at_check"]
    if [(r["name"], r["kind"]) for r in actual] != [(r["name"], r["kind"]) for r in expected]:
        raise RuntimeError("latest_closeout_inventory_changed")
    for a, b in zip(actual, expected):
        if a["name"] != "closeout-final-v1.json" and a != b:
            raise RuntimeError("latest_closeout_metadata_changed")
    closed = receipt["remote_closeout"]
    if (closed.get("scope") != LATEST_SCOPE or closed.get("status") != "CHECKED_NO_UNEXPECTED_FILES"
            or closed.get("restoration_verified") is not True or closed.get("capture_exit_verified") is not True):
        raise RuntimeError("latest_remote_closeout_unresolved")
    records[LATEST_SCOPE] = {"inventory": receipt["remote_final_inventory"], "closeout": closed}
    return records


def remote_prepare():
    report = {"schema": "reachy-input-preparation-v1", "candidate_sha256": EXPECTED,
              "selfcheck_sha256": SELFCHECK_SHA, "status": "INCOMPLETE", "audio_opened": False,
              "settings_changed": False, "execution_authorized": False,
              "candidate_path": REMOTE, "candidate_present_verified": False}
    stage = "verify_packet"
    try:
        packet = json.loads(sys.stdin.buffer.read(180001))
        payload = base64.b64decode(packet["helper"], validate=True)
        checker = base64.b64decode(packet["selfcheck"], validate=True)
        if sha(payload) != EXPECTED or sha(checker) != SELFCHECK_SHA:
            raise RuntimeError("source_identity_changed")
        helper = {"__name__": "verified_candidate", "__file__": REMOTE}
        exec(compile(payload, REMOTE, "exec"), helper)
        if helper["EXECUTION_RELEASED"] is not False:
            raise RuntimeError("candidate_must_remain_unreleased")
        helper["require_robot_account"]()
        stage = "previous_closeouts"
        helper["private_directory"](Path(REMOTE_ROOT))
        if helper["pending_runs"]():
            raise RuntimeError("previous_remote_closeout_unresolved")
        if set(packet["prior_runs"]) != set(EXPECTED_SCOPES):
            raise RuntimeError("previous_remote_scope_mismatch")
        for scope, reviewed in packet["prior_runs"].items():
            path = Path(scope)
            helper["private_directory"](path)
            if (helper["inventory"](path) != reviewed["inventory"]
                    or json.loads(read_regular(path / "closeout.json")) != reviewed["closeout"]):
                raise RuntimeError("previous_remote_closeout_changed")
        report["previous_scopes_verified"] = len(EXPECTED_SCOPES)
        stage = "synthetic_terminal"
        probe = {"__name__": "automatic_terminal_check"}
        exec(compile(checker, "<automatic-terminal-check>", "exec"), probe)
        report["terminal"] = probe["terminal_selfcheck"](helper["TerminalInputReader"])
        if report["terminal"]["status"] != "PASS":
            raise RuntimeError("synthetic_terminal_not_passed")
        stage = "install_unreleased_candidate"
        report["candidate_created"] = install_exact(REMOTE, payload, EXPECTED)
        report["candidate_present_verified"] = True
        stage = "read_only_preflight"
        report["preflight"] = helper["preflight_report"]()
        report["status"] = "PREPARATION_OK" if report["preflight"]["machine_checks_passed"] is True else "CHECKS_FAILED"
    except Exception as error:
        report["status"] = "FAILED"
        report["failed_stage"] = stage
        report["error_type"] = type(error).__name__
        # Never retain raw exception output, passwords or input contents.
    report["checked_utc"] = utc_now()
    print(json.dumps(report, allow_nan=False), flush=True)


def remote_source(scopes):
    constants = {"EXPECTED": EXPECTED, "SELFCHECK_SHA": SELFCHECK_SHA,
                 "REMOTE": REMOTE, "REMOTE_ROOT": REMOTE_ROOT, "EXPECTED_SCOPES": sorted(scopes)}
    source = "import base64, hashlib, json, os, stat, sys\nfrom pathlib import Path\nfrom datetime import datetime, timezone\n"
    source += "\n".join(key + " = " + repr(value) for key, value in constants.items()) + "\n"
    source += "\n".join(inspect.getsource(fn) for fn in (sha, read_regular, utc_now, install_exact, remote_prepare))
    return source + "\nremote_prepare()\n"


def ssh_command(scopes):
    encoded = base64.b64encode(remote_source(scopes).encode()).decode("ascii")
    code = "import base64;exec(base64.b64decode('" + encoded + "'))"
    return ["ssh", "-T", "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=10",
            "-o", "ConnectionAttempts=1", "-o", "NumberOfPasswordPrompts=1", "-o",
            "ServerAliveInterval=15", "-o", "ServerAliveCountMax=4", "pollen@192.168.1.251",
            shlex.join([PYTHON, "-I", "-B", "-c", code])]


def validate_report(report):
    if (not isinstance(report, dict) or report.get("schema") != "reachy-input-preparation-v1"
            or report.get("candidate_sha256") != EXPECTED or report.get("selfcheck_sha256") != SELFCHECK_SHA
            or report.get("candidate_path") != REMOTE
            or any(report.get(k) is not False for k in ("audio_opened", "settings_changed", "execution_authorized"))):
        raise RuntimeError("preparation_report_identity_invalid")
    if report.get("status") != "PREPARATION_OK":
        return False
    terminal, flight = report.get("terminal", {}), report.get("preflight", {})
    for section in (terminal, flight):
        if (not isinstance(section, dict) or not isinstance(section.get("checks"), list)
                or any(not isinstance(x, dict) or not isinstance(x.get("name"), str)
                       for x in section["checks"])):
            raise RuntimeError("preparation_report_shape_invalid")
    names = {"one_enter", "split_blank_line", "duplicate_enters_visible", "text_classified_not_saved", "canonical_eof"}
    checks = terminal.get("checks", [])
    if (report.get("previous_scopes_verified") != 9 or report.get("candidate_present_verified") is not True
            or terminal.get("schema") != "reachy-input-pty-selfcheck-v1"
            or terminal.get("input_source") != "isolated_synthetic_pty"
            or terminal.get("status") != "PASS" or len(checks) != 5
            or {x.get("name") for x in checks} != names
            or any(x.get("ok") is not True or x.get("reader_exited") is not True
                   or x.get("terminal_modes_unchanged") is not True for x in checks)
            or any(terminal.get(k) is not False for k in ("physical_keyboard_tested", "capture_load_tested", "audio_opened", "settings_changed"))
            or flight.get("schema") != "reachy-mic-health-v3-session" or flight.get("mode") != "READ_ONLY"
            or flight.get("helper_sha256") != EXPECTED or flight.get("machine_checks_passed") is not True
            or flight.get("execution_authorized") is not False or flight.get("consumer_isolation_verified") is not False
            or len(flight.get("checks", [])) != 17
            or {x.get("name") for x in flight["checks"]} != PREFLIGHT_CHECKS
            or any(x.get("ok") is not True for x in flight["checks"])):
        raise RuntimeError("preparation_checks_incomplete")
    return True


def prepare_once(root=LOCAL_ROOT, runner=subprocess.run):
    if not sys.stdin.isatty():
        raise RuntimeError("interactive_PowerShell_required")
    helper, checker = sources()
    records = previous_runs()
    packet = {"helper": base64.b64encode(helper).decode(), "selfcheck": base64.b64encode(checker).decode(),
              "prior_runs": records}
    payload = json.dumps(packet).encode()
    if len(payload) > 180000:
        raise RuntimeError("preparation_packet_too_large")
    root = safe_local_directory(root)
    directory = root / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8])
    directory.mkdir()
    initial = {"schema": "reachy-input-local-preparation-v1", "started_utc": utc_now(),
               "candidate_sha256": EXPECTED, "selfcheck_sha256": SELFCHECK_SHA,
               "launcher_sha256": sha(read_regular(Path(__file__), 100000)),
               "status": "STARTED", "automatic_retry": False, "recording_authorized": False}
    write_new(directory / "started.json", initial)
    print("AUTOMATIC PREPARATION ONLY. Keep phone PAUSED and Reachy apps/pages closed.", flush=True)
    print("No Play cue or timed Enter. Only the SSH password may be requested.", flush=True)
    print("Synthetic terminal checks, new execution-blocked helper copy, then read-only readiness. No recording or routing.", flush=True)
    report = dict(initial)
    code = 2
    try:
        outcome = runner(ssh_command(records), input=payload, stdout=subprocess.PIPE, timeout=150)
        report["ssh_exit_code"] = outcome.returncode
        raw = outcome.stdout or b""
        if len(raw) > 262144:
            raise RuntimeError("preparation_output_too_large")
        remote = json.loads(raw)
        report["remote"] = remote
        if outcome.returncode:
            raise RuntimeError("connection_or_remote_failure")
        passed = validate_report(remote)
        report["status"] = "PREPARATION_OK_REVIEW_REQUIRED" if passed else "PREPARATION_FAILED_REVIEW_REQUIRED"
        code = 0 if passed else 2
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        report["status"] = "INTERRUPTED_OR_FAILED_REVIEW_REQUIRED"
        report["error_type"] = type(error).__name__
    finally:
        report["finished_utc"] = utc_now()
        write_new(directory / "report.json", report)
        print("REPORT SAVED: " + str(directory / "report.json"), flush=True)
        print("Send the report for review. Do not run an old microphone launcher or restart this check automatically.", flush=True)
    return code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--inspect", action="store_true")
    mode.add_argument("--prepare-once", action="store_true")
    args = parser.parse_args(argv)
    if args.inspect:
        sources()
        records = previous_runs()
        print(json.dumps({"mode": "OFFLINE", "previous_scopes_verified": len(records),
                          "candidate_sha256": EXPECTED, "recording_authorized": False}))
        return 0
    if args.prepare_once:
        return prepare_once()
    parser.print_help()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as error:
        print("STOP: " + str(error), file=sys.stderr)
        raise SystemExit(2)
