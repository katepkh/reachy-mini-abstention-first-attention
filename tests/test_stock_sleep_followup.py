"""Offline regression coverage for the new fixed sleep session; no robot access."""

import ast
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts import request_reachy_stock_sleep_followup as m
from tests import test_stock_sleep_current as shared


class FollowupSleepTests(shared.CurrentSleepTests):
    def setUp(self):
        self.binding = patch.object(shared, "m", m)
        self.binding.start()
        self.addCleanup(self.binding.stop)

    def test_prior_launcher_and_all_function_bodies_preserved(self):
        original = m.ROOT / "scripts/request_reachy_stock_sleep_current.py"
        payload = m.read_regular(original)
        self.assertEqual(m.sha(payload),
                         "4165098523e9fa9e400ac27c96d106a33c733f13c07910014c1e15ccdf719f19")
        def bodies(data):
            return [ast.dump(item, include_attributes=False)
                    for item in ast.parse(data).body
                    if isinstance(item, (ast.FunctionDef, ast.ClassDef))]
        self.assertEqual(bodies(payload), bodies(m.read_regular(Path(m.__file__))))
        self.assertEqual(m.SESSION, "standard-sleep-20261008-02")
        self.assertNotEqual(m.JOURNAL.name, "standard-sleep-20261008-01.jsonl")
        self.assertNotEqual(m.AUTHORIZATION.name,
                            "standard-sleep-20261008-01-authorization.json")


if __name__ == "__main__":
    unittest.main()
