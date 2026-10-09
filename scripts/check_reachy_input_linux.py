"""One automatic Linux software check; no audio, playback, robot API or motion.

Default/help and --inspect stay offline. --check-once asks only for the SSH
password in the console, then exercises generated data without operator cues.
No complete diagnostic module is sent or installed; no live permission exists.
"""
import argparse
import ast
import hashlib
import json
import math
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import check_reachy_keyboard as local

HELPER = ROOT / "tools/reachy_mic_health_observed_candidate.py"
HELPER_SHA = "0194421ce766de35cbf936901896b69187c8c9bfe506adecc3b3bef4cf8d4823"
HARNESS = ROOT / "tools/reachy_input_linux_selfcheck.py"
HARNESS_SHA = "e9524ea814c9c6d56e1eb222d2360f8becf19367c4248d183f5d101efeb13b80"
DEPENDENCIES = {
    "scripts/check_reachy_keyboard.py": "88a7deed87ecbea663b054b5bdf5ce935593536ab7390c08ceb0c3612db582cc",
    "scripts/run_reachy_mic_diagnostic.py": "d38f202b9375f8bf542f991bfebdc52e7f442b839f15939e9108488f46267d9c",
}
DEFINITIONS = {"Stop", "Stats", "TerminalInputReader", "terminal_input_metadata",
               "InputObservation", "ObservedSelector", "ObservedTerminalInputReader",
               "capture_pair", "stop_own_capture"}
CONSTANTS = {"RATE", "ROUTES", "PAIRS"}
RUN_ID = "observed-linux-20261008-01"
LOCAL_ROOT = ROOT / "data/private/mic_input_linux_check"
PYTHON = "/venvs/mini_daemon/bin/python"
PREFIX = "LINUX_SYNTHETIC_RESULT "


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source_bundle():
    for relative, expected in DEPENDENCIES.items():
        if sha(local.read_regular(ROOT / relative, 100000)) != expected:
            raise RuntimeError("local_dependency_changed")
    helper = local.read_regular(HELPER, 100000)
    harness = local.read_regular(HARNESS, 30000)
    if sha(helper) != HELPER_SHA or sha(harness) != HARNESS_SHA:
        raise RuntimeError("synthetic_source_changed")
    source = helper.decode("utf-8")
    tree = ast.parse(source)
    selected, found = [], set()
    for node in tree.body:
        name = None
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in DEFINITIONS:
            name = node.name
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id in CONSTANTS):
            name = node.targets[0].id
        if name is not None:
            if name in found:
                raise RuntimeError("duplicate_selected_definition")
            selected.append(ast.get_source_segment(source, node))
            found.add(name)
    if found != DEFINITIONS | CONSTANTS:
        raise RuntimeError("missing_selected_definition")
    definitions = "\n\n".join(selected)
    text = harness.decode("utf-8")
    payload = (text + "\nraise SystemExit(remote_main(" + repr(definitions) + "))\n").encode("utf-8")
    if len(payload) > 100000:
        raise RuntimeError("payload_too_large")
    return {"payload": payload, "definitions": definitions, "harness": text,
            "definitions_sha256": sha(definitions.encode("utf-8"))}


def ssh_command(payload):
    # Source is sent on stdin: avoid the Windows command-line length limit.
    # Exact length plus SHA binds the in-memory program before any execution.
    bootstrap = ("import sys,hashlib;data=sys.stdin.buffer.read(" + str(len(payload) + 1) + ");"
                 "assert len(data)==" + str(len(payload)) + ";"
                 "assert hashlib.sha256(data).hexdigest()==" + repr(sha(payload)) + ";"
                 "exec(compile(data,'<no-audio-linux-check>','exec'))")
    return ["ssh", "-T", "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=10",
            "-o", "ConnectionAttempts=1", "-o", "NumberOfPasswordPrompts=1",
            "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=4",
            "pollen@192.168.1.251", shlex.join([PYTHON, "-I", "-B", "-c", bootstrap])]


