"""Offline keyboard-only tests: synthetic bytes and fake SSH; no robot/audio."""
import ast
import base64
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import shlex
import socket
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts import check_reachy_exact_reader as launch
from tools import reachy_exact_reader_probe as probe
from tools import reachy_mic_health_input_next as original


class CounterTests(unittest.TestCase):
    def test_counts_only_and_identical_bytes_returned(self):
        payload = b'private-fixture\r\n'
        reader = Mock(return_value=payload)
        count = probe.ReadCounts(0, read=reader, clock=lambda: 2.)
        self.assertIs(count(12, 64), payload)
        reader.assert_called_once_with(12, 64)
        report = count.snapshot()
        self.assertEqual((report['cr'], report['lf'], report['other']), (1, 1, 15))
        self.assertEqual(report['first_read_ms'], 2000)
        self.assertNotIn('private-fixture', json.dumps(report))

    def test_eof_count_not_enter(self):
        count = probe.ReadCounts(0, read=lambda *_: b'', clock=lambda: 1.)
        self.assertEqual(count(1, 64), b'')
        self.assertEqual(count.snapshot()['eof_reads'], 1)


class ExactReaderTests(unittest.TestCase):
    def exercise(self, payload, *, eof=False):
        incoming, outgoing = socket.socketpair()
        try:
            if payload:
                outgoing.sendall(payload)
            if eof:
                outgoing.shutdown(socket.SHUT_WR)
            return probe.observe_reader(original.TerminalInputReader, incoming, timeout=.3, settle=.04,
                                        read=lambda fd, n: incoming.recv(n))
        finally:
            incoming.close()
            outgoing.close()

    def test_lf_and_crlf_recognized_by_unchanged_reader(self):
        for payload, cr in ((b'\n', 0), (b'\r\n', 1)):
            with self.subTest(payload=payload):
                result = self.exercise(payload)
                self.assertEqual(result['status'], 'received')
                self.assertEqual(result['counts']['cr'], cr)
                self.assertEqual(result['counts']['lf'], 1)
                self.assertTrue(result['reader_exit_verified'])
                self.assertFalse(result['physical_keypress_time_known'])

    def test_bare_cr_reproduces_no_event_without_silently_fixing_reader(self):
        result = self.exercise(b'\r')
        self.assertEqual(result['status'], 'bytes_without_enter_event')
        self.assertEqual((result['counts']['bytes'], result['counts']['cr'], result['counts']['lf']), (1, 1, 0))
        self.assertEqual(result['events'], [])
        self.assertTrue(result['reader_exit_verified'])

    def test_no_bytes_distinguished_from_unrecognized_bytes(self):
        result = self.exercise(b'')
        self.assertEqual(result['status'], 'no_input_observed')
        self.assertEqual(result['counts']['reads'], 0)

    def test_text_never_appears_in_numeric_result(self):
        result = self.exercise(b'private-fixture\n')
        self.assertEqual(result['status'], 'unexpected_text')
        self.assertNotIn('private-fixture', json.dumps(result))

    def test_duplicate_and_eof_distinct(self):
        self.assertEqual(self.exercise(b'\n\n')['status'], 'multiple_events')
        self.assertEqual(self.exercise(b'', eof=True)['status'], 'terminal_closed')

    def test_reader_fault_or_unverified_exit_cannot_pass(self):
        reader = Mock()
        reader.drain.side_effect = RuntimeError('private-detail')
        for close_fault in (None, RuntimeError('private-detail')):
            reader.close.side_effect = close_fault
            result = probe.observe_reader(Mock(return_value=reader), object(), timeout=.001)
            self.assertNotEqual(result['status'], 'received')
            self.assertNotIn('private-detail', json.dumps(result))

    def test_constructor_failure_and_interrupt_are_reported_without_content(self):
        for error, status in ((OSError('private-detail'), 'probe_error'), (KeyboardInterrupt(), 'interrupted')):
            result = probe.observe_reader(Mock(side_effect=error), object())
            self.assertEqual(result['status'], status)
            self.assertNotIn('private-detail', json.dumps(result))


