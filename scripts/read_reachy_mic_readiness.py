"""Collect one private read-only robot metadata report through operator SSH.

No recording, device writes, settings changes or remote file deployment.
Without --collect, show help and make no connection. Enter passwords only in
the OpenSSH console; this launcher never handles or saves the password.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import uuid


ROOT = Path(__file__).resolve().parents[1]
PYTHON = "/venvs/mini_daemon/bin/python"
SCHEMA = "reachy-mic-readiness-v2"


def ssh_command():
    remote = shlex.join([PYTHON, "-I", "-B", "-", "--report"])
    return ["ssh", "-T", "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=5",
            "-o", "ConnectionAttempts=1", "-o", "ServerAliveInterval=5",
            "-o", "ServerAliveCountMax=2", "-o", "NumberOfPasswordPrompts=1",
            "pollen@192.168.1.251", remote]


def decode_report(payload):
    if len(payload) > 1024 * 1024:
        raise ValueError("oversized report")
    data = json.loads(payload)
    if (not isinstance(data, dict) or data.get("schema") != SCHEMA
            or data.get("execution_authorized") is not False
            or data.get("purpose") != "read_only_metadata_review"
            or not isinstance(data.get("checks"), dict)
            or not isinstance(data.get("unavailable_checks"), list)):
        raise ValueError("unexpected report contract")
    return data


def save_report(data, source_hash, directory):
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S-%fZ")
    target = directory / ("reachy-mic-readiness-" + stamp + "-" + uuid.uuid4().hex[:8] + ".json")
    record = {**data, "collector_source_sha256": source_hash,
              "local_received_utc": datetime.now(timezone.utc).isoformat()}
    with target.open("x", encoding="utf-8") as output:
        json.dump(record, output, indent=2, allow_nan=False)
        output.write("\n")
    return target


def collect():
    source = (ROOT / "tools/reachy_mic_readiness.py").read_bytes()
    print("Corrected v2 READ-ONLY metadata report. No audio capture or settings changes.", flush=True)
    print("Enter the SSH password if prompted; typed characters are invisible.", flush=True)
    print("The checks take up to about one minute after login. No robot file is installed.", flush=True)
    # SSH reads the password from its console, independently of piped source stdin.
    # Leave stderr attached to the console so authentication messages remain visible.
    result = subprocess.run(ssh_command(), input=source, stdout=subprocess.PIPE, timeout=150)
    if result.returncode:
        print("Report collection did not finish. Send the terminal output; no automatic retry.")
        return 2
    data = decode_report(result.stdout)
    target = save_report(data, hashlib.sha256(source).hexdigest(), ROOT / "data/private/mic_readiness")
    print("REPORT SAVED (not an execution PASS): " + str(target))
    print("Checks with unavailable information: " + str(len(data["unavailable_checks"])))
    print("Optional files/directories not present: " + str(len(data.get("optional_not_present", []))))
    print("Send this path or attach the JSON for review. Do not run the microphone helper yet.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collect", action="store_true", help="SSH read-only report; save JSON privately on this laptop")
    args = parser.parse_args()
    if not args.collect:
        parser.print_help()
        return 0
    return collect()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        print("Report stopped: " + type(error).__name__ + ". No settings-change command was sent.", file=sys.stderr)
        raise SystemExit(2)
