"""Offline replacement tests: fake SSH, temporary control records, no sensors."""
from contextlib import ExitStack, redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from scripts import run_reachy_mic_input_login_replacement as r


class ReplacementTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        tmp = self.stack.enter_context(tempfile.TemporaryDirectory())
        self.local = Path(tmp) / 'run'
        self.reviews = Path(tmp) / 'reviews'
        self.local.mkdir()
        self.reviews.mkdir()
        for name, value in {'LOCAL': self.local, 'REVIEW_ROOT': self.reviews,
                            'REVIEW': self.reviews / 'review.json',
                            'AUTHORIZATION': self.reviews / 'authorization.json',
                            'STARTED': self.local / (r.ATTEMPT + '-started.json')}.items():
            self.stack.enter_context(patch.object(r, name, value))
        self.ns = r.load_reviewed()
        # Directory guards must inspect the generated fixture, not depend on
        # an operator's ignored data/private tree being present in a checkout.
        fixture_root = Path(tmp)
        (fixture_root / 'data/private').mkdir(parents=True)
        self.stack.enter_context(patch.object(r, 'ROOT', fixture_root))
        self.ns['LOCAL'] = self.local
        self.ns['prior_evidence'] = Mock(return_value={})
        records = {'authorization.json': self.ns['approval_contract'](self.local),
                   'closeout.json': {'schema': 'reachy-mic-local-closeout-v1', 'session': r.SESSION,
                                     'helper_sha256': r.HELPER_SHA, 'remote_scope': self.ns['REMOTE_SCOPE'],
                                     'status': 'PENDING'},
                   'deployment.json': {'ssh_exit_code': 255, 'report': None},
                   'interrupted.json': {'stage': 'deployment_preflight'}}
        for name, record in records.items():
            (self.local / name).write_text(json.dumps(record))
        self.originals = {name: (self.local / name).read_bytes() for name in records}
        self.review = {'status': 'PRELOGIN_FAILURE_REVIEWED_REMOTE_CHECK_REQUIRED',
                       'session': r.SESSION, 'local_scope': str(self.local),
                       'remote_scope': self.ns['REMOTE_SCOPE'],
                       'file_sha256': {name: r.sha(data) for name, data in self.originals.items()},
                       'local_after_inventory': self.ns['local_inventory'](self.local)}
        r.REVIEW.write_text(json.dumps(self.review))
        self.stack.enter_context(patch.object(r, 'REVIEW_SHA', r.sha(r.REVIEW.read_bytes())))
        r.AUTHORIZATION.write_text(json.dumps(r.required_authorization(self.ns)))
        self.stack.enter_context(patch.object(r.sys.stdin, 'isatty', return_value=True))

    def configure(self):
        r.review_and_authorization(self.ns)
        r.configure_replacement(self.ns, self.review)

    def assert_preserved(self):
        for name, payload in self.originals.items():
            self.assertEqual((self.local / name).read_bytes(), payload)

    def preflight(self, absent=True):
        result = {'schema': self.ns['SCHEMA'], 'mode': 'READ_ONLY', 'helper_sha256': r.HELPER_SHA,
                  'execution_authorized': False, 'consumer_isolation_verified': False,
                  'machine_checks_passed': True, 'checks': [{'name': str(i), 'ok': True} for i in range(17)]}
        if absent:
            result['login_replacement_precheck'] = r.absence_receipt(self.ns)
        return result

    def bundle(self):
        return {'schema': 'reachy-mic-session-export-v1', 'session': r.SESSION,
                'helper_sha256': r.HELPER_SHA, 'root': self.ns['REMOTE_ROOT'],
                'run': None, 'audio_exported': False, 'deletion_performed': False}

    def test_default_no_loading_connection_or_start(self):
        with patch.object(r, 'load_reviewed') as load, redirect_stdout(io.StringIO()):
            self.assertEqual(r.main([]), 0)
        load.assert_not_called()
        self.assertFalse(r.STARTED.exists())

    def test_source_drift_stops_before_import(self):
        bad = self.reviews / 'bad.py'
        bad.write_text('raise AssertionError("must not execute")')
        with patch.object(r, 'BASE', bad), self.assertRaisesRegex(RuntimeError, 'launcher_changed'):
            r.load_reviewed()

    def test_missing_or_changed_private_authorization_rejected(self):
        expected = r.required_authorization(self.ns)
        for key, value in (('approved', False), ('run_limit', True), ('helper_sha256', 'changed'),
                           ('wrapper_sha256', 'changed'), ('review_sha256', 'changed'),
                           ('local_scope', 'other'), ('remote_absence_required_before_deployment', False)):
            r.AUTHORIZATION.write_text(json.dumps({**expected, key: value}))
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, 'approval_required'):
                r.review_and_authorization(self.ns)
        with patch.object(r, 'AUTHORIZATION', self.reviews / 'absent'), self.assertRaises(FileNotFoundError):
            r.review_and_authorization(self.ns)
        self.assertFalse(r.STARTED.exists())

    def test_review_and_all_original_files_pinned(self):
        with patch.object(r, 'REVIEW_SHA', 'changed'), self.assertRaisesRegex(RuntimeError, 'review_changed'):
            r.review_and_authorization(self.ns)
        for name, payload in self.originals.items():
            (self.local / name).write_bytes(payload + b' ')
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, 'failure_record_changed'):
                r.review_and_authorization(self.ns)
            (self.local / name).write_bytes(payload)

    def test_start_inventory_and_exclusive_latch_preserve_originals(self):
        self.configure()
        self.ns['begin_local'](self.local)
        first = r.STARTED.read_bytes()
        self.assertEqual(json.loads(first)['local_before'], self.review['local_after_inventory'])
        with self.assertRaisesRegex(RuntimeError, 'spent_or_local_inventory'):
            self.ns['begin_local'](self.local)
        self.assertEqual(r.STARTED.read_bytes(), first)
        self.assert_preserved()

    def test_unexpected_entry_blocks_before_start_without_reading_it(self):
        self.configure()
        (self.local / 'unexpected.wav').write_bytes(b'not-media-test-fixture')
        with self.assertRaisesRegex(RuntimeError, 'local_inventory'):
            self.ns['begin_local'](self.local)
        self.assertFalse(r.STARTED.exists())

    def test_generated_source_absence_guard_before_any_deployment(self):
        old_run, old_collect = self.ns['remote_source']('run'), self.ns['remote_source']('collect')
        self.configure()
        self.assertEqual(self.ns['remote_source']('run'), old_run)
        self.assertEqual(self.ns['remote_source']('collect'), old_collect)
        source = self.ns['remote_source']('deploy')
        definitions, tail = source.rsplit('\nrequire_absent_paths(', 1)
        remote = {}
        exec(definitions, remote)
        paths = [self.reviews / ('remote-' + str(i)) for i in range(3)]
        remote.update(dict(zip(('REMOTE_SCOPE', 'REMOTE', 'REMOTE_AUTH'), map(str, paths))))
        deploy = Mock()
        remote['remote_deploy'] = deploy
        exec('require_absent_paths(' + tail, remote)
        deploy.assert_called_once()
        for i, p in enumerate(paths):
            p.write_text('unexpected')
            deploy.reset_mock()
            with self.subTest(path=i), self.assertRaisesRegex(RuntimeError, 'unexpected_remote_session'):
                exec('require_absent_paths(' + tail, remote)
            deploy.assert_not_called()
            p.unlink()  # Temporary fixture only.
        with patch.object(r.os, 'lstat', side_effect=PermissionError), self.assertRaises(PermissionError):
            r.require_absent_paths(paths)
        command = self.ns['ssh_command']('deploy')
        self.assertLess(len(subprocess.list2cmdline(command)), 30000)

    def test_absence_receipt_required_for_interactive_execution(self):
        self.configure()
        for invalid in (self.preflight(False), {**self.preflight(), 'login_replacement_precheck': {}}):
            with self.assertRaisesRegex(RuntimeError, 'absence_not_verified'):
                self.ns['validate_preflight'](json.dumps(invalid).encode())
        self.assertTrue(self.ns['validate_preflight'](json.dumps(self.preflight()).encode())['machine_checks_passed'])

    def test_write_mapping_never_overwrites_old_records(self):
        self.configure()
        for name in ('deployment.json', 'interrupted.json', 'execution-exit.json'):
            self.ns['write_new'](self.local / name, {'replacement': True})
            self.assertTrue((self.local / (r.ATTEMPT + '-' + name)).exists())
            with self.assertRaises(FileExistsError):
                self.ns['write_new'](self.local / name, {})
        with self.assertRaisesRegex(RuntimeError, 'output_name'):
            self.ns['write_new'](self.local / 'closeout.json', {})
        self.assert_preserved()

    def test_success_deploy_run_collect_once_and_no_second_attempt(self):
        self.configure()
        runner = Mock(side_effect=[types.SimpleNamespace(returncode=0, stdout=json.dumps(self.preflight()).encode()),
                                  types.SimpleNamespace(returncode=0),
                                  types.SimpleNamespace(returncode=0, stdout=json.dumps(self.bundle()).encode())])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.ns['run_once'](self.local, runner), 0)
            with self.assertRaisesRegex(RuntimeError, 'spent_or_local_inventory'):
                self.ns['run_once'](self.local, runner)
        self.assertEqual(runner.call_count, 3)
        self.assertEqual(len(list(self.local.glob('review-*.json'))), 1)
        self.assertTrue((self.local / (r.ATTEMPT + '-execution-exit.json')).exists())
        self.assert_preserved()

    def test_deployment_rejection_stops_no_run_and_remains_spent(self):
        self.configure()
        runner = Mock(return_value=types.SimpleNamespace(returncode=255, stdout=b''))
        with redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError, 'deployment_failed'):
            self.ns['run_once'](self.local, runner)
        runner.assert_called_once()
        self.assertTrue(r.STARTED.exists())
        self.assertTrue((self.local / (r.ATTEMPT + '-interrupted.json')).exists())
        self.assert_preserved()

    def test_execution_timeout_keeps_pending_and_does_not_retry(self):
        self.configure()
        runner = Mock(side_effect=[types.SimpleNamespace(returncode=0, stdout=json.dumps(self.preflight()).encode()),
                                  subprocess.TimeoutExpired('fake', 300)])
        with redirect_stdout(io.StringIO()), self.assertRaises(subprocess.TimeoutExpired):
            self.ns['run_once'](self.local, runner)
        self.assertEqual(runner.call_count, 2)
        self.assertTrue(r.STARTED.exists())
        self.assert_preserved()


if __name__ == '__main__':
    unittest.main()