class ProbeTests(unittest.TestCase):
    def run_case(self, first_status='received', second_status='received', *, tty=True, changed=False):
        output = []
        first = Mock(return_value={'status': first_status})
        second = Mock(return_value={'status': second_status})
        before = {'tty': tty, 'ICANON': tty, 'ICRNL': True}
        after = {**before, 'ICRNL': False} if changed else before
        code = probe.run_probe(original.TerminalInputReader, stream=object(), first=first, second=second,
                               terminal=Mock(side_effect=[before, after]), output=lambda s, **_: output.append(s))
        result = json.loads(next(s.split(' ',1)[1] for s in output if s.startswith('EXACT_READER_RESULT ')))
        return code, result, first, second, output

    def test_two_steps_and_no_capture_authority(self):
        code, result, first, second, output = self.run_case()
        self.assertEqual(code, 0)
        first.assert_called_once()
        second.assert_called_once()
        self.assertEqual([s['reader'] for s in result['steps']], ['input','exact_diagnostic_class'])
        for field in ('audio_opened','settings_changed','remote_files_written','recording_authorized',
                      'keypress_contents_retained','capture_load_tested','physical_keypress_time_known'):
            self.assertIs(result[field], False)
        self.assertEqual(result['wait_limit_per_prompt_seconds'], 120)

    def test_first_failure_does_not_start_second(self):
        code, result, _, second, _ = self.run_case(first_status='no_input_observed')
        self.assertEqual(code, 20)
        second.assert_not_called()

    def test_second_failure_is_not_overridden_by_first_success(self):
        self.assertEqual(self.run_case(second_status='bytes_without_enter_event')[0], 24)

    def test_unsupported_terminal_never_reads(self):
        code, _, first, second, _ = self.run_case(tty=False)
        self.assertEqual(code, 22)
        first.assert_not_called()
        second.assert_not_called()

    def test_terminal_drift_does_not_pass_or_attempt_restore(self):
        self.assertEqual(self.run_case(changed=True)[0], 29)

    def test_initial_input_handoff_and_timeout(self):
        selector = Mock()
        read = Mock(return_value='')
        result = probe.initial_enter(object(), selector_factory=lambda: selector, read_line=read)
        self.assertEqual(result['status'], 'received')
        read.assert_called_once()
        selector.select.assert_called_once_with(timeout=120)
        selector.close.assert_called_once()
        selector.select.return_value=[]
        read.reset_mock()
        self.assertEqual(probe.initial_enter(object(), selector_factory=lambda: selector, read_line=read)['status'], 'no_input_observed')
        read.assert_not_called()


