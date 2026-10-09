"""Local-only reproduction of the preserved reader AND capture loop together.

Only selected, hash-pinned definitions are loaded; no live execute/USB/HTTP code
is present. Connected local sockets substitute for terminal and capture pipes.
Samples are generated integers, not microphone data. Timing is accelerated five
times in this harness only; RATE, sample counts and original limits are intact.
This is not a Linux PTY, actual capture child, SSH or hardware-load validation.
"""
import ast
from contextlib import ExitStack
import hashlib
import math
from pathlib import Path
import queue
import selectors
import socket
import struct
import subprocess
import threading
import time
from types import SimpleNamespace
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "tools/reachy_mic_health_input_next.py"
SOURCE_SHA = "dbdddf79e2e7103a1fa3a78d03e65eb8415a73f43b454b0f516e12406ebc8368"
DEFINITIONS = {"Stop", "Stats", "TerminalInputReader", "capture_command", "capture_pair"}


def load_definitions(namespace):
    payload = SOURCE.read_bytes()
    if hashlib.sha256(payload).hexdigest() != SOURCE_SHA:
        raise RuntimeError("preserved_helper_changed")
    tree = ast.parse(payload)
    selected = [node for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in DEFINITIONS]
    if {node.name for node in selected} != DEFINITIONS:
        raise RuntimeError("missing_test_definition")
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace


