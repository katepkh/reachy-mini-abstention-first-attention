"""Offline instrumentation tests. No SSH, audio, robot API or routing access."""
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
import threading
import time
import types
import unittest
from unittest.mock import Mock, patch

from tools import reachy_input_observation as telemetry
from tools import reachy_mic_health_observed_candidate as m
from tools import reachy_mic_health_input_next as original
from tests import test_mic_capture_input_integration as integration


class ObservationTests(unittest.TestCase):
    def test_read_returns_identical_payload_but_only_counts_are_retained(self):
        payload = b"private-secret-123 \t\v\f\r\n"
        observer = telemetry.InputObservation(clock=lambda: 5., origin=1.)
        read = Mock(return_value=payload)
        self.assertIs(observer.read(read, 9, 64), payload)
        read.assert_called_once_with(9, 64)
        report = observer.snapshot()
        self.assertEqual(report["counts"]["bytes"], len(payload))
        self.assertEqual(report["counts"]["lf"], 1)
        self.assertEqual(report["counts"]["cr"], 1)
        self.assertEqual(report["counts"]["other_whitespace"], 4)
        self.assertEqual(report["counts"]["other"], len(b"private-secret-123"))
        self.assertEqual(report["relative_ms"]["first_read"], 4000)
        self.assertFalse(report["typed_contents_retained"])
        self.assertNotIn("private-secret", repr(vars(observer)))
        self.assertNotIn("private-secret", json.dumps(report))

    def test_empty_read_and_error_are_distinct_sanitized_and_reraised(self):
        observer = telemetry.InputObservation()
        self.assertEqual(observer.read(lambda *_: b"", 1, 64), b"")
        error = OSError(5, "private-error-secret")
        with self.assertRaises(OSError) as caught:
            observer.read(Mock(side_effect=error), 1, 64)
        self.assertIs(caught.exception, error)
        report = observer.snapshot()
        self.assertEqual(report["counts"]["eof_reads"], 1)
        self.assertEqual(report["counts"]["read_errors"], 1)
        self.assertEqual(report["last_errno"], 5)
        self.assertEqual(report["last_error_stage"], "read")
        self.assertNotIn("private-error-secret", json.dumps(report))

    def test_progress_visible_while_read_blocks_without_holding_lock(self):
        observer = telemetry.InputObservation()
        started, release = threading.Event(), threading.Event()
        def read(*_):
            started.set()
            release.wait(2)
            return b"\n"
        worker = threading.Thread(target=lambda: observer.read(read, 1, 64))
        worker.start()
        try:
            self.assertTrue(started.wait(1))
            report = observer.snapshot()
            self.assertEqual(report["counts"]["read_calls"], 1)
            self.assertEqual(report["counts"]["read_returns"], 0)
        finally:
            release.set()
            worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(observer.snapshot()["counts"]["read_returns"], 1)

    def test_selector_passes_timeout_results_and_errors_unchanged(self):
        for stage in (None, "register", "select", "close"):
            observer = telemetry.InputObservation()
            underlying = Mock()
            results = [object()]
            underlying.select.return_value = results
            wrapper = observer.selector(lambda: underlying)
            if stage:
                getattr(underlying, stage).side_effect = OSError(5, "private-detail")
            with self.subTest(stage=stage):
                if stage:
                    with self.assertRaises(OSError):
                        getattr(wrapper, stage)(*(('stream', 1) if stage == 'register' else ()))
                    self.assertNotIn("private-detail", json.dumps(observer.snapshot()))
                else:
                    wrapper.register("stream", 1)
                    self.assertIs(wrapper.select(timeout=.05), results)
                    wrapper.close()
                    underlying.select.assert_called_once_with(timeout=.05)
                    self.assertEqual(observer.snapshot()["counts"]["select_ready"], 1)

    def test_saturation_is_explicit_and_storage_is_constant(self):
        observer = telemetry.InputObservation(clock=lambda: 5.)
        initial = set(observer.snapshot()["counts"])
        observer.counts["bytes"] = observer.LIMIT
        observer.read(lambda *_: b"\n", 1, 64)
        report = observer.snapshot()
        self.assertTrue(report["counter_saturated"])
        self.assertEqual(report["counts"]["bytes"], observer.LIMIT)
        self.assertEqual(set(report["counts"]), initial)
        self.assertLess(len(json.dumps(report)), 2200)
        self.assertEqual(report["clock_origin"], "reader_init")

    def test_terminal_metadata_uses_only_read_calls_and_stores_no_ids(self):
        fake_termios = types.SimpleNamespace(ICRNL=1, IGNCR=2, INLCR=4, ICANON=1,
            ECHO=2, ISIG=4, IEXTEN=8, VMIN=0, VTIME=1,
            tcgetattr=Mock(return_value=[1, 0, 0, 15, 0, 0, [b"\x01", b"\x00"]]))
        fake_os = types.SimpleNamespace(name="posix", isatty=Mock(return_value=True),
                                       tcgetpgrp=Mock(return_value=98765), getpgrp=Mock(return_value=98765))
        with patch.object(telemetry, "os", fake_os), patch.dict("sys.modules", {"termios": fake_termios}):
            result = telemetry.terminal_input_metadata(Mock(fileno=lambda: 9))
        self.assertEqual(result["status"], "available")
        self.assertTrue(result["foreground_matches"])
        self.assertTrue(result["ICANON"])
        self.assertTrue(result["ICRNL"])
        self.assertEqual(result["VMIN"], 1)
        self.assertNotIn("98765", json.dumps(result))
        fake_termios.tcgetattr.assert_called_once_with(9)

    def test_terminal_unavailable_is_not_fabricated_as_healthy(self):
        result = telemetry.terminal_input_metadata(Mock(fileno=Mock(side_effect=OSError("secret"))))
        self.assertEqual(result["status"], "read_error")
        self.assertIsNone(result["foreground_matches"])
        self.assertNotIn("secret", json.dumps(result))


