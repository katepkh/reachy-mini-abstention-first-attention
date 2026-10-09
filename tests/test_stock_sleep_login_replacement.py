"""Offline login-replacement checks; fake SSH and temporary numeric records."""

import ast
from contextlib import ExitStack
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import request_reachy_stock_sleep_login_replacement as m
from tests import test_stock_sleep_current as shared


class LoginReplacementSleepTests(shared.CurrentSleepTests):
    def setUp(self):
        self.binding = patch.object(shared, "m", m)
        self.binding.start()
        self.addCleanup(self.binding.stop)

    def fixture(self, stack, root):
        result = super().fixture(stack, root)
        for name, payload in (("FAILED_JOURNAL", b"synthetic pending journal"),
                              ("FAILURE_REVIEW", b"synthetic reviewed denial"),
                              ("FAILED_LAUNCHER", b"synthetic prior launcher")):
            path = root / (name + ".fixture")
            path.write_bytes(payload)
            stack.enter_context(patch.object(m, name, path))
            stack.enter_context(patch.object(m, name + "_SHA", m.sha(payload)))
        return result

    def test_changed_or_missing_evidence_blocks_before_connection(self):
        for name in ("FAILED_JOURNAL", "FAILURE_REVIEW", "FAILED_LAUNCHER"):
            for missing in (False, True):
                with self.subTest(name=name, missing=missing), tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
                    journal, _, _ = self.fixture(stack, Path(tmp))
                    path = getattr(m, name)
                    if missing:
                        path.unlink()
                    else:
                        path.write_bytes(b"changed evidence")
                    run = stack.enter_context(patch.object(subprocess, "run"))
                    with self.assertRaises((RuntimeError, FileNotFoundError)):
                        m.main(["--sleep-once"])
                    run.assert_not_called()
                    self.assertFalse(journal.exists())

    def test_preserved_prior_launcher_and_unchanged_transport_main(self):
        prior = m.read_regular(m.FAILED_LAUNCHER)
        self.assertEqual(m.sha(prior), m.FAILED_LAUNCHER_SHA)
        def bodies(data):
            return {item.name: ast.dump(item, include_attributes=False)
                    for item in ast.parse(data).body
                    if isinstance(item, ast.FunctionDef)}
        before = bodies(prior)
        after = bodies(m.read_regular(Path(m.__file__)))
        self.assertEqual(set(before), set(after))
        for name in before:
            if name != "check_authorization":
                self.assertEqual(before[name], after[name], name)
        self.assertEqual(m.SESSION, "standard-sleep-20261008-02-login-replacement-01")
        self.assertNotEqual(m.JOURNAL, m.FAILED_JOURNAL)


if __name__ == "__main__":
    unittest.main()
