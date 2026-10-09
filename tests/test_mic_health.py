"""Synthetic-only tests. No robot, USB, camera or sound device is opened."""

import io
from contextlib import ExitStack
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools import reachy_mic_health as m


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class TestStats(unittest.TestCase):
    def stats(self, samples):
        stats = m.Stats()
        stats.feed(b"".join(struct.pack("<hh", *row) for row in samples))
        return stats.report()

    def test_empty_no_nan(self):
        result = self.stats([])
        self.assertEqual(result["frames"], 0)
        self.assertIsNone(result["correlation"])
        json.dumps(result, allow_nan=False)

    def test_digital_zero_not_finite_db(self):
        result = self.stats([(0, 0)] * 40)
        for channel in result["channels"]:
            self.assertIsNone(channel["rms_dbfs"])
            self.assertEqual(channel["zero_fraction"], 1)
            self.assertEqual(channel["longest_unchanged_samples"], 40)

    def test_stuck_nonzero_not_silence(self):
        result = self.stats([(100, -200)] * 20)
        self.assertEqual(result["channels"][0]["zero_fraction"], 0)
        self.assertTrue(result["channels"][0]["zero_variance"])
        self.assertAlmostEqual(result["channels"][1]["dc"], -200 / 32768)

    def test_level_ratio_and_correlation(self):
        result = self.stats([(-1000, -500), (1000, 500)] * 100)
        self.assertAlmostEqual(result["channels"][0]["rms"], 1000 / 32768)
        difference = result["channels"][0]["rms_dbfs"] - result["channels"][1]["rms_dbfs"]
        self.assertAlmostEqual(difference, 20 * math.log10(2))
        self.assertAlmostEqual(result["correlation"], 1)
        self.assertEqual(result["equal_fraction"], 0)

    def test_both_signed_rails_clip(self):
        result = self.stats([(-32768, 32767), (32767, -32768), (0, 0)])
        for channel in result["channels"]:
            self.assertEqual(channel["clip_fraction"], 2 / 3)
            self.assertEqual(channel["peak"], 1)

    def test_duplicate_channels(self):
        result = self.stats([(index, index) for index in range(20)])
        self.assertEqual(result["equal_fraction"], 1)
        self.assertEqual(result["correlation"], 1)

    def test_flat_run_survives_chunks(self):
        stats = m.Stats()
        stats.feed(struct.pack("<hhhh", 5, 0, 5, 0))
        stats.feed(struct.pack("<hhhh", 5, 0, 7, 0))
        self.assertEqual(stats.report()["channels"][0]["longest_unchanged_samples"], 3)
        self.assertEqual(stats.report()["channels"][1]["longest_unchanged_samples"], 4)

    def test_partial_frame_rejected(self):
        for count in (1, 2, 3, 5):
            with self.assertRaises(m.Stop):
                m.Stats().feed(bytes(count))

    def test_no_waveform_in_report(self):
        stats = self.stats([(11, 29), (22, 31)])
        self.assertEqual(set(stats), {"frames", "channels", "correlation", "equal_fraction"})