class LauncherTests(unittest.TestCase):
    def test_exact_class_ast_and_source_pins(self):
        payload, _ = launch.source_bundle()
        actual=ast.parse(payload)
        source=ast.parse(launch.HELPER.read_bytes())
        cls=lambda tree,name: next(ast.dump(n) for n in tree.body if isinstance(n,ast.ClassDef) and n.name==name)
        for name in ('Stop','TerminalInputReader'):
            self.assertEqual(cls(actual,name),cls(source,name))
        self.assertEqual(hashlib.sha256(launch.HELPER.read_bytes()).hexdigest(),launch.HELPER_SHA)
        self.assertEqual(hashlib.sha256(launch.PROBE.read_bytes()).hexdigest(),launch.PROBE_SHA)
        self.assertFalse(any(isinstance(n,ast.FunctionDef) and n.name=='capture_pair' for n in actual.body))

    def test_transport_inherits_exact_ssh_console_options(self):
        from scripts import run_reachy_mic_input_next as mic
        command=launch.ssh_command()
        self.assertEqual(command[:-1],mic.ssh_command('run')[:-1])
        self.assertLess(len(subprocess.list2cmdline(command)),30000)
        remote=shlex.split(command[-1])
        self.assertEqual(remote[:4],[mic.PYTHON,'-I','-B','-c'])
        encoded=next(n.value for n in ast.walk(ast.parse(remote[4])) if isinstance(n,ast.Constant) and isinstance(n.value,str) and len(n.value)>100)
        self.assertEqual(base64.b64decode(encoded),launch.source_bundle()[0])

    def test_remote_payload_has_no_capture_api_file_write_or_process_calls(self):
        tree=ast.parse(launch.source_bundle()[0])
        imports={a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names}
        self.assertEqual(imports,{'os','queue','selectors','threading','time','json','sys','termios'})
        calls={ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n,ast.Call)}
        self.assertFalse(calls & {'open','exec','eval','os.open','os.system','os.execv','termios.tcsetattr','termios.tcflush'})

    def test_remote_payload_executes_only_probe_with_exact_class(self):
        payload=launch.source_bundle()[0].decode()
        definitions, tail=payload.rsplit('\nraise SystemExit(',1)
        ns={}
        exec(definitions,ns)
        runner=Mock(return_value=24)
        ns['run_probe']=runner
        with self.assertRaises(SystemExit) as result:
            exec('raise SystemExit('+tail,ns)
        self.assertEqual(result.exception.code,24)
        runner.assert_called_once_with(ns['TerminalInputReader'])

    def test_once_only_console_handles_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(launch.sys.stdin,'isatty',return_value=True), redirect_stdout(io.StringIO()):
            runner=Mock(return_value=SimpleNamespace(returncode=24))
            self.assertEqual(launch.check_once(Path(tmp),runner),24)
            runner.assert_called_once_with(launch.ssh_command(),timeout=300)
            directory=Path(tmp)/launch.RUN_ID
            self.assertEqual({p.name for p in directory.iterdir()},{'started.json','report.json'})
            saved=json.loads((directory/'report.json').read_text())
            self.assertEqual(saved['status'],'BYTES_WITHOUT_ENTER_EVENT')
            self.assertFalse(saved['key_contents_or_passwords_captured'])
            original=(directory/'report.json').read_bytes()
            with self.assertRaises(FileExistsError):
                launch.check_once(Path(tmp),runner)
            self.assertEqual(runner.call_count,1)
            self.assertEqual((directory/'report.json').read_bytes(),original)

    def test_failure_reports_without_retry_or_sensitive_error(self):
        for error in (OSError('private-detail'),subprocess.TimeoutExpired('ssh',300),KeyboardInterrupt()):
            with tempfile.TemporaryDirectory() as tmp, patch.object(launch.sys.stdin,'isatty',return_value=True), redirect_stdout(io.StringIO()):
                runner=Mock(side_effect=error)
                self.assertNotEqual(launch.check_once(Path(tmp),runner),0)
                runner.assert_called_once()
                record=(Path(tmp)/launch.RUN_ID/'report.json').read_text()
                self.assertNotIn('private-detail',record)
                self.assertEqual(json.loads(record)['status'],'INTERRUPTED_OR_CONNECTION_UNCERTAIN')

    def test_no_connection_or_directory_on_source_drift_or_noninteractive(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)/'absent'
            runner=Mock()
            with patch.object(launch.sys.stdin,'isatty',return_value=False), self.assertRaises(RuntimeError):
                launch.check_once(directory,runner)
            with patch.object(launch.sys.stdin,'isatty',return_value=True), patch.object(launch,'PROBE_SHA','changed'), self.assertRaises(RuntimeError):
                launch.check_once(directory,runner)
            self.assertFalse(directory.exists())
            runner.assert_not_called()

    def test_default_and_inspect_are_offline(self):
        with patch.object(launch,'check_once',side_effect=AssertionError('no SSH')), redirect_stdout(io.StringIO()):
            self.assertEqual(launch.main([]),0)
            self.assertEqual(launch.main(['--inspect']),0)


if __name__=='__main__':
    unittest.main()
