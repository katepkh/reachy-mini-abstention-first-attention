import ast
from pathlib import Path
import unittest

import reachy_stage4.split_authorization as split_authorization
from reachy_stage4.split_authorization import (
    RETURN_ARM_PHRASE,
    TARGET_ARM_PHRASE,
    apply_design_event,
    create_split_motion_design,
)


def artifact(decision, digest="a" * 64, person="Owner"):
    return {
        "artifact_reference": "records/reply.txt",
        "artifact_sha256": digest,
        "recorded_by": person,
        "recorded_at_utc": "2026-09-02T12:00:00Z",
        "decision": decision,
    }


def authorization(identifier, phrase):
    return {
        "authorization_id": identifier,
        "authorized_by": "operator",
        "authorized_at_utc": "2026-09-02T12:00:01Z",
        "phrase": phrase,
    }


def approved_session():
    session = create_split_motion_design("UP", operator_identifier="Operator")
    return apply_design_event(
        session,
        "RECORD_EXTERNAL_APPROVALS",
        {
            "owner_scope": artifact("SCOPE_CONFIRMED", person="Robot Owner"),
            "independent_review": artifact(
                "PROTOCOL_APPROVED", digest="b" * 64, person="Independent Reviewer"
            ),
        },
    )


class SplitAuthorizationTests(unittest.TestCase):
    def test_owner_and_reviewer_must_be_different_people(self):
        session = create_split_motion_design("UP", operator_identifier="Operator")
        with self.assertRaisesRegex(ValueError, "different people"):
            apply_design_event(
                session,
                "RECORD_EXTERNAL_APPROVALS",
                {
                    "owner_scope": artifact("SCOPE_CONFIRMED", person="same"),
                    "independent_review": artifact(
                        "PROTOCOL_APPROVED", digest="b" * 64, person="Same"
                    ),
                },
            )

    def test_reviewer_must_not_be_the_operator(self):
        session = create_split_motion_design("UP", operator_identifier="Operator")
        with self.assertRaisesRegex(ValueError, "reviewer and operator"):
            apply_design_event(
                session,
                "RECORD_EXTERNAL_APPROVALS",
                {
                    "owner_scope": artifact("SCOPE_CONFIRMED", person="Robot Owner"),
                    "independent_review": artifact(
                        "PROTOCOL_APPROVED", digest="b" * 64, person="operator"
                    ),
                },
            )

    def test_target_authorization_cannot_skip_preflight(self):
        with self.assertRaisesRegex(ValueError, "invalid"):
            apply_design_event(approved_session(), "AUTHORIZE_TARGET", authorization("t1", TARGET_ARM_PHRASE))

    def test_target_success_requires_new_return_preflight_and_authorization(self):
        session = approved_session()
        session = apply_design_event(session, "TARGET_PREFLIGHT_PASS", artifact("TARGET_PREFLIGHT_PASS"))
        session = apply_design_event(session, "AUTHORIZE_TARGET", authorization("target-1", TARGET_ARM_PHRASE))
        session = apply_design_event(session, "TARGET_STARTED", {"executor_receipt": "receipt-1"})
        session = apply_design_event(session, "TARGET_OBSERVED_SUCCESS", artifact("TARGET_OBSERVED_SUCCESS", "c" * 64))
        self.assertEqual(session["state"], "RETURN_PREFLIGHT_REQUIRED")
        with self.assertRaisesRegex(ValueError, "invalid"):
            apply_design_event(session, "AUTHORIZE_RETURN", authorization("return-1", RETURN_ARM_PHRASE))
        session = apply_design_event(session, "RETURN_PREFLIGHT_PASS", artifact("RETURN_PREFLIGHT_PASS", "d" * 64))
        with self.assertRaisesRegex(ValueError, "fresh identifier"):
            apply_design_event(session, "AUTHORIZE_RETURN", authorization("target-1", RETURN_ARM_PHRASE))
        session = apply_design_event(session, "AUTHORIZE_RETURN", authorization("return-1", RETURN_ARM_PHRASE))
        self.assertEqual(session["state"], "RETURN_AUTHORIZED")

    def test_failed_target_never_authorizes_return(self):
        session = approved_session()
        session = apply_design_event(session, "TARGET_PREFLIGHT_PASS", artifact("TARGET_PREFLIGHT_PASS"))
        session = apply_design_event(session, "AUTHORIZE_TARGET", authorization("target-1", TARGET_ARM_PHRASE))
        session = apply_design_event(session, "TARGET_STARTED", {"executor_receipt": "receipt-1"})
        session = apply_design_event(session, "TARGET_OBSERVED_FAILURE", {"reason": "unexpected sound"})
        self.assertEqual(session["state"], "ABORT_NO_AUTOMATIC_RETURN")
        self.assertIn("return is not authorized", session["next_requirement"])

    def test_health_failure_from_review_state_aborts(self):
        session = apply_design_event(
            approved_session(), "HEALTH_FAILURE", {"reason": "stale telemetry"}
        )
        self.assertEqual(session["state"], "ABORT_NO_AUTOMATIC_RETURN")

    def test_module_exposes_no_command_or_transport_surface(self):
        tree = ast.parse(Path(split_authorization.__file__).read_text(encoding="utf-8"))
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertTrue(imports.isdisjoint({"requests", "websockets", "socket", "aiohttp"}))
        called = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertTrue(called.isdisjoint({"send", "connect", "goto_target", "set_target"}))


if __name__ == "__main__":
    unittest.main()
