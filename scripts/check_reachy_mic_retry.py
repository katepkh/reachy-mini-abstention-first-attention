"""One read-only verification of the corrected USB reader, not a new audio run.

Default is help. Send only the reviewed read-only probe plus the candidate's
exact reader/error definitions through SSH stdin. Never deploy the candidate,
call its guard, clear a latch, change a route or open audio.
"""

import argparse
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import read_reachy_mic_startup as previous
from scripts import run_reachy_mic_diagnostic as original
from tools import reachy_mic_health_v3 as candidate


SCHEMA = "reachy-mic-retry-check-v1"
BASE_PROBE_HASH = "1fd10ec27fb2b35ab6bb09ba585dd6def626e29ee1c41c8bd3aac04732e51162"
OUTPUT = ROOT / "data/private/mic_retry_check" / original.SESSION
# These exact records were reviewed together with the terminal's pre-login
# "connect to host ... port 22: Connection timed out" message. Empty events or
# SSH exit 255 alone would NOT establish a connect-stage failure.
CONNECT_TIMEOUT_START_HASH = "dac42c7e66aa5e4618cc5932db2c09ce319731f3f535b1a03d66e9739352c3bb"
CONNECT_TIMEOUT_REPORT_HASH = "f831fc7f1e15edc3028c92675fb8771abc29e4a4feebc378cec5b1a4a139b4fc"


def reviewed_failure():
    directory, review_hash = previous.reviewed_run()
    raw = original.read_regular(previous.OUTPUT / "report.json", 1024 * 1024)
    report = json.loads(raw)
    if (report.get("schema") != previous.SCHEMA or report.get("source_sha256") != BASE_PROBE_HASH
            or report.get("ssh_exit_code") != 0 or report.get("transport_error") is not None
            or report.get("invalid_lines") != 0):
        raise RuntimeError("matching_completed_startup_probe_required")
    stages = {row.get("stage"): row for row in report.get("events", []) if row.get("event") == "stage_finished"}
    for key in candidate.ROUTES:
        event = stages.get("usb_read_" + key, {})
        if event.get("status") != "observed" or event.get("value", {}).get("status_byte") != 64:
            raise RuntimeError("reviewed_status_64_evidence_required")
    for name in ("baseline_before", "baseline_after"):
        if stages.get(name, {}).get("value", {}).get("matches_failed_run_baseline") is not True:
            raise RuntimeError("reviewed_baseline_match_required")
    if stages.get("run_inventory_after", {}).get("value", {}).get("unchanged") is not True:
        raise RuntimeError("reviewed_inventory_match_required")
    return directory, {"failure_review_sha256": review_hash, "startup_report_sha256": hashlib.sha256(raw).hexdigest()}


def reader_source():
    definitions = (candidate.Stop, candidate.USBReadError, candidate.GuardFailure,
                   candidate.safe_error_details, candidate.read_route_with_retry)
    constants = {key: getattr(candidate, key) for key in
                 ("USB_READ_BUDGET", "USB_READ_ATTEMPTS", "USB_RETRY_DELAY")}
    return ("import math\n" + "\n".join(key + " = " + repr(value) for key, value in constants.items())
            + "\n" + "\n".join(inspect.getsource(item) for item in definitions))


def remote_source():
    base = (ROOT / "tools/reachy_mic_startup_probe.py").read_bytes()
    if hashlib.sha256(base).hexdigest() != BASE_PROBE_HASH:
        raise RuntimeError("base_probe_source_changed")
    reader = reader_source()
    identity = hashlib.sha256(Path(candidate.__file__).read_bytes()).hexdigest()
    adapter = '''
error_details = safe_error_details
class RetryReadOnlyUSB(ReadOnlyUSB):
    def read_route(self, name):
        if name not in ROUTES or name in self.attempted or self.device is None:
            raise ProbeError("read_not_allowlisted_or_already_attempted")
        self.attempted.add(name)
        return read_route_with_retry(self.device, name)
class RetryProbe(Probe):
    def __init__(self):
        super().__init__(usb_factory=RetryReadOnlyUSB)
    def emit(self, item):
        super().emit({"candidate_sha256": CANDIDATE_HASH, "reader_sha256": READER_HASH, **item})
Probe = RetryProbe
main()
'''
    # The acquisition helper itself is NOT sent or evaluated on the robot.
    source = "namespace = {'__name__': 'read_only_retry_check'}\n"
    source += "exec(compile(" + repr(base) + ", '<pinned-read-only-probe>', 'exec'), namespace)\n"
    source += "exec(compile(" + repr(reader) + ", '<candidate-read-only-reader>', 'exec'), namespace)\n"
    source += "namespace.update(" + repr({"SCHEMA": SCHEMA, "CANDIDATE_HASH": identity,
                                          "READER_HASH": hashlib.sha256(reader.encode()).hexdigest()}) + ")\n"
    source += "exec(" + repr(adapter) + ", namespace)\n"
    return source.encode()


