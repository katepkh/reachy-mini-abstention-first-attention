"""Automatic no-audio Linux exercise; only isolated PTYs and generated samples.

Receives source-pinned definitions, never a full diagnostic module. Hardware
checks are stubs. The only child is Python emitting generated stereo integers
to a pipe. No device, robot API, file installation, or operator input is used.
"""
import math
import os
import queue
import selectors
import signal
import struct
import subprocess
import sys
import threading
import time
from types import SimpleNamespace


SCHEMA = "reachy-input-linux-synthetic-v1"
CASES = ("generated_enter", "generated_no_input")
RESULT_PREFIX = "LINUX_SYNTHETIC_RESULT "
LIMIT_SECONDS = 55
# Nonblocking output, a fixed deadline and parent-loss detection bound this
# generated-data child even if its supervisor disappears or stops reading.
GENERATOR = '''import os, select, struct, time
parent = os.getppid()
start = time.monotonic()
os.set_blocking(1, False)
sent = 0
pending = b""
try:
    while time.monotonic() - start < 39 and os.getppid() == parent:
        due = min(38 * 16000, int((time.monotonic() - start) * 16000))
        if not pending and due > sent:
            frames = min(1024, due - sent)
            pending = struct.pack("<hhhh", -100, 75, 100, -75) * (frames // 2)
            if frames % 2:
                pending += struct.pack("<hh", -100, 75)
            sent += frames
        if pending and select.select([], [1], [], .02)[1]:
            try:
                count = os.write(1, pending)
                pending = pending[count:]
            except BlockingIOError:
                pass
        else:
            time.sleep(.002)
except (BrokenPipeError, OSError):
    pass
'''


class HarnessStop(RuntimeError):
    pass


def generator_command():
    return [sys.executable, "-I", "-B", "-c", GENERATOR]


def stop_for_signal(signum, frame):
    raise HarnessStop("bounded_check_interrupted")


def expected_case(case):
    """Check full counts, unchanged decisions and completed resource cleanup."""
    result = case["result"]
    timing = result.get("operator_input", {})
    snapshots = timing.get("reader_observability", {})
    final = snapshots.get("after_close", {})
    counts = final.get("counts", {})
    if not (case["terminal_modes_unchanged"] and case["synthetic_sender_exited"]
            and case["child_reaped"] and case["reader_threads_exited"]
            and case["pipes_closed"] and case["pty_closed"]
            and result.get("capture_exit_verified") and timing.get("reader_exit_verified")
            and set(snapshots) == {"at_start", "at_play", "before_close", "after_close"}
            and final.get("thread_alive") is False and final.get("last_error_stage") is None
            and final.get("reader_fault") is None and final.get("counter_saturated") is False
            and counts.get("thread_starts") == counts.get("thread_exits") == 1
            and counts.get("selector_close_calls") == counts.get("selector_close_returns") == 1
            and counts.get("read_calls") == counts.get("read_returns")
            and counts.get("select_calls") == counts.get("select_returns")
            and counts.get("select_returns", 0) > 0
            and result.get("summaries", {}).get("quiet", {}).get("frames") == 48000):
        return False
    if case["name"] == "generated_enter":
        events = timing.get("events", [])
        return (case["outcome"] == "COMPLETE" and result.get("complete") is True
                and case["synthetic_input_written"] and len(events) == 1
                and events[0].get("kind") == "enter" and events[0].get("accepted") is True
                and counts.get("bytes") == counts.get("lf") == counts.get("enter_events") == 1
                and result.get("summaries", {}).get("playback", {}).get("frames") == 160000)
    return (case["name"] == "generated_no_input"
            and case["outcome"] == "confirmation_deadline_no_observed_enter"
            and result.get("complete") is False and timing.get("events") == []
            and counts.get("bytes") == counts.get("read_calls") == 0
            and not case["synthetic_input_written"] and "playback" not in result.get("summaries", {}))


