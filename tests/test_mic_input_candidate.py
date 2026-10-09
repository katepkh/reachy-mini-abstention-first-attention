"""Offline input/capture scheduling tests; no robot, audio device or SSH access."""
import ast
from contextlib import ExitStack
import hashlib
import inspect
import json
import os
from pathlib import Path
import queue
import selectors
import socket
import struct
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import Mock, patch

from tools import reachy_mic_health_input_candidate as m
from tools import reachy_mic_health_missing_pair_speaker as previous


class CaptureTests(unittest.TestCase):
    @staticmethod
    def pcm(seconds):
        return struct.pack("<hhhh", -100, -50, 100, 50) * (16 * seconds // 2)

    def run_capture(self, events, *, check=None, reader_fault=None,
                    close_fault=None, guard_dead=False, construct_fault=None,
                    after_drain=None):
        now = [0.0]
        source = iter(events)
        pending = []
        operator = Mock()
        def drain():
            if reader_fault:
                raise m.Stop(reader_fault)
            batch = pending[:]
            pending.clear()
            operator.observed_through = now[0]
            if after_drain:
                after_drain(now, pending)
            return batch
        operator.drain.side_effect = drain
        operator.close.side_effect = m.Stop(close_fault) if close_fault else None
        pcm_pipe, err_pipe = Mock(), Mock()
        pcm_pipe.fileno.return_value, err_pipe.fileno.return_value = 10, 11
        process = types.SimpleNamespace(stdout=pcm_pipe, stderr=err_pipe)
        guard = types.SimpleNamespace(process=Mock())
        guard.process.poll.return_value = 1 if guard_dead else None
        selector = Mock()
        payload = [b""]
        def select(timeout):
            event = next(source, ("pcm", b""))
            kind, value = event
            if kind == "call":
                value(now, pending)
                return []
            if kind == "interrupt":
                raise KeyboardInterrupt()
            if kind == "time":
                now[0] += value
                return []
            now[0] += .01
            if kind == "operator":
                pending.append({"kind": value, "observed_at": now[0]})
                return []
            payload[0] = value
            return [(types.SimpleNamespace(data=kind), None)]
        selector.select.side_effect = select
        self.result = {}
        with ExitStack() as stack:
            for obj, key, value in ((m, "RATE", 16),):
                stack.enter_context(patch.object(obj, key, value))
            stack.enter_context(patch.object(m.subprocess, "Popen", return_value=process))
            factory = stack.enter_context(patch.object(m, "TerminalInputReader", return_value=operator))
            if construct_fault:
                factory.side_effect = RuntimeError("reader start failed")
            stack.enter_context(patch.object(m.selectors, "DefaultSelector", return_value=selector))
            stack.enter_context(patch.object(m.os, "set_blocking"))
            stack.enter_context(patch.object(m.os, "read", side_effect=lambda *_: payload[0]))
            stack.enter_context(patch.object(m.time, "monotonic", side_effect=lambda: now[0]))
            self.printed = stack.enter_context(patch.object(m, "print"))
            stack.enter_context(patch.object(m, "check_robot", side_effect=lambda: check(now, pending) if check else None))
            stop = stack.enter_context(patch.object(m, "stop_own_capture"))
            try:
                m.capture_pair(0, self.result, guard)
            finally:
                stop.assert_called_once_with(process)
                pcm_pipe.close.assert_called_once()
                err_pipe.close.assert_called_once()
                if not construct_fault:
                    operator.close.assert_called_once()
                    selector.close.assert_called_once()
        return self.result

    def test_complete_counts_and_existing_phase_lengths(self):
        result = self.run_capture([("pcm", self.pcm(5)), ("operator", "enter"), ("pcm", self.pcm(12))])
        self.assertTrue(result["complete"])
        self.assertEqual(result["microphones"], [2, 3])
        self.assertEqual(len(result["blocks"]), 13)
        self.assertEqual(result["summaries"]["quiet"]["frames"], 48)
        self.assertEqual(result["summaries"]["playback"]["frames"], 160)
        self.assertTrue(result["capture_exit_verified"])
        timing = result["operator_input"]
        self.assertTrue(timing["reader_exit_verified"])
        self.assertFalse(timing["physical_keypress_time_known"])
        self.assertEqual(timing["confirmation_limit_s"], 10)
        self.assertTrue(timing["events"][0]["accepted"])

    def test_fragmented_pcm(self):
        quiet, play = self.pcm(5), self.pcm(12)
        result = self.run_capture([("pcm", quiet[:3]), ("pcm", quiet[3:]),
                                   ("operator", "enter"), ("pcm", play[:1]), ("pcm", play[1:])])
        self.assertTrue(result["complete"])

    def waiting(self):
        # Fresh synthetic PCM throughout the wait; clock models seconds, not speed.
        return [("pcm", self.pcm(5))] + [("time", 1), ("pcm", self.pcm(1))] * 9

    def test_on_time_observation_survives_delayed_main_processing(self):
        def queued(now, pending):
            pending.append({"kind": "enter", "observed_at": .01 + 9.99})
            now[0] = .01 + 10.01
        result = self.run_capture(self.waiting() + [("call", queued), ("pcm", self.pcm(12))])
        self.assertTrue(result["complete"])
        timing = result["operator_input"]
        event = timing["events"][0]
        self.assertLess(event["observed_ms"] - timing["prompt_started_ms"], 10000)
        self.assertGreater(event["processed_ms"] - timing["prompt_started_ms"], 10000)
        self.assertTrue(event["accepted"])

    def test_status_check_delay_does_not_erase_queued_event(self):
        def check(now, pending):
            if now[0] > 9:
                pending.append({"kind": "enter", "observed_at": .01 + 9.99})
                now[0] += .02
        result = self.run_capture(self.waiting() + [("pcm", self.pcm(1)), ("time", 1),
                                                   ("pcm", self.pcm(12))], check=check)
        self.assertTrue(result["complete"])
        self.assertTrue(result["operator_input"]["events"][0]["accepted"])

    def test_event_between_snapshot_and_expiry_decision_is_not_lost(self):
        calls = [0]
        def race(now, pending):
            if 9.99 < now[0] < 10:
                calls[0] += 1
                if calls[0] == 2:  # Pre-select snapshot, after the previous poll.
                    pending.append({"kind": "enter", "observed_at": 10.0})
                    now[0] = 10.02
        result = self.run_capture(self.waiting() + [("time", .895), ("pcm", self.pcm(12))],
                                  after_drain=race)
        self.assertEqual(calls[0], 2)
        self.assertTrue(result["complete"])
        self.assertTrue(result["operator_input"]["events"][0]["accepted"])

    def test_equal_or_late_observation_is_rejected_not_backdated(self):
        for offset in (10.0, 10.01):
            with self.subTest(offset=offset):
                def late(now, pending):
                    now[0] = .01 + offset
                    pending.append({"kind": "enter", "observed_at": now[0]})
                with self.assertRaisesRegex(m.Stop, "confirmation_observed_after_deadline"):
                    self.run_capture(self.waiting() + [("call", late)])
                self.assertFalse(self.result["operator_input"]["events"][0]["accepted"])

    def test_no_observation_has_distinct_diagnostic(self):
        with self.assertRaisesRegex(m.Stop, "confirmation_deadline_no_observed_enter"):
            self.run_capture(self.waiting() + [("time", 1)])
        self.assertIn("deadline_check_ms", self.result["operator_input"])

    def test_early_text_eof_and_duplicate_inputs_abort(self):
        cases = [([("operator", "enter")], "unexpected_operator_input"),
                 ([("pcm", self.pcm(5)), ("operator", "text")], "unexpected_operator_input"),
                 ([("pcm", self.pcm(5)), ("operator", "eof")], "terminal_closed"),
                 ([("pcm", self.pcm(5)), ("operator", "enter"), ("operator", "enter")], "unexpected_operator_input")]
        for events, reason in cases:
            with self.subTest(reason=reason, events=len(events)):
                with self.assertRaisesRegex(m.Stop, reason):
                    self.run_capture(events)
                self.assertTrue(self.result["capture_exit_verified"])

    def test_queued_early_enter_cannot_become_valid_after_phase_changes(self):
        def early(now, pending):
            pending.append({"kind": "enter", "observed_at": 0.0})
        with self.assertRaisesRegex(m.Stop, "unexpected_operator_input"):
            self.run_capture([("pcm", self.pcm(5)), ("call", early)])

    def test_duplicate_same_batch_is_not_silently_swallowed(self):
        def doubled(now, pending):
            pending.extend([{"kind": "enter", "observed_at": now[0]}] * 2)
        with self.assertRaisesRegex(m.Stop, "unexpected_operator_input"):
            self.run_capture([("pcm", self.pcm(5)), ("call", doubled)])
        self.assertEqual([e["accepted"] for e in self.result["operator_input"]["events"]], [True, False])

    def test_invalid_or_future_event_times_stop(self):
        for value in (-1, float("nan"), float("inf"), 999, "not a timestamp"):
            def invalid(now, pending):
                pending.append({"kind": "enter", "observed_at": value})
            with self.subTest(value=value), self.assertRaisesRegex(m.Stop, "operator_timestamp_invalid"):
                self.run_capture([("pcm", self.pcm(5)), ("call", invalid)])

    def test_extra_enter_during_playback_preserves_partial_stats(self):
        with self.assertRaisesRegex(m.Stop, "unexpected_operator_input"):
            self.run_capture([("pcm", self.pcm(5)), ("operator", "enter"),
                              ("pcm", self.pcm(3)), ("operator", "enter")])
        self.assertEqual(self.result["partial_phase"]["phase"], "playback")
        self.assertEqual(self.result["partial_phase"]["frames"], 16)

    def test_failures_always_close_reader_and_capture(self):
        for events, kwargs, error in [([("interrupt", None)], {}, KeyboardInterrupt),
                ([], {"guard_dead": True}, m.Stop), ([('error', b'driver detail')], {}, m.Stop),
                ([("time", 2.1)], {}, m.Stop), ([], {"reader_fault": "operator_reader_error"}, m.Stop),
                ([], {"close_fault": "operator_reader_exit_unverified"}, m.Stop),
                ([], {"construct_fault": True}, RuntimeError)]:
            with self.subTest(kwargs=kwargs, events=events), self.assertRaises(error):
                self.run_capture(events, **kwargs)
            self.assertTrue(self.result["capture_exit_verified"])

    def test_failed_reader_shutdown_cannot_return_success(self):
        with self.assertRaisesRegex(m.Stop, "operator_reader_exit_unverified"):
            self.run_capture([("pcm", self.pcm(5)), ("operator", "enter"), ("pcm", self.pcm(12))],
                             close_fault="operator_reader_exit_unverified")
        self.assertFalse(self.result["operator_input"]["reader_exit_verified"])
        self.assertTrue(self.result["capture_exit_verified"])

    def test_hardware_check_failure_still_wins_over_input(self):
        def fail(now, pending):
            pending.append({"kind": "enter", "observed_at": now[0]})
            raise m.Stop("robot_drift")
        with self.assertRaisesRegex(m.Stop, "robot_drift"):
            self.run_capture(self.waiting(), check=fail)

    def test_stall_limit_rechecked_after_blocking_status(self):
        def delay(now, pending):
            now[0] += 3
            pending.append({"kind": "enter", "observed_at": now[0]})
        with self.assertRaisesRegex(m.Stop, "capture_deadline_or_stall"):
            self.run_capture(self.waiting(), check=delay)

    def test_queued_enter_cannot_extend_hard_capture_limit(self):
        def expired(now, pending):
            pending.append({"kind": "enter", "observed_at": now[0]})
            now[0] = 37.0
        with self.assertRaisesRegex(m.Stop, "capture_deadline_or_stall"):
            self.run_capture([("pcm", self.pcm(5)), ("call", expired)])
        self.assertEqual(self.result["operator_input"]["events"], [])


class ReaderTests(unittest.TestCase):
    def socket_reader(self, **kwargs):
        receiver, sender = socket.socketpair()
        self.addCleanup(receiver.close)
        self.addCleanup(sender.close)
        reader = m.TerminalInputReader(receiver, read=lambda fd, n: receiver.recv(n), **kwargs)
        self.addCleanup(reader.close)
        return reader, receiver, sender

    def event(self, reader):
        return reader.events.get(timeout=2)

    def test_real_selector_thread_observes_while_main_is_not_draining(self):
        reader, receiver, sender = self.socket_reader()
        sender.sendall(b"\n")
        # Wait for publication, not main-loop consumption or a fabricated timestamp.
        with reader.events.not_empty:
            self.assertTrue(reader.events.not_empty.wait_for(lambda: reader.events._qsize() > 0, timeout=2))
        after_publication = time.monotonic()
        events = reader.drain()
        self.assertEqual([e["kind"] for e in events], ["enter"])
        self.assertLessEqual(events[0]["observed_at"], after_publication)
        self.assertGreaterEqual(reader.observed_through, events[0]["observed_at"])
        reader.close()
        self.assertFalse(reader.thread.is_alive())
        self.assertGreaterEqual(receiver.fileno(), 0)  # Never owns/closes stdin.

    def test_crlf_and_separate_blank_lines(self):
        reader, _, sender = self.socket_reader()
        sender.sendall(b" \t\r\n\n")
        self.assertEqual(self.event(reader)["kind"], "enter")
        self.assertEqual(self.event(reader)["kind"], "enter")

    def test_split_whitespace_line(self):
        reader, _, sender = self.socket_reader()
        sender.sendall(b" ")
        sender.sendall(b"\n")
        self.assertEqual(self.event(reader)["kind"], "enter")

    def test_later_publication_cannot_predate_empty_snapshot(self):
        reader, _, sender = self.socket_reader()
        self.assertEqual(reader.drain(), [])
        cutoff = reader.observed_through
        sender.sendall(b"\n")
        self.assertGreaterEqual(self.event(reader)["observed_at"], cutoff)

    def test_eof_is_an_event_not_an_enter(self):
        reader, _, sender = self.socket_reader()
        sender.shutdown(socket.SHUT_WR)
        self.assertEqual(self.event(reader)["kind"], "eof")

    def test_text_is_sanitized_and_not_retained_in_event(self):
        reader, _, sender = self.socket_reader(clock=lambda: 42.)
        sender.sendall(b"private-text\n")
        self.assertEqual(self.event(reader), {"kind": "text", "observed_at": 42.})

    def test_excessive_whitespace_is_rejected(self):
        reader, _, sender = self.socket_reader()
        sender.sendall(b" " * 257)
        self.assertEqual(self.event(reader)["kind"], "text")

    def test_overflow_is_fail_closed(self):
        receiver, sender = socket.socketpair()
        try:
            reader = m.TerminalInputReader(receiver, read=lambda fd, n: receiver.recv(n))
            sender.sendall(b"\n" * 9)
            reader.thread.join(timeout=2)
            self.assertFalse(reader.thread.is_alive())
            with self.assertRaisesRegex(m.Stop, "operator_input_overflow"):
                reader.drain()
            with self.assertRaisesRegex(m.Stop, "operator_input_overflow"):
                reader.close()
        finally:
            receiver.close()
            sender.close()

    def test_read_or_selector_error_is_sanitized(self):
        for stage in ("register", "read", "close"):
            selector = Mock()
            selector.select.return_value = [object()]
            if stage != "read":
                getattr(selector, stage).side_effect = OSError("private detail")
            read = Mock(return_value=b"")
            if stage == "read":
                read.side_effect = OSError("private detail")
            reader = m.TerminalInputReader(Mock(), read=read, selector_factory=lambda: selector)
            reader.thread.join(timeout=2)
            with self.subTest(stage=stage):
                with self.assertRaisesRegex(m.Stop, "^operator_reader_error$"):
                    reader.drain()
                with self.assertRaisesRegex(m.Stop, "^operator_reader_error$"):
                    reader.close()
                selector.close.assert_called_once()

    def test_unverified_reader_exit_is_not_ignored(self):
        release = threading.Event()
        selected = threading.Event()
        selector = Mock()
        def blocked(timeout):
            selected.set()
            release.wait(3)
            return []
        selector.select.side_effect = blocked
        reader = m.TerminalInputReader(Mock(), selector_factory=lambda: selector)
        try:
            self.assertTrue(selected.wait(2))
            with self.assertRaisesRegex(m.Stop, "operator_reader_exit_unverified"):
                reader.close()
        finally:
            release.set()
            reader.thread.join(timeout=2)
        self.assertFalse(reader.thread.is_alive())

    @unittest.skipUnless(os.name == "posix", "Linux/POSIX PTY unavailable on this Windows host")
    def test_canonical_pty_without_terminal_mode_changes(self):
        import termios
        master, slave = os.openpty()
        stream = os.fdopen(slave, "rb", buffering=0)
        reader = None
        try:
            before = termios.tcgetattr(slave)
            self.assertTrue(before[3] & termios.ICANON)
            reader = m.TerminalInputReader(stream)
            os.write(master, b"\n")
            self.assertEqual(self.event(reader)["kind"], "enter")
            reader.close()
            self.assertEqual(termios.tcgetattr(slave), before)
            self.assertFalse(stream.closed)
        finally:
            if reader is not None:
                reader.close()
            stream.close()
            os.close(master)


class BoundaryTests(unittest.TestCase):
    def test_old_source_and_all_non_capture_definitions_unchanged(self):
        self.assertEqual(hashlib.sha256(Path(previous.__file__).read_bytes()).hexdigest(),
                         "320939f520bb702d306cab05c0a3fa9134289d5d3de38871feab63e8cf15fe90")
        def definitions(module):
            return {node.name: ast.dump(node) for node in ast.parse(inspect.getsource(module)).body
                    if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
        old, new = definitions(previous), definitions(m)
        self.assertEqual(set(new) - set(old), {"TerminalInputReader"})
        self.assertEqual({key for key in old if old[key] != new[key]}, {"capture_pair"})
        self.assertEqual((m.PAIR_LIMIT, m.RESTORE_LIMIT, m.RATE), (40., 5., 16000))
        self.assertEqual(m.capture_command(), previous.capture_command())
        self.assertEqual(m.PAIRS, previous.PAIRS)
        self.assertFalse(m.EXECUTION_RELEASED)
        self.assertNotEqual(m.SESSION, previous.SESSION)
        self.assertNotEqual(m.AUTHORIZATION_PATH, previous.AUTHORIZATION_PATH)

    def test_execution_and_guard_block_before_hardware_or_file_access(self):
        with ExitStack() as stack:
            stack.enter_context(patch.object(m.sys.stdin, "isatty", return_value=True))
            forbidden = [stack.enter_context(patch.object(m, name, side_effect=AssertionError(name)))
                         for name in ("require_robot_account", "snapshot", "USBBoard", "private_directory",
                                      "protect_own_process", "create_session_directory")]
            for action in (m.require_execution_authorization, m.execute, lambda: m.guard_main(m.SESSION_DIRECTORY)):
                with self.assertRaisesRegex(m.Stop, "candidate_execution_not_released"):
                    action()
            for mock in forbidden:
                mock.assert_not_called()

    def test_reader_failure_reaches_parent_restoration_and_aborted_report(self):
        for reason in ("operator_reader_error", "operator_reader_exit_unverified"):
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
                directory = Path(tmp) / "runs" / "one"
                stack.enter_context(patch.object(m, "RUN_ROOT", directory.parent))
                stack.enter_context(patch.object(m, "SESSION_DIRECTORY", directory))
                stack.enter_context(patch.object(m.sys.stdin, "isatty", return_value=True))
                stack.enter_context(patch.object(m, "require_execution_authorization"))
                stack.enter_context(patch.object(m, "protect_own_process"))
                stack.enter_context(patch.object(m, "snapshot", return_value={"helper_sha256": "fixture"}))
                stack.enter_context(patch.object(m, "input", return_value=m.ACK, create=True))
                stack.enter_context(patch.object(m, "print"))
                calls = []
                def guard(path):
                    def request(action, expected, **kwargs):
                        calls.append(action)
                        if action == "restore":
                            m.save_json(path / "guard.json", {"restoration": "ROUTES_RESTORED"})
                    return types.SimpleNamespace(request=request, close=lambda: None)
                def capture(pair, result, guard):
                    result.update(capture_exit_verified=True, complete=False,
                                  operator_input={"reader_exit_verified": False})
                    raise m.Stop(reason)
                stack.enter_context(patch.object(m, "GuardClient", side_effect=guard))
                stack.enter_context(patch.object(m, "capture_pair", side_effect=capture))
                self.assertEqual(m.execute(), 2)
                self.assertEqual(calls, ["begin", "restore"])
                result = json.loads((directory / "result.json").read_text())
                self.assertEqual(result["status"], "ABORTED_REVIEW_REQUIRED")
                self.assertEqual(result["reason"], reason)
                self.assertEqual(result["route_restoration"], "ROUTES_RESTORED")
                self.assertFalse(result["pair_results"][0]["operator_input"]["reader_exit_verified"])


def load_tests(loader, standard_tests, pattern):
    # Exercise unchanged numeric and USB/guard code against this candidate too.
    for filename, old_import, classes, excluded in (
            ("test_mic_health.py", "reachy_mic_health as m", ("TestStats",), ()),
            ("test_mic_missing_pair_fixed.py", "reachy_mic_health_missing_pair_fixed as m",
             ("AdapterRepairTests",), ("test_only_adapter_cardinality_and_release_gate_changed",))):
        path = Path(__file__).with_name(filename)
        source = path.read_text().replace(old_import, "reachy_mic_health_input_candidate as m")
        module = types.ModuleType("input_candidate_" + path.stem)
        module.__file__ = str(path)
        exec(compile(source, str(path), "exec"), module.__dict__)
        for name in classes:
            cls = getattr(module, name)
            for method in excluded:
                delattr(cls, method)
            standard_tests.addTests(loader.loadTestsFromTestCase(cls))
    return standard_tests


if __name__ == "__main__":
    unittest.main()
