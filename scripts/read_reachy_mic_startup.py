"""One read-only startup probe of the failed two-pair session; never retry capture.

Default: help, no connection. Password goes to the OpenSSH console only.
The old helper, failed run and its PENDING close-out are not modified.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys

if __package__:
    from . import run_reachy_mic_diagnostic as original
else:
    import run_reachy_mic_diagnostic as original


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "reachy-mic-startup-probe-v1"
OUTPUT = ROOT / "data/private/mic_startup_probe" / original.SESSION


def reviewed_run():
    paths = list(original.LOCAL.glob("review-*.json"))
    if len(paths) != 1:
        raise RuntimeError("expected_one_reviewed_failure_report")
    payload = original.read_regular(paths[0], 2 * 1024 * 1024)
    bundle = original.decode_export(payload)
    run = bundle["run"]
    if not isinstance(run, dict):
        raise RuntimeError("missing_failed_run")
    result = run.get("records", {}).get("result.json", {})
    if (result.get("reason") != "guard_EOF" or result.get("pair_results") != []
            or result.get("status") != "RESTORATION_UNVERIFIED"
            or run.get("missing_records") != ["guard.json"]):
        raise RuntimeError("not_the_reviewed_startup_failure")
    return run["directory"], hashlib.sha256(payload).hexdigest()


def ssh_command(directory):
    remote = shlex.join([original.PYTHON, "-I", "-B", "-", "--probe", "--run-directory", directory])
    return ["ssh", "-T", "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=10",
            "-o", "ConnectionAttempts=1", "-o", "ServerAliveInterval=10", "-o",
            "ServerAliveCountMax=2", "-o", "NumberOfPasswordPrompts=1", "pollen@192.168.1.251", remote]


def decode_events(payload):
    if not isinstance(payload, bytes) or len(payload) > 1024 * 1024:
        raise ValueError("invalid_or_oversized_report")
    events, invalid_lines = [], 0
    for line in payload.splitlines():
        try:
            item = json.loads(line)
            if (not isinstance(item, dict) or item.get("schema") != SCHEMA
                    or item.get("execution_authorized") is not False):
                raise ValueError("unexpected_event")
            events.append(item)
        except (ValueError, UnicodeError):
            invalid_lines += 1  # Never save arbitrary output or a partial traceback.
    return events, invalid_lines


def collect():
    directory, review_hash = reviewed_run()
    source = (ROOT / "tools/reachy_mic_startup_probe.py").read_bytes()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    original.write_new(OUTPUT / "started.json", {
        "schema": SCHEMA, "utc": datetime.now(timezone.utc).isoformat(), "status": "PENDING",
        "source_sha256": hashlib.sha256(source).hexdigest(), "review_sha256": review_hash,
        "run_directory": directory, "automatic_retry": False, "execution_authorized": False})
    print("ONE READ-ONLY startup probe. Leave robot apps/pages closed and phone playback paused.", flush=True)
    print("No audio capture, routing writes, installed files, lock changes or cleanup.", flush=True)
    print("Enter the SSH password if prompted; typed characters are invisible.", flush=True)
    print("After login, allow up to about 45 seconds. A failed stage will be saved, not hidden.", flush=True)
    failure, code, payload = None, None, b""
    try:
        outcome = subprocess.run(ssh_command(directory), input=source, stdout=subprocess.PIPE, timeout=120)
        code, payload = outcome.returncode, outcome.stdout
    except subprocess.TimeoutExpired as error:
        failure, payload = "ssh_timeout", error.output or b""
    except (OSError, KeyboardInterrupt) as error:
        failure = type(error).__name__
    events, invalid_lines = decode_events(payload)
    target = OUTPUT / "report.json"
    original.write_new(target, {"schema": SCHEMA, "source_sha256": hashlib.sha256(source).hexdigest(),
        "utc": datetime.now(timezone.utc).isoformat(), "events": events, "invalid_lines": invalid_lines,
        "ssh_exit_code": code, "transport_error": failure, "execution_authorized": False,
        "closeout_status": "PENDING", "automatic_retry": False})
    print("REPORT SAVED: " + str(target), flush=True)
    print("Send this path for review. Do not repeat the probe or run the two-pair diagnostic.", flush=True)
    return 0 if code == 0 and not invalid_lines and events and events[-1].get("event") == "finished" else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collect", action="store_true")
    args = parser.parse_args(argv)
    if not args.collect:
        parser.print_help()
        return 0
    return collect()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as error:
        print("Probe stopped: " + type(error).__name__ + ". Send the output; do not retry.", file=sys.stderr)
        raise SystemExit(2)
