"""Read-only investigation of the v2 guard's pre-capture startup failure.

Sent through SSH stdin, never installed. No guard invocation, journal creation,
lock acquisition, PCM access, routing writes, resource-limit changes or cleanup.
Every stage is flushed as JSONL, so partial/failed probes retain useful evidence.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time


SCHEMA = "reachy-mic-startup-probe-v1"
EXPECTED = "01b14cb7ac76c67c81bba12a11509dafc97c8eac8b28ceada0982cf1a8bc0e7d"
HELPER = Path("/home/pollen/reachy_mic_health_v2.py")
RUN_ROOT = Path("/home/pollen/reachy-mic-health-runs-v2")
LOCK = Path("/tmp/reachy-mic-health.lock")
ROUTES = ("AUDIO_MGR_OP_L", "AUDIO_MGR_OP_R")


class ProbeError(RuntimeError):
    """Fixed reason code, not an arbitrary exception message."""


def error_details(error):
    result = {"error_type": type(error).__name__}
    if isinstance(error, ProbeError):
        result["reason"] = str(error)
    elif type(error).__name__ == "Stop" and re.fullmatch(r"[a-zA-Z0-9_;:. -]{1,200}", str(error)):
        result["reason"] = str(error)  # Fixed codes from the hash-pinned helper.
    for field in ("errno", "backend_error_code", "returncode"):
        value = getattr(error, field, None)
        if type(value) is int:
            result[field] = value
    if isinstance(error, ImportError):
        name = getattr(error, "name", None)
        if isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9_.]{1,100}", name):
            result["missing_module"] = name
    # No arbitrary stderr, traceback, exception text, environment or device serial.
    return result


def read_regular(path, limit=100000):
    before = path.lstat()
    if (not stat.S_ISREG(before.st_mode) or path.is_symlink()
            or before.st_size > limit or before.st_uid != os.getuid()):
        raise ProbeError("unsafe_or_oversized_file")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as source:
        opened = os.fstat(source.fileno())
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise ProbeError("file_identity_changed")
        data = source.read(limit + 1)
        after = os.fstat(source.fileno())
    if len(data) > limit or (opened.st_size, opened.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ProbeError("file_changed_or_oversized")
    return data


def load_helper():
    payload = read_regular(HELPER)
    if hashlib.sha256(payload).hexdigest() != EXPECTED:
        raise ProbeError("helper_hash_changed")
    namespace = {"__name__": "verified_read_only_helper", "__file__": str(HELPER)}
    # This exact pinned module has standard-library-only, side-effect-free imports.
    # Only its read-only functions are used below, never main/execute/guard/USBBoard.
    exec(compile(payload, str(HELPER), "exec"), namespace)
    namespace["require_robot_account"]()
    return namespace


def validate_scope(helper, directory):
    if directory.parent != RUN_ROOT or not re.fullmatch(r"run-[A-Za-z0-9_-]{1,64}", directory.name):
        raise ProbeError("unexpected_run_scope")
    helper["private_directory"](RUN_ROOT)
    helper["private_directory"](directory)
    rows = helper["inventory"](directory)
    expected = {"baseline.json", "approval.json", "result.json", "closeout.json"}
    if {row["name"] for row in rows} != expected or any(row["kind"] != "file" for row in rows):
        raise ProbeError("startup_failure_inventory_changed")
    records = {name: json.loads(read_regular(directory / name)) for name in expected}
    if any(not isinstance(value, dict) or value.get("helper_sha256") != EXPECTED
           for value in records.values()):
        raise ProbeError("run_record_identity_changed")
    result, closeout = records["result.json"], records["closeout.json"]
    if (result.get("schema") != "reachy-mic-health-v2" or result.get("reason") != "guard_EOF"
            or result.get("pair_results") != [] or result.get("status") != "RESTORATION_UNVERIFIED"
            or closeout.get("schema") != "reachy-mic-closeout-v1"
            or closeout.get("status") != "PENDING" or closeout.get("scope") != str(directory)
            or records["approval.json"] != {"scope": helper["ACK"], "helper_sha256": EXPECTED}):
        raise ProbeError("not_the_reviewed_pre_capture_failure")
    baseline = records["baseline.json"]
    if set(baseline) != {"asoundrc_sha256", "mixer_sha256", "parameters", "helper_sha256", "privacy_profile"}:
        raise ProbeError("baseline_contract_changed")
    return baseline, rows


def inspect_lock():
    """Metadata/owner lookup only: never create, flock, unlink or replace a lock."""
    try:
        info = LOCK.lstat()
    except FileNotFoundError:
        return {"present": False, "lock_acquisition_tested": False, "owners": []}
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ProbeError("unsafe_lock_metadata")
    outcome = subprocess.run(["fuser", str(LOCK)], capture_output=True, timeout=2)
    if outcome.returncode not in (0, 1) or len(outcome.stdout) > 4096:
        raise ProbeError("lock_owners_unavailable")
    values = outcome.stdout.decode("ascii").split()
    if any(not value.isdigit() for value in values) or len(values) > 32:
        raise ProbeError("invalid_lock_owner_response")
    return {"present": True, "mode": stat.S_IMODE(info.st_mode), "owners": [int(v) for v in values],
            "lock_acquisition_tested": False, "complete_process_isolation_verified": False}


class ReadOnlyUSB:
    """Two fixed vendor-IN register reads; no OUT/control setter interface."""

    def __init__(self):
        import usb.core
        import usb.util
        from libusb_package import get_libusb1_backend
        self.core, self.util = usb.core, usb.util
        self.backend = get_libusb1_backend()
        self.device = None
        self.attempted = set()
        if self.backend is None:
            raise ProbeError("libusb_backend_unavailable")

    def enumerate(self):
        devices = list(self.core.find(find_all=True, idVendor=0x38FB, idProduct=0x1001, backend=self.backend))
        if len(devices) != 1:
            raise ProbeError("expected_one_audio_board")
        self.device = devices[0]
        return {"matching_devices": 1}

    def read_route(self, name):
        if name not in ROUTES or name in self.attempted or self.device is None:
            raise ProbeError("read_not_allowlisted_or_already_attempted")
        self.attempted.add(name)  # No automatic retry, even after a failed read.
        command = 15 if name == ROUTES[0] else 19
        response = bytes(self.device.ctrl_transfer(0xC0, 0, 0x80 | command, 35, 3, 500))
        value = {"response_length": len(response), "status_byte": response[0] if response else None,
                 "values": list(response[1:]) if len(response) == 3 and response[0] == 0 else None,
                 "v2_read_would_accept": len(response) == 3 and response[0] == 0}
        return value

    def close(self):
        if self.device is not None:
            self.util.dispose_resources(self.device)


class Probe:
    def __init__(self, output=sys.stdout, usb_factory=ReadOnlyUSB):
        self.output, self.usb_factory = output, usb_factory
        self.stages = []
        self.deadline = time.monotonic() + 45

    def emit(self, item):
        event = {"schema": SCHEMA, "execution_authorized": False, **item}
        self.output.write(json.dumps(event, allow_nan=False) + "\n")
        self.output.flush()

    def stage(self, name, action, describe=lambda value: value, *, closing=False):
        self.emit({"event": "stage_started", "stage": name})
        started = time.monotonic()
        try:
            if started >= self.deadline and not closing:
                raise ProbeError("probe_budget_expired")
            value = action()
            row = {"stage": name, "status": "observed", "value": describe(value)}
        except Exception as error:
            value = None
            row = {"stage": name, "status": "unavailable", **error_details(error)}
        row["elapsed_ms"] = round((time.monotonic() - started) * 1000, 2)
        self.stages.append(row)
        self.emit({"event": "stage_finished", **row})
        return value

    def collect(self, directory):
        self.emit({"event": "started", "utc": datetime.now(timezone.utc).isoformat(),
                   "mode": "READ_ONLY_STARTUP_PROBE", "run_directory": str(directory),
                   "helper_sha256": EXPECTED, "audio_capture": False, "routing_writes": False,
                   "remote_file_writes": False, "closeout_modified": False})
        helper = self.stage("helper_identity_and_account", load_helper, lambda _: {"sha256": EXPECTED})
        if helper is None:
            return self.finish()
        scope = self.stage("failed_run_records", lambda: validate_scope(helper, directory),
                           lambda item: {"inventory": item[1], "closeout_status": "PENDING"})
        if scope is None:
            return self.finish()
        baseline, before_inventory = scope
        # Ignore only THIS run when observing the same startup platform checks.
        # This is diagnostic parity, not clearance of the pending execution gate.
        checks = self.stage("startup_platform_checks", lambda: helper["inspect_platform"](directory)[0])
        config = self.stage("baseline_before", lambda: self.snapshot(helper),
                            lambda value: {**value, "matches_failed_run_baseline": value == baseline})
        lock = self.stage("guard_lock_metadata", inspect_lock)
        usb = self.stage("usb_dependencies_and_backend", self.usb_factory, lambda _: {"backend_available": True})
        safe = (checks is not None and all(row["ok"] for row in checks)
                and config == baseline and lock is not None and not lock["owners"])
        if usb is not None:
            try:
                if safe:
                    device = self.stage("usb_device_enumeration", usb.enumerate)
                    if device is not None:
                        for name in ROUTES:
                            self.stage("usb_read_" + name, lambda name=name: usb.read_route(name))
                else:
                    self.emit({"event": "usb_reads_skipped", "reason": "startup_prerequisite_unavailable_or_changed"})
            finally:
                self.stage("usb_handle_closed", usb.close, closing=True)
        self.stage("robot_state_after", lambda: helper["inspect_platform"](directory)[0])
        self.stage("baseline_after", lambda: self.snapshot(helper),
                   lambda value: {**value, "matches_failed_run_baseline": value == baseline})
        self.stage("run_inventory_after", lambda: helper["inventory"](directory),
                   lambda value: {"inventory": value, "unchanged": value == before_inventory})
        self.finish()

    @staticmethod
    def snapshot(helper):
        return {"asoundrc_sha256": hashlib.sha256(read_regular(Path("/home/pollen/.asoundrc"))).hexdigest(),
                "mixer_sha256": helper["mixer_digest"](), "parameters": helper["read_parameters"](),
                "helper_sha256": EXPECTED, "privacy_profile": helper["PRIVACY_PROFILE"]}

    def finish(self):
        self.emit({"event": "finished", "status": "REVIEW_REQUIRED", "closeout_status": "PENDING",
                   "unavailable_stages": [row["stage"] for row in self.stages if row["status"] == "unavailable"],
                   "original_exception_recovered": False, "guard_started": False,
                   "audio_capture": False, "routing_writes": False, "remote_file_writes": False,
                   "not_exercised": ["core_limit_set", "lock_acquisition", "journal_write", "guard_IPC"],
                   "transient_original_failure_may_not_recur": True})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--run-directory", type=Path)
    args = parser.parse_args(argv)
    if not args.probe:
        parser.print_help()
        return 0
    if args.run_directory is None:
        parser.error("--run-directory is required")
    Probe().collect(args.run_directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
