"""Offline-only review/reconciliation/preflight boundary tests."""

from contextlib import ExitStack, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from scripts import prepare_reachy_mic_v3 as m
from tools import reachy_mic_health as old


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.folder = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.run = self.folder / "run-fixture"
        self.run.mkdir(mode=0o700)
        baseline = {"fixture": True}
        closed = {"schema": old.CLOSEOUT_SCHEMA, "run_id": self.run.name, "scope": str(self.run),
                  "helper_sha256": "fixture", "status": "PENDING", "before": [],
                  "restoration_verified": False, "capture_exit_verified": True}
        records = {"baseline.json": baseline, "closeout.json": closed,
                   "result.json": {"reason": "guard_EOF", "status": "RESTORATION_UNVERIFIED", "pair_results": []},
                   "approval.json": {"fixture": True}}
        for name, data in records.items():
            old.save_json(self.run / name, data)
        self.rows = old.inventory(self.run)
        self.expected = {"records": records, "inventory": self.rows, "directory": str(self.run)}
        self.helper = {"snapshot": Mock(return_value=baseline), "inventory": old.inventory,
                       "finish_closeout": Mock(wraps=old.finish_closeout)}
        self.stack.enter_context(patch.object(m, "validate_scope", return_value=(baseline, self.rows)))
        self.stack.enter_context(patch.object(m, "inspect_lock", return_value={"owners": []}))
        self.stack.enter_context(patch.object(m, "diagnostic_processes", return_value=[]))
        # Test files are temporary, owned by this test; use the portable reader.
        self.stack.enter_context(patch.object(m, "read_regular", m.original.read_regular))

    def test_only_closeout_changes_original_failure_stays_failed(self):
        before = {path.name: path.read_bytes() for path in self.run.iterdir()}
        result = m.reconcile_record(self.helper, self.run, self.expected)
        self.assertEqual(result["updated_closeout"]["status"], "CHECKED_NO_UNEXPECTED_FILES")
        self.assertEqual(result["original_closeout"]["status"], "PENDING")
        self.assertEqual(result["deleted_files"], [])
        for name in before:
            if name != "closeout.json":
                self.assertEqual((self.run / name).read_bytes(), before[name])
        self.assertFalse((self.run / "guard.json").exists())
        self.assertEqual(self.helper["snapshot"].call_count, 2)
        self.helper["finish_closeout"].assert_called_once()

    def test_process_lock_or_baseline_mismatch_prevents_update(self):
        for target, value in (("diagnostic_processes", [123]), ("inspect_lock", {"owners": [123]})):
            with patch.object(m, target, return_value=value), self.assertRaises(m.ProbeError):
                m.reconcile_record(self.helper, self.run, self.expected)
        self.helper["snapshot"].return_value = {"changed": True}
        with self.assertRaises(m.ProbeError):
            m.reconcile_record(self.helper, self.run, self.expected)
        self.helper["finish_closeout"].assert_not_called()

    def test_second_snapshot_change_prevents_update(self):
        self.helper["snapshot"].side_effect = [self.expected["records"]["baseline.json"], {}]
        with self.assertRaisesRegex(m.ProbeError, "second_baseline"):
            m.reconcile_record(self.helper, self.run, self.expected)
        self.helper["finish_closeout"].assert_not_called()

    def test_changed_record_or_unexpected_file_prevents_update(self):
        (self.run / "result.json").write_text('{"changed":true}')
        with self.assertRaisesRegex(m.ProbeError, "failed_run_changed"):
            m.reconcile_record(self.helper, self.run, self.expected)
        self.helper["finish_closeout"].assert_not_called()

    def test_file_arriving_during_review_prevents_update(self):
        self.helper["inventory"] = Mock(return_value=self.rows + [{"name": "unexpected.wav"}])
        with self.assertRaises(m.ProbeError):
            m.reconcile_record(self.helper, self.run, self.expected)
        self.helper["finish_closeout"].assert_not_called()


