import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from reachy_stage4.external_records import (
    OWNER_OBSERVABILITY_ACTIONS,
    OWNER_SCHEMA,
    REVIEW_SCHEMA,
    require_independent_protocol_approval,
    require_owner_observability_scope,
)


class ExternalRecordTests(unittest.TestCase):
    def write_record(self, root, schema, decision, **extra):
        artifact = root / "reply.txt"
        artifact.write_text("actual external reply", encoding="utf-8")
        record = {
            "schema": schema,
            "decision": decision,
            "recorded_by": "External person",
            "recorded_at_utc": "2026-09-02T12:00:00Z",
            "source_artifact": {
                "path": "reply.txt",
                "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
            },
            **extra,
        }
        path = root / "record.json"
        path.write_text(json.dumps(record), encoding="utf-8")
        return path

    def test_owner_record_requires_all_observability_actions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self.write_record(
                root,
                OWNER_SCHEMA,
                "SCOPE_CONFIRMED",
                approved_actions=sorted(OWNER_OBSERVABILITY_ACTIONS),
                return_condition_definition="Practical equivalence per reviewed protocol",
            )
            record = require_owner_observability_scope(path)
            self.assertEqual(record["decision"], "SCOPE_CONFIRMED")

    def test_owner_record_cannot_omit_original_daemon_restoration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self.write_record(
                root,
                OWNER_SCHEMA,
                "SCOPE_CONFIRMED",
                approved_actions=[
                    "powered_baseline_inventory_and_receive_only_capture"
                ],
                return_condition_definition="Practical equivalence",
            )
            with self.assertRaisesRegex(ValueError, "restore_original_daemon"):
                require_owner_observability_scope(path)

    def test_owner_record_requires_return_condition_definition(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self.write_record(
                root,
                OWNER_SCHEMA,
                "SCOPE_CONFIRMED",
                approved_actions=sorted(OWNER_OBSERVABILITY_ACTIONS),
            )
            with self.assertRaisesRegex(ValueError, "return condition"):
                require_owner_observability_scope(path)

    def test_tampered_external_reply_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self.write_record(
                root,
                OWNER_SCHEMA,
                "SCOPE_CONFIRMED",
                approved_actions=sorted(OWNER_OBSERVABILITY_ACTIONS),
                return_condition_definition="Practical equivalence",
            )
            (root / "reply.txt").write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "does not match"):
                require_owner_observability_scope(path)

    def test_independent_review_requires_expertise_and_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self.write_record(
                root,
                REVIEW_SCHEMA,
                "PROTOCOL_APPROVED",
                reviewer_expertise="robot motion planning and controls",
                return_protocol_decision="APPROVED",
                vendor_review_required=False,
                reviewed_manifest_sha256="a" * 64,
            )

    def test_independent_review_blocks_when_vendor_review_is_required(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self.write_record(
                root,
                REVIEW_SCHEMA,
                "PROTOCOL_APPROVED",
                reviewer_expertise="robot motion planning and controls",
                return_protocol_decision="APPROVED",
                vendor_review_required=True,
                reviewed_manifest_sha256="a" * 64,
            )
            with self.assertRaisesRegex(ValueError, "vendor review"):
                require_independent_protocol_approval(path)

    def test_independent_review_is_bound_to_exact_manifest_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text('{"packet": 1}\n', encoding="utf-8")
            path = self.write_record(
                root,
                REVIEW_SCHEMA,
                "PROTOCOL_APPROVED",
                reviewer_expertise="robot motion planning and controls",
                return_protocol_decision="APPROVED",
                vendor_review_required=False,
                reviewed_manifest_sha256=hashlib.sha256(
                    manifest.read_bytes()
                ).hexdigest(),
            )
            require_independent_protocol_approval(
                path,
                review_manifest_path=manifest,
            )
            manifest.write_text('{"packet": 2}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "current review manifest"):
                require_independent_protocol_approval(
                    path,
                    review_manifest_path=manifest,
                )
            self.assertEqual(
                require_independent_protocol_approval(path)["decision"],
                "PROTOCOL_APPROVED",
            )


if __name__ == "__main__":
    unittest.main()