def validated_result(output, bundle, returncode):
    """Save only bounded, known numeric/control vocabulary; never arbitrary stdout."""
    if not isinstance(output, bytes) or len(output) > 65536:
        raise ValueError("invalid_result_size")
    lines = output.decode("utf-8").splitlines()
    if len(lines) != 1 or not lines[0].startswith(PREFIX):
        raise ValueError("missing_or_unexpected_output")
    result = json.loads(lines[0][len(PREFIX):])
    # Only literal control strings from the pinned definitions/harness are
    # allowed, including dictionary keys. All other leaves must be numeric,
    # boolean or null. Passwords, free-form text and raw buffers are rejected.
    known = {node.value for source in (bundle["definitions"], bundle["harness"])
             for node in ast.walk(ast.parse(source))
             if isinstance(node, ast.Constant) and isinstance(node.value, str)}

    def validate(value, depth=0):
        if depth > 12:
            raise ValueError("result_too_deep")
        if value is None or type(value) is bool:
            return
        if type(value) in (int, float):
            if not math.isfinite(value) or abs(value) > 1e12:
                raise ValueError("invalid_result_number")
        elif isinstance(value, str):
            if value not in known or len(value) > 100:
                raise ValueError("unexpected_result_text")
        elif isinstance(value, list) and len(value) <= 40:
            for item in value:
                validate(item, depth + 1)
        elif isinstance(value, dict) and len(value) <= 50:
            for key, item in value.items():
                validate(key, depth + 1)
                validate(item, depth + 1)
        else:
            raise ValueError("unexpected_result_type")
    validate(result)
    # Load only the separately pinned, sensor-free harness, not the candidate.
    namespace = {"__name__": "local_synthetic_result_validator"}
    exec(compile(bundle["harness"], "<pinned-result-validator>", "exec"), namespace)
    if (not isinstance(result, dict) or result.get("schema") != namespace["SCHEMA"]
            or result.get("status") not in {"PASS", "FAIL"}
            or returncode != (0 if result["status"] == "PASS" else 20)):
        raise ValueError("result_status_mismatch")
    for name in ("physical_keyboard_tested", "audio_opened", "recording_authorized",
                 "settings_changed", "robot_api_called", "remote_files_installed",
                 "real_audio_capture_tested", "operator_terminal_used", "clock_accelerated"):
        if result.get(name) is not False:
            raise ValueError("result_scope_mismatch")
    cases = result.get("cases")
    if not isinstance(cases, list) or len(cases) > 2:
        raise ValueError("invalid_case_count")
    if result["status"] == "PASS":
        if (tuple(c.get("name") for c in cases) != namespace["CASES"]
                or any(c.get("ok") is not True or not namespace["expected_case"](c) for c in cases)):
            raise ValueError("invalid_pass_result")
    return result


def check_once(root=LOCAL_ROOT, runner=subprocess.run):
    if not sys.stdin.isatty():
        raise RuntimeError("interactive_PowerShell_required_for_SSH_password")
    bundle = source_bundle()
    root = local.safe_local_directory(root)
    directory = root / RUN_ID
    directory.mkdir()  # Exclusive: a timeout/interruption never resets this latch.
    initial = {"schema": "reachy-input-linux-local-v1", "run_id": RUN_ID, "status": "STARTED",
               "started_utc": local.utc_now(), "candidate_sha256": HELPER_SHA,
               "harness_sha256": HARNESS_SHA, "definitions_sha256": bundle["definitions_sha256"],
               "payload_sha256": sha(bundle["payload"]), "automatic_retry": False,
               "recording_authorized": False, "remote_file_installation": False,
               "password_captured": False, "operator_terminal_forwarded": False}
    local.write_new(directory / "started.json", initial)
    print("AUTOMATIC SOFTWARE CHECK ONLY. Leave the phone paused. No audio or movement.", flush=True)
    print("Enter the SSH password if asked. After that, do nothing: NO Play and NO Enter prompts.", flush=True)
    print("Two generated-data checks should take about 35 seconds after login. Maximum check time: 55 seconds.", flush=True)
    report, code = dict(initial), 1
    try:
        completed = runner(ssh_command(bundle["payload"]), input=bundle["payload"],
                           stdout=subprocess.PIPE, stderr=None, timeout=95)
        report["ssh_exit_code"] = completed.returncode
        try:
            report["result"] = validated_result(completed.stdout, bundle, completed.returncode)
            report["status"] = "SYNTHETIC_" + report["result"]["status"]
            code = 0 if report["status"] == "SYNTHETIC_PASS" else 1
        except (ValueError, TypeError, KeyError, OverflowError, AttributeError):
            report["status"] = "CONNECTION_OR_RESULT_UNVERIFIED"
            # No stdout or stderr copied into the record on parse failure.
    except (OSError, subprocess.TimeoutExpired, KeyboardInterrupt):
        report["status"] = "INTERRUPTED_OR_CONNECTION_UNCERTAIN"
    finally:
        report["finished_utc"] = local.utc_now()
        local.write_new(directory / "report.json", report)
        print(report["status"], flush=True)
        print("REPORT SAVED: " + str(directory / "report.json"), flush=True)
        print("Send the final output for review. Do not repeat this check or start a microphone test.", flush=True)
    return code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--inspect", action="store_true")
    modes.add_argument("--check-once", action="store_true")
    args = parser.parse_args(argv)
    if args.inspect:
        bundle = source_bundle()
        print(json.dumps({"mode": "OFFLINE", "run_id": RUN_ID, "payload_bytes": len(bundle["payload"]),
                          "payload_sha256": sha(bundle["payload"]),
                          "definitions_sha256": bundle["definitions_sha256"],
                          "recording_authorized": False, "remote_files_installed": False}))
        return 0
    if args.check_once:
        return check_once()
    parser.print_help()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError):
        print("STOP: local source or one-use preparation needs review. Do not rerun.", file=sys.stderr)
        raise SystemExit(1)