def decode_events(payload):
    if not isinstance(payload, bytes) or len(payload) > 1024 * 1024:
        raise ValueError("invalid_or_oversized_report")
    events, invalid = [], 0
    for line in payload.splitlines():
        try:
            value = json.loads(line)
            if (not isinstance(value, dict) or value.get("schema") != SCHEMA
                    or value.get("execution_authorized") is not False):
                raise ValueError("unexpected_contract")
            events.append(value)
        except (ValueError, UnicodeError):
            invalid += 1
    return events, invalid


def reviewed_connect_timeout(directory, evidence, source_hash):
    """Accept only the reviewed pre-login failure, never a generic failed run."""
    raw_start = original.read_regular(OUTPUT / "started.json")
    raw_report = original.read_regular(OUTPUT / "report.json")
    if (hashlib.sha256(raw_start).hexdigest() != CONNECT_TIMEOUT_START_HASH
            or hashlib.sha256(raw_report).hexdigest() != CONNECT_TIMEOUT_REPORT_HASH):
        raise RuntimeError("not_the_reviewed_connect_timeout")
    started, report = json.loads(raw_start), json.loads(raw_report)
    if (started.get("schema") != SCHEMA or report.get("schema") != SCHEMA
            or started.get("source_sha256") != source_hash or report.get("source_sha256") != source_hash
            or started.get("run_directory") != directory
            or any(started.get(key) != value for key, value in evidence.items())
            or started.get("execution_authorized") is not False
            or report.get("execution_authorized") is not False
            or report.get("events") != [] or report.get("invalid_lines") != 0
            or report.get("ssh_exit_code") != 255 or report.get("transport_error") is not None
            or report.get("closeout_status") != "PENDING"):
        raise RuntimeError("reviewed_connect_timeout_binding_changed")
    return {"replacement_reason": "reviewed_pre_login_connect_timeout",
            "previous_started_sha256": CONNECT_TIMEOUT_START_HASH,
            "previous_report_sha256": CONNECT_TIMEOUT_REPORT_HASH}


def collect(reviewed_replacement=False):
    directory, evidence = reviewed_failure()
    source = remote_source()
    source_hash = hashlib.sha256(source).hexdigest()
    replacement = reviewed_connect_timeout(directory, evidence, source_hash) if reviewed_replacement else {}
    output = OUTPUT.with_name(OUTPUT.name + "-connect-replacement-01") if reviewed_replacement else OUTPUT
    output.mkdir(parents=True, exist_ok=True)
    original.write_new(output / "started.json", {"schema": SCHEMA, "utc": original.utc_now(),
        "source_sha256": source_hash, **evidence, **replacement, "status": "PENDING", "execution_authorized": False,
        "automatic_retry": False, "run_directory": directory})
    if reviewed_replacement:
        print("ONE reviewed replacement for the pre-login connection timeout. Original records preserved.", flush=True)
    print("ONE READ-ONLY USB retry check. Keep Reachy's apps closed and phone playback paused.", flush=True)
    print("No audio, routing writes, helper installation or close-out changes.", flush=True)
    print("Only status-64 reads may repeat: at most 10 attempts within 500 ms per register.", flush=True)
    print("Enter the SSH password if prompted; characters are invisible.", flush=True)
    code, error, payload = None, None, b""
    try:
        result = subprocess.run(previous.ssh_command(directory), input=source, stdout=subprocess.PIPE, timeout=120)
        code, payload = result.returncode, result.stdout
    except subprocess.TimeoutExpired as failure:
        error, payload = "ssh_timeout", failure.output or b""
    except (OSError, KeyboardInterrupt) as failure:
        error = type(failure).__name__
    events, invalid = decode_events(payload)
    target = output / "report.json"
    original.write_new(target, {"schema": SCHEMA, "utc": original.utc_now(), "source_sha256": source_hash,
        **replacement,
        "events": events, "invalid_lines": invalid, "ssh_exit_code": code, "transport_error": error,
        "execution_authorized": False, "closeout_status": "PENDING", "automatic_retry": False})
    print("REPORT SAVED: " + str(target), flush=True)
    print("Send this path for review. Do not start the two-pair diagnostic or repeat this check.", flush=True)
    return 0 if code == 0 and not invalid and events and events[-1].get("event") == "finished" else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--collect", action="store_true")
    action.add_argument("--retry-reviewed-connect-timeout", action="store_true",
                        help="One separately logged read-only replacement for the reviewed pre-login timeout only.")
    args = parser.parse_args(argv)
    if not args.collect and not args.retry_reviewed_connect_timeout:
        parser.print_help()
        return 0
    return collect(reviewed_replacement=args.retry_reviewed_connect_timeout)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as error:
        print("Read-only check stopped: " + type(error).__name__ + ". Send the output; do not retry.", file=sys.stderr)
        raise SystemExit(2)
