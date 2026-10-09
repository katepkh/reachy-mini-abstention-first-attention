"""Prepared session tests. All SSH, capture and USB operations use fakes."""
import ast
from contextlib import redirect_stdout
import copy
import inspect
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from scripts import run_reachy_mic_input as launch
from scripts import prepare_reachy_mic_input as preparation
from tools import reachy_mic_health_input_candidate as candidate
from tools import reachy_mic_health_input_run as m
from tests.test_mic_input_preparation import report as preparation_fixture


class PreparedSessionTests(unittest.TestCase):
    def test_all_function_class_bodies_identical_to_tested_candidate(self):
        def definitions(module):
            return {n.name: ast.dump(n) for n in ast.parse(inspect.getsource(module)).body
                    if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        self.assertEqual(definitions(m), definitions(candidate))
        def assignments(module):
            return {ast.dump(n.targets[0]): ast.dump(n.value)
                    for n in ast.parse(inspect.getsource(module)).body if isinstance(n, ast.Assign)}
        old, new = assignments(candidate), assignments(m)
        self.assertEqual(set(old), set(new))
        self.assertEqual({k for k in old if old[k] != new[k]},
                         {ast.dump(ast.Name(id=k, ctx=ast.Store())) for k in
                          ('EXECUTION_RELEASED', 'SESSION', 'CANDIDATE_SHA256', 'AUTHORIZATION_PATH')})
        self.assertEqual(launch.sha(Path(candidate.__file__).read_bytes()), launch.INPUT_CANDIDATE_SHA)
        self.assertEqual(launch.sha(Path(m.__file__).read_bytes()), launch.EXPECTED)
        self.assertFalse(candidate.EXECUTION_RELEASED)
        self.assertTrue(m.EXECUTION_REQUIRES_PRIVATE_AUTHORIZATION)
        self.assertEqual(m.SESSION, 'missing-pair-v3-04')
        self.assertEqual(m.CANDIDATE_SHA256, launch.INPUT_CANDIDATE_SHA)
        self.assertEqual((m.PAIR_LIMIT, m.RESTORE_LIMIT, m.RATE), (40., 5., 16000))
        self.assertEqual(m.PAIRS, ({m.ROUTES[0]: [3, 2], m.ROUTES[1]: [3, 3]},))

    def test_reviewed_preparation_bound_and_failed_checks_rejected(self):
        valid = {'status': 'PREPARATION_OK_REVIEW_REQUIRED', 'ssh_exit_code': 0,
                 'recording_authorized': False, 'candidate_sha256': launch.INPUT_CANDIDATE_SHA,
                 'launcher_sha256': launch.PREPARATION_LAUNCHER_SHA, 'remote': preparation_fixture()}
        variants = [valid]
        for key, value in (('status', 'FAILED'), ('ssh_exit_code', False),
                           ('recording_authorized', True), ('candidate_sha256', 'changed')):
            variants.append({**valid, key: value})
        for section in ('terminal', 'preflight'):
            changed = copy.deepcopy(valid)
            changed['remote'][section]['checks'][0]['ok'] = False
            variants.append(changed)
        with tempfile.TemporaryDirectory() as tmp, patch.object(preparation, 'sources'):
            path = Path(tmp) / 'report.json'
            for i, record in enumerate(variants):
                path.write_text(json.dumps(record))
                with patch.object(launch, 'PREPARATION_REPORT', path), \
                        patch.object(launch, 'PREPARATION_REPORT_SHA', launch.sha(path.read_bytes())):
                    if i == 0:
                        self.assertEqual(launch.reviewed_input_preparation(), valid)
                    else:
                        with self.assertRaises(RuntimeError):
                            launch.reviewed_input_preparation()
            with patch.object(launch, 'PREPARATION_REPORT', path):
                with self.assertRaisesRegex(RuntimeError, 'preparation_changed'):
                    launch.reviewed_input_preparation()

    def test_contract_binds_new_input_build_prerequisite_and_ninth_receipt(self):
        contract = launch.approval_contract(launch.LOCAL)
        self.assertEqual(contract['input_candidate_sha256'], launch.INPUT_CANDIDATE_SHA)
        self.assertEqual(contract['reviewed_input_preparation_sha256'], launch.PREPARATION_REPORT_SHA)
        self.assertEqual(contract['input_session_closeout_sha256'], launch.INPUT_RECEIPT_SHA)
        self.assertEqual(contract['session_authorization']['microphone_indices'], [2, 3])
        self.assertEqual(contract['session_authorization']['pair_limit'], 1)
        self.assertEqual(contract['session_authorization']['candidate_sha256'], launch.INPUT_CANDIDATE_SHA)
        self.assertEqual(contract['remote_scope'], m.SESSION_DIRECTORY.as_posix())

    def test_walkthrough_is_offline_and_does_not_approve(self):
        with patch.object(launch, 'run_once') as run, patch.object(launch, 'collect') as collect, \
                patch('builtins.input', side_effect=AssertionError('no input')), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(launch.main(['--walkthrough']), 0)
        run.assert_not_called()
        collect.assert_not_called()
        self.assertIn('NO second pair', out.getvalue())


def module_from(filename, replacements):
    path = Path(__file__).with_name(filename)
    source = path.read_text(encoding='utf-8')
    for old, new in replacements:
        if old not in source:
            raise AssertionError('test reuse marker missing: ' + old)
        source = source.replace(old, new)
    module = types.ModuleType('input_session_' + path.stem)
    module.__file__ = str(path)
    exec(compile(source, str(path), 'exec'), module.__dict__)
    return module


def load_tests(loader, suite, pattern):
    # Exercise the actual prepared build through every independent-reader and
    # capture-loop case, including delayed processing, real socket I/O and EOF.
    module = module_from('test_mic_input_candidate.py', [
        ('reachy_mic_health_input_candidate as m', 'reachy_mic_health_input_run as m')])
    for name in ('CaptureTests', 'ReaderTests'):
        suite.addTests(loader.loadTestsFromTestCase(getattr(module, name)))
    suite.addTest(module.BoundaryTests('test_reader_failure_reaches_parent_restoration_and_aborted_report'))

    module = module_from('test_mic_v3_session.py', [
        ('run_reachy_mic_v3 as launch', 'run_reachy_mic_input as launch'),
        ('reachy_mic_health_v3_run as m', 'reachy_mic_health_input_run as m'),
        ('/run-two-pair-v3-01', '/run-missing-pair-v3-04')])
    exclusions = {
        'SessionHelperTests': {'test_all_measurement_and_recovery_definitions_unchanged_from_candidate',
                               'test_parent_flow_only_adds_authorization_and_fixed_one_shot_scope'},
        'SessionLauncherTests': {'test_generated_deployment_blocks_on_old_scope_drift_and_never_starts_capture',
                                 'test_local_prior_missing_pending_changed_and_unexpected_records_refuse'}}
    for cls, omitted in exclusions.items():
        for name in loader.getTestCaseNames(getattr(module, cls)):
            if name not in omitted:
                suite.addTest(getattr(module, cls)(name))

    module = module_from('test_mic_missing_pair_fixed.py', [
        ('reachy_mic_health_missing_pair_fixed as m', 'reachy_mic_health_input_run as m')])
    for name in loader.getTestCaseNames(module.AdapterRepairTests):
        if name not in {'test_candidate_execute_and_guard_stop_before_hardware_and_files',
                        'test_only_adapter_cardinality_and_release_gate_changed'}:
            suite.addTest(module.AdapterRepairTests(name))

    # Reuse known single-pair parent and scoped predecessor tests, expanded to
    # include the latest input-aborted session. No real private files are changed.
    module = module_from('test_mic_missing_pair_speaker.py', [
        ('run_reachy_mic_missing_pair_speaker as launch', 'run_reachy_mic_input as launch'),
        ('reachy_mic_health_missing_pair_speaker as m', 'reachy_mic_health_input_run as m'),
        ('range(8)', 'range(9)'),
        ('"REPAIRED_SCOPE", "STIMULUS_SCOPE")', '"REPAIRED_SCOPE", "STIMULUS_SCOPE", "INPUT_SCOPE")'),
        ('("missing-pair-v3-02", "STIMULUS"))',
         '("missing-pair-v3-02", "STIMULUS"), ("missing-pair-v3-03", "INPUT"))'),
        ('self.assertEqual(len(launch.prior_evidence()), 8)', 'self.assertEqual(len(launch.prior_evidence()), 9)'),
        ('stack.enter_context(patch.object(launch, "ROOT", root))',
         'stack.enter_context(patch.object(launch, "ROOT", root))\n            stack.enter_context(patch.object(launch, "reviewed_input_preparation"))'),
        ('patch.object(launch, "STIMULUS_RECEIPT_SHA", "changed")',
         'patch.object(launch, "INPUT_RECEIPT_SHA", "changed")')])
    for name in ('test_eight_remote_predecessors_before_install',
                 'test_eight_local_predecessors_and_latest_receipt_required',
                 'test_only_missing_routes_and_one_use', 'test_single_pair_parent_success',
                 'test_single_pair_abort_restores_without_repeat', 'test_wrong_live_confirmation_never_routes',
                 'test_missing_private_approval_stops_before_connection_or_run_record'):
        suite.addTest(module.MissingPairTests(name))
    return suite


if __name__ == '__main__':
    unittest.main()
