"""Keyboard-only harness for an injected, byte-identical diagnostic reader class.

The launcher extracts only Stop and TerminalInputReader from a pinned source.
No microphone/helper execution, network API, settings writes or remote files.
The os.read observer returns the original bytes unchanged and retains counts
only. This instrumentation and the absence of capture load limit conclusions.
"""
import json
import os
import selectors
import sys
import threading
import time

WAIT_SECONDS = 120.0
OBSERVATION_SETTLE_SECONDS = 1.0
EXIT_CODES = {"received": 0, "no_input_observed": 20, "unexpected_text": 21,
              "unsupported_terminal": 22, "terminal_closed": 23,
              "bytes_without_enter_event": 24, "probe_error": 25,
              "interrupted": 26, "multiple_events": 27,
              "reader_exit_unverified": 28, "terminal_modes_changed": 29,
              "observation_after_deadline": 30}


def terminal_metadata(stream):
    if os.name != "posix" or not stream.isatty():
        return {"tty": False}
    import termios
    state = termios.tcgetattr(stream.fileno())  # Never tcsetattr or flush input.
    result = {"tty": True}
    for group, names in ((0, ("ICRNL", "IGNCR", "INLCR")),
                         (3, ("ICANON", "ECHO", "ISIG", "IEXTEN"))):
        result.update({name: bool(state[group] & getattr(termios, name)) for name in names})
    for name in ("VEOL", "VEOL2", "VMIN", "VTIME"):
        value = state[6][getattr(termios, name)]
        result[name] = value[0] if isinstance(value, bytes) else value
    return result


def initial_enter(stream, *, read_line=input, timeout=WAIT_SECONDS,
                  clock=time.monotonic, selector_factory=selectors.DefaultSelector):
    """Same input() handoff as the live start, without an acquisition phrase."""
    start = clock()
    selector = selector_factory()
    try:
        selector.register(stream, selectors.EVENT_READ)
        if not selector.select(timeout=timeout):
            return {"status": "no_input_observed", "elapsed_ms": round((clock()-start)*1000, 3)}
        observed = clock()
        try:
            empty = read_line() == ""
        except EOFError:
            status = "terminal_closed"
        else:
            status = "unexpected_text" if not empty else ("received" if observed-start <= timeout else "observation_after_deadline")
        return {"status": status, "elapsed_ms": round((clock()-start)*1000, 3)}
    finally:
        selector.close()


class ReadCounts:
    """Count fixed categories; never retain a payload, text or individual keys."""
    def __init__(self, start, *, read=os.read, clock=time.monotonic):
        self.start, self.read, self.clock = start, read, clock
        self.lock = threading.Lock()
        self.counts = {"reads": 0, "bytes": 0, "cr": 0, "lf": 0, "other": 0,
                       "eof_reads": 0, "first_read_ms": None, "last_read_ms": None}

    def __call__(self, fd, count):
        payload = self.read(fd, count)
        cr, lf = payload.count(b"\r"), payload.count(b"\n")
        elapsed = round((self.clock()-self.start)*1000, 3)
        with self.lock:
            c = self.counts
            c["reads"] += 1
            c["bytes"] += len(payload)
            c["cr"] += cr
            c["lf"] += lf
            c["other"] += len(payload)-cr-lf
            c["eof_reads"] += not payload
            if c["first_read_ms"] is None:
                c["first_read_ms"] = elapsed
            c["last_read_ms"] = elapsed
        return payload  # Identical bytes, not translated or normalized.

    def snapshot(self):
        with self.lock:
            return dict(self.counts)