class ObservedReaderTests(unittest.TestCase):
    def reader_case(self, payload, expected, *, eof=False):
        rx, tx = socket.socketpair()
        reader = m.ObservedTerminalInputReader(rx, read=lambda fd, n: rx.recv(n), origin=time.monotonic())
        try:
            if payload:
                tx.sendall(payload)
            if eof:
                tx.shutdown(socket.SHUT_WR)
            if expected:
                event = reader.events.get(timeout=2)
                self.assertEqual(event["kind"], expected)
            else:
                deadline = time.monotonic() + 2
                while reader.observation.snapshot()["counts"]["read_returns"] < bool(payload) and time.monotonic() < deadline:
                    time.sleep(.005)
                self.assertEqual(reader.drain(), [])
            reader.close()
            report = reader.observation_report()
            self.assertFalse(report["thread_alive"])
            self.assertEqual(report["counts"]["thread_starts"], 1)
            self.assertEqual(report["counts"]["thread_exits"], 1)
            self.assertEqual(report["counts"]["bytes"], len(payload))
            self.assertEqual(report["counts"]["emit_ok"], int(bool(expected)))
            self.assertEqual(report["clock_origin"], "capture_start")
            self.assertLess(len(json.dumps(report)), 2700)
            return report
        finally:
            reader.close()
            rx.close()
            tx.close()

    def test_lf_crlf_and_cr_keep_existing_recognition(self):
        for payload, expected in ((b"\n", "enter"), (b"\r\n", "enter"), (b"\r", None)):
            with self.subTest(payload=payload):
                report = self.reader_case(payload, expected)
                self.assertEqual(report["counts"]["cr"], payload.count(b"\r"))
                self.assertEqual(report["counts"]["lf"], payload.count(b"\n"))

    def test_no_bytes_text_and_eof_are_distinct(self):
        empty = self.reader_case(b"", None)
        text = self.reader_case(b"secret-text\n", "text")
        eof = self.reader_case(b"", "eof", eof=True)
        self.assertEqual(empty["counts"]["read_returns"], 0)
        self.assertGreater(empty["counts"]["select_calls"], 0)
        self.assertEqual(text["counts"]["text_events"], 1)
        self.assertNotIn("secret-text", json.dumps(text))
        self.assertEqual(eof["counts"]["eof_reads"], 1)

    def test_read_error_progress_and_fault_are_preserved(self):
        selector = Mock()
        selector.select.return_value = [object()]
        reader = m.ObservedTerminalInputReader(Mock(), read=Mock(side_effect=OSError(5, "secret")),
                                              selector_factory=lambda: selector)
        reader.thread.join(2)
        with self.assertRaisesRegex(m.Stop, "operator_reader_error"):
            reader.close()
        report = reader.observation_report()
        self.assertEqual(report["counts"]["read_errors"], 1)
        self.assertEqual(report["reader_fault"], "operator_reader_error")
        self.assertNotIn("secret", json.dumps(report))

    def test_blocked_selector_and_unverified_exit_remain_visible(self):
        entered, release = threading.Event(), threading.Event()
        selector = Mock()
        def select(timeout):
            entered.set()
            release.wait(3)
            return []
        selector.select.side_effect = select
        reader = m.ObservedTerminalInputReader(Mock(), selector_factory=lambda: selector)
        try:
            self.assertTrue(entered.wait(1))
            before = reader.observation_report()
            self.assertTrue(before["thread_alive"])
            self.assertEqual(before["counts"]["select_calls"], 1)
            self.assertEqual(before["counts"]["select_returns"], 0)
            self.assertEqual(before["counts"]["read_calls"], 0)
            with self.assertRaisesRegex(m.Stop, "operator_reader_exit_unverified"):
                reader.close()
            after = reader.observation_report()
            self.assertTrue(after["thread_alive"])
            self.assertTrue(after["stop_requested"])
        finally:
            release.set()
            reader.thread.join(2)
            reader.close()
        self.assertFalse(reader.observation_report()["thread_alive"])

    def test_unavailable_snapshot_does_not_change_parser_or_mask_cleanup(self):
        rx, tx = socket.socketpair()
        reader = m.ObservedTerminalInputReader(rx, read=lambda fd, n: rx.recv(n))
        try:
            with patch.object(reader.observation, "snapshot", side_effect=RuntimeError("private")):
                self.assertEqual(reader.observation_report()["status"], "unavailable")
            tx.sendall(b"\n")
            self.assertEqual(reader.events.get(timeout=2)["kind"], "enter")
        finally:
            reader.close()
            rx.close()
            tx.close()