def run_case(definitions, name):
    import termios

    if name not in CASES:
        raise HarnessStop("unknown_synthetic_case")
    master, slave = os.openpty()  # New isolated terminal, never /dev/tty.
    stream = None
    prompt, finish = threading.Event(), threading.Event()
    readers, children = [], []
    sender = None
    state = {"written": False, "sender_error": False}
    case = {"name": name, "outcome": "HARNESS_ERROR", "result": {},
            "terminal_modes_unchanged": False, "synthetic_sender_exited": False,
            "synthetic_input_written": False, "child_reaped": False,
            "reader_threads_exited": False, "pipes_closed": False, "pty_closed": False}
    before = None
    ns = None
    try:
        stream = os.fdopen(slave, "rb", buffering=0)
        before = termios.tcgetattr(slave)
        if not before[3] & termios.ICANON or not before[0] & termios.ICRNL:
            raise HarnessStop("isolated_terminal_defaults_unsupported")

        def output(message, **kwargs):
            # Suppress real diagnostic phone instructions; no operator action.
            if message.startswith("PLAY + ENTER NOW"):
                prompt.set()

        def spawn(command, **kwargs):
            if children or command != generator_command() or kwargs != {
                    "stdin": subprocess.DEVNULL, "stdout": subprocess.PIPE,
                    "stderr": subprocess.PIPE, "start_new_session": True}:
                raise HarnessStop("unapproved_child_request")
            child = subprocess.Popen(command, **kwargs)
            children.append(child)
            return child

        ns = {"__name__": "isolated_generated_capture", "math": math, "os": os,
              "queue": queue, "selectors": selectors, "signal": signal, "struct": struct,
              "threading": threading, "time": time, "sys": SimpleNamespace(stdin=stream),
              "subprocess": SimpleNamespace(Popen=spawn, PIPE=subprocess.PIPE,
                                            DEVNULL=subprocess.DEVNULL, TimeoutExpired=subprocess.TimeoutExpired),
              "print": output, "capture_command": generator_command,
              "check_robot": lambda: None}  # Explicit stub, not a readiness check.
        exec(compile(definitions, "<pinned-synthetic-definitions>", "exec"), ns)
        exact = ns["ObservedTerminalInputReader"]

        def reader_factory(source, **kwargs):
            if source is not stream or readers:
                raise HarnessStop("unapproved_reader_request")
            reader = exact(source, **kwargs)
            readers.append(reader)
            return reader

        ns["ObservedTerminalInputReader"] = reader_factory

        def send_generated_enter():
            try:
                end = time.monotonic() + 10
                while not prompt.wait(.05):
                    if finish.is_set() or time.monotonic() > end:
                        return
                if finish.wait(.35):
                    return
                # CR traverses the isolated PTY's existing ICRNL translation;
                # the unchanged reader should observe exactly one LF.
                state["written"] = os.write(master, b"\r") == 1
            except Exception:
                state["sender_error"] = True  # No exception content retained.

        if name == "generated_enter":
            sender = threading.Thread(target=send_generated_enter, daemon=True)
            sender.start()
        guard = SimpleNamespace(process=SimpleNamespace(poll=lambda: None))
        try:
            ns["capture_pair"](0, case["result"], guard)
            case["outcome"] = "COMPLETE"
        except ns["Stop"] as error:
            # Known fixed implementation reasons only, never arbitrary text.
            allowed = {"confirmation_deadline_no_observed_enter", "capture_deadline_or_stall",
                       "capture_driver_error", "capture_ended_early", "operator_reader_error",
                       "operator_reader_exit_unverified", "unexpected_operator_input",
                       "capture_process_group_exit_unverified", "terminal_closed",
                       "operator_input_overflow", "confirmation_observed_after_deadline"}
            case["outcome"] = str(error) if str(error) in allowed else "CAPTURE_ERROR"
    except Exception:
        case["outcome"] = "HARNESS_ERROR"
    finally:
        finish.set()
        if sender is not None:
            sender.join(timeout=1)
        case["synthetic_sender_exited"] = sender is None or not sender.is_alive()
        case["synthetic_input_written"] = state["written"] and not state["sender_error"]
        for reader in readers:
            try:
                reader.close()
            except Exception:
                pass
        case["reader_threads_exited"] = bool(readers) and all(not r.thread.is_alive() for r in readers)
        # Normally capture_pair already stopped/reaped its child. Only an
        # abnormal failure before that finally can reach this owned-child path.
        for child in children:
            if child.poll() is None:
                try:
                    ns["stop_own_capture"](child)
                except Exception:
                    pass
            for pipe in (child.stdout, child.stderr):
                pipe.close()
        case["child_reaped"] = len(children) == 1 and children[0].poll() is not None
        case["pipes_closed"] = len(children) == 1 and children[0].stdout.closed and children[0].stderr.closed
        try:
            if before is not None:
                case["terminal_modes_unchanged"] = termios.tcgetattr(slave) == before
        finally:
            try:
                if stream is not None:
                    stream.close()
                else:
                    os.close(slave)
            finally:
                os.close(master)
                case["pty_closed"] = True
    case["ok"] = expected_case(case)
    return case


def run_check(definitions):
    report = {"schema": SCHEMA, "status": "FAIL", "cases": [],
              "input_source": "isolated_generated_pty", "sample_source": "generated_integer_pipe",
              "physical_keyboard_tested": False, "audio_opened": False,
              "recording_authorized": False, "settings_changed": False,
              "robot_api_called": False, "remote_files_installed": False,
              "real_audio_capture_tested": False, "hardware_checks_stubbed": True,
              "operator_terminal_used": False, "clock_accelerated": False}
    if os.name != "posix" or not sys.platform.startswith("linux"):
        report["reason"] = "LINUX_REQUIRED"
        return report
    saved = {}
    try:
        for sig in (signal.SIGALRM, signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
            saved[sig] = signal.signal(sig, stop_for_signal)
        signal.alarm(LIMIT_SECONDS)
        for name in CASES:
            case = run_case(definitions, name)
            report["cases"].append(case)
            if not case["ok"]:
                report["reason"] = "SYNTHETIC_CASE_FAILED"
                break
        else:
            report["status"] = "PASS"
    except BaseException:
        report["reason"] = "INTERRUPTED_OR_HARNESS_ERROR"
    finally:
        signal.alarm(0)
        for sig, handler in saved.items():
            signal.signal(sig, handler)
    return report


def remote_main(definitions):
    import json
    report = run_check(definitions)
    print(RESULT_PREFIX + json.dumps(report, separators=(",", ":"), allow_nan=False), flush=True)
    return 0 if report["status"] == "PASS" else 20