def run_scenario(name, *, fragments=(b"\n",), delay=2.7, status_delay=0.0,
                 input_eof=False, capture_fault=None, guard_fault=False,
                 reader_gate=False, cpu_delay=0.0, speed=5.0):
    """Exercise exact functions with real threads, selectors and synthetic bytes.

    reader_gate deliberately prevents reads for the whole confirmation interval,
    then releases at shutdown; it models unavailable observation, NOT a discovered
    cause. The gate is outside the preserved reader, in the injected selector.
    """
    origin = time.monotonic()
    clock = lambda: (time.monotonic() - origin) * speed
    stop = threading.Event()
    prompt = threading.Event()
    gate_release = threading.Event()
    status_active = threading.Event()
    sender_done = threading.Event()
    errors = queue.Queue()
    result, counts, log, threads, readers = {}, {"reads": 0, "bytes": 0, "lf": 0, "cr": 0}, [], [], []
    counters_lock = threading.Lock()
    state = {"status_checks": 0, "delayed": False, "capture_started": False,
             "capture_stopped": False, "input_sent": False, "reader_closed": False}
    with ExitStack() as resources:
        def pair():
            rx, tx = socket.socketpair()
            resources.callback(rx.close)
            resources.callback(tx.close)
            return rx, tx
        terminal, keys = pair()
        pcm, samples = pair()
        stderr, driver = pair()
        channels = {s.fileno(): s for s in (terminal, pcm, stderr)}
        process = SimpleNamespace(stdout=pcm, stderr=stderr)

        def read(fd, size):
            payload = channels[fd].recv(size)
            if channels[fd] is terminal:
                with counters_lock:
                    counts["reads"] += 1
                    counts["bytes"] += len(payload)
                    counts["lf"] += payload.count(b"\n")
                    counts["cr"] += payload.count(b"\r")
            return payload

        def popen(command, **kwargs):
            if kwargs != {"stdin": subprocess.DEVNULL, "stdout": subprocess.PIPE,
                          "stderr": subprocess.PIPE, "start_new_session": True}:
                raise AssertionError("capture console isolation changed")
            if command != ns["capture_command"]():
                raise AssertionError("capture command changed")
            state["capture_started"] = True
            state["capture_origin"] = clock()
            return process

        def stop_capture(owned):
            if owned is not process:
                raise AssertionError("wrong fake capture")
            state["capture_stopped"] = True
            stop.set()

        def output(message, **kwargs):
            if message.startswith("PLAY + ENTER"):
                state["prompt_at"] = clock()
                prompt.set()
            log.append(message.splitlines()[0])

        def check_robot():
            state["status_checks"] += 1
            if prompt.is_set() and not state["delayed"] and (status_delay or cpu_delay):
                state["delayed"] = True
                status_active.set()
                end = clock() + cpu_delay
                while clock() < end:
                    pass  # Simulate main-thread CPU work, not hardware work.
                stop.wait(status_delay / speed)

        class GatedSelector:
            def __init__(self):
                self.selector = selectors.DefaultSelector()
            def register(self, *args):
                return self.selector.register(*args)
            def select(self, timeout):
                if reader_gate and not gate_release.is_set():
                    gate_release.wait(timeout)
                    return []
                return self.selector.select(timeout)
            def close(self):
                return self.selector.close()

        ns = load_definitions({"__name__": "synthetic_capture_only", "math": math,
            "queue": queue, "struct": struct, "threading": threading, "selectors": selectors,
            "time": SimpleNamespace(monotonic=clock), "sys": SimpleNamespace(stdin=terminal),
            "os": SimpleNamespace(read=read, set_blocking=lambda fd, enabled: channels[fd].setblocking(enabled)),
            "subprocess": SimpleNamespace(Popen=popen, PIPE=subprocess.PIPE, DEVNULL=subprocess.DEVNULL),
            "RATE": 16000, "ROUTES": ("L", "R"), "PAIRS": ({"L": [3, 2], "R": [3, 3]},),
            "check_robot": check_robot, "stop_own_capture": stop_capture, "print": output})
        exact_reader = ns["TerminalInputReader"]

        def reader_factory(stream):
            reader = exact_reader(stream, selector_factory=GatedSelector)
            original_close = reader.close
            def close():
                # Stop before releasing a synthetic unavailable-reader gate.
                reader.stop.set()
                gate_release.set()
                original_close()
                state["reader_closed"] = True
            reader.close = close
            readers.append(reader)
            return reader
        ns["TerminalInputReader"] = reader_factory

        def launch(action):
            def guarded():
                try:
                    action()
                except BaseException as exc:
                    if not stop.is_set():
                        errors.put(type(exc).__name__)
            worker = threading.Thread(target=guarded, daemon=True)
            worker.start()
            threads.append(worker)

        def feed_capture():
            while not state["capture_started"] and not stop.wait(.001):
                pass
            sent = 0
            while not stop.is_set():
                elapsed = clock() - state["capture_origin"]
                if elapsed > 39:
                    errors.put("harness_capture_deadline")
                    return
                if prompt.is_set() and capture_fault:
                    if capture_fault == "driver":
                        driver.sendall(b"synthetic-driver-fault")
                    elif capture_fault == "eof":
                        samples.shutdown(socket.SHUT_WR)
                    elif capture_fault != "stall":
                        raise AssertionError("unknown capture fault")
                    return
                frames = min(4096, int(elapsed * ns["RATE"]) - sent)
                if frames > 0:
                    samples.sendall(struct.pack("<hh", -100, 75) * frames)
                    sent += frames
                stop.wait(.002)

        def send_input():
            if not prompt.wait(8 / speed + 1):
                if not stop.is_set():
                    errors.put("harness_prompt_missing")
                return
            if status_delay or cpu_delay:
                if not status_active.wait(3 / speed + 1):
                    errors.put("harness_status_delay_missing")
                    return
            if stop.wait(delay / speed):
                return
            for fragment in fragments:
                keys.sendall(fragment)
            state["input_sent"] = bool(fragments)
            state["sent_at"] = clock()
            if input_eof:
                keys.shutdown(socket.SHUT_WR)
            sender_done.set()

        launch(feed_capture)
        launch(send_input)
        guard = SimpleNamespace(process=SimpleNamespace(poll=lambda: 1 if guard_fault and prompt.is_set() else None))
        outcome = "COMPLETE"
        try:
            ns["capture_pair"](0, result, guard)
        except ns["Stop"] as exc:
            outcome = str(exc)
        finally:
            stop.set()
            gate_release.set()
            for reader in readers:
                reader.close()
            for worker in threads:
                worker.join(timeout=2)
            if any(worker.is_alive() for worker in threads):
                raise AssertionError("harness_thread_exit_unverified")
            if not errors.empty():
                raise AssertionError(errors.get())
        return {"scenario": name, "outcome": outcome, "counts": dict(counts),
                "result": result, "status_checks": state["status_checks"],
                "synthetic_input_sent": state["input_sent"],
                "capture_stub_stopped": state["capture_stopped"],
                "reader_exited": all(not r.thread.is_alive() for r in readers),
                "wall_seconds": round(time.monotonic() - origin, 3),
                "clock_speedup": speed, "audio_device_opened": False,
                "robot_connected": False, "actual_capture_process_tested": False,
                "linux_terminal_tested": False}


