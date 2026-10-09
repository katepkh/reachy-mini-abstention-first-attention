"""Exercise the real USBBoard/RouteGuard code with a synthetic USB transport."""
import ast
from contextlib import ExitStack
import hashlib
import io
import json
from pathlib import Path
import queue
import unittest
from unittest.mock import patch

from tools import reachy_mic_health_missing_pair as old
from tools import reachy_mic_health_missing_pair_fixed as m


class USBTransport:
    def __init__(self):
        self.values = {15: [8, 0], 19: [8, 0]}
        self.calls = []
        self.fail_out = None
        self.short_out = None
        self.ignore_out = None
        self.out_count = 0

    def ctrl_transfer(self, direction, request, command, index, data, timeout):
        assert request == 0 and index == 35 and 1 <= timeout <= 500
        self.calls.append((direction, command, data))
        if direction == 0xC0:
            assert data == 3 and command in (143, 147)
            return bytes([0, *self.values[command & 0x7F]])
        assert direction == 0x40 and command in (15, 19)
        assert isinstance(data, bytes) and len(data) == 2 and timeout == 500
        self.out_count += 1
        if self.ignore_out != self.out_count:
            self.values[command] = list(data)
        if self.fail_out == self.out_count:
            raise OSError("synthetic post-write failure")
        return 1 if self.short_out == self.out_count else 2


def adapter(module=m):
    board = module.USBBoard.__new__(module.USBBoard)
    board.dev = USBTransport()
    return board


