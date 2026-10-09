"""Operator-supervised, single stock sleep request; never microphone acquisition.

Default is help. --sleep-once requires an interactive local console. Source is
sent over verified SSH to Python stdin, not installed on Reachy. The local
exclusive journal prevents rerunning this one-off authorization accidentally.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import inspect
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
JOURNAL = ROOT / "data/private/stock_sleep/standard-sleep-once-v1.jsonl"


def remote_once(request=None, emit=None, pause=None, clock=None):
    """At most one POST; observation failures never initiate recovery motion."""
    import json
    import time
    import uuid
    from datetime import datetime, timezone
    from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

    status_path = "/api/daemon/status"
    app_path = "/api/apps/current-app-status"
    lock_path = "/api/daemon/robot-app-lock-status"
    moves_path = "/api/move/running"
    state_path = ("/api/state/full?with_head_pose=false&with_body_yaw=false"
                  "&with_antenna_positions=false&with_control_mode=true&with_doa=false")
    sleep_path = "/api/move/play/goto_sleep"
    allowed_gets = {status_path, app_path, lock_path, moves_path, state_path}
    pause = pause or time.sleep
    clock = clock or time.monotonic
    emit = emit or (lambda item: print(json.dumps(item, allow_nan=False), flush=True))
    sent = False
    stage = "precheck"

    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            raise RuntimeError("redirect_refused")

    opener = build_opener(ProxyHandler({}), NoRedirect())

    def http(method, path):
        req = Request("http://127.0.0.1:8000" + path, method=method,
                      data=b"" if method == "POST" else None,
                      headers={"Accept": "application/json", "Cache-Control": "no-cache"})
        with opener.open(req, timeout=2) as response:
            if response.status != 200:
                raise RuntimeError("unexpected_http_status")
            data = response.read(65537)
        if len(data) > 65536:
            raise RuntimeError("oversized_response")
        return json.loads(data)

    transport = request or http

    def call(method, path):
        nonlocal sent
        if method == "POST" and path == sleep_path and not sent:
            # Latch BEFORE transport: a timeout may still mean the robot acted.
            sent = True
            emit({"event": "SLEEP_REQUEST_MAY_BE_SENT", "automatic_retry": False})
        elif method != "GET" or path not in allowed_gets:
            raise RuntimeError("request_not_allowed")
        return transport(method, path)

    def snapshot(own_move=None):
        started = clock()
        if call("GET", app_path) is not None:
            raise RuntimeError("active_app")
        lock = call("GET", lock_path)
        if not isinstance(lock, dict) or lock.get("state") != "free":
            raise RuntimeError("managed_app_slot_not_free")
        moves = call("GET", moves_path)
        if not isinstance(moves, list) or len(moves) > 1:
            raise RuntimeError("unexpected_moves")
        ids = [str(uuid.UUID(item["uuid"])) for item in moves]
        if any(value != own_move for value in ids):
            raise RuntimeError("another_move_running")
        state = call("GET", state_path)
        if not isinstance(state, dict) or not isinstance(state.get("timestamp"), str):
            raise RuntimeError("missing_state_timestamp")
        stamp = datetime.fromisoformat(state["timestamp"].replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - stamp).total_seconds()
        if not 0 <= age <= 2:
            raise RuntimeError("stale_state_response")
        status = call("GET", status_path)
        if not isinstance(status, dict):
            raise RuntimeError("invalid_daemon_status")
        if status.get("state") != "running" or status.get("version") != "1.9.0":
            raise RuntimeError("unexpected_daemon_state_or_version")
        for key in ("simulation_enabled", "mockup_sim_enabled", "no_media", "media_released"):
            if status.get(key) is not False:
                raise RuntimeError("not_verified_physical_media_daemon")
        backend = status.get("backend_status")
        if ("error" not in status or status["error"] is not None
                or not isinstance(backend, dict) or "error" not in backend
                or backend["error"] is not None):
            raise RuntimeError("daemon_or_backend_error_or_unknown")
        mode = backend.get("motor_control_mode")
        if mode not in ("enabled", "disabled") or state.get("control_mode") != mode:
            raise RuntimeError("motor_mode_unknown_or_inconsistent")
        if clock() - started > 2:
            raise RuntimeError("precheck_responses_too_slow")
        return {"daemon_state": "running", "motor_mode": mode,
                "media_available": True, "own_move_running": bool(ids),
                "state_response_age_seconds": age,
                "hardware_sample_age_not_exposed": True}

    try:
        before = snapshot()
        pause(0.5)
        current = snapshot()
        if current["motor_mode"] != before["motor_mode"]:
            raise RuntimeError("motor_state_changed_during_precheck")
        emit({"event": "BEFORE", **current})
        if current["motor_mode"] == "disabled":
            emit({"event": "ALREADY_DISABLED_NO_COMMAND", "sleep_requests": 0})
            return 0
        stage = "sleep_request_or_verification"
        result = call("POST", sleep_path)
        own_move = str(uuid.UUID(result["uuid"]))
        emit({"event": "REQUEST_ACKNOWLEDGED", "move_uuid": own_move})
        deadline = clock() + 20
        consecutive_disabled = 0
        while clock() < deadline:
            pause(0.5)
            current = snapshot(own_move)
            emit({"event": "AFTER", **current})
            if current["motor_mode"] == "disabled" and not current["own_move_running"]:
                consecutive_disabled += 1
                if consecutive_disabled == 2:
                    emit({"event": "DISABLED_OBSERVED_DAEMON_RUNNING", "sleep_requests": 1,
                          "microphone_test_started": False, "sleep_pose_verified": False})
                    return 0
            else:
                consecutive_disabled = 0
                if not current["own_move_running"]:
                    raise RuntimeError("sleep_task_ended_without_disabled_mode")
        raise RuntimeError("disabled_state_not_verified_before_deadline")
    except (Exception, KeyboardInterrupt) as error:
        emit({"event": "STOP_REVIEW_REQUIRED", "stage": stage,
              "request_may_have_been_sent": sent, "error_type": type(error).__name__,
              "reason": str(error) if isinstance(error, RuntimeError) else "request_or_schema_failure",
              "automatic_retry": False, "automatic_recovery_motion": False})
        return 2


def source_bytes():
    return (inspect.getsource(remote_once) + "\nraise SystemExit(remote_once())\n").encode()


def create_journal(path, source):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation also refuses existing symlinks; no reset/delete option.
    journal = path.open("x", encoding="utf-8")
    journal.write(json.dumps({"event": "PENDING_OPERATOR_STOCK_SLEEP",
                             "utc": datetime.now(timezone.utc).isoformat(),
                             "source_sha256": hashlib.sha256(source).hexdigest()}) + "\n")
    journal.flush()
    os.fsync(journal.fileno())
    return journal


def reviewed_retry_journal(directory, source):
    """One manual replacement only, tied to the preserved reviewed first log.

    A missing result alone is NOT permission to repeat a movement. The private
    review must independently establish failure before remote execution.
    """
    original = directory / "standard-sleep-once-v1.jsonl"
    review_path = directory / "connect-timeout-review-v1.json"
    replacement = directory / "standard-sleep-once-v1-replacement.jsonl"
    if replacement.exists():
        raise RuntimeError("Replacement already attempted; do not retry. Send: " + str(replacement))
    original_bytes = original.read_bytes()
    review_bytes = review_path.read_bytes()
    if len(original_bytes) > 4096 or len(review_bytes) > 8192:
        raise RuntimeError("Unexpected review record size")
    entries = [json.loads(line) for line in original_bytes.splitlines() if line.strip()]
    review = json.loads(review_bytes)
    expected_source = hashlib.sha256(source).hexdigest()
    if (len(entries) != 1 or not isinstance(entries[0], dict)
            or entries[0].get("event") != "PENDING_OPERATOR_STOCK_SLEEP"
            or entries[0].get("source_sha256") != expected_source
            or not isinstance(review, dict)
            or review.get("schema") != "reachy-stock-sleep-connect-timeout-review-v1"
            or review.get("classification") != "ssh_connection_timeout_before_remote_execution"
            or review.get("failed_journal_sha256") != hashlib.sha256(original_bytes).hexdigest()
            or review.get("remote_source_sha256") != expected_source
            or type(review.get("replacement_attempt_limit")) is not int
            or review["replacement_attempt_limit"] != 1
            or review.get("operator_confirmation_still_required") is not True):
        raise RuntimeError("No matching reviewed pre-execution connection failure; no retry")
    return replacement


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--sleep-once", action="store_true")
    modes.add_argument("--retry-reviewed-connect-timeout", action="store_true",
                       help="one operator-confirmed replacement after a private pre-execution timeout review")
    args = parser.parse_args(argv)
    if not args.sleep_once and not args.retry_reviewed_connect_timeout:
        parser.print_help()
        return 0
    if not sys.stdin.isatty():
        raise RuntimeError("Use an interactive local PowerShell console")
    source = source_bytes()
    journal_path = (reviewed_retry_journal(JOURNAL.parent, source)
                    if args.retry_reviewed_connect_timeout else JOURNAL)
    if journal_path.exists():
        raise RuntimeError("This one-shot session already has a journal. Do not retry; send: " + str(journal_path))
    if args.retry_reviewed_connect_timeout:
        print("One reviewed replacement for the failed SSH connection. Original log preserved.")
    print("One STOCK SLEEP sequence: head/antenna motion, stock sound, then torque release.")
    print("Close Reachy apps, camera/pilot pages and other clients. Pause the phone.")
    print("Remain beside Reachy on its stable surface; clear the head/antenna/drop space.")
    print("Keep hands out of the mechanism and the physical power control accessible.")
    print("No capture, audio routing, direct torque command, restart or automatic return.")
    print("Ctrl+C/closing this window does NOT cancel an already accepted robot movement.")
    if input("When those checks are true and you are watching Reachy, type SLEEP ONCE: ") != "SLEEP ONCE":
        print("Cancelled. No connection or movement request.")
        return 0
    remote = shlex.join(["/venvs/mini_daemon/bin/python", "-I", "-B", "-"])
    command = ["ssh", "-T", "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=5",
               "-o", "ConnectionAttempts=1", "-o", "NumberOfPasswordPrompts=1",
               "-o", "ServerAliveInterval=5", "-o", "ServerAliveCountMax=2",
               "pollen@192.168.1.251", remote]
    with create_journal(journal_path, source) as journal:
        print("SSH password stays in the console; its characters are invisible.", flush=True)
        print("Watch Reachy. No robot helper file is installed. Journal: " + str(journal_path), flush=True)
        try:
            outcome = subprocess.run(command, input=source, stdout=subprocess.PIPE, timeout=120)
            # Only the bounded JSON event stream from our remote program is expected.
            if len(outcome.stdout) > 262144:
                raise RuntimeError("oversized_result")
            events = [json.loads(line) for line in outcome.stdout.splitlines()]
            for event in events:
                journal.write(json.dumps(event, allow_nan=False) + "\n")
            journal.flush()
            os.fsync(journal.fileno())
            terminal = events[-1].get("event") if events else "MISSING_RESULT"
            success = outcome.returncode == 0 and terminal in (
                "ALREADY_DISABLED_NO_COMMAND", "DISABLED_OBSERVED_DAEMON_RUNNING")
            print(terminal)
            if not success:
                print("STOP: outcome needs review. Do not rerun or send recovery movement.")
                if events and isinstance(events[-1], dict):
                    print("Reason: " + str(events[-1].get("reason", "missing verified completion")))
            print("Send this journal path or the terminal screenshot: " + str(journal_path))
            print("Do not start the microphone diagnostic or reopen robot apps yet.")
            return 0 if success else 2
        except (Exception, KeyboardInterrupt) as error:
            journal.write(json.dumps({"event": "LOCAL_INTERRUPTION_OUTCOME_UNKNOWN",
                                      "error_type": type(error).__name__, "automatic_retry": False}) + "\n")
            journal.flush()
            os.fsync(journal.fileno())
            raise RuntimeError("Outcome unknown; this does NOT cancel robot motion. Do not retry. Send: " + str(journal_path)) from error


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, KeyboardInterrupt) as error:
        print("STOP: " + (str(error) or type(error).__name__), file=sys.stderr)
        raise SystemExit(2)
