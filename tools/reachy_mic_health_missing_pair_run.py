"""Corrected session missing-pair-v3-02; separate private approval required.

No Reachy SDK construction, robot motion, HTTP POST, firmware operation, or raw
audio file output. Hardware imports are deferred until explicit execution.
See docs/MICROPHONE_HEALTH_DIAGNOSTIC.md before deploying or running.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import re
import selectors
import shutil
import signal
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request


SCHEMA = "reachy-mic-health-v3-session"
EXECUTION_RELEASED = True  # Still requires exact session authorization plus live confirmation.
EXECUTION_REQUIRES_PRIVATE_AUTHORIZATION = True
SESSION = "missing-pair-v3-02"
CANDIDATE_SHA256 = "cfa88aa8c30fb4a9f2d5b55f367117ceef6ab6a1cc5ea9e3acb90d72cb6dec87"
AUTHORIZATION_PATH = Path("/home/pollen/reachy_mic_missing_pair_v3_02_authorization.json")
PRIVACY_PROFILE = "application-numeric-artifacts-os-residuals-disclosed-v1"
RUN_ROOT = Path("/home/pollen/reachy-mic-health-runs-v2")
SESSION_DIRECTORY = RUN_ROOT / ("run-" + SESSION)
CLOSEOUT_SCHEMA = "reachy-mic-closeout-v1"
RECORD_NAMES = {"baseline.json", "approval.json", "guard.json", "result.json", "closeout.json"}
RATE = 16000
ROUTES = ("AUDIO_MGR_OP_L", "AUDIO_MGR_OP_R")
BASELINE = {key: [8, 0] for key in ROUTES}
PAIRS = ({ROUTES[0]: [3, 2], ROUTES[1]: [3, 3]},)
PAIR_LIMIT = 40.0
RESTORE_LIMIT = 5.0
ACK = ("APPROVE MIC INPUTS 2 AND 3 ONLY; NO OTHER AUDIO CLIENTS; RESTORE ROUTING; "
       "ACCEPT OS RESIDUALS; CHECK RUN FILES")
PARAMETERS = (
    "VERSION", "AEC_NUM_MICS", "AEC_MIC_ARRAY_TYPE", "AEC_MIC_ARRAY_GEO",
    *ROUTES, "AUDIO_MGR_MIC_GAIN", "AUDIO_MGR_REF_GAIN",
    "AUDIO_MGR_SELECTED_CHANNELS", "AUDIO_MGR_SYS_DELAY", "SHF_BYPASS",
    "PP_AGCONOFF", "PP_MIN_NS", "PP_MIN_NN", "PP_ECHOONOFF",
    "AEC_ASROUTONOFF", "AEC_FIXEDBEAMSONOFF",
)
SOURCE_HASHES = {
    "audio_doa.py": "7a670a00c1cf5c765a8c7069af5c0051deb078146095e63be73c269b0637e628",
    "audio_control_utils.py": "f975055dde2bc72830f34e4c093b735a463fe9335807ca5a271bacef7787c729",
}


class Stop(RuntimeError):
    """A bounded diagnostic stops; do not improvise a retry."""


USB_READ_BUDGET = 0.5
USB_READ_ATTEMPTS = 10
USB_RETRY_DELAY = 0.01


class USBReadError(Stop):
    def __init__(self, reason, details):
        super().__init__(reason)
        self.details = {**details, "reason": reason}


class GuardFailure(Stop):
    def __init__(self, details):
        super().__init__("guard_failure_reported")
        self.details = details


def safe_error_details(error, depth=0):
    """Bounded control metadata only; never export arbitrary stderr/tracebacks."""
    details = {"error_type": type(error).__name__}
    if isinstance(error, (USBReadError, GuardFailure)):
        details["details"] = error.details
    if isinstance(error, Stop) or type(error).__name__ in ("ProbeError", "Stop"):
        reason = str(error)
        if re.fullmatch(r"[A-Za-z0-9_;:. -]{1,200}", reason):
            details["reason"] = reason
    for name in ("errno", "backend_error_code", "returncode"):
        value = getattr(error, name, None)
        if type(value) is int:
            details[name] = value
    if isinstance(error, ImportError):
        name = getattr(error, "name", None)
        if isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9_.]{1,100}", name):
            details["missing_module"] = name
    cause = error.__cause__ or error.__context__
    if cause is not None and cause is not error and depth < 2:
        details["preceding_error"] = safe_error_details(cause, depth + 1)
    return details


def read_route_with_retry(device, key, *, deadline=None, clock=time.monotonic, sleep=time.sleep):
    """Vendor-IN only. Retry status 64, never a transfer exception or a write.

    The original 500-ms read allowance covers ALL attempts and inter-read waits.
    An enclosing pair/restoration deadline can only shorten it. timeout=0 would
    mean unlimited in libusb, so never issue a transfer with less than 1 ms left.
    """
    if key not in ROUTES:
        raise USBReadError("parameter_not_allowlisted", {"attempts": 0})
    started = clock()
    end = min(started + USB_READ_BUDGET, deadline) if deadline is not None else started + USB_READ_BUDGET
    statuses, lengths, timeouts = [], [], []
    def details():
        return {"parameter": key, "attempts": len(timeouts), "status_bytes": statuses[:],
                "response_lengths": lengths[:], "timeouts_ms": timeouts[:],
                "elapsed_ms": round((clock() - started) * 1000, 3)}
    command = 15 if key == ROUTES[0] else 19
    for attempt in range(USB_READ_ATTEMPTS):
        timeout_ms = min(500, math.floor((end - clock()) * 1000))
        if timeout_ms < 1:
            raise USBReadError("usb_read_deadline", details())
        timeouts.append(timeout_ms)
        try:
            response = bytes(device.ctrl_transfer(0xC0, 0, 0x80 | command, 35, 3, timeout_ms))
        except Exception as error:
            failure = {**details(), **safe_error_details(error)}
            raise USBReadError("usb_transfer_failed", failure) from error
        lengths.append(len(response))
        statuses.append(response[0] if response else None)
        if clock() >= end:
            raise USBReadError("usb_read_deadline", details())
        if len(response) != 3:
            raise USBReadError("usb_short_or_oversized_read", details())
        if response[0] == 0:
            return {"values": list(response[1:]), **details()}
        if response[0] != 64:
            raise USBReadError("usb_unexpected_status", details())
        if attempt + 1 == USB_READ_ATTEMPTS:
            raise USBReadError("usb_retry_limit", details())
        if end - clock() <= USB_RETRY_DELAY + 0.001:
            raise USBReadError("usb_read_deadline", details())
        sleep(USB_RETRY_DELAY)
    raise USBReadError("usb_retry_limit", details())


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save_json(path, value):
    """Atomic numeric/control-only records, never a PCM sink."""
    temporary = path.with_suffix(path.suffix + ".new")
    # A stale temporary file/link is evidence to review, not something to clobber.
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                         getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        json.dump(value, output, indent=2, allow_nan=False)
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def private_directory(path):
    """No links, unexpected owner, or shared permissions on the run root/child."""
    info = path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or path.is_symlink()
            or getattr(info, "st_file_attributes", 0) & 0x400
            or (hasattr(os, "getuid") and info.st_uid != os.getuid())
            or (sys.platform == "linux" and info.st_mode & 0o077)):
        raise Stop("run_directory_not_private_regular_directory")


def inventory(directory):
    """Immediate-child metadata only; never follow links or inspect contents."""
    private_directory(directory)
    rows = []
    with os.scandir(directory) as entries:
        for entry in entries:
            if len(rows) >= 128:
                raise Stop("run_inventory_limit")
            info = entry.stat(follow_symlinks=False)
            kind = ("link" if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400
                    else "file" if stat.S_ISREG(info.st_mode) else "other")
            rows.append({"name": entry.name, "kind": kind, "bytes": info.st_size,
                         "mtime_ns": info.st_mtime_ns})
    return sorted(rows, key=lambda row: row["name"])


def pending_runs(root=None, current=None):
    """Private numeric records only; missing/unsafe/incomplete records block reuse."""
    root = RUN_ROOT if root is None else root
    if not root.exists() and not root.is_symlink():
        return []
    private_directory(root)
    pending = []
    with os.scandir(root) as entries:
        for index, entry in enumerate(entries):
            if index >= 128:
                raise Stop("run_registry_limit_review_required")
            path = Path(entry.path)
            if current is not None and path == current:
                continue
            try:
                private_directory(path)
                target = path / "closeout.json"
                info = target.lstat()
                if (not stat.S_ISREG(info.st_mode) or target.is_symlink()
                        or getattr(info, "st_file_attributes", 0) & 0x400 or info.st_size > 131072):
                    raise Stop("unsafe_closeout_record")
                record = json.loads(target.read_text())
                if (record.get("schema") != CLOSEOUT_SCHEMA
                        or record.get("scope") != str(path)
                        or record.get("status") not in ("CHECKED_NO_UNEXPECTED_FILES", "CLEANED_AND_RECHECKED")
                        or record.get("restoration_verified") is not True
                        or record.get("capture_exit_verified") is not True):
                    pending.append(path.name)
                # A new unexpected entry after close-out reopens the run.
                elif any(row["kind"] != "file" or row["name"] not in RECORD_NAMES
                         for row in inventory(path)):
                    pending.append(path.name)
            except (OSError, ValueError, AttributeError, Stop):
                pending.append(path.name)
    return sorted(pending)


def begin_closeout(directory):
    before = inventory(directory)
    if before:
        raise Stop("new_run_directory_not_empty")
    record = {"schema": CLOSEOUT_SCHEMA, "run_id": directory.name,
              "started_utc": utc_now(), "scope": str(directory),
              "helper_sha256": digest(Path(__file__).read_bytes()),
              "privacy_profile": PRIVACY_PROFILE, "before": before,
              "status": "PENDING", "reason": "run_not_closed",
              "restoration_verified": False, "capture_exit_verified": False,
              "content_inspected": False, "forensic_erasure_claim": False,
              "deleted_files": []}
    save_json(directory / "closeout.json", record)
    return record


def finish_closeout(directory, record, *, restoration_verified, capture_exit_verified):
    """No deletion. A crash/disconnect before this leaves a durable PENDING record."""
    record = {**record, "checked_utc": utc_now(), "restoration_verified": restoration_verified,
              "capture_exit_verified": capture_exit_verified, "status": "PENDING"}
    try:
        after = inventory(directory)
        unexpected = [row for row in after if row["kind"] != "file" or row["name"] not in RECORD_NAMES]
        record.update(after=after, unexpected=unexpected)
        if unexpected:
            record["reason"] = "unexpected_entries_exact_path_review_required"
        elif not restoration_verified or not capture_exit_verified:
            record["reason"] = "process_exit_or_restoration_unverified"
        else:
            record.update(status="CHECKED_NO_UNEXPECTED_FILES", reason=None)
    except (OSError, Stop):
        record["reason"] = "after_inventory_unavailable"
    save_json(directory / "closeout.json", record)
    return record


class Stats:
    """Integer sufficient statistics; no retained sample arrays."""

    def __init__(self):
        self.n = 0
        self.sum = [0, 0]
        self.sq = [0, 0]
        self.peak = [0, 0]
        self.zeros = [0, 0]
        self.clips = [0, 0]
        self.last = [None, None]
        self.run = [0, 0]
        self.longest = [0, 0]
        self.cross = 0
        self.equal = 0

    def feed(self, pcm):
        if len(pcm) % 4:
            raise Stop("incomplete_stereo_frame")
        for left, right in struct.iter_unpack("<hh", pcm):
            self.n += 1
            self.cross += left * right
            self.equal += left == right
            for channel, value in enumerate((left, right)):
                self.sum[channel] += value
                self.sq[channel] += value * value
                self.peak[channel] = max(self.peak[channel], abs(value))
                self.zeros[channel] += value == 0
                self.clips[channel] += value in (-32768, 32767)
                self.run[channel] = self.run[channel] + 1 if value == self.last[channel] else 1
                self.last[channel] = value
                self.longest[channel] = max(self.longest[channel], self.run[channel])

    def report(self):
        channels = []
        variances = []
        for channel in (0, 1):
            mean = self.sum[channel] / self.n if self.n else 0
            variance = max(0.0, self.sq[channel] / self.n - mean * mean) if self.n else 0
            variances.append(variance)
            rms = math.sqrt(variance) / 32768
            channels.append({
                "dc": mean / 32768, "rms": rms,
                "rms_dbfs": 20 * math.log10(rms) if rms else None,
                "zero_variance": variance == 0,
                "peak": self.peak[channel] / 32768,
                "zero_fraction": self.zeros[channel] / self.n if self.n else None,
                "clip_fraction": self.clips[channel] / self.n if self.n else None,
                "longest_unchanged_samples": self.longest[channel],
            })
        covariance = (self.cross / self.n - self.sum[0] * self.sum[1] / self.n**2) if self.n else 0
        denominator = math.sqrt(variances[0] * variances[1])
        correlation = max(-1.0, min(1.0, covariance / denominator)) if denominator else None
        return {"frames": self.n, "channels": channels, "correlation": correlation,
                "equal_fraction": self.equal / self.n if self.n else None}


class RouteGuard:
    """Only writer; independent from the audio process and its terminal.

    The injected board has two bounded read/write methods. Clock and journal
    are injectable so failures can be exercised without opening hardware.
    """

    def __init__(self, board, journal, clock=time.monotonic):
        self.board, self.journal, self.clock = board, journal, clock
        self.baseline = {key: board.read(key) for key in ROUTES}
        if self.baseline != BASELINE:
            raise Stop("unexpected_baseline_routes")
        self.used = 0
        self.dirty = False
        self.terminal = False
        self.deadline = None
        self.restoration = "NOT_CHANGED"
        self.events = []
        self.note("baseline_preserved")  # Journal failure prohibits any write.

    def note(self, event, persist=True):
        self.events.append({"event": event, "monotonic_s": self.clock(),
                            "pairs_reserved": self.used, "restoration": self.restoration})
        if persist:
            self.journal({"schema": SCHEMA, "baseline": self.baseline, "events": self.events,
                          "dirty": self.dirty, "terminal": self.terminal,
                          "restoration": self.restoration})

    def read_before(self, key, deadline=None):
        # Fakes retain their simple interface; hardware receives the outer budget.
        if hasattr(self.board, "read_before"):
            return self.board.read_before(key, deadline)
        return self.board.read(key)

    def current(self):
        return {key: self.read_before(key, self.deadline) for key in ROUTES}

    def begin(self, pair):
        if self.terminal or self.dirty or type(pair) is not int or pair != self.used or pair not in range(len(PAIRS)):
            raise Stop("sequence_or_terminal_state")
        if self.current() != self.baseline:
            self.terminal = True
            self.note("external_route_drift_before_write")
            raise Stop("external_route_drift")
        self.used += 1
        self.dirty = True  # A timed-out USB write may still have been applied.
        self.restoration = "PENDING"
        try:
            self.note("pair_reserved_before_write")
        except BaseException:
            self.dirty = False  # No device write has yet been attempted.
            self.terminal = True
            raise
        self.deadline = self.clock() + PAIR_LIMIT
        try:
            for key in ROUTES:
                if self.clock() >= self.deadline:
                    raise Stop("pair_deadline")
                self.board.write(key, PAIRS[pair][key])
            if self.current() != PAIRS[pair]:
                raise Stop("route_readback_mismatch")
            # Do not block the active watchdog on filesystem I/O.
            self.note("pair_routes_verified", persist=False)
        except BaseException:
            self.terminal = True
            self.restore()
            raise

    def restore(self):
        if not self.dirty:
            return self.restoration
        end = self.clock() + RESTORE_LIMIT
        failed = False
        # A failed journal must never prevent a restoration attempt.
        for key in ROUTES:
            try:
                if self.clock() >= end:
                    raise Stop("restore_deadline")
                current = self.read_before(key, end)
                if current not in (self.baseline[key], PAIRS[self.used - 1][key]):
                    raise Stop("external_route_drift_preserved")
                if self.clock() >= end:
                    raise Stop("restore_deadline")
                self.board.write(key, self.baseline[key])
            except BaseException:
                failed = True
        for _ in range(2):
            for key in ROUTES:
                try:
                    if self.clock() >= end or self.read_before(key, end) != self.baseline[key]:
                        raise Stop("restore_readback")
                except BaseException:
                    failed = True
        failed = failed or self.clock() > end
        self.restoration = "RESTORATION_UNVERIFIED" if failed else "ROUTES_RESTORED"
        self.dirty = failed
        self.deadline = None
        if failed:
            self.terminal = True
        try:
            self.note("restoration_finished")
        except BaseException:
            self.terminal = True
            self.restoration = "RESTORATION_UNVERIFIED"
        return self.restoration

    def tick(self):
        if self.deadline is not None and self.clock() >= self.deadline:
            self.terminal = True
            self.restore()
            return True
        return False


class FakeBoard:
    """For synthetic rehearsal only; never detects or opens hardware."""

    def __init__(self):
        self.values = {key: value[:] for key, value in BASELINE.items()}
        self.writes = []

    def read(self, key):
        return self.values[key][:]

    def write(self, key, value):
        if key not in ROUTES or value not in ([8, 0], [3, 0], [3, 1], [3, 2], [3, 3]):
            raise Stop("write_not_allowlisted")
        self.writes.append((key, value[:]))
        self.values[key] = value[:]


class USBBoard:
    """Minimal two-field XVF3800 adapter; no SDK constructors or bulk apply."""

    def __init__(self):
        import usb.core
        import usb.util
        from libusb_package import get_libusb1_backend
        devices = list(usb.core.find(find_all=True, idVendor=0x38FB, idProduct=0x1001,
                                    backend=get_libusb1_backend()))
        if len(devices) != 1:
            raise Stop("expected_one_audio_board")
        self.dev = devices[0]
        self.util = usb.util

    @staticmethod
    def command(key):
        if key not in ROUTES:
            raise Stop("parameter_not_allowlisted")
        return 15 if key == ROUTES[0] else 19

    def read(self, key):
        return self.read_before(key, None)

    def read_before(self, key, deadline):
        return read_route_with_retry(self.dev, key, deadline=deadline)["values"]

    def write(self, key, value):
        command = self.command(key)
        allowed = (BASELINE[key], *(pair[key] for pair in PAIRS))
        if value not in allowed or any(type(item) is not int for item in value):
            raise Stop("route_not_allowlisted")
        count = self.dev.ctrl_transfer(0x40, 0, command, 35, bytes(value), 500)
        if count != 2:
            raise Stop("usb_short_write")

    def close(self):
        self.util.dispose_resources(self.dev)


def get_json(route):
    allowed = {"/api/daemon/status", "/api/apps/current-app-status"}
    allowed.update("/api/audio/config/parameter/" + name for name in PARAMETERS)
    if route not in allowed:
        raise Stop("http_route_not_allowlisted")
    # Disable proxies and redirects; GET only to the robot's loopback daemon.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            raise Stop("unexpected_redirect")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open("http://127.0.0.1:8000" + route, timeout=0.5) as response:
        payload = response.read(65537)
        if len(payload) > 65536:
            raise Stop("oversized_status")
        return json.loads(payload)


def robot_blockers(status):
    """D030: running media daemon is not permission for enabled motors."""
    if not isinstance(status, dict):
        return ["invalid_daemon_status"]
    problems = []
    if status.get("state") != "running" or status.get("version") != "1.9.0" or status.get("error", True) is not None:
        problems.append("daemon_state_version_or_error")
    if status.get("simulation_enabled") is not False or status.get("mockup_sim_enabled") is not False:
        problems.append("not_verified_physical_backend")
    if status.get("no_media") is not False or status.get("media_released") is not False:
        problems.append("daemon_media_unavailable")
    backend = status.get("backend_status")
    if not isinstance(backend, dict):
        problems.append("missing_backend_status")
    else:
        if backend.get("motor_control_mode") != "disabled":
            problems.append("motor_mode_not_verified_disabled")
        if backend.get("error", True) is not None:
            problems.append("backend_error_or_unknown")
    # backend.ready is not a motor-mode signal in the pinned implementation.
    return problems


def check_robot_status():
    problems = robot_blockers(get_json("/api/daemon/status"))
    if problems:
        raise Stop(";".join(problems))


def check_app():
    if get_json("/api/apps/current-app-status") is not None:
        raise Stop("active_robot_app")


def check_robot():
    check_robot_status()
    check_app()


def validate_asoundrc(text):
    """Accept only the observed simple configuration; whitespace/comments ignored."""
    text = re.sub(r"#[^\n]*", "", text)
    tokens = re.findall(r'"[^"\n]*"|[{}]|[^\s{}]+', text)
    expected = '''pcm.!default { type hw card 0 }
ctl.!default { type hw card 0 }
pcm.reachymini_audio_sink { type dmix ipc_key 4241
slave { pcm "hw:0,0" channels 2 period_size 1024 buffer_size 4096 rate 16000 }
bindings { 0 0 1 1 } }
pcm.reachymini_audio_src { type dsnoop ipc_key 4242
slave { pcm "hw:0,0" channels 2 rate 16000 period_size 1024 buffer_size 4096 } }'''
    if tokens != re.findall(r'"[^"\n]*"|[{}]|[^\s{}]+', expected):
        raise Stop("asoundrc_differs_from_reviewed_snapshot")


def capture_owner():
    """Inspect the existing reader; do not change its limits or lifecycle."""
    result = subprocess.run(["fuser", "/dev/snd/pcmC0D0c"], capture_output=True,
                            check=True, timeout=2)
    owners = result.stdout.decode("ascii").split()
    if len(owners) != 1 or not owners[0].isdigit():
        raise Stop("capture_owner_not_single_verified_daemon")
    process = Path("/proc") / owners[0]
    arguments = process.joinpath("cmdline").read_bytes().rstrip(b"\0").split(b"\0")
    expected = [b"-u", b"-m", b"reachy_mini.daemon.app.main",
                b"--wireless-version", b"--no-wake-up-on-start"]
    if arguments[1:] != expected or process.stat().st_uid != os.getuid():
        raise Stop("capture_owner_differs_from_reviewed_daemon")
    limits = process.joinpath("limits").read_text()
    if not re.search(r"(?m)^Max core file size\s+0\s+\S+\s+bytes\s*$", limits):
        raise Stop("existing_daemon_core_retention_not_excluded")
    return int(owners[0])


def require_robot_account():
    if sys.platform != "linux" or Path.home() != Path("/home/pollen"):
        raise Stop("requires_reviewed_robot_linux_account")


def swap_metadata():
    lines = Path("/proc/swaps").read_text().strip().splitlines()
    if not lines or lines[0].split() != ["Filename", "Type", "Size", "Used", "Priority"]:
        raise Stop("swap_metadata_unavailable")
    rows = []
    for line in lines[1:]:
        fields = line.split()
        if len(fields) != 5:
            raise Stop("invalid_swap_metadata")
        rows.append({"device": fields[0], "type": fields[1], "size_kib": int(fields[2]),
                     "used_kib": int(fields[3]), "priority": int(fields[4])})
    return {"active_swap": rows, "settings_changed": False,
            "privacy_profile": PRIVACY_PROFILE, "os_residuals_possible": True}


def check_core_pattern():
    if Path("/proc/sys/kernel/core_pattern").read_text().lstrip().startswith("|"):
        raise Stop("piped_core_collector_requires_separate_review")


def protect_own_process():
    """Execution/guard only. Never change the daemon or global OS settings."""
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def check_tool(executable):
    if shutil.which(executable) is None:
        raise Stop("missing_" + executable)


def check_card():
    if not re.search(r"(?m)^\s*0\s+\[Audio\s*\].*USB-Audio - Reachy Mini Audio", Path("/proc/asound/cards").read_text()):
        raise Stop("audio_device_missing")
    if Path("/proc/asound/card0/usbid").read_text().strip().lower() != "38fb:1001":
        raise Stop("audio_card_identity_drift")


def check_source(name, expected):
    media = Path("/venvs/mini_daemon/lib/python3.12/site-packages/reachy_mini/media")
    if digest((media / name).read_bytes()) != expected:
        raise Stop("installed_source_drift")


def inspect_platform(current=None):
    """Collect all independent machine blockers, without opening media or USB."""
    require_robot_account()
    checks = []
    def probe(name, action):
        try:
            value = action()
            checks.append({"name": name, "ok": True, "value": value})
            return value
        except Exception as exc:
            checks.append({"name": name, "ok": False,
                           "reason": str(exc) if isinstance(exc, Stop) else type(exc).__name__})
    probe("swap_metadata", swap_metadata)  # D029: disclose, do not disable/reject.
    probe("core_pattern", check_core_pattern)
    for executable in ("arecord", "timeout", "amixer", "fuser"):
        probe("tool_" + executable, lambda executable=executable: check_tool(executable))
    probe("audio_card", check_card)
    config = probe("asoundrc", lambda: Path("/home/pollen/.asoundrc").read_text())
    if config is not None:
        checks[-1]["value"] = {"sha256": digest(config.encode())}
        probe("asoundrc_contract", lambda: validate_asoundrc(config))
    for name, expected in SOURCE_HASHES.items():
        probe("source_" + name, lambda name=name, expected=expected: check_source(name, expected))
    probe("capture_owner", capture_owner)
    probe("robot_status", check_robot_status)
    probe("current_app", check_app)
    pending = probe("previous_closeout", lambda: pending_runs(current=current))
    if pending:
        checks[-1].update(ok=False, reason="previous_closeout_pending")
    return checks, config


def platform_checks(current=None):
    checks, config = inspect_platform(current)
    failures = [item["name"] + ":" + item["reason"] for item in checks if not item["ok"]]
    if failures:
        raise Stop(";".join(failures))
    return config.encode()


def read_parameters():
    parameters = {}
    end = time.monotonic() + 10
    for name in PARAMETERS:
        if time.monotonic() >= end:
            raise Stop("snapshot_deadline")
        item = get_json("/api/audio/config/parameter/" + name)
        if item.get("name") != name or not isinstance(item.get("values"), list):
            raise Stop("invalid_parameter_response")
        parameters[name] = item["values"]
    if parameters["VERSION"] != [2, 1, 2] or parameters["AEC_NUM_MICS"] != [4]:
        raise Stop("firmware_or_microphone_inventory_drift")
    if any(parameters[key] != BASELINE[key] for key in ROUTES):
        raise Stop("unexpected_baseline_routes")
    return parameters


def mixer_digest():
    mixer = subprocess.run(["amixer", "-c", "0", "scontents"], capture_output=True, check=True, timeout=2)
    return digest(mixer.stdout)


def snapshot(current=None):
    config = platform_checks(current)
    return {"asoundrc_sha256": digest(config), "mixer_sha256": mixer_digest(),
            "parameters": read_parameters(), "helper_sha256": digest(Path(__file__).read_bytes()),
            "privacy_profile": PRIVACY_PROFILE}


def preflight_report():
    checks, _ = inspect_platform()
    for name, action in (("parameters", read_parameters), ("mixer", mixer_digest)):
        try:
            checks.append({"name": name, "ok": True, "value": action()})
        except Exception as exc:
            checks.append({"name": name, "ok": False,
                           "reason": str(exc) if isinstance(exc, Stop) else type(exc).__name__})
    return {"schema": SCHEMA, "mode": "READ_ONLY", "checked_utc": utc_now(),
            "helper_sha256": digest(Path(__file__).read_bytes()), "checks": checks,
            "machine_checks_passed": all(item["ok"] for item in checks),
            "consumer_isolation_verified": False, "execution_authorized": False,
            "privacy_profile": PRIVACY_PROFILE, "os_residuals_possible": True,
            "proposed_inventory_root": str(RUN_ROOT),
            "manual_requirements": ["fresh_operator_consumer_isolation_review",
                                    "physical_setup_and_motor_state_review",
                                    "specific_routing_acquisition_and_inventory_approval"]}


def serve_guard(board, journal, incoming, outgoing, clock=time.monotonic):
    """IPC reader may block; the independent guard loop never waits on it."""
    messages = queue.Queue(maxsize=8)
    def reader():
        try:
            while True:
                line = incoming.readline(4097)
                if not line or len(line) > 4096:
                    messages.put(None)
                    return
                messages.put(json.loads(line))
        except BaseException:
            messages.put(None)
    threading.Thread(target=reader, daemon=True).start()
    guard = RouteGuard(board, journal, clock)
    def send(value):
        outgoing.write(json.dumps(value, allow_nan=False) + "\n")
        outgoing.flush()
    last = clock()
    try:
        send({"status": "READY"})
        while not guard.terminal:
            if guard.tick():
                break
            if not guard.dirty and clock() - last > 60:
                break
            try:
                message = messages.get(timeout=0.05)
            except queue.Empty:
                continue
            last = clock()
            if not isinstance(message, dict):
                break
            if message == {"action": "finish"}:
                break
            if set(message) == {"action", "pair"} and message["action"] == "begin":
                guard.begin(message["pair"])
                send({"status": "ROUTED", "pair": message["pair"]})
            elif message == {"action": "restore"} and guard.dirty:
                send({"status": guard.restore()})
                if guard.used == len(PAIRS):
                    break
            else:
                raise Stop("invalid_guard_message")
    finally:
        guard.terminal = True
        # Do not retry an already unverified restoration automatically.
        if guard.dirty and guard.restoration != "RESTORATION_UNVERIFIED":
            guard.restore()
        try:
            guard.note("guard_finished")
            send({"status": guard.restoration})
        except (BrokenPipeError, OSError):
            pass


def guard_main(directory, progress=lambda stage: None):
    progress("session_authorization")
    require_execution_authorization()
    if Path(directory) != SESSION_DIRECTORY:
        raise Stop("wrong_session_guard_directory")
    progress("run_directory")
    directory = Path(directory)
    private_directory(RUN_ROOT)
    if directory.parent != RUN_ROOT or not directory.name.startswith("run-"):
        raise Stop("unexpected_recovery_directory")
    private_directory(directory)
    progress("platform_checks")
    platform_checks(directory)
    progress("own_core_limit")
    protect_own_process()
    progress("approval_and_closeout")
    if not (directory / "baseline.json").is_file():
        raise Stop("missing_baseline_manifest")
    approval = json.loads((directory / "approval.json").read_text())
    if approval != {"scope": ACK, "helper_sha256": digest(Path(__file__).read_bytes())}:
        raise Stop("missing_matching_operator_confirmation")
    closeout = json.loads((directory / "closeout.json").read_text())
    if (closeout.get("schema") != CLOSEOUT_SCHEMA or closeout.get("scope") != str(directory)
            or closeout.get("status") != "PENDING"
            or closeout.get("helper_sha256") != digest(Path(__file__).read_bytes())):
        raise Stop("missing_pending_closeout")
    # Held for the guard's lifetime, including restoration. Do not remove it:
    # unlinking a flock file can let a second guard lock a different inode.
    progress("guard_lock")
    import fcntl
    descriptor = os.open("/tmp/reachy-mic-health.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    lock_info = os.fstat(descriptor)
    if lock_info.st_uid != os.getuid() or lock_info.st_mode & 0o077:
        os.close(descriptor)
        raise Stop("unsafe_lock_file")
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BaseException:
        os.close(descriptor)
        raise Stop("another_guard_present")
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    def terminate(*_):
        raise Stop("guard_terminated")
    signal.signal(signal.SIGTERM, terminate)
    board = None
    try:
        progress("usb_backend_and_device")
        board = USBBoard()
        progress("guard_baseline_and_session")
        serve_guard(board, lambda value: save_json(directory / "guard.json", value), sys.stdin, sys.stdout)
    finally:
        try:
            if board is not None:
                board.close()
        finally:
            os.close(descriptor)


def guard_entry(directory, outgoing=sys.stdout):
    """Used by a future reviewed entrypoint; all startup/session errors are IPC."""
    stage = "entry"
    def progress(value):
        nonlocal stage
        stage = value
    try:
        guard_main(directory, progress)
        return 0
    except BaseException as error:
        outgoing.write(json.dumps({"status": "GUARD_ERROR", "stage": stage,
                                   **safe_error_details(error)}, allow_nan=False) + "\n")
        outgoing.flush()
        return 2


class GuardClient:
    def __init__(self, directory):
        self.process = subprocess.Popen([sys.executable, "-B", str(Path(__file__).resolve()),
                                         "--guard", str(directory)], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                        text=True, start_new_session=True, bufsize=1)
        self.messages = queue.Queue()
        def read():
            try:
                while True:
                    line = self.process.stdout.readline(4097)
                    if not line:
                        return
                    if len(line) > 4096:
                        self.messages.put({"status": "PROTOCOL_ERROR"})
                        return
                    self.messages.put(json.loads(line))
            except (ValueError, OSError):
                self.messages.put({"status": "PROTOCOL_ERROR"})
            finally:
                self.messages.put({"status": "EOF"})
        threading.Thread(target=read, daemon=True).start()
        try:
            self.expect("READY", timeout=15)
        except BaseException:
            self.close()
            raise

    def expect(self, status, timeout=7):
        try:
            message = self.messages.get(timeout=timeout)
        except queue.Empty as exc:
            raise Stop("guard_timeout") from exc
        if isinstance(message, dict) and message.get("status") == "GUARD_ERROR":
            raise GuardFailure(message)
        if not isinstance(message, dict):
            raise Stop("guard_protocol_error")
        if message.get("status") != status:
            raise Stop("guard_" + str(message.get("status")))
        return message

    def request(self, action, expected, **kwargs):
        if self.process.poll() is not None:
            raise Stop("guard_exited")
        self.process.stdin.write(json.dumps({"action": action, **kwargs}) + "\n")
        self.process.stdin.flush()
        return self.expect(expected)

    def close(self):
        # Closing the pipe, not killing the independent restoration process.
        if self.process.stdin and not self.process.stdin.closed:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=7)
        except subprocess.TimeoutExpired:
            raise Stop("guard_exit_unverified")


def capture_command():
    return ["timeout", "--signal=TERM", "--kill-after=1s", "39s", "arecord",
            "--quiet", "--nonblock", "--fatal-errors", "--device=reachymini_audio_src",
            "--file-type=raw", "--format=S16_LE", "--rate=16000", "--channels=2",
            "--duration=38", "--period-size=1024", "--buffer-size=4096",
            "--disable-resample", "--disable-channels", "--disable-format", "--disable-softvol"]


def stop_own_capture(process):
    # Check the owned session's entire process group, not just timeout's exit.
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            process.wait(timeout=1)
            return
        deadline = time.monotonic() + 1
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass
        while time.monotonic() < deadline:
            try:
                os.killpg(process.pid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.02)
    raise Stop("capture_process_group_exit_unverified")


def capture_pair(pair, result, guard):
    process = subprocess.Popen(capture_command(), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True)
    selector = None
    phases = {"flush": 2 * RATE, "quiet": 3 * RATE, "settle": 2 * RATE, "playback": 10 * RATE}
    phase = "flush"
    count = 0
    block = Stats()
    total = Stats()
    pcm = bytearray()
    started = last_pcm = last_check = time.monotonic()
    wait_started = None
    result.update({"pair": pair, "microphones": [PAIRS[pair][key][1] for key in ROUTES], "blocks": [],
                   "summaries": {}, "complete": False, "capture_exit_verified": False})
    try:
        print("WAIT - keep the phone PAUSED and stay silent. Do NOT press Enter; wait for PLAY.", flush=True)
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ, "pcm")
        selector.register(process.stderr, selectors.EVENT_READ, "error")
        selector.register(sys.stdin, selectors.EVENT_READ, "operator")
        for pipe in (process.stdout, process.stderr):
            os.set_blocking(pipe.fileno(), False)
        while True:
            now = time.monotonic()
            if now - started >= 37 or now - last_pcm > 2:
                raise Stop("capture_deadline_or_stall")
            if guard.process.poll() is not None:
                raise Stop("guard_exited_during_capture")
            if now - last_check >= 2:
                check_robot()
                last_check = time.monotonic()
            if phase == "wait" and now - wait_started >= 10:
                raise Stop("operator_deadline")
            events = selector.select(timeout=0.05)
            for key, _ in events:
                if key.data == "operator":
                    line = sys.stdin.readline()
                    if not line:
                        raise Stop("terminal_closed")
                    if phase != "wait" or line.strip():
                        raise Stop("unexpected_operator_input")
                    phase, count = "settle", 0
                    print("ENTER RECEIVED - keep the clip PLAYING. Do NOT press Enter again or pause until PAUSE appears.", flush=True)
                elif key.data == "error":
                    data = os.read(process.stderr.fileno(), 4096)
                    if data:
                        raise Stop("capture_driver_error")
                    selector.unregister(process.stderr)
                else:
                    data = os.read(process.stdout.fileno(), 65536)
                    if not data:
                        raise Stop("capture_ended_early")
                    last_pcm = time.monotonic()
                    pcm.extend(data)
            while len(pcm) >= 4:
                frames = len(pcm) // 4
                if phase == "wait":
                    del pcm[:frames * 4]
                    break
                take = min(frames, phases[phase] - count)
                if phase in ("quiet", "playback"):
                    take = min(take, RATE - block.n)
                    payload = pcm[:take * 4]
                    block.feed(payload)
                    total.feed(payload)
                    payload[:] = b"\x00" * len(payload)
                del pcm[:take * 4]
                count += take
                if phase in ("quiet", "playback") and block.n == RATE:
                    result["blocks"].append({"phase": phase, "second": count // RATE, **block.report()})
                    block = Stats()
                if count == phases[phase]:
                    if phase == "flush":
                        phase, count = "quiet", 0
                    elif phase == "quiet":
                        result["summaries"][phase] = total.report()
                        total = Stats()
                        phase = "wait"
                        wait_started = time.monotonic()
                        print("PLAY + ENTER NOW (both actions within 10 seconds):\n1. PHONE: tap Play on the SAME EXISTING CLIP at 50%.\n2. POWERSHELL: immediately press Enter ONCE in this window. Phone playback alone does not confirm this step.", flush=True)
                    elif phase == "settle":
                        phase, count = "playback", 0
                    else:
                        result["summaries"][phase] = total.report()
                        result["complete"] = True
                        return
    finally:
        result["elapsed_s"] = time.monotonic() - started
        if not result["complete"] and phase in ("quiet", "playback"):
            result["partial_phase"] = {"phase": phase, **total.report()}
        pcm[:] = b"\x00" * len(pcm)
        try:
            if selector is not None:
                selector.close()
        finally:
            try:
                stop_own_capture(process)
                result["capture_exit_verified"] = True
            finally:
                process.stdout.close()
                process.stderr.close()


def wait_enter(prompt):
    print(prompt, flush=True)
    selector = selectors.DefaultSelector()
    try:
        selector.register(sys.stdin, selectors.EVENT_READ)
        if not selector.select(timeout=30):
            raise Stop("preparation_not_confirmed")
        line = sys.stdin.readline()
        if not line or line.strip():
            raise Stop("preparation_not_confirmed")
    finally:
        selector.close()



def required_authorization():
    """Exact session capability; no user correspondence is copied to Reachy."""
    return {"schema": "reachy-mic-session-authorization-v1", "session": SESSION,
            "helper_sha256": digest(Path(__file__).read_bytes()),
            "candidate_sha256": CANDIDATE_SHA256, "remote_scope": SESSION_DIRECTORY.as_posix(),
            "run_limit": 1, "pair_limit": 1, "microphone_indices": [2, 3], "routing_and_transient_capture_approved": True,
            "physical_setup_confirmation_required_at_start": True,
            "consumer_isolation_confirmation_required_at_start": True,
            "os_residuals_accepted": True, "restoration_risk_accepted": True,
            "metadata_inventory_approved": True}


def validate_session_authorization(approved):
    required = required_authorization()
    if (not isinstance(approved, dict) or set(approved) != set(required)
            or any(type(approved[key]) is not type(value) or approved[key] != value
                   for key, value in required.items())):
        raise Stop("matching_session_authorization_required")
    return approved


def require_execution_authorization():
    """Reject unreleased builds, then require exact private session approval."""
    if not EXECUTION_RELEASED:
        raise Stop("candidate_execution_not_released")
    require_robot_account()
    path = AUTHORIZATION_PATH
    before = path.lstat()
    if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid()
            or before.st_mode & 0o077 or before.st_size > 8192):
        raise Stop("unsafe_session_authorization")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as source:
        opened = os.fstat(source.fileno())
        if (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) != (
                before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns):
            raise Stop("session_authorization_changed")
        payload = source.read(8193)
        after = os.fstat(source.fileno())
    if (len(payload) > 8192 or (opened.st_size, opened.st_mtime_ns) !=
            (after.st_size, after.st_mtime_ns)):
        raise Stop("session_authorization_changed")
    approved = json.loads(payload)
    return validate_session_authorization(approved)


def create_session_directory():
    """An exclusive fixed name remains spent after success, abort or corruption."""
    directory = SESSION_DIRECTORY
    directory.mkdir(mode=0o700)  # Never exist_ok, never remove/reset on error.
    private_directory(directory)
    return directory

def execute():
    if not sys.stdin.isatty():
        raise Stop("interactive_operator_required")
    require_execution_authorization()
    baseline = snapshot()  # No audio opened and no route changed.
    protect_own_process()
    print("Close all Reachy apps and browser/media clients, leaving the daemon running.")
    print("Phone: front mark, one metre, microphone height; same EXISTING CLIP at 50%, PAUSED at the start. Do not record anything new.")
    print("This changes TWO microphone-output routing fields temporarily and reads transient audio.")
    print("Restoration can fail after hardware/power loss. No firmware, gain, motion, or response.")
    print("No intentional raw-media files/export. OS swap/residual copies are possible; no erasure guarantee.")
    print("Session " + SESSION + "; metadata-only inventory: " + str(SESSION_DIRECTORY))
    print("This scope does not scan other folders. Unexpected files require review, not automatic deletion.")
    print("ONE missing pair only: inputs 2 and 3. Inputs 0 and 1 will NOT be measured again.")
    print("STAY IN POWERSHELL until the final report. There is NO second-pair prompt.")
    print("LIVE START CONFIRMATION: phone PAUSED at the beginning, same clip at 50%.")
    print("Confirm ONLY if Reachy is resting with head down, apps/pages and other audio clients closed, and you are beside it with clear mechanism space.")
    print("Typing the scope below confirms those current setup conditions. If unsure, do NOT confirm; stop for review.")
    print("Confirming below starts the ONLY pair quiet measurement automatically after fresh checks.")
    print("Do NOT press Enter again after confirmation. Keep the phone paused and wait for the live PLAY cue.")
    print("At that live cue, BOTH actions are required: tap Play on the phone, then immediately press Enter ONCE in PowerShell within 10 seconds. Do not wait for the clip to finish.")
    print("When ready, and after approval in the research chat, type exactly:\n" + ACK, flush=True)
    if input() != ACK:
        raise Stop("approval_not_confirmed")
    if snapshot() != baseline:
        raise Stop("baseline_changed_during_approval")
    RUN_ROOT.mkdir(mode=0o700, exist_ok=True)
    private_directory(RUN_ROOT)
    if pending_runs():
        raise Stop("previous_closeout_pending")
    directory = create_session_directory()
    closeout = begin_closeout(directory)  # Durable before any capture or route write.
    save_json(directory / "baseline.json", baseline)
    save_json(directory / "approval.json", {"scope": ACK, "helper_sha256": baseline["helper_sha256"]})
    report = {"schema": SCHEMA, "pair_results": [], "status": "INCOMPLETE",
              "helper_sha256": baseline["helper_sha256"], "retains_raw_media": False,
              "privacy_profile": PRIVACY_PROFILE, "os_residuals_possible": True}
    guard = None
    try:
        guard = GuardClient(directory)
        for pair in range(len(PAIRS)):
            print("ONLY PAIR STARTING (inputs 2 and 3) - keep phone PAUSED. No extra Enter; wait for PLAY.", flush=True)
            if snapshot(directory) != baseline:
                raise Stop("baseline_drift_before_pair")
            guard.request("begin", "ROUTED", pair=pair)
            result = {}
            report["pair_results"].append(result)
            try:
                capture_pair(pair, result, guard)
            finally:
                guard.request("restore", "ROUTES_RESTORED")
            if snapshot(directory) != baseline:
                raise Stop("post_restoration_sentinel_mismatch")
            result["restoration"] = "RESTORED"
            save_json(directory / "result.json", report)
            print("PAUSE THE PHONE NOW. Original routes and sentinel settings verified for this pair.", flush=True)
        report["status"] = "COMPLETE_RESTORED"
    except BaseException as exc:
        report["status"] = "ABORTED_REVIEW_REQUIRED"
        report["error_type"] = type(exc).__name__
        report["failure_details"] = safe_error_details(exc)
        if isinstance(exc, Stop):
            report["reason"] = str(exc)
    finally:
        if guard is not None:
            try:
                guard.close()
            except BaseException:
                report["status"] = "RESTORATION_UNVERIFIED"
        try:
            recovery = json.loads((directory / "guard.json").read_text())
            report["route_restoration"] = recovery["restoration"]
            if recovery["restoration"] not in ("ROUTES_RESTORED", "NOT_CHANGED") or snapshot(directory) != baseline:
                report["status"] = "RESTORATION_UNVERIFIED"
        except BaseException:
            report["status"] = "RESTORATION_UNVERIFIED"
        save_json(directory / "result.json", report)
        closed = finish_closeout(directory, closeout,
                                 restoration_verified=report["status"] != "RESTORATION_UNVERIFIED",
                                 capture_exit_verified=all(item.get("capture_exit_verified") is True
                                                           for item in report["pair_results"]))
        report["ordinary_file_closeout"] = closed["status"]
        save_json(directory / "result.json", report)
        print(json.dumps({"status": report["status"], "numeric_output_directory": str(directory)}), flush=True)
        print("PAUSE the phone. Stop. Preserve these numeric files; do not repeat, reset or resume the pilot.", flush=True)
    return 0 if report["status"] == "COMPLETE_RESTORED" and closed["status"] != "PENDING" else 2


def simulate():
    board = FakeBoard()
    records = []
    guard = RouteGuard(board, records.append)
    for pair in range(len(PAIRS)):
        guard.begin(pair)
        assert guard.restore() == "ROUTES_RESTORED"
    stats = Stats()
    stats.feed(b"".join(struct.pack("<hh", value, value // 2) for value in (-1000, 1000) * 100))
    return {"mode": "SYNTHETIC_ONLY", "hardware_opened": False, "restoration": guard.restoration,
            "reserved_pairs": guard.used, "synthetic_statistics": stats.report()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--simulate", action="store_true", help="offline synthetic rehearsal (default)")
    modes.add_argument("--preflight", action="store_true", help="robot-only read-only checks; no capture or routing")
    modes.add_argument("--execute", action="store_true", help="requires separate approval and interactive confirmation")
    modes.add_argument("--guard", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.guard:
        return guard_entry(args.guard)
    elif args.execute:
        return execute()
    elif args.preflight:
        print(json.dumps(preflight_report(), indent=2, allow_nan=False))
    else:
        print(json.dumps(simulate(), indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Stop, KeyboardInterrupt) as error:
        print("STOP: " + (str(error) or type(error).__name__), file=sys.stderr)
        raise SystemExit(2)