class TestGuard(unittest.TestCase):
    def setUp(self):
        self.board = m.FakeBoard()
        self.clock = Clock()
        self.records = []
        self.guard = m.RouteGuard(self.board, self.records.append, self.clock)

    def test_constructor_is_read_only(self):
        self.assertEqual(self.board.writes, [])
        self.assertEqual(self.records[0]["baseline"], m.BASELINE)

    def test_two_pairs_and_restore(self):
        for pair in (0, 1):
            self.guard.begin(pair)
            self.assertEqual(self.board.values, m.PAIRS[pair])
            self.assertEqual(self.guard.restore(), "ROUTES_RESTORED")
            self.assertEqual(self.board.values, m.BASELINE)
        self.assertEqual(len(self.board.writes), 8)
        with self.assertRaises(m.Stop):
            self.guard.begin(2)

    def test_out_of_order_and_repeat_prohibited(self):
        for invalid in (1, -1, True, "0", None):
            with self.assertRaises(m.Stop):
                self.guard.begin(invalid)
        self.guard.begin(0)
        with self.assertRaises(m.Stop):
            self.guard.begin(1)
        self.guard.restore()
        with self.assertRaises(m.Stop):
            self.guard.begin(0)

    def test_unknown_baseline_prevents_write(self):
        self.board.values[m.ROUTES[0]] = [3, 1]
        with self.assertRaises(m.Stop):
            m.RouteGuard(self.board, self.records.append)
        self.assertEqual(self.board.writes, [])

    def test_external_drift_not_overwritten(self):
        self.board.values[m.ROUTES[1]] = [3, 2]
        with self.assertRaises(m.Stop):
            self.guard.begin(0)
        self.assertEqual(self.board.writes, [])

    def test_external_drift_during_pair_preserved(self):
        self.guard.begin(0)
        self.board.values[m.ROUTES[0]] = [3, 3]
        self.assertEqual(self.guard.restore(), "RESTORATION_UNVERIFIED")
        self.assertEqual(self.board.values[m.ROUTES[0]], [3, 3])
        self.assertEqual(self.board.values[m.ROUTES[1]], [8, 0])

    def test_reservation_storage_failure_has_zero_writes(self):
        self.guard.journal = Mock(side_effect=OSError("full"))
        with self.assertRaises(OSError):
            self.guard.begin(0)
        self.assertFalse(self.guard.dirty)
        self.assertEqual(self.board.writes, [])

    def test_active_watchdog_never_waits_for_journal(self):
        def journal(_):
            self.assertEqual(self.board.values, m.BASELINE)
        self.guard.journal = journal
        self.guard.begin(0)
        self.guard.restore()

    def test_partial_write_restores_both(self):
        original = self.board.write
        def fail_right(key, value):
            if key == m.ROUTES[1] and value == [3, 1]:
                raise OSError("synthetic USB timeout")
            original(key, value)
        self.board.write = fail_right
        with self.assertRaises(OSError):
            self.guard.begin(0)
        self.assertEqual(self.board.values, m.BASELINE)
        self.assertTrue(self.guard.terminal)
        self.assertEqual(self.guard.restoration, "ROUTES_RESTORED")

    def test_acknowledged_but_wrong_readback_aborts(self):
        original = self.board.write
        def ignore_second(key, value):
            if key == m.ROUTES[1] and value == [3, 1]:
                return
            original(key, value)
        self.board.write = ignore_second
        with self.assertRaises(m.Stop):
            self.guard.begin(0)
        self.assertEqual(self.board.values, m.BASELINE)

    def test_write_timeout_after_apply_restores(self):
        original = self.board.write
        def apply_then_fail(key, value):
            original(key, value)
            if key == m.ROUTES[0] and value == [3, 0]:
                raise OSError("applied then timed out")
        self.board.write = apply_then_fail
        with self.assertRaises(OSError):
            self.guard.begin(0)
        self.assertEqual(self.board.values, m.BASELINE)

    def test_expiry_restores_and_latches(self):
        self.guard.begin(0)
        self.clock.now = m.PAIR_LIMIT
        self.assertTrue(self.guard.tick())
        self.assertEqual(self.board.values, m.BASELINE)
        with self.assertRaises(m.Stop):
            self.guard.begin(1)

    def test_failed_restore_reported_not_hidden(self):
        self.guard.begin(0)
        original = self.board.write
        def fail_restore(key, value):
            if key == m.ROUTES[0] and value == [8, 0]:
                raise OSError("hardware unavailable")
            original(key, value)
        self.board.write = fail_restore
        self.assertEqual(self.guard.restore(), "RESTORATION_UNVERIFIED")
        self.assertTrue(self.guard.terminal)
        self.assertEqual(self.board.values[m.ROUTES[1]], [8, 0])

    def test_restore_is_time_bounded(self):
        self.guard.begin(0)
        original = self.board.write
        def slow(key, value):
            self.clock.now += 3
            original(key, value)
        self.board.write = slow
        self.assertEqual(self.guard.restore(), "RESTORATION_UNVERIFIED")
        self.assertLessEqual(self.clock.now, 6)

    def test_initial_journal_failure_no_write(self):
        def fail(_):
            raise OSError("storage full")
        with self.assertRaises(OSError):
            m.RouteGuard(self.board, fail)
        self.assertEqual(self.board.writes, [])

    def test_journal_failure_after_routing_does_not_skip_restore(self):
        self.guard.begin(0)
        def fail(_):
            raise OSError("storage full")
        self.guard.journal = fail
        self.assertEqual(self.guard.restore(), "RESTORATION_UNVERIFIED")
        self.assertEqual(self.board.values, m.BASELINE)

    def test_ctrl_c_during_partial_route(self):
        original = self.board.write
        def interrupt(key, value):
            original(key, value)
            if value == [3, 0]:
                raise KeyboardInterrupt()
        self.board.write = interrupt
        with self.assertRaises(KeyboardInterrupt):
            self.guard.begin(0)
        self.assertEqual(self.board.values, m.BASELINE)

    def test_disconnect_restores(self):
        incoming = io.StringIO('{"action":"begin","pair":0}\n')
        outgoing = io.StringIO()
        m.serve_guard(self.board, self.records.append, incoming, outgoing)
        self.assertEqual(self.board.values, m.BASELINE)
        self.assertEqual(json.loads(outgoing.getvalue().splitlines()[-1])["status"], "ROUTES_RESTORED")

    def test_invalid_message_restores(self):
        incoming = io.StringIO('{"action":"begin","pair":0}\n{"action":"write","name":"gain"}\n')
        with self.assertRaises(m.Stop):
            m.serve_guard(self.board, self.records.append, incoming, io.StringIO())
        self.assertEqual(self.board.values, m.BASELINE)

    def test_normal_ipc_sequence(self):
        messages = [{"action": "begin", "pair": 0}, {"action": "restore"},
                    {"action": "begin", "pair": 1}, {"action": "restore"}]
        incoming = io.StringIO("\n".join(map(json.dumps, messages)) + "\n")
        m.serve_guard(self.board, self.records.append, incoming, io.StringIO())
        self.assertEqual(self.board.values, m.BASELINE)
        self.assertEqual(len(self.board.writes), 8)

    def test_real_pipe_eof_restores_fake_device(self):
        source = '''import sys
from tools import reachy_mic_health as m
board = m.FakeBoard()
m.serve_guard(board, lambda value: None, sys.stdin, sys.stdout)
assert board.values == m.BASELINE
'''
        process = subprocess.Popen([sys.executable, "-B", "-c", source],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True)
        try:
            output, errors = process.communicate('{"action":"begin","pair":0}\n', timeout=5)
            self.assertEqual(process.returncode, 0, errors)
            statuses = [json.loads(line)["status"] for line in output.splitlines()]
            self.assertEqual(statuses, ["READY", "ROUTED", "ROUTES_RESTORED"])
        finally:
            if process.poll() is None:
                process.kill()  # Only this synthetic child, never a robot process.
                process.wait(timeout=2)


