"""One keyboard-only SSH check per explicit invocation; no capture or install.

Default/help and --inspect are offline. --check-once keeps stdin/stdout/stderr
on the operator console, exactly as the microphone launcher's interactive SSH.
Passwords and key contents are never captured by this launcher. Each explicit
invocation preserves its own local metadata; there is no automatic retry.
"""

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shlex
import stat
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.run_reachy_mic_diagnostic import read_regular, write_new

PROBE = ROOT / "tools/reachy_keyboard_probe.py"
EXPECTED = "e6a8aa5d0fea76e8d143ecf2ec4246186e2c0d946610af758c4fbe7d0f66c2aa"
LOCAL_ROOT = ROOT / "data/private/mic_keyboard_check"
PYTHON = "/venvs/mini_daemon/bin/python"
OUTCOMES = {0: "BOTH_ENTER_ACKNOWLEDGED", 20: "NO_INPUT_OBSERVED_BEFORE_DEADLINE",
            21: "UNEXPECTED_TEXT", 22: "UNSUPPORTED_TERMINAL", 23: "TERMINAL_CLOSED",
            24: "INPUT_PRESENT_AT_EXPIRY_TIME_UNKNOWN", 25: "PROBE_ERROR", 26: "INTERRUPTED"}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def source_bytes():
    payload = read_regular(PROBE, 24000)
    if hashlib.sha256(payload).hexdigest() != EXPECTED:
        raise RuntimeError("keyboard_probe_source_changed")
    return payload


def ssh_command():
    encoded = base64.b64encode(source_bytes()).decode("ascii")
    code = "import base64;exec(compile(base64.b64decode('" + encoded + "'),'<keyboard-only-probe>','exec'))"
    remote = shlex.join([PYTHON, "-I", "-B", "-c", code])
    return ["ssh", "-t", "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=10",
            "-o", "ConnectionAttempts=1", "-o", "NumberOfPasswordPrompts=1",
            "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=4",
            "pollen@192.168.1.251", remote]


def safe_local_directory(path):
    path = Path(path).absolute()
    # Check existing ancestors BEFORE creating children; never follow a link.
    for current in reversed((path, *path.parents)):
        if current.exists() or current.is_symlink():
            info = current.lstat()
            if (not stat.S_ISDIR(info.st_mode) or current.is_symlink()
                    or getattr(info, "st_file_attributes", 0) & 0x400):
                raise RuntimeError("unsafe_local_report_directory")
    path.mkdir(parents=True, exist_ok=True)
    return path


def check_once(root=LOCAL_ROOT, runner=subprocess.run):
    if not sys.stdin.isatty():
        raise RuntimeError("interactive_PowerShell_required")
    command = ssh_command()  # Verify code before creating a run record or connecting.
    root = safe_local_directory(root)
    directory = root / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8])
    directory.mkdir()
    initial = {"schema": "reachy-keyboard-local-report-v1", "started_utc": utc_now(),
               "probe_sha256": EXPECTED, "status": "STARTED", "automatic_retry": False,
               "audio_opened": False, "settings_changed": False, "remote_file_installation": False,
               "recording_authorized": False, "stdin_stdout_stderr": "inherited_console",
               "key_contents_or_passwords_captured": False}
    write_new(directory / "started.json", initial)
    print("KEYBOARD ONLY: leave the phone PAUSED. No playback, microphone or movement.", flush=True)
    print("Enter the SSH password if requested. Then press Enter once at each of TWO labelled prompts.", flush=True)
    print("Each prompt allows two minutes. No quick Play/Enter action is needed.", flush=True)
    print("The detailed timing stays on this console; only exit/status metadata is saved locally.", flush=True)
    print("Report folder: " + str(directory), flush=True)
    report = dict(initial)
    exit_code = 1
    try:
        outcome = runner(command, timeout=300)  # Deliberately inherit all three console streams.
        report["ssh_exit_code"] = outcome.returncode
        report["status"] = OUTCOMES.get(outcome.returncode, "CONNECTION_OR_REMOTE_FAILURE")
        report["both_enters_acknowledged"] = outcome.returncode == 0
        exit_code = outcome.returncode
    except (OSError, subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        report["status"] = "INTERRUPTED_OR_CONNECTION_UNCERTAIN"
        report["error_type"] = type(error).__name__
        report["both_enters_acknowledged"] = False
    finally:
        report["finished_utc"] = utc_now()
        report["result_basis"] = "embedded_probe_exit_status; detailed numeric timings remain in console, not captured"
        write_new(directory / "report.json", report)
        print("REPORT SAVED: " + str(directory / "report.json"), flush=True)
        print("Send the final output for review. Do not start a microphone test or automatically repeat this check.", flush=True)
    return exit_code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check-once", action="store_true")
    mode.add_argument("--inspect", action="store_true")
    args = parser.parse_args(argv)
    if args.inspect:
        source_bytes()
        print(json.dumps({"mode": "OFFLINE", "probe_sha256": EXPECTED,
                          "remote_files_installed": False, "audio_opened": False,
                          "recording_authorized": False}))
        return 0
    if args.check_once:
        return check_once()
    parser.print_help()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as error:
        print("STOP: " + str(error), file=sys.stderr)
        raise SystemExit(1)
