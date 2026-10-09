"""Operator-run copy plus READ-ONLY preflight. No capture or routing authority.

Run locally in an interactive Windows PowerShell window. OpenSSH asks the
operator for the password directly; this script does not receive or save it.
Only --deploy-preflight opens SSH. --self-test is entirely offline.
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
import tempfile
import unittest
import uuid


EXPECTED = "01b14cb7ac76c67c81bba12a11509dafc97c8eac8b28ceada0982cf1a8bc0e7d"
DESTINATION = "/home/pollen/reachy_mic_health_v2.py"
PYTHON = "/venvs/mini_daemon/bin/python"
ROOT = Path(__file__).resolve().parents[1]


def install_exact(path, payload, expected):
    """Create exclusively, or reuse the identical existing regular file."""
    if hashlib.sha256(payload).hexdigest() != expected:
        raise RuntimeError("Source hash mismatch; nothing copied")
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow, 0o600)
    except FileExistsError:
        if not stat.S_ISREG(os.lstat(path).st_mode):
            raise RuntimeError("Existing destination is not a regular file; refusing")
        created = False
    else:
        created = True
        with os.fdopen(descriptor, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
    # Read from this verified descriptor, never execute an unverified copy.
    descriptor = os.open(path, os.O_RDONLY | nofollow)
    with os.fdopen(descriptor, "rb") as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise RuntimeError("Destination type changed; stop")
        if hasattr(os, "getuid") and info.st_uid != os.getuid():
            raise RuntimeError("Destination has another owner; stop")
        if hashlib.sha256(source.read(100001)).hexdigest() != expected:
            raise RuntimeError("Existing/partial destination differs; not overwritten, not run")
    return created


def remote_program():
    # This small transport bootstrap is visible here for review; base64 only
    # protects its quoting through PowerShell/OpenSSH/the remote POSIX shell.
    return ("import base64, hashlib, os, stat, sys\n"
            + inspect.getsource(install_exact)
            + "\npayload = base64.b64decode(sys.stdin.buffer.read(150000), validate=True)\n"
            + f"created = install_exact({DESTINATION!r}, payload, {EXPECTED!r})\n"
            + "print('HELPER_COPIED' if created else 'IDENTICAL_HELPER_REUSED', file=sys.stderr, flush=True)\n"
            + f"print('SHA256_VERIFIED: {EXPECTED}', file=sys.stderr, flush=True)\n"
            + "print('READ_ONLY_PREFLIGHT_ONLY; no recording or routing writes', file=sys.stderr, flush=True)\n"
            + f"os.execv({PYTHON!r}, [{PYTHON!r}, '-I', '-B', {DESTINATION!r}, '--preflight'])\n")


def decode_preflight(payload):
    if len(payload) > 1024 * 1024:
        raise RuntimeError("Oversized preflight report")
    report = json.loads(payload)
    if (not isinstance(report, dict) or report.get("schema") != "reachy-mic-health-v2"
            or report.get("mode") != "READ_ONLY" or report.get("helper_sha256") != EXPECTED
            or report.get("execution_authorized") is not False
            or report.get("consumer_isolation_verified") is not False
            or not isinstance(report.get("checks"), list) or not report["checks"]
            or not all(isinstance(item, dict) and isinstance(item.get("name"), str)
                       and type(item.get("ok")) is bool for item in report["checks"])
            or report.get("machine_checks_passed") is not all(item["ok"] for item in report["checks"])):
        raise RuntimeError("Unexpected preflight contract; do not execute")
    return report


def save_preflight(report, directory):
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S-%fZ")
    target = directory / ("reachy-mic-preflight-v2-" + stamp + "-" + uuid.uuid4().hex[:8] + ".json")
    with target.open("x", encoding="utf-8") as output:
        json.dump(report, output, indent=2, allow_nan=False)
        output.write("\n")
    return target


def deploy():
    path = ROOT / "tools" / "reachy_mic_health.py"
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != EXPECTED:
        raise RuntimeError("Local helper changed; stop for review before transfer")
    bootstrap = base64.b64encode(remote_program().encode()).decode("ascii")
    code = "import base64;exec(base64.b64decode('" + bootstrap + "'))"
    remote = shlex.join([PYTHON, "-I", "-B", "-c", code])
    command = ["ssh", "-T", "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=5",
               "-o", "ConnectionAttempts=1", "-o", "ServerAliveInterval=5",
               "-o", "ServerAliveCountMax=2", "-o", "NumberOfPasswordPrompts=1",
               "pollen@192.168.1.251", remote]
    print("Copying the reviewed v2 helper to a NEW path; v1 is not overwritten.", flush=True)
    print("Then one READ-ONLY preflight: no capture, routing, motor or OS-setting changes.", flush=True)
    print("Enter the SSH password if prompted; typed characters are invisible.", flush=True)
    outcome = subprocess.run(command, input=base64.b64encode(payload), stdout=subprocess.PIPE, timeout=120)
    if outcome.returncode:
        print("STOP: copy/preflight did not complete successfully. Send the output for review.")
    else:
        report = decode_preflight(outcome.stdout)
        target = save_preflight(report, ROOT / "data/private/mic_preflight")
        print("REPORT SAVED (not execution approval): " + str(target))
        for item in report["checks"]:
            if not item["ok"]:
                print("BLOCKER: " + item["name"] + " — " + item.get("reason", "review required"))
        print("Manual review still required: motor/physical setup, other audio consumers and run scope.")
        print("Send the saved report path. Do not run --execute or change any robot setting.")
    return outcome.returncode


class OfflineCopyTests(unittest.TestCase):
    def test_exclusive_copy_identical_reuse_and_different_file_refusal(self):
        payload = b"synthetic helper fixture\n"
        expected = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory(prefix="reachy-copy-test-") as directory:
            path = Path(directory) / "helper.py"
            self.assertTrue(install_exact(path, payload, expected))
            self.assertFalse(install_exact(path, payload, expected))
            other = b"different fixture\n"
            with self.assertRaises(RuntimeError):
                install_exact(path, other, hashlib.sha256(other).hexdigest())
            self.assertEqual(path.read_bytes(), payload)

    def test_bad_source_creates_nothing(self):
        with tempfile.TemporaryDirectory(prefix="reachy-copy-test-") as directory:
            path = Path(directory) / "helper.py"
            with self.assertRaises(RuntimeError):
                install_exact(path, b"fixture", "incorrect")
            self.assertFalse(path.exists())

    def test_directory_refused(self):
        with tempfile.TemporaryDirectory(prefix="reachy-copy-test-") as directory:
            with self.assertRaises((RuntimeError, OSError)):
                install_exact(directory, b"fixture", hashlib.sha256(b"fixture").hexdigest())

    def test_remote_entry_is_preflight_only(self):
        source = remote_program()
        compile(source, "<copy-preflight-bootstrap>", "exec")
        self.assertIn("'--preflight'", source)
        self.assertNotIn("--execute", source)
        self.assertNotIn("--guard", source)

    def test_local_source_matches_reviewed_hash_and_new_destination(self):
        self.assertEqual(hashlib.sha256((ROOT / "tools/reachy_mic_health.py").read_bytes()).hexdigest(), EXPECTED)
        self.assertEqual(DESTINATION, "/home/pollen/reachy_mic_health_v2.py")

    def test_report_validation_and_unique_private_outputs(self):
        report = {"schema": "reachy-mic-health-v2", "mode": "READ_ONLY", "helper_sha256": EXPECTED,
                  "execution_authorized": False, "consumer_isolation_verified": False,
                  "checks": [{"name": "motor", "ok": False}], "machine_checks_passed": False}
        self.assertEqual(decode_preflight(json.dumps(report).encode()), report)
        for key, value in (("execution_authorized", True), ("helper_sha256", "wrong"),
                           ("checks", []), ("machine_checks_passed", True)):
            with self.assertRaises(RuntimeError):
                decode_preflight(json.dumps({**report, key: value}).encode())
        with tempfile.TemporaryDirectory() as directory:
            first = save_preflight(report, Path(directory))
            second = save_preflight(report, Path(directory))
            self.assertNotEqual(first, second)
            self.assertEqual(json.loads(first.read_text()), report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--deploy-preflight", action="store_true")
    modes.add_argument("--self-test", action="store_true")
    arguments = parser.parse_args()
    if arguments.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(OfflineCopyTests)
        return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1
    return deploy()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        print("STOP: " + (str(error) or type(error).__name__), file=sys.stderr)
        raise SystemExit(2)