class AdapterRepairTests(unittest.TestCase):
    def test_original_failure_reproduces_before_any_out_transfer(self):
        board = adapter(old)
        guard = old.RouteGuard(board, lambda _: None)
        with self.assertRaises(IndexError):
            guard.begin(0)
        self.assertEqual(board.dev.out_count, 0)
        self.assertEqual(guard.restoration, "RESTORATION_UNVERIFIED")

    def test_actual_adapter_single_pair_and_double_readback(self):
        board = adapter()
        guard = m.RouteGuard(board, lambda _: None)
        guard.begin(0)
        self.assertEqual(board.dev.values, {15: [3, 2], 19: [3, 3]})
        self.assertEqual(guard.restore(), "ROUTES_RESTORED")
        writes = [(c, list(v)) for d, c, v in board.dev.calls if d == 0x40]
        self.assertEqual(writes, [(15, [3, 2]), (19, [3, 3]), (15, [8, 0]), (19, [8, 0])])
        self.assertEqual(board.dev.calls[-4:], [(0xC0, 143, 3), (0xC0, 147, 3)] * 2)
        for value in (0, 1, -1, True, None):
            with self.assertRaises(m.Stop):
                guard.begin(value)
        self.assertEqual(board.dev.out_count, 4)

    def test_wrong_route_key_value_and_type_are_blocked_before_io(self):
        for key, value in [("GAIN", [8, 0]), (m.ROUTES[0], [3, 0]),
                           (m.ROUTES[1], [3, 1]), (m.ROUTES[0], [3, 3]),
                           (m.ROUTES[1], [3, 2]), (m.ROUTES[0], [8, False]),
                           (m.ROUTES[0], [3.0, 2]), (m.ROUTES[0], [3]),
                           (m.ROUTES[0], None), (m.ROUTES[0], "32")]:
            with self.subTest(key=key, value=value):
                board = adapter()
                with self.assertRaises(m.Stop):
                    board.write(key, value)
                self.assertEqual(board.dev.calls, [])

    def test_partial_short_or_exception_writes_restore_without_retrying_target(self):
        for failure in ("fail_out", "short_out", "ignore_out"):
            for number in (1, 2):
                with self.subTest(failure=failure, number=number):
                    board = adapter()
                    setattr(board.dev, failure, number)
                    guard = m.RouteGuard(board, lambda _: None)
                    with self.assertRaises((OSError, m.Stop)):
                        guard.begin(0)
                    self.assertTrue(guard.terminal)
                    self.assertEqual(guard.restoration, "ROUTES_RESTORED")
                    self.assertEqual(board.dev.values, {15: [8, 0], 19: [8, 0]})
                    targets = [v for d, _, v in board.dev.calls if d == 0x40 and v != bytes([8, 0])]
                    self.assertLessEqual(targets.count(bytes([3, 2])), 1)
                    self.assertLessEqual(targets.count(bytes([3, 3])), 1)

    def test_failed_restore_is_not_claimed_verified_even_if_readback_matches(self):
        board = adapter()
        guard = m.RouteGuard(board, lambda _: None)
        guard.begin(0)
        board.dev.fail_out = 3
        self.assertEqual(guard.restore(), "RESTORATION_UNVERIFIED")
        self.assertTrue(guard.dirty)
        self.assertTrue(guard.terminal)

    def test_external_drift_is_not_overwritten(self):
        board = adapter()
        guard = m.RouteGuard(board, lambda _: None)
        guard.begin(0)
        board.dev.values[15] = [7, 7]
        self.assertEqual(guard.restore(), "RESTORATION_UNVERIFIED")
        self.assertEqual(board.dev.values[15], [7, 7])

    def test_watchdog_restores_through_actual_adapter(self):
        now = [0.0]
        board = adapter()
        # Deadlines below are synthetic; retain the real adapter read/write path.
        with patch.object(m.time, "monotonic", side_effect=lambda: now[0]), \
             patch.object(m, "read_route_with_retry", wraps=lambda device, key, deadline=None:
                          old.read_route_with_retry(device, key, deadline=deadline, clock=lambda: now[0])):
            guard = m.RouteGuard(board, lambda _: None, clock=lambda: now[0])
            guard.begin(0)
            now[0] = m.PAIR_LIMIT
            self.assertTrue(guard.tick())
        self.assertEqual(guard.restoration, "ROUTES_RESTORED")

    def test_ipc_exits_after_one_restore_without_third_message(self):
        messages = queue.Queue()
        messages.put({"action": "begin", "pair": 0})
        messages.put({"action": "restore"})
        calls = []
        def get(timeout):
            calls.append(timeout)
            if len(calls) > 2:
                raise AssertionError("guard incorrectly waited after the only pair")
            return messages.get_nowait()
        output = io.StringIO()
        with patch.object(m.queue, "Queue") as factory, patch.object(m.threading, "Thread"):
            factory.return_value.get.side_effect = get
            m.serve_guard(adapter(), lambda _: None, io.StringIO(), output)
        self.assertEqual(len(calls), 2)
        self.assertEqual([json.loads(x)["status"] for x in output.getvalue().splitlines()],
                         ["READY", "ROUTED", "ROUTES_RESTORED", "ROUTES_RESTORED"])

    def test_candidate_execute_and_guard_stop_before_hardware_and_files(self):
        self.assertIs(m.EXECUTION_RELEASED, False)
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

    def test_only_adapter_cardinality_and_release_gate_changed(self):
        def definitions(module):
            return {n.name: ast.dump(n) for n in ast.parse(Path(module.__file__).read_text()).body
                    if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        a, b = definitions(old), definitions(m)
        self.assertEqual(a.keys(), b.keys())
        self.assertEqual({k for k in a if a[k] != b[k]},
                         {"USBBoard", "serve_guard", "require_execution_authorization"})
        self.assertEqual((m.PAIR_LIMIT, m.RESTORE_LIMIT, m.RATE), (40.0, 5.0, 16000))
        self.assertEqual(m.PAIRS, old.PAIRS)
        root = Path(m.__file__).resolve().parents[1]
        for file, expected in [
            ("tools/reachy_mic_health_missing_pair.py", "2e18a7c7b706590ce726c00c3e6e2c87523d0b75ddc2eb069eeb139b6615303a"),
            ("scripts/run_reachy_mic_missing_pair.py", "d4ea2df205f3e62668f78a905171451984af6b1226304f822c1f50881ae6b428")]:
            self.assertEqual(hashlib.sha256((root / file).read_bytes()).hexdigest(), expected)


if __name__ == "__main__":
    unittest.main()