class ProcessChecks(unittest.TestCase):
    def test_only_process_ids_exported_and_no_process_signals(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pid = str(os.getpid() + 1000)
            (root / pid).mkdir()
            (root / pid / "cmdline").write_bytes(b"python\0/home/pollen/reachy_mic_health_v2.py\0--guard\0private\0")
            self.assertEqual(m.diagnostic_processes(root), [int(pid)])
            (root / pid / "cmdline").write_bytes(b"python\0-m\0reachy_mini.daemon.app.main\0")
            self.assertEqual(m.diagnostic_processes(root), [])
            (root / pid / "cmdline").write_bytes(b"arecord\0--quiet\0")
            self.assertEqual(m.diagnostic_processes(root), [int(pid)])

    def test_disappeared_process_is_allowed_but_oversized_command_stops(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "123456").mkdir()
            self.assertEqual(m.diagnostic_processes(root), [])
            (root / "123456" / "cmdline").write_bytes(b"x" * 65537)
            with self.assertRaises(m.ProbeError):
                m.diagnostic_processes(root)


class RemoteBundleTests(unittest.TestCase):
    def test_generated_bundle_runs_only_review_install_preflight_with_fakes(self):
        # Intercept only the final remote entry, then exercise that exact entry
        # with fake resources. The preserved probe's main must remain inert.
        real_exec = exec
        source = m.remote_source()
        import ast
        tree = ast.parse(source)
        inner = tree.body[0].value.args[0].args[0].value
        inner = inner.removesuffix("raise SystemExit(remote_main())\n")
        ns = {"__name__": "fixture"}
        real_exec(compile(inner, "<fixture>", "exec"), ns)
        self.assertEqual(ns["PREPARATION_SCHEMA"], m.SCHEMA)
        payload = (m.ROOT / "tools/reachy_mic_health_v3.py").read_bytes()
        import base64
        request = json.dumps({"candidate": base64.b64encode(payload).decode(),
                              "run": {"directory": "/fixture"}}).encode()
        ns["sys"] = types.SimpleNamespace(stdin=types.SimpleNamespace(buffer=io.BytesIO(request)))
        ns["load_helper"] = Mock(return_value={})
        ns["reconcile_record"] = Mock(return_value={"updated_closeout": {"status": "CHECKED_NO_UNEXPECTED_FILES"}})
        ns["install_exact"] = Mock(return_value=True)
        ns["read_regular"] = Mock(return_value=payload)
        ns["Path"] = Mock(return_value=Mock(exists=lambda: False, is_symlink=lambda: False))
        preflight = Mock(return_value={"mode": "READ_ONLY", "execution_authorized": False})
        def candidate_exec(code, candidate_scope):
            candidate_scope.update(EXECUTION_RELEASED=False, preflight_report=preflight)
        ns["exec"] = candidate_exec
        stream = io.StringIO()
        with redirect_stdout(stream):
            self.assertEqual(ns["remote_main"](), 0)
        events = [json.loads(row) for row in stream.getvalue().splitlines()]
        self.assertEqual([row["event"] for row in events],
                         ["stage_started", "closeout_reconciled", "candidate_installed", "candidate_preflight", "finished"])
        ns["install_exact"].assert_called_once_with(m.DESTINATION, payload, m.CANDIDATE_HASH)
        preflight.assert_called_once_with()
        self.assertTrue(all(row["execution_authorized"] is False for row in events))

    def test_bundle_fails_before_install_when_reconciliation_is_unavailable(self):
        import ast
        import base64
        inner = ast.parse(m.remote_source()).body[0].value.args[0].args[0].value
        ns = {"__name__": "fixture"}
        exec(compile(inner.removesuffix("raise SystemExit(remote_main())\n"), "<fixture>", "exec"), ns)
        payload = (m.ROOT / "tools/reachy_mic_health_v3.py").read_bytes()
        request = json.dumps({"candidate": base64.b64encode(payload).decode(), "run": {"directory": "/fixture"}}).encode()
        ns["sys"] = types.SimpleNamespace(stdin=types.SimpleNamespace(buffer=io.BytesIO(request)))
        ns["load_helper"] = Mock(return_value={})
        ns["Path"] = Mock(return_value=Mock(exists=lambda: False, is_symlink=lambda: False))
        ns["reconcile_record"] = Mock(side_effect=ns["ProbeError"]("state_changed"))
        ns["install_exact"] = Mock()
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(ns["remote_main"](), 2)
        ns["install_exact"].assert_not_called()
        self.assertEqual(json.loads(output.getvalue().splitlines()[-1])["reason"], "state_changed")


class LocalReviewTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        baseline = {"parameters": {key: [8, 0] for key in m.retry.candidate.ROUTES}}
        self.rows = [{"name": name, "kind": "file"} for name in ("baseline.json", "approval.json", "result.json", "closeout.json")]
        self.failed = {"run": {"directory": "/fixture", "inventory": self.rows, "record_errors": [],
                              "stable_inventory": True,
                              "records": {"baseline.json": baseline, "closeout.json": {"unexpected": []},
                                          "result.json": {"status": "RESTORATION_UNVERIFIED"}}}}
        values = {"baseline_before": {**baseline, "matches_failed_run_baseline": True},
                  "baseline_after": {**baseline, "matches_failed_run_baseline": True},
                  "startup_platform_checks": [{"ok": True}], "robot_state_after": [{"ok": True}],
                  "failed_run_records": {"inventory": self.rows},
                  "run_inventory_after": {"inventory": self.rows, "unchanged": True}}
        for key in m.retry.candidate.ROUTES:
            values["usb_read_" + key] = {"values": [8, 0], "status_bytes": [64, 0]}
        events = [{"event": "stage_finished", "stage": key, "value": value, "status": "observed",
                   "candidate_sha256": m.CANDIDATE_HASH} for key, value in values.items()]
        events.append({"event": "finished", "unavailable_stages": [], "candidate_sha256": m.CANDIDATE_HASH})
        self.report = {"schema": m.retry.SCHEMA, "ssh_exit_code": 0, "invalid_lines": 0,
                       "transport_error": None, "execution_authorized": False, "utc": "fixture",
                       "source_sha256": hashlib.sha256(b"fixture").hexdigest(), "events": events}
        self.stack.enter_context(patch.object(m.retry, "reviewed_failure", return_value=("/fixture", {"failure_review_sha256": m.FAILURE_HASH})))
        self.stack.enter_context(patch.object(m.retry, "remote_source", return_value=b"fixture"))
        self.stack.enter_context(patch.object(m, "pinned_json", side_effect=lambda path, digest: self.failed if digest == m.FAILURE_HASH else self.report))
        local_rows = [{"name": name, "kind": "file"} for name in ("authorization.json", "closeout.json", "execution-exit.json", m.FAILURE_NAME)]
        self.inventory = self.stack.enter_context(patch.object(m.original, "local_inventory", return_value=local_rows))

    def test_complete_review_is_still_pending_remote_reconciliation(self):
        review = m.local_review()
        self.assertEqual(review["review_status"], "REVIEW_COMPLETE")
        self.assertEqual(review["status"], "PENDING")
        self.assertEqual(review["remote_ordinary_file_review"]["status"], "CHECKED_NO_UNEXPECTED_FILES")
        self.assertFalse(review["execution_authorized"])
        self.assertFalse(review["robot_return_final_check_complete"])
        self.assertEqual(review["deleted_files"], [])

    def test_unexpected_local_file_blocks_without_opening_it(self):
        self.inventory.return_value += [{"name": "unexpected.wav", "kind": "file"}]
        with self.assertRaisesRegex(RuntimeError, "local_unexpected"):
            m.local_review()

    def test_changed_baseline_inventory_or_unavailable_stage_blocks(self):
        for key, replacement in (("baseline_after", {}), ("run_inventory_after", {"inventory": [], "unchanged": False}),
                                 ("robot_state_after", [{"ok": False}])):
            row = next(item for item in self.report["events"] if item.get("stage") == key)
            value = row["value"]
            row["value"] = replacement
            with self.assertRaises(RuntimeError):
                m.local_review()
            row["value"] = value

    def test_pinned_evidence_changed_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "record.json"
            target.write_text("{}")
            # Exercise the real function, not the fixture's pinned_json mock.
            from importlib import util
            spec = util.spec_from_file_location("fixture_preparation", m.__file__)
            fresh = util.module_from_spec(spec)
            spec.loader.exec_module(fresh)
            with self.assertRaisesRegex(RuntimeError, "evidence_changed"):
                fresh.pinned_json(target, "wrong")


class LauncherTests(unittest.TestCase):
    def test_default_no_action_and_modes_exclusive(self):
        with patch.object(m, "reconcile_preflight") as remote, patch.object(m, "local_review") as review, redirect_stdout(io.StringIO()):
            self.assertEqual(m.main([]), 0)
            remote.assert_not_called()
            review.assert_not_called()
            with patch.object(m.sys, "stderr", io.StringIO()), self.assertRaises(SystemExit):
                m.main(["--review-local", "--reconcile-preflight"])

    def test_interactive_console_required(self):
        with patch.object(m.sys, "stdin", types.SimpleNamespace(isatty=lambda: False)), self.assertRaises(RuntimeError):
            m.reconcile_preflight()

    def test_partial_disconnect_saved_and_second_attempt_blocked(self):
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            root = Path(folder)
            receipt = root / "review.json"
            review = {"remote_scope": "/fixture", "reviewed_utc": "2026-10-02T22:00:00+00:00"}
            receipt.write_text(json.dumps(review))
            stack.enter_context(patch.object(m, "REVIEW", receipt))
            stack.enter_context(patch.object(m, "OUTPUT", root / "output"))
            stack.enter_context(patch.object(m, "local_review", return_value=review))
            stack.enter_context(patch.object(m, "pinned_json", return_value={"run": {}}))
            stack.enter_context(patch.object(m.sys, "stdin", types.SimpleNamespace(isatty=lambda: True)))
            event = {"schema": m.SCHEMA, "execution_authorized": False, "event": "closeout_reconciled"}
            failure = subprocess.TimeoutExpired("fixture", 120, output=json.dumps(event).encode())
            run = stack.enter_context(patch.object(m.subprocess, "run", side_effect=failure))
            stack.enter_context(redirect_stdout(io.StringIO()))
            self.assertEqual(m.reconcile_preflight(), 2)
            saved = json.loads((m.OUTPUT / "report.json").read_text())
            self.assertEqual(saved["events"], [event])
            self.assertEqual(saved["local_closeout_status"], "PENDING_REPORT_REVIEW")
            self.assertFalse(saved["execution_authorized"])
            with self.assertRaises(FileExistsError):
                m.reconcile_preflight()
            run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