class BoundaryTests(unittest.TestCase):
    def test_original_is_preserved_and_all_non_capture_functions_unchanged(self):
        self.assertEqual(hashlib.sha256(Path(original.__file__).read_bytes()).hexdigest(), integration.SOURCE_SHA)
        def definitions(module):
            return {n.name: ast.dump(n) for n in ast.parse(inspect.getsource(module)).body
                    if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        before, after = definitions(original), definitions(m)
        self.assertEqual({name for name in before if before[name] != after[name]}, {"capture_pair"})
        self.assertEqual(set(after) - set(before), {"InputObservation", "ObservedSelector",
                                                  "ObservedTerminalInputReader", "terminal_input_metadata"})
        embedded = definitions(telemetry)
        for name in embedded:
            self.assertEqual(embedded[name], after[name])
        self.assertFalse(m.EXECUTION_RELEASED)
        self.assertNotEqual(m.SESSION, original.SESSION)
        self.assertNotEqual(m.AUTHORIZATION_PATH, original.AUTHORIZATION_PATH)
        self.assertEqual((m.RATE, m.PAIR_LIMIT, m.RESTORE_LIMIT, m.PAIRS),
                         (original.RATE, original.PAIR_LIMIT, original.RESTORE_LIMIT, original.PAIRS))

    def test_capture_only_inserts_diagnostics_around_unchanged_control(self):
        candidate = inspect.getsource(m.capture_pair)
        for inserted in ('    diagnostics = timing["reader_observability"] = {}\n',
                         '        diagnostics["at_start"] = operator.observation_report()\n',
                         '                        diagnostics["at_play"] = operator.observation_report()\n'):
            self.assertEqual(candidate.count(inserted), 1)
            candidate = candidate.replace(inserted, '')
        candidate = candidate.replace('ObservedTerminalInputReader(sys.stdin, origin=started)', 'TerminalInputReader(sys.stdin)')
        new = '''                try:
                    diagnostics["before_close"] = operator.observation_report()
                finally:
                    try:
                        operator.close()
                        timing["reader_exit_verified"] = True
                    finally:
                        diagnostics["after_close"] = operator.observation_report()
'''
        self.assertEqual(candidate.count(new), 1)
        candidate = candidate.replace(new, '                operator.close()\n                timing["reader_exit_verified"] = True\n')
        self.assertEqual(ast.dump(ast.parse(candidate)), ast.dump(ast.parse(inspect.getsource(original.capture_pair))))

    def test_execute_and_guard_reject_before_hardware_or_files(self):
        with ExitStack() as stack:
            stack.enter_context(patch.object(m.sys.stdin, "isatty", return_value=True))
            forbidden = [stack.enter_context(patch.object(m, name, side_effect=AssertionError(name)))
                         for name in ("require_robot_account", "snapshot", "USBBoard", "private_directory",
                                      "protect_own_process", "create_session_directory")]
            for action in (m.require_execution_authorization, m.execute, lambda: m.guard_main(m.SESSION_DIRECTORY)):
                with self.assertRaisesRegex(m.Stop, "candidate_execution_not_released"):
                    action()
            for check in forbidden:
                check.assert_not_called()

    def test_telemetry_has_no_write_or_network_or_content_export_interfaces(self):
        tree = ast.parse(inspect.getsource(telemetry))
        imports = {alias.name for n in ast.walk(tree) if isinstance(n, ast.Import) for alias in n.names}
        self.assertEqual(imports, {"os", "threading", "time", "termios"})
        calls = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        self.assertFalse(calls & {"tcsetattr", "tcflush", "tcsetpgrp", "write", "write_text", "write_bytes",
                                  "open", "connect", "send", "decode", "hexdigest"})


def load_observed_definitions(namespace):
    names = integration.DEFINITIONS | {"InputObservation", "ObservedSelector", "ObservedTerminalInputReader",
                                      "terminal_input_metadata"}
    tree = ast.parse(Path(m.__file__).read_text())
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), m.__file__, "exec"), namespace)
    namespace["terminal_input_metadata"] = lambda _: {"status": "synthetic_socket", "tty": False,
                                                       "foreground_matches": None}
    return namespace