class TestCapture(unittest.TestCase):
    """Exercise the phase loop with fake PCM/pipes/clock, not sound devices."""

    def run_capture(self, events, operator="\n", guard_dead=False, robot_error=False):
        clock = Clock()
        pcm_pipe = Mock()
        pcm_pipe.fileno.return_value = 10
        error_pipe = Mock()
        error_pipe.fileno.return_value = 11
        process = SimpleNamespace(stdout=pcm_pipe, stderr=error_pipe)
        guard = SimpleNamespace(process=SimpleNamespace(poll=lambda: 1 if guard_dead else None))
        pending = iter(events)
        current = {}
        selector = Mock()
        def select(timeout):
            kind, value = next(pending, ("pcm", b""))
            if kind == "interrupt":
                raise KeyboardInterrupt()
            if kind == "time":
                clock.now += value
                return []
            clock.now += 0.01
            current["payload"] = value
            return [(SimpleNamespace(data=kind), None)]
        selector.select.side_effect = select
        result = {}
        with ExitStack() as stack:
            stack.enter_context(patch.object(m, "RATE", 16))
            stack.enter_context(patch.object(m.subprocess, "Popen", return_value=process))
            stack.enter_context(patch.object(m.selectors, "DefaultSelector", return_value=selector))
            stack.enter_context(patch.object(m.os, "set_blocking"))
            stack.enter_context(patch.object(m.os, "read", side_effect=lambda *_: current["payload"]))
            stack.enter_context(patch.object(m.time, "monotonic", side_effect=clock))
            stack.enter_context(patch.object(m.sys, "stdin", io.StringIO(operator)))
            stack.enter_context(patch.object(m, "print"))
            stack.enter_context(patch.object(m, "check_robot", side_effect=m.Stop("robot_drift") if robot_error else None))
            stop = stack.enter_context(patch.object(m, "stop_own_capture"))
            try:
                m.capture_pair(0, result, guard)
            finally:
                self.result = result
                stop.assert_called_once_with(process)
                selector.close.assert_called_once()
                pcm_pipe.close.assert_called_once()
                error_pipe.close.assert_called_once()
        return result

    @staticmethod
    def pcm(seconds):
        return struct.pack("<hhhh", -100, -50, 100, 50) * (16 * seconds // 2)

    def test_complete_sequence_counts_and_phases(self):
        result = self.run_capture([("pcm", self.pcm(5)), ("operator", None),
                                   ("pcm", self.pcm(12))])
        self.assertTrue(result["complete"])
        self.assertEqual(len(result["blocks"]), 13)
        self.assertEqual(result["summaries"]["quiet"]["frames"], 48)
        self.assertEqual(result["summaries"]["playback"]["frames"], 160)

    def test_fragmented_pcm_reassembled(self):
        quiet = self.pcm(5)
        playback = self.pcm(12)
        events = [("pcm", quiet[:3]), ("pcm", quiet[3:]), ("operator", None),
                  ("pcm", playback[:1]), ("pcm", playback[1:])]
        self.assertTrue(self.run_capture(events)["complete"])

    def test_driver_error_stops_without_raw_error_dump(self):
        with self.assertRaisesRegex(m.Stop, "capture_driver_error"):
            self.run_capture([("error", b"synthetic xrun")])

    def test_eof_preserves_partial_numeric_summary(self):
        with self.assertRaisesRegex(m.Stop, "capture_ended_early"):
            self.run_capture([("pcm", self.pcm(3)), ("pcm", b"")])
        self.assertEqual(self.result["partial_phase"]["frames"], 16)
        self.assertFalse(self.result["complete"])

    def test_stall_stops(self):
        with self.assertRaisesRegex(m.Stop, "capture_deadline_or_stall"):
            self.run_capture([("time", 2.1)])

    def test_operator_timeout_while_pcm_keeps_arriving(self):
        events = [("pcm", self.pcm(5))]
        events += [("time", 1), ("pcm", self.pcm(1))] * 11
        with self.assertRaisesRegex(m.Stop, "operator_deadline"):
            self.run_capture(events)

    def test_terminal_eof_aborts(self):
        with self.assertRaisesRegex(m.Stop, "terminal_closed"):
            self.run_capture([("pcm", self.pcm(5)), ("operator", None)], operator="")

    def test_ctrl_c_cleans_capture(self):
        with self.assertRaises(KeyboardInterrupt):
            self.run_capture([("interrupt", None)])

    def test_guard_death_aborts(self):
        with self.assertRaisesRegex(m.Stop, "guard_exited_during_capture"):
            self.run_capture([], guard_dead=True)

    def test_robot_state_drift_aborts(self):
        with self.assertRaisesRegex(m.Stop, "robot_drift"):
            self.run_capture([("time", 1.5), ("pcm", self.pcm(1)), ("time", 1)],
                             robot_error=True)


class TestBoundaries(unittest.TestCase):
    def test_reviewed_alsa_config_and_drift(self):
        config = '''pcm.!default { type hw card 0 }
ctl.!default { type hw card 0 }
pcm.reachymini_audio_sink { type dmix ipc_key 4241
slave { pcm "hw:0,0" channels 2 period_size 1024 buffer_size 4096 rate 16000 }
bindings { 0 0 1 1 } }
pcm.reachymini_audio_src { type dsnoop ipc_key 4242
slave { pcm "hw:0,0" channels 2 rate 16000 period_size 1024 buffer_size 4096 } }'''
        m.validate_asoundrc(config)
        m.validate_asoundrc("# comment\n" + config.replace(" ", "  "))
        for changed in (config.replace("4096", "1024"), config.replace("dsnoop", "file"),
                        config.replace("hw:0,0", "hw:1,0"), config + '\n</tmp/extra.conf>'):
            with self.assertRaises(m.Stop):
                m.validate_asoundrc(changed)

    def test_existing_reader_core_dump_boundary(self):
        command = b"python\0-u\0-m\0reachy_mini.daemon.app.main\0--wireless-version\0--no-wake-up-on-start\0"
        with patch.object(m.subprocess, "run", return_value=SimpleNamespace(stdout=b"940")), \
             patch.object(m.Path, "read_bytes", return_value=command), \
             patch.object(m.Path, "stat", return_value=SimpleNamespace(st_uid=1000)), \
             patch.object(m.os, "getuid", return_value=1000, create=True):
            with patch.object(m.Path, "read_text", return_value="Max core file size        0      unlimited       bytes\n"):
                self.assertEqual(m.capture_owner(), 940)
            with patch.object(m.Path, "read_text", return_value="Max core file size unlimited unlimited bytes\n"):
                with self.assertRaisesRegex(m.Stop, "core_retention"):
                    m.capture_owner()

    def test_non_allowlisted_usb_name(self):
        for key in ("SAVE_CONFIGURATION", "AUDIO_MGR_MIC_GAIN", "REBOOT"):
            with self.assertRaises(m.Stop):
                m.USBBoard.command(key)

    def test_write_allowlist_and_timeout(self):
        calls = []
        class Device:
            def ctrl_transfer(self, *args):
                calls.append(args)
                return 2
        board = object.__new__(m.USBBoard)
        board.dev = Device()
        board.write(m.ROUTES[0], [3, 0])
        self.assertEqual(calls, [(0x40, 0, 15, 35, b"\x03\x00", 500)])
        for invalid in ([3, 1], [3, 4], [1, 0], [8, 1], [True, 0]):
            with self.assertRaises(m.Stop):
                board.write(m.ROUTES[0], invalid)

    def test_read_status_and_length(self):
        class Device:
            def __init__(self, value):
                self.value = value
            def ctrl_transfer(self, *args):
                return self.value
        board = object.__new__(m.USBBoard)
        for invalid in (b"", b"\x00\x08", b"\x40\x08\x00", b"\x00\x08\x00\x00"):
            board.dev = Device(invalid)
            with self.assertRaises(m.Stop):
                board.read(m.ROUTES[0])
        board.dev = Device(b"\x00\x08\x00")
        self.assertEqual(board.read(m.ROUTES[0]), [8, 0])

    def test_no_unapproved_http_route(self):
        for route in ("/api/volume/current", "/api/daemon/start", "/api/audio/config/apply"):
            with self.assertRaises(m.Stop):
                m.get_json(route)

    def test_motor_state_and_app_gate(self):
        valid = {"state": "running", "error": None, "version": "1.9.0",
                 "simulation_enabled": False, "mockup_sim_enabled": False,
                 "no_media": False, "media_released": False,
                 "backend_status": {"motor_control_mode": "disabled", "error": None, "ready": False}}
        with patch.object(m, "get_json", side_effect=[valid, None]):
            m.check_robot()
        for key, value in (("state", "stopped"), ("error", "fault"), ("version", "1.11.0"),
                           ("simulation_enabled", True), ("mockup_sim_enabled", True),
                           ("no_media", True), ("media_released", True)):
            with patch.object(m, "get_json", return_value={**valid, key: value}):
                with self.assertRaises(m.Stop):
                    m.check_robot()
        with patch.object(m, "get_json", side_effect=[valid, {"name": "app"}]):
            with self.assertRaises(m.Stop):
                m.check_robot()

    def test_capture_command_exact_safe_source(self):
        command = m.capture_command()
        self.assertIn("--device=reachymini_audio_src", command)
        self.assertIn("--fatal-errors", command)
        self.assertIn("--file-type=raw", command)
        self.assertIn("--duration=38", command)
        self.assertNotIn("aplay", command)
        self.assertFalse(any(value.endswith(".wav") for value in command))

    def test_noninteractive_execute_refused_before_snapshot(self):
        with patch.object(m.sys.stdin, "isatty", return_value=False), patch.object(m, "snapshot") as snapshot:
            with self.assertRaises(m.Stop):
                m.execute()
            snapshot.assert_not_called()

    def test_default_cli_is_synthetic(self):
        outcome = subprocess.run([sys.executable, "-B", str(Path(m.__file__))], capture_output=True, check=True, text=True)
        result = json.loads(outcome.stdout)
        self.assertFalse(result["hardware_opened"])
        self.assertEqual(result["mode"], "SYNTHETIC_ONLY")

    def test_json_manifest_no_nan(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "numeric.json"
            m.save_json(target, {"frames": 3})
            self.assertEqual(json.loads(target.read_text()), {"frames": 3})


if __name__ == "__main__":
    unittest.main()
