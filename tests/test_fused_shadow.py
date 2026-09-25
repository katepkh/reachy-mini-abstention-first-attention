from __future__ import annotations

import ast
import unittest
from pathlib import Path

from reachy_avsync import SynchronyDecision
from reachy_stage3v.fused_shadow import (
    FUSED_SHADOW_SPEC_V1,
    ShadowObservation,
    SpatialEvidence,
    SynchronyEvidence,
    fuse_shadow_observation,
    spatial_from_revised,
    synchrony_from_decision,
)
from reachy_stage3v.revised_policy import RevisedEvidence


ROOT = Path(__file__).resolve().parents[1]


class FusedShadowTests(unittest.TestCase):
    def spatial(self, status: str = "SUPPORTED", **changes: object) -> SpatialEvidence:
        values: dict[str, object] = {
            "status": status,
            "observed_ms": 900.0,
            "face_track_id": "face-a",
            "heading_deg": 10.0,
            "reason": "TEMPORAL_CONSENSUS",
        }
        values.update(changes)
        return SpatialEvidence(**values)  # type: ignore[arg-type]

    def synchrony(self, status: str = "SUPPORTED", **changes: object) -> SynchronyEvidence:
        values: dict[str, object] = {
            "status": status,
            "observed_ms": 920.0,
            "face_track_id": "face-a",
            "correlation": 0.8,
            "lag_ms": 40.0,
            "reason": "STABLE_SYNCHRONY_CANDIDATE_NOT_IDENTITY",
        }
        values.update(changes)
        return SynchronyEvidence(**values)  # type: ignore[arg-type]

    def fuse(
        self,
        spatial: SpatialEvidence | None = None,
        synchrony: SynchronyEvidence | None = None,
        *,
        healthy: bool = True,
    ):
        return fuse_shadow_observation(
            ShadowObservation(
                elapsed_ms=1000.0,
                healthy=healthy,
                health_reason="READY" if healthy else "STATE_STALE",
                spatial=spatial or self.spatial(),
                synchrony=synchrony or self.synchrony(),
            )
        )

    def test_supported_same_face_selects_only_a_shadow_candidate(self) -> None:
        decision = self.fuse()
        self.assertEqual(decision.state, "SELECT")
        self.assertEqual(decision.candidate_face_track_id, "face-a")
        self.assertEqual(decision.candidate_heading_deg, 10.0)
        self.assertFalse(decision.motion_authorized)
        self.assertFalse(decision.response_authorized)
        self.assertEqual(decision.actuation_commands, 0)
        self.assertEqual(decision.response_commands, 0)

    def test_pending_input_holds(self) -> None:
        self.assertEqual(self.fuse(self.spatial("PENDING")).state, "HOLD")
        self.assertEqual(self.fuse(synchrony=self.synchrony("PENDING")).state, "HOLD")

    def test_conflict_abstention_unavailable_and_health_fail_closed(self) -> None:
        self.assertEqual(self.fuse(self.spatial("CONFLICT")).state, "ABSTAIN")
        self.assertEqual(self.fuse(synchrony=self.synchrony("ABSTAIN")).state, "ABSTAIN")
        self.assertEqual(self.fuse(synchrony=self.synchrony("UNAVAILABLE")).state, "ABSTAIN")
        self.assertEqual(self.fuse(healthy=False).state, "ABSTAIN")

    def test_face_track_mismatch_abstains(self) -> None:
        decision = self.fuse(synchrony=self.synchrony(face_track_id="face-b"))
        self.assertEqual(decision.state, "ABSTAIN")
        self.assertEqual(decision.reason, "FACE_TRACK_MISMATCH")

    def test_stale_skewed_or_invalid_heading_abstains(self) -> None:
        self.assertIn("STALE", self.fuse(self.spatial(observed_ms=0.0)).reason)
        self.assertEqual(
            self.fuse(self.spatial(observed_ms=600.0), self.synchrony(observed_ms=920.0)).reason,
            "EVIDENCE_CLOCK_SKEW_EXCESSIVE",
        )
        self.assertEqual(self.fuse(self.spatial(heading_deg=None)).reason, "SPATIAL_HEADING_INVALID")
        self.assertEqual(
            self.fuse(self.spatial(heading_deg=FUSED_SHADOW_SPEC_V1.max_abs_heading_deg + 1.0)).reason,
            "SPATIAL_HEADING_OUTSIDE_SHADOW_SCOPE",
        )

    def test_malformed_runtime_values_fail_closed_instead_of_raising(self) -> None:
        bad_time = self.fuse(self.spatial(observed_ms="not-a-time"))
        bad_status = self.fuse(self.spatial(status=["SUPPORTED"]))
        empty_track = self.fuse(self.spatial(face_track_id=""))
        self.assertEqual(bad_time.reason, "SPATIAL_NONFINITE_EVIDENCE_TIME")
        self.assertEqual(bad_status.reason, "INVALID_SPATIAL_STATUS")
        self.assertEqual(empty_track.reason, "FACE_TRACK_ID_MISSING")

    def test_adapters_preserve_candidate_not_identity_boundary(self) -> None:
        spatial = spatial_from_revised(
            900.0,
            "face-a",
            RevisedEvidence(True, 10.0, "TEMPORAL_CONSENSUS"),
        )
        synchrony = synchrony_from_decision(
            920.0,
            SynchronyDecision(
                "SUPPORTED_CANDIDATE",
                "STABLE_SYNCHRONY_CANDIDATE_NOT_IDENTITY",
                "face-a",
                0.8,
                40.0,
                3,
            ),
        )
        self.assertEqual(spatial.status, "SUPPORTED")
        self.assertEqual(synchrony.status, "SUPPORTED")
        self.assertIn("NOT_IDENTITY", synchrony.reason)

    def test_raw_or_pending_synchrony_cannot_select(self) -> None:
        raw = synchrony_from_decision(
            920.0,
            SynchronyDecision("CANDIDATE", "SYNCHRONY_CANDIDATE_NOT_IDENTITY", "face-a", 0.8, 0.0),
        )
        pending = synchrony_from_decision(
            920.0,
            SynchronyDecision("ABSTAIN", "SYNCHRONY_CONSENSUS_PENDING", None, 0.8, 0.0, 2),
        )
        self.assertEqual(raw.status, "PENDING")
        self.assertEqual(pending.status, "PENDING")
        self.assertEqual(self.fuse(synchrony=raw).state, "HOLD")

    def test_module_has_no_network_media_sdk_or_actuation_imports(self) -> None:
        path = ROOT / "reachy_stage3v" / "fused_shadow.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        forbidden = {"requests", "websockets", "aiohttp", "cv2", "sounddevice", "reachy_mini"}
        self.assertTrue(imported.isdisjoint(forbidden), imported & forbidden)

    def test_spec_fingerprint_is_deterministic(self) -> None:
        first = FUSED_SHADOW_SPEC_V1.payload()
        second = FUSED_SHADOW_SPEC_V1.payload()
        self.assertEqual(first, second)
        self.assertEqual(len(str(first["fingerprint"])), 64)


if __name__ == "__main__":
    unittest.main()