class IntegrationTests(unittest.TestCase):
    def check_case(self, name, expected="COMPLETE", **kwargs):
        report = run_scenario(name, **kwargs)
        self.assertEqual(report["outcome"], expected, report)
        self.assertTrue(report["capture_stub_stopped"])
        self.assertTrue(report["reader_exited"])
        self.assertTrue(report["result"]["capture_exit_verified"])
        self.assertTrue(report["result"]["operator_input"]["reader_exit_verified"])
        if expected == "COMPLETE":
            self.assertEqual(report["result"]["summaries"]["quiet"]["frames"], 48000)
            self.assertEqual(report["result"]["summaries"]["playback"]["frames"], 160000)
            self.assertEqual(len(report["result"]["blocks"]), 13)
            self.assertTrue(report["result"]["operator_input"]["events"][0]["accepted"])
        return report

    def test_real_reader_and_full_rate_capture_lf(self):
        report = self.check_case("normal_lf")
        self.assertEqual(report["counts"]["lf"], 1)

    def test_crlf_and_fragmented_whitespace(self):
        for fragments in ((b"\r\n",), (b" ", b"\t", b"\n")):
            with self.subTest(fragments=fragments):
                self.check_case("normal_line_fragments", fragments=fragments)

    def test_reader_observes_during_main_status_block(self):
        report = self.check_case("status_delay", delay=.1, status_delay=.8)
        event = report["result"]["operator_input"]["events"][0]
        self.assertGreater(event["processed_ms"] - event["observed_ms"], 300)

    def test_main_cpu_work_does_not_hide_enter(self):
        self.check_case("cpu_work", delay=.1, cpu_delay=.8)

    def test_missing_and_cr_only_have_same_old_event_log(self):
        for fragments, byte_count in (((), 0), ((b"\r",), 1)):
            with self.subTest(fragments=fragments):
                report = self.check_case("no_recognized_enter", "confirmation_deadline_no_observed_enter",
                                         fragments=fragments)
                self.assertEqual(report["result"]["operator_input"]["events"], [])
                self.assertEqual(report["counts"]["bytes"], byte_count)

    def test_synthetic_unavailable_reader_is_not_evidence_of_no_key_sent(self):
        report = self.check_case("unavailable_reader", "confirmation_deadline_no_observed_enter", reader_gate=True)
        self.assertTrue(report["synthetic_input_sent"])
        self.assertEqual(report["counts"]["reads"], 0)
        self.assertEqual(report["result"]["operator_input"]["events"], [])

    def test_text_duplicate_and_eof_stop(self):
        for fragments, eof, outcome in (((b"x\n",), False, "unexpected_operator_input"),
                                        ((b"\n\n",), False, "unexpected_operator_input"),
                                        ((), True, "terminal_closed")):
            with self.subTest(outcome=outcome, fragments=fragments):
                self.check_case("invalid_input", outcome, fragments=fragments, input_eof=eof, delay=.1)

    def test_capture_failures_and_guard_exit_still_win(self):
        for fault, reason in (("driver", "capture_driver_error"), ("eof", "capture_ended_early"),
                              ("stall", "capture_deadline_or_stall")):
            with self.subTest(fault=fault):
                self.check_case("capture_fault", reason, capture_fault=fault, delay=.1)
        self.check_case("guard_exit", "guard_exited_during_capture", guard_fault=True)

    def test_source_loader_has_no_hardware_or_execution_definitions(self):
        namespace = load_definitions({"time": time, "os": SimpleNamespace(read=lambda *_: b""),
                                      "selectors": selectors})
        self.assertEqual({name for name in namespace if name in DEFINITIONS}, DEFINITIONS)
        for name in ("execute", "USBBoard", "GuardClient", "get_json", "snapshot", "main"):
            self.assertNotIn(name, namespace)


if __name__ == "__main__":
    unittest.main()