def observe_reader(reader_type, stream, *, timeout=WAIT_SECONDS, settle=OBSERVATION_SETTLE_SECONDS,
                   read=os.read, clock=time.monotonic, sleep=time.sleep):
    start = clock()
    counter = ReadCounts(start, read=read, clock=clock)
    reader, events = None, []
    result = {"status": "probe_error", "reader_exit_verified": False,
              "physical_keypress_time_known": False}
    try:
        reader = reader_type(stream, read=counter, clock=clock)
        while True:
            events.extend(reader.drain())
            if len(events) > 8:
                raise RuntimeError("bounded_events_exceeded")
            counts = counter.snapshot()
            elapsed = clock()-start
            if (counts["reads"] and elapsed-counts["last_read_ms"]/1000 >= settle) or elapsed >= timeout:
                break
            sleep(.01)
    except KeyboardInterrupt:
        result["status"] = "interrupted"
    except Exception as error:
        result["error_type"] = type(error).__name__
    finally:
        if reader is not None:
            try:
                reader.close()
                result["reader_exit_verified"] = True
                events.extend(reader.drain())  # Include any observation published during shutdown.
            except Exception as error:
                result.update(status="reader_exit_unverified", error_type=type(error).__name__)
        counts = counter.snapshot()
        result["counts"] = counts
        result["events"] = [{"kind": e["kind"], "observed_ms": round((e["observed_at"]-start)*1000, 3)} for e in events[:8]]
        result["elapsed_ms"] = round((clock()-start)*1000, 3)
    if result["status"] != "interrupted" and "error_type" not in result and result["reader_exit_verified"]:
        kinds = [e["kind"] for e in events]
        if not kinds:
            status = "bytes_without_enter_event" if counts["bytes"] else "no_input_observed"
        elif len(kinds) != 1:
            status = "multiple_events"
        elif kinds[0] == "enter":
            status = "received" if events[0]["observed_at"]-start <= timeout else "observation_after_deadline"
        else:
            status = "terminal_closed" if kinds[0] == "eof" else "unexpected_text"
        result["status"] = status
    return result


def run_probe(reader_type, *, stream=None, output=print, terminal=terminal_metadata,
              first=initial_enter, second=observe_reader):
    stream = sys.stdin if stream is None else stream
    result = {"schema": "reachy-exact-reader-keyboard-probe-v1", "steps": [],
              "audio_opened": False, "settings_changed": False, "remote_files_written": False,
              "recording_authorized": False, "keypress_contents_retained": False,
              "physical_keypress_time_known": False, "capture_load_tested": False,
              "wait_limit_per_prompt_seconds": WAIT_SECONDS,
              "counts_only_read_wrapper": True}
    try:
        before = terminal(stream)
        result["terminal_before"] = before
        if not before.get("tty") or not before.get("ICANON"):
            result["status"] = "unsupported_terminal"
        else:
            output("KEYBOARD ONLY. Phone stays PAUSED. No audio, routing or movement.", flush=True)
            output("STEP 1/2: press Enter ONCE when ready. You have TWO MINUTES; no need to rush.", flush=True)
            step = first(stream)
            result["steps"].append({"step": 1, "reader": "input", **step})
            result["status"] = step["status"]
            if step["status"] == "received":
                output("STEP 1: ENTER RECEIVED.", flush=True)
                output("STEP 2/2: press Enter ONCE when ready. TWO MINUTES again. Then wait for the result; do not press again.", flush=True)
                step = second(reader_type, stream)
                result["steps"].append({"step": 2, "reader": "exact_diagnostic_class", **step})
                result["status"] = step["status"]
                output("STEP 2: " + step["status"].upper() + ".", flush=True)
            result["terminal_after"] = terminal(stream)
            if before != result["terminal_after"]:
                result["status"] = "terminal_modes_changed"
    except KeyboardInterrupt:
        result["status"] = "interrupted"
    except Exception as error:
        result.update(status="probe_error", error_type=type(error).__name__)
    output("EXACT_READER_RESULT " + json.dumps(result, allow_nan=False), flush=True)
    output("CHECK ENDED. Send this result for review. Do not start a microphone test or repeat this check.", flush=True)
    return EXIT_CODES[result["status"]]
