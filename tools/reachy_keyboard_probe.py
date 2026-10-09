"""Terminal-only probe, sent in memory over SSH. No robot/device/file access.

The deadline-aware reader is an offline candidate, NOT an acquisition release.
Readiness is polled before expiry is classified. A key first observed after the
deadline is explicitly ambiguous, never silently accepted as on-time input.
The first read uses input(), then the second uses selector + stdin.readline(),
matching the diagnostic's two Python input APIs. No key contents are retained.
"""

import json
import os
import selectors
import sys
import time


SCHEMA = "reachy-keyboard-only-probe-v1"
WAIT_SECONDS = 120.0
EXIT_CODES = {"received": 0, "no_input_observed_before_deadline": 20,
              "unexpected_text": 21, "unsupported_terminal": 22,
              "terminal_closed": 23, "input_present_at_expiry_time_unknown": 24,
              "probe_error": 25, "interrupted": 26}


def wait_for_enter(stream, read_line, *, timeout=WAIT_SECONDS,
                   selector_factory=selectors.DefaultSelector,
                   clock=time.monotonic):
    """Record when readiness is OBSERVED, not when a physical key was pressed."""
    started = clock()
    deadline = started + timeout
    selector = selector_factory()
    try:
        selector.register(stream, selectors.EVENT_READ)
        while True:
            before_poll = clock()
            # A zero-time poll at expiry distinguishes pending input from none.
            events = selector.select(timeout=max(0.0, min(0.1, deadline - before_poll)))
            observed = clock()
            if events:
                try:
                    empty_line = read_line()
                except EOFError:
                    status = "terminal_closed"
                else:
                    if not empty_line:
                        status = "unexpected_text"
                    elif observed > deadline:
                        status = "input_present_at_expiry_time_unknown"
                    else:
                        status = "received"
                return {"status": status,
                        "readiness_observed_ms": round((observed - started) * 1000, 3),
                        "read_finished_ms": round((clock() - started) * 1000, 3),
                        "physical_keypress_time_known": False}
            if observed >= deadline:
                return {"status": "no_input_observed_before_deadline",
                        "wait_elapsed_ms": round((observed - started) * 1000, 3),
                        "physical_keypress_time_known": False}
    finally:
        selector.close()


def terminal_metadata(stream):
    if os.name != "posix" or not stream.isatty():
        return {"tty": False, "canonical": False}
    import termios
    attrs = termios.tcgetattr(stream.fileno())  # Read only; never tcsetattr.
    return {"tty": True, "canonical": bool(attrs[3] & termios.ICANON),
            "echo": bool(attrs[3] & termios.ECHO)}


def selector_line(stream):
    line = stream.readline(4097)
    if line == "":
        raise EOFError()
    return line in ("\n", "\r\n")


def run_probe(*, stream=None, output=print, wait=wait_for_enter,
              terminal=terminal_metadata, first_input=input):
    stream = sys.stdin if stream is None else stream
    result = {"schema": SCHEMA, "steps": [], "audio_opened": False,
              "settings_changed": False, "remote_files_written": False,
              "recording_authorized": False, "keypress_contents_retained": False,
              "wait_limit_per_prompt_seconds": WAIT_SECONDS}
    try:
        result["terminal"] = terminal(stream)
        if not result["terminal"].get("tty") or not result["terminal"].get("canonical"):
            result["status"] = "unsupported_terminal"
        else:
            output("KEYBOARD CHECK ONLY. Leave the phone PAUSED. No microphone, routing or movement.", flush=True)
            for number in (1, 2):
                output("STEP %d/2 - press Enter ONCE in this PowerShell window when ready. You have two minutes; no need to rush." % number, flush=True)
                reader = (lambda: first_input() == "") if number == 1 else (lambda: selector_line(stream))
                record = wait(stream, reader)
                result["steps"].append({"step": number, "reader": "input" if number == 1 else "selector_readline", **record})
                if record["status"] != "received":
                    result["status"] = record["status"]
                    break
                output("STEP %d: ENTER RECEIVED." % number, flush=True)
            else:
                result["status"] = "received"
    except KeyboardInterrupt:
        result["status"] = "interrupted"
    except Exception as error:
        result["status"] = "probe_error"
        result["error_type"] = type(error).__name__  # Never arbitrary exception/input text.
    output("KEYBOARD_CHECK_RESULT " + json.dumps(result, allow_nan=False), flush=True)
    if result["status"] == "received":
        output("KEYBOARD CHECK COMPLETE. Both Enter presses reached the reader. No recording is authorized.", flush=True)
    else:
        output("KEYBOARD CHECK STOPPED. Keep this output for review; do not start a microphone test.", flush=True)
    return EXIT_CODES[result["status"]]


if __name__ == "__main__":
    raise SystemExit(run_probe())
