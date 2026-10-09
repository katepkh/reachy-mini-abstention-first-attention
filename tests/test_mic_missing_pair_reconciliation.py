"""Offline scoped reconciliation contracts; all robot/SSH operations are mocked."""
from contextlib import ExitStack, redirect_stdout
import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts import reconcile_reachy_mic_missing_pair as r


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        source = r.remote_source()
        self.assertTrue(source.endswith("raise SystemExit(remote_main())\n"))
        self.ns = {"__name__": "offline_fixture"}
        exec(compile(source.rsplit("raise SystemExit(remote_main())", 1)[0], "<remote-fixture>", "exec"), self.ns)
        self.directory = Path(r.REMOTE)
        self.rows = [{"name": name, "kind": "file", "bytes": 50, "mtime_ns": 1791010174441029784}
                     for name in sorted(r.RECORD_NAMES)]
        self.values = {name: {"fixture": name} for name in r.RECORD_NAMES}
        self.values["closeout.json"] = {"status": "PENDING", "before": [], "unexpected": []}
        self.expected = {"directory": r.REMOTE, "records": copy.deepcopy(self.values),
                         "inventory": copy.deepcopy(self.rows)}
        self.helper = {"private_directory": Mock(), "inventory": Mock(side_effect=lambda _: copy.deepcopy(self.rows)),
                       "snapshot": Mock(side_effect=lambda _: copy.deepcopy(self.values["baseline.json"]))}
        def finish(directory, record, **flags):
            self.assertEqual(directory, self.directory)
            self.assertEqual(flags, {"restoration_verified": True, "capture_exit_verified": True})
            self.values["closeout.json"] = {**record, **flags, "status": "CHECKED_NO_UNEXPECTED_FILES"}
            next(row for row in self.rows if row["name"] == "closeout.json")["bytes"] += 10
            return copy.deepcopy(self.values["closeout.json"])
        self.helper["finish_closeout"] = Mock(side_effect=finish)
        self.ns["read_regular"] = Mock(side_effect=lambda path: json.dumps(self.values[path.name]).encode())
        self.ns["inspect_lock"] = Mock(return_value={"owners": []})
        self.ns["diagnostic_processes"] = Mock(return_value=[])

    def run_reconcile(self):
        return self.ns["reconcile_record"](self.helper, self.directory, self.expected)

    def test_updates_only_closeout_after_two_equal_snapshots(self):
        value = self.run_reconcile()
        self.assertEqual(self.helper["snapshot"].call_args_list[0].args, (self.directory,))
        self.assertEqual(self.helper["snapshot"].call_count, 2)
        self.helper["finish_closeout"].assert_called_once()
        self.assertEqual(value["original_closeout"]["status"], "PENDING")
        self.assertEqual(value["updated_closeout"]["status"], "CHECKED_NO_UNEXPECTED_FILES")
        for name in r.RECORD_NAMES - {"closeout.json"}:
            self.assertEqual(self.values[name], self.expected["records"][name])
        self.assertEqual(value["deleted_files"], [])

    def test_drift_missing_files_processes_or_unknown_state_prevent_write(self):
        for failure in ("path", "inventory", "record", "baseline", "lock", "process", "second_baseline"):
            with self.subTest(failure=failure):
                self.setUp()
                if failure == "path": self.directory = self.directory.parent
                if failure == "inventory": self.rows.append({"name": "unexpected.wav"})
                if failure == "record": self.values["result.json"] = {"changed": True}
                if failure == "baseline": self.helper["snapshot"].return_value = {"different": True}; self.helper["snapshot"].side_effect = None
                if failure == "lock": self.ns["inspect_lock"].return_value = {"owners": [123]}
                if failure == "process": self.ns["diagnostic_processes"].return_value = [123]
                if failure == "second_baseline": self.helper["snapshot"].side_effect = [self.values["baseline.json"], {}]
                with self.assertRaises(self.ns["ProbeError"]): self.run_reconcile()
                self.helper["finish_closeout"].assert_not_called()

    def test_wrong_raw_report_stops_before_loading_helper(self):
        self.ns["sys"] = Mock(stdin=Mock(buffer=io.BytesIO(b"{}")))
        self.ns["load_helper"] = Mock()
        with redirect_stdout(io.StringIO()): self.assertEqual(self.ns["remote_main"](), 2)
        self.ns["load_helper"].assert_not_called()

    def test_remote_program_only_metadata_checks_and_one_closeout_update(self):
        raw = json.dumps({"run": self.expected}).encode()
        self.ns["REPORT_SHA"] = hashlib.sha256(raw).hexdigest()
        self.ns["sys"] = Mock(stdin=Mock(buffer=io.BytesIO(raw)))
        self.helper["preflight_report"] = Mock(return_value={"execution_authorized": False})
        self.ns["load_helper"] = Mock(return_value=self.helper)
        out = io.StringIO()
        with redirect_stdout(out): self.assertEqual(self.ns["remote_main"](), 0)
        events = [json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual([v["event"] for v in events], ["checking", "closeout_reconciled", "after_preflight", "finished"])
        self.assertTrue(all(v["execution_authorized"] is False for v in events))
        self.assertFalse(events[-1]["audio_capture"])
        self.assertFalse(events[-1]["helper_installed"])

    def test_helper_identity_mismatch_prevents_execution(self):
        self.ns["read_regular"] = Mock(return_value=b"raise Exception('must not execute')")
        with self.assertRaisesRegex(self.ns["ProbeError"], "helper_hash_changed"):
            self.ns["load_helper"]()

    def test_process_check_covers_actual_deployed_session_names(self):
        for number in range(1, 6):
            self.assertIn("reachy_mic_health_two_pair_v3_" + str(number).zfill(2) + ".py", self.ns["DIAGNOSTIC_NAMES"])
        self.assertIn("reachy_mic_health_missing_pair_v3_01.py", self.ns["DIAGNOSTIC_NAMES"])
        self.assertIn("arecord", self.ns["DIAGNOSTIC_NAMES"])

    def test_operator_launcher_timeout_saved_and_no_retry(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            output = Path(tmp) / "attempt"
            stack.enter_context(patch.object(r, "OUTPUT", output))
            stack.enter_context(patch.object(r.sys.stdin, "isatty", return_value=True))
            stack.enter_context(patch.object(r, "local_review", return_value={"reviewed_utc": "now", "status": "PENDING"}))
            stack.enter_context(patch.object(r.records, "read_regular", return_value=b'{"reviewed_utc":"then","status":"PENDING"}'))
            stack.enter_context(patch.object(r, "remote_source", return_value="source_fixture"))
            stack.enter_context(patch.object(r, "pinned", return_value=b"report_fixture"))
            ssh = stack.enter_context(patch.object(r.subprocess, "run", side_effect=subprocess.TimeoutExpired("ssh", 120)))
            stack.enter_context(redirect_stdout(io.StringIO()))
            self.assertEqual(r.reconcile_once(), 2)
            result = json.loads((output / "report.json").read_text())
            self.assertEqual(result["transport_error"], "ssh_timeout")
            self.assertEqual(result["local_closeout_status"], "PENDING_REPORT_REVIEW")
            self.assertFalse(result["automatic_retry"])
            with self.assertRaises(FileExistsError): r.reconcile_once()
            ssh.assert_called_once()


if __name__ == "__main__":
    unittest.main()