# Reuse the real-thread/socket harness with only the candidate loader and
# instrumented-reader injection changed. No live helper is imported for execute.
source = inspect.getsource(integration.run_scenario)
for before, after in (("ns = load_definitions({", "ns = load_observed_definitions({"),
                       ('exact_reader = ns["TerminalInputReader"]', 'exact_reader = ns["ObservedTerminalInputReader"]'),
                       ("def reader_factory(stream):", "def reader_factory(stream, **kwargs):"),
                       ("reader = exact_reader(stream, selector_factory=GatedSelector)",
                        "reader = exact_reader(stream, selector_factory=GatedSelector, **kwargs)"),
                       ('ns["TerminalInputReader"] = reader_factory', 'ns["ObservedTerminalInputReader"] = reader_factory')):
    if source.count(before) != 1:
        raise RuntimeError("integration_harness_changed")
    source = source.replace(before, after)
namespace = {**integration.__dict__, "load_observed_definitions": load_observed_definitions}
exec(compile(source, '<observed-synthetic-capture>', 'exec'), namespace)
run_observed = namespace["run_scenario"]


class CaptureObservationTests(unittest.TestCase):
    def test_success_and_status_delay_include_fixed_bounded_checkpoints(self):
        report = run_observed("observed_success", status_delay=.8, delay=.1)
        self.assertEqual(report["outcome"], "COMPLETE")
        self.assertEqual(report["result"]["summaries"]["quiet"]["frames"], 48000)
        self.assertEqual(report["result"]["summaries"]["playback"]["frames"], 160000)
        checkpoints = report["result"]["operator_input"]["reader_observability"]
        self.assertEqual(set(checkpoints), {"at_start", "at_play", "before_close", "after_close"})
        final = checkpoints["after_close"]
        self.assertEqual(final["counts"]["lf"], 1)
        self.assertEqual(final["counts"]["enter_events"], 1)
        self.assertFalse(final["thread_alive"])
        self.assertTrue(report["capture_stub_stopped"])
        self.assertLess(len(json.dumps(checkpoints)), 12000)

    def test_timeout_counts_distinguish_cr_without_claiming_no_keypress(self):
        for name, fragments, gate in (("no_bytes", (), False), ("only_cr", (b"\r",), False),
                                       ("gated_reader", (b"\n",), True)):
            with self.subTest(name=name):
                report = run_observed(name, fragments=fragments, reader_gate=gate)
                self.assertEqual(report["outcome"], "confirmation_deadline_no_observed_enter")
                timing = report["result"]["operator_input"]
                self.assertEqual(timing["events"], [])
                before = timing["reader_observability"]["before_close"]
                self.assertTrue(before["thread_alive"])
                if name == "only_cr":
                    self.assertEqual(before["counts"]["cr"], 1)
                    self.assertEqual(before["counts"]["lf"], 0)
                else:
                    self.assertEqual(before["counts"]["read_calls"], 0)
                self.assertGreater(before["counts"]["select_returns"], 0)
                self.assertTrue(timing["reader_exit_verified"])
                self.assertTrue(report["capture_stub_stopped"])


def load_tests(loader, suite, pattern):
    # Existing decision, failure, queue, cleanup and real-reader tests run with
    # the observed class too, not merely the new counter tests.
    from tests import test_mic_input_candidate as old_tests
    source = inspect.getsource(old_tests)
    source = source.replace('reachy_mic_health_input_candidate as m', 'reachy_mic_health_observed_candidate as m')
    source = source.replace('m.TerminalInputReader', 'm.ObservedTerminalInputReader')
    # CaptureTests patches the constructor by attribute name as well.
    source = source.replace('patch.object(m, "TerminalInputReader",', 'patch.object(m, "ObservedTerminalInputReader",')
    module = types.ModuleType('observed_original_regressions')
    module.__file__ = old_tests.__file__
    exec(compile(source, old_tests.__file__, 'exec'), module.__dict__)
    for name in ('CaptureTests', 'ReaderTests'):
        suite.addTests(loader.loadTestsFromTestCase(getattr(module, name)))
    return suite


if __name__ == '__main__':
    unittest.main()
