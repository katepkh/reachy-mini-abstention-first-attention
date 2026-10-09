"""One operator-run keyboard check; no robot sensor/settings access or install.

Default/help and --inspect are offline. --check-once is separately latched
before SSH, inherits console I/O and sends only the pinned reader classes plus
a keyboard-only harness. Passwords and key contents are never captured.
"""
import argparse
import ast
import base64
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import check_reachy_keyboard as previous

HELPER = ROOT / "tools/reachy_mic_health_input_next.py"
HELPER_SHA = "dbdddf79e2e7103a1fa3a78d03e65eb8415a73f43b454b0f516e12406ebc8368"
PROBE = ROOT / "tools/reachy_exact_reader_probe.py"
PROBE_SHA = "c8156a8e64b82b6ded90e0b52b4e620488ff244d7964ab44d85505965507ebf6"
DEPENDENCIES = {
    "scripts/check_reachy_keyboard.py": "88a7deed87ecbea663b054b5bdf5ce935593536ab7390c08ceb0c3612db582cc",
    "scripts/run_reachy_mic_diagnostic.py": "d38f202b9375f8bf542f991bfebdc52e7f442b839f15939e9108488f46267d9c",
}
RUN_ID = "reader-path-20261008-01"
LOCAL_ROOT = ROOT / "data/private/mic_keyboard_reader_check"
PYTHON = "/venvs/mini_daemon/bin/python"
OUTCOMES = {0: "BOTH_ENTER_READERS_ACKNOWLEDGED", 20: "NO_INPUT_OBSERVED",
            21: "UNEXPECTED_TEXT", 22: "UNSUPPORTED_TERMINAL", 23: "TERMINAL_CLOSED",
            24: "BYTES_WITHOUT_ENTER_EVENT", 25: "PROBE_ERROR", 26: "INTERRUPTED",
            27: "MULTIPLE_EVENTS", 28: "READER_EXIT_UNVERIFIED",
            29: "TERMINAL_MODES_CHANGED", 30: "OBSERVATION_AFTER_DEADLINE"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source_bundle():
    for relative, expected in DEPENDENCIES.items():
        if sha(previous.read_regular(ROOT / relative, 100000)) != expected:
            raise RuntimeError("keyboard_dependency_changed")
    helper = previous.read_regular(HELPER, 100000)
    probe = previous.read_regular(PROBE, 24000)
    if sha(helper) != HELPER_SHA or sha(probe) != PROBE_SHA:
        raise RuntimeError("exact_reader_source_changed")
    source = helper.decode("utf-8")
    nodes = {n.name: n for n in ast.parse(source).body if isinstance(n, ast.ClassDef)}
    definitions = "\n\n".join(ast.get_source_segment(source, nodes[name]) for name in ("Stop", "TerminalInputReader"))
    remote = ("import os, queue, selectors, threading, time\n" + definitions + "\n\n"
              + probe.decode("utf-8") + "\nraise SystemExit(run_probe(TerminalInputReader))\n")
    return remote.encode("utf-8"), sha(definitions.encode("utf-8"))


def ssh_command(payload=None):
    payload = source_bundle()[0] if payload is None else payload
    encoded = base64.b64encode(payload).decode("ascii")
    code = "import base64;exec(compile(base64.b64decode('" + encoded + "'),'<exact-reader-keyboard-check>','exec'))"
    remote = shlex.join([PYTHON, "-I", "-B", "-c", code])
    return ["ssh", "-t", "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=10",
            "-o", "ConnectionAttempts=1", "-o", "NumberOfPasswordPrompts=1",
            "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=4",
            "pollen@192.168.1.251", remote]


def check_once(root=LOCAL_ROOT, runner=subprocess.run):
    if not sys.stdin.isatty():
        raise RuntimeError("interactive_PowerShell_required")
    payload, reader_sha = source_bundle()
    command = ssh_command(payload)
    if len(subprocess.list2cmdline(command)) >= 30000:
        raise RuntimeError("keyboard_command_too_long")
    root = previous.safe_local_directory(root)
    directory = root / RUN_ID
    directory.mkdir()  # Exclusive one-attempt latch; preserve any interrupted folder.
    initial = {"schema": "reachy-exact-reader-local-report-v1", "run_id": RUN_ID,
               "status": "STARTED", "started_utc": previous.utc_now(),
               "helper_sha256": HELPER_SHA, "probe_sha256": PROBE_SHA,
               "reader_definitions_sha256": reader_sha, "remote_payload_sha256": sha(payload),
               "automatic_retry": False, "audio_opened": False, "settings_changed": False,
               "remote_file_installation": False, "recording_authorized": False,
               "stdin_stdout_stderr": "inherited_console", "capture_load_tested": False,
               "key_contents_or_passwords_captured": False}
    previous.write_new(directory / "started.json", initial)
    print("KEYBOARD ONLY. Keep the phone PAUSED; no playback, microphone or movement.", flush=True)
    print("Enter the SSH password if asked. Press Enter ONCE at each of TWO labelled prompts.", flush=True)
    print("Each prompt allows TWO MINUTES. No need to rush. Do not type any other text.", flush=True)
    print("Detailed numeric counts stay in this console; local files retain status/source metadata only.", flush=True)
    report, exit_code = dict(initial), 1
    try:
        outcome = runner(command, timeout=300)  # Inherit all console handles, like the diagnostic.
        exit_code = outcome.returncode
        report.update(ssh_exit_code=exit_code, status=OUTCOMES.get(exit_code, "CONNECTION_OR_REMOTE_FAILURE"))
    except (OSError, subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        report.update(status="INTERRUPTED_OR_CONNECTION_UNCERTAIN", error_type=type(error).__name__)
    finally:
        report["finished_utc"] = previous.utc_now()
        report["result_basis"] = "embedded_probe_exit_status; detailed numeric counts/timing remain in console"
        previous.write_new(directory / "report.json", report)
        print("REPORT SAVED: " + str(directory / "report.json"), flush=True)
        print("Send the final output for review. Do not rerun or start a microphone test.", flush=True)
    return exit_code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--inspect", action="store_true")
    modes.add_argument("--check-once", action="store_true")
    args = parser.parse_args(argv)
    if args.inspect:
        payload, reader_sha = source_bundle()
        print(json.dumps({"mode": "OFFLINE", "run_id": RUN_ID, "reader_definitions_sha256": reader_sha,
                          "remote_payload_sha256": sha(payload), "recording_authorized": False,
                          "audio_opened": False, "remote_files_installed": False}))
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
        print("Do not repeat this command; preserve the report for review.", file=sys.stderr)
        raise SystemExit(1)
