"""Bounded input-path metadata only; no device, network, write or logging API.

Embedded verbatim in the unreleased standalone diagnostic candidate. Counters
are saturating; timestamps are relative to the supplied capture origin. Payloads
pass through unchanged and are never attached to telemetry or retained here.
"""
import os
import threading
import time


def terminal_input_metadata(stream):
    """Read only: no tty paths, process IDs, typed contents or mode setters."""
    report = {"status": "unavailable", "tty": None, "foreground_matches": None,
              "ICANON": None, "ECHO": None, "ICRNL": None, "IGNCR": None,
              "INLCR": None, "ISIG": None, "IEXTEN": None, "VMIN": None, "VTIME": None}
    try:
        fd = stream.fileno()
        report["tty"] = bool(os.isatty(fd))
        if os.name != "posix":
            report["status"] = "not_posix"
            return report
        if not report["tty"]:
            report["status"] = "not_tty"
            return report
        import termios
        state = termios.tcgetattr(fd)
        for name in ("ICRNL", "IGNCR", "INLCR"):
            report[name] = bool(state[0] & getattr(termios, name))
        for name in ("ICANON", "ECHO", "ISIG", "IEXTEN"):
            report[name] = bool(state[3] & getattr(termios, name))
        for name in ("VMIN", "VTIME"):
            value = state[6][getattr(termios, name)]
            value = value if isinstance(value, int) else value[0]
            report[name] = int(value)
        report["foreground_matches"] = os.tcgetpgrp(fd) == os.getpgrp()
        report["status"] = "available"
    except Exception:
        # Never retain exception text, paths, terminal contents or arguments.
        report["status"] = "read_error"
    return report


class InputObservation:
    """Constant-space observations; never hold this lock during I/O or emit."""
    LIMIT = 1000000
    COUNTERS = ("thread_starts", "thread_exits", "register_calls", "register_returns",
                "select_calls", "select_returns", "select_ready", "select_empty",
                "read_calls", "read_returns", "read_errors", "bytes", "lf", "cr",
                "other_whitespace", "other", "eof_reads", "emit_attempts", "emit_ok",
                "emit_rejected", "enter_events", "text_events", "eof_events",
                "register_errors", "select_errors", "selector_close_calls",
                "selector_close_returns", "selector_close_errors")
    MARKS = ("thread_start", "thread_exit", "register_start", "register_return",
             "select_start", "select_return", "read_start", "read_return",
             "first_read", "last_emit", "selector_close_start", "selector_close_return")

    def __init__(self, *, clock=time.monotonic, origin=None):
        self.clock = clock
        self.clock_origin = "reader_init" if origin is None else "capture_start"
        self.origin = clock() if origin is None else origin
        self.lock = threading.Lock()
        self.counts = dict.fromkeys(self.COUNTERS, 0)
        self.marks = dict.fromkeys(self.MARKS, None)
        self.saturated = False
        self.last_error_stage = None
        self.last_errno = None

    def _add(self, name, count=1):
        value = self.counts[name] + count
        if value > self.LIMIT:
            self.saturated = True
        self.counts[name] = min(self.LIMIT, value)

    def mark(self, counter, mark):
        with self.lock:
            self._add(counter)
            self.marks[mark] = round((self.clock() - self.origin) * 1000, 3)

    def error(self, stage, error):
        with self.lock:
            self._add(stage + "_errors")
            self.last_error_stage = stage
            errno = getattr(error, "errno", None)
            self.last_errno = errno if type(errno) is int and 0 <= errno <= 65535 else None

    def read(self, original, fd, size):
        self.mark("read_calls", "read_start")
        try:
            payload = original(fd, size)
        except BaseException as error:
            self.error("read", error)
            raise
        with self.lock:
            self._add("read_returns")
            self._add("bytes", len(payload))
            self._add("lf", payload.count(b"\n"))
            self._add("cr", payload.count(b"\r"))
            whitespace = sum(payload.count(bytes((byte,))) for byte in (9, 11, 12, 32))
            self._add("other_whitespace", whitespace)
            self._add("other", len(payload) - payload.count(b"\n") - payload.count(b"\r") - whitespace)
            if not payload:
                self._add("eof_reads")
            now = round((self.clock() - self.origin) * 1000, 3)
            self.marks["read_return"] = now
            if self.marks["first_read"] is None:
                self.marks["first_read"] = now
        return payload

    def emitted(self, kind, accepted):
        with self.lock:
            self._add("emit_attempts")
            self._add("emit_ok" if accepted else "emit_rejected")
            if accepted:
                self._add({"enter": "enter_events", "text": "text_events", "eof": "eof_events"}[kind])
            self.marks["last_emit"] = round((self.clock() - self.origin) * 1000, 3)

    def selector(self, factory):
        return ObservedSelector(factory(), self)

    def snapshot(self):
        with self.lock:
            return {"schema": "reachy-input-observation-v1", "counts": dict(self.counts),
                    "relative_ms": dict(self.marks), "counter_limit": self.LIMIT,
                    "counter_saturated": self.saturated, "last_error_stage": self.last_error_stage,
                    "last_errno": self.last_errno, "clock_origin": self.clock_origin,
                    "concurrent_snapshot": True,
                    "physical_keypress_time_known": False, "typed_contents_retained": False}


class ObservedSelector:
    def __init__(self, original, observation):
        self.original, self.observation = original, observation

    def register(self, *args, **kwargs):
        self.observation.mark("register_calls", "register_start")
        try:
            result = self.original.register(*args, **kwargs)
        except BaseException as error:
            self.observation.error("register", error)
            raise
        self.observation.mark("register_returns", "register_return")
        return result

    def select(self, timeout=None):
        self.observation.mark("select_calls", "select_start")
        try:
            result = self.original.select(timeout=timeout)
        except BaseException as error:
            self.observation.error("select", error)
            raise
        self.observation.mark("select_returns", "select_return")
        with self.observation.lock:
            self.observation._add("select_ready" if result else "select_empty")
        return result

    def close(self):
        self.observation.mark("selector_close_calls", "selector_close_start")
        try:
            result = self.original.close()
        except BaseException as error:
            self.observation.error("selector_close", error)
            raise
        self.observation.mark("selector_close_returns", "selector_close_return")
        return result
