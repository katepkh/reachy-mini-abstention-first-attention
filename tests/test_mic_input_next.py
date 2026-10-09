"""Offline successor tests. No real SSH, sensors, routing or private writes."""
import ast
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from scripts import run_reachy_mic_input_next as launch
from tools import reachy_mic_health_input_next as helper
from tools import reachy_mic_health_input_run as previous


class NextInputTests(unittest.TestCase):
    def test_helper_changes_only_fixed_session_and_capability_path(self):
        def body(module):
            return ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        old, new = body(previous), body(helper)
        defs = lambda tree: {n.name: ast.dump(n) for n in tree.body
                            if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        self.assertEqual(defs(old), defs(new))
        assigns = lambda tree: {ast.dump(n.targets[0]): ast.dump(n.value)
                               for n in tree.body if isinstance(n, ast.Assign)}
        before, after = assigns(old), assigns(new)
        self.assertEqual({k for k in before if before[k] != after[k]},
                         {ast.dump(ast.Name(id=k, ctx=ast.Store()))
                          for k in ("SESSION", "AUTHORIZATION_PATH")})
        self.assertEqual(launch.sha(Path(previous.__file__).read_bytes()),
                         "19e54ed1fae751b96565268688faa6048d11a8fac6e1336228efffd22c44d908")

    def fixture(self, stack, root):
        directory = root / "data/private/mic_closeout" / launch.NO_CAPTURE_SESSION
        directory.mkdir(parents=True)
        record = directory / "record.json"
        record.write_text('{"fixture": true}', encoding="utf-8")
        receipt = {
            "schema": "reachy-mic-no-execution-final-closeout-v1",
            "session": launch.NO_CAPTURE_SESSION, "status": "CHECKED_NO_UNEXPECTED_FILES",
            "local_scope": str(directory.resolve()), "remote_scope": launch.NO_CAPTURE_SCOPE,
            "diagnostic_capture_started": False, "routing_changed": False,
            "baseline_parameters_mixer_asoundrc_match": True, "after_machine_checks_passed": 17,
            "remote_after_check": {"state": "ABSENT"},
            "local_after_check": {"inventory_except_this_receipt": launch.local_inventory(directory)},
            "source_evidence_sha256": {"record.json": launch.sha(record.read_bytes())}}
        path = directory / "closeout-final-v1.json"
        path.write_text(json.dumps(receipt), encoding="utf-8")
        stack.enter_context(patch.object(launch, "ROOT", root))
        stack.enter_context(patch.object(launch, "NO_CAPTURE_RECEIPT_SHA", launch.sha(path.read_bytes())))
        return directory, path, receipt

    def test_no_execution_predecessor_is_verified_without_rewriting(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            directory, path, receipt = self.fixture(stack, Path(tmp))
            before = {p.name: p.read_bytes() for p in directory.iterdir()}
            self.assertEqual(launch.no_capture_predecessor(), receipt)
            self.assertEqual(before, {p.name: p.read_bytes() for p in directory.iterdir()})

    def test_bad_receipt_record_or_unexpected_entry_blocks(self):
        for kind in ("missing_receipt", "changed_receipt", "changed_record", "unexpected"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
                directory, path, _ = self.fixture(stack, Path(tmp))
                if kind == "missing_receipt":
                    path.unlink()
                elif kind == "changed_receipt":
                    path.write_text("{}")
                elif kind == "changed_record":
                    (directory / "record.json").write_text("{}")
                else:
                    (directory / "unknown.wav").write_bytes(b"synthetic-not-audio")
                with self.assertRaises((RuntimeError, FileNotFoundError)):
                    launch.no_capture_predecessor()

    def test_semantically_unresolved_receipt_blocks(self):
        changes = {"status": "PENDING", "session": "other", "remote_scope": "other",
                   "diagnostic_capture_started": True, "routing_changed": True,
                   "baseline_parameters_mixer_asoundrc_match": False,
                   "after_machine_checks_passed": 16, "remote_after_check": {"state": "UNKNOWN"}}
        for key, value in changes.items():
            with self.subTest(key=key), tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
                _, path, receipt = self.fixture(stack, Path(tmp))
                receipt[key] = value
                path.write_text(json.dumps(receipt), encoding="utf-8")
                stack.enter_context(patch.object(launch, "NO_CAPTURE_RECEIPT_SHA", launch.sha(path.read_bytes())))
                with self.assertRaisesRegex(RuntimeError, "not_verified"):
                    launch.no_capture_predecessor()

    def test_missing_or_changed_record_hash_blocks_even_with_matching_metadata_fixture(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            directory, path, receipt = self.fixture(stack, Path(tmp))
            receipt["source_evidence_sha256"]["record.json"] = "wrong"
            path.write_text(json.dumps(receipt), encoding="utf-8")
            stack.enter_context(patch.object(launch, "NO_CAPTURE_RECEIPT_SHA", launch.sha(path.read_bytes())))
            with self.assertRaisesRegex(RuntimeError, "record_changed"):
                launch.no_capture_predecessor()

    def test_prior_evidence_cannot_skip_no_capture_review(self):
        with patch.object(launch, "reviewed_input_preparation"), \
                patch.object(launch, "no_capture_predecessor", side_effect=RuntimeError("blocked")) as review:
            with self.assertRaisesRegex(RuntimeError, "blocked"):
                launch.prior_evidence()
            review.assert_called_once()

    def test_existing_paths_links_and_access_errors_are_not_absence(self):
        paths = (launch.NO_CAPTURE_SCOPE, launch.REMOTE_SCOPE, launch.REMOTE, launch.REMOTE_AUTH)
        with patch.object(launch.os, "lstat", side_effect=FileNotFoundError):
            launch.require_absent_paths(paths)
        for existing in paths:
            def stat(path):
                if path == existing:
                    return types.SimpleNamespace(st_mode=0)
                raise FileNotFoundError
            with self.subTest(path=existing), patch.object(launch.os, "lstat", side_effect=stat):
                with self.assertRaises(RuntimeError):
                    launch.require_absent_paths(paths)
        with patch.object(launch.os, "lstat", side_effect=PermissionError):
            with self.assertRaises(PermissionError):
                launch.require_absent_paths(paths)

    def test_generated_deploy_blocks_before_packet_or_install_on_prior_path(self):
        source = launch.remote_source("deploy")
        compile(source, "<offline-deploy>", "exec")
        with patch.object(launch.os, "lstat", return_value=types.SimpleNamespace(st_mode=0)):
            with self.assertRaisesRegex(RuntimeError, "unexpected_prior_or_new_session_path"):
                exec(source, {"__name__": "offline_generated_test"})

    def test_approval_binds_no_capture_predecessor(self):
        contract = launch.approval_contract(launch.LOCAL)
        self.assertEqual(contract["no_capture_predecessor_closeout_sha256"],
                         launch.NO_CAPTURE_RECEIPT_SHA)
        self.assertEqual(contract["no_capture_predecessor_scope"], launch.NO_CAPTURE_SCOPE)
        self.assertEqual(contract["session_authorization"]["session"], helper.SESSION)


def load_tests(loader, suite, pattern):
    # Reuse the complete reviewed session suite on the new helper/launcher,
    # including independent reader, one-pair capture, guard and nine old scopes.
    path = Path(__file__).with_name("test_mic_input_session.py")
    source = path.read_text(encoding="utf-8")
    source = source.replace("run_reachy_mic_input as launch", "run_reachy_mic_input_next as launch")
    source = source.replace("reachy_mic_health_input_run as m", "reachy_mic_health_input_next as m")
    source = source.replace("missing-pair-v3-04", "missing-pair-v3-05")
    marker = 'stack.enter_context(patch.object(launch, "reviewed_input_preparation"))'
    source = source.replace(marker, marker + '\\n            stack.enter_context(patch.object(launch, "no_capture_predecessor"))')
    inherited = types.ModuleType("next_input_inherited_session_tests")
    inherited.__file__ = str(path)
    exec(compile(source, str(path), "exec"), inherited.__dict__)
    suite.addTests(loader.loadTestsFromModule(inherited))
    return suite


if __name__ == "__main__":
    unittest.main()
