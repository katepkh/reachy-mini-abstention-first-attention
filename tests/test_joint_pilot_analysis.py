from __future__ import annotations

import ast
import csv
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from reachy_stage3v.joint_pilot_analysis import (
    analyze_joint_pilot,
    assess_joint_pilot_quality,
    joint_pilot_candidate_specs,
    load_joint_pilot_trial,
)
from reachy_stage3v.joint_pilot_protocol import (
    joint_pilot_protocol_payload,
    randomized_joint_pilot_trials,
)
from reachy_stage3v.joint_pilot_synthetic import write_synthetic_joint_pilot


ROOT = Path(__file__).resolve().parents[1]


class JointPilotAnalysisTests(unittest.TestCase):
    def test_grid_contains_300_unique_settings(self) -> None:
        settings = joint_pilot_candidate_specs()
        keys = {
            (spec.min_correlation, spec.max_abs_lag_ms, smoothing, spatial)
            for spec, smoothing, spatial in settings
        }
        self.assertEqual(len(settings), 300)
        self.assertEqual(len(keys), 300)

    def test_synthetic_bundle_passes_without_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_synthetic_joint_pilot(root)
            report = analyze_joint_pilot(root)
        self.assertEqual(report["status"], "PILOT_PASSED_INTERNAL_VALIDATION_NOT_CONFIRMATION")
        self.assertEqual(report["schema"], "reachy-joint-shadow-no-motion-pilot-result-v2")
        self.assertTrue(report["internal_validation_passed"])
        self.assertGreater(report["eligible_development_candidate_count"], 0)
        self.assertEqual(report["candidate_count"], 300)
        self.assertEqual(report["robot_connections"], 0)
        self.assertEqual(report["actuation_commands"], 0)
        self.assertEqual(len(report["execution_fingerprint"]), 64)
        self.assertEqual(len(report["binding_manifest_sha256"]), 64)
        self.assertEqual(len(report["selected_candidate"]["trials"]), 14)
        self.assertTrue(
            all(
                trial["split"] == "development"
                for trial in report["selected_candidate"]["trials"]
            )
        )
        self.assertEqual(len(report["internal_validation"]["trials"]), 7)
        validation = report["baseline_metrics"]["internal_validation"]
        self.assertEqual(validation["fused_abstaining"]["false_positive"], 0)
        self.assertGreater(validation["acoustic_only"]["false_positive"], 0)

    def test_metadata_schedule_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_synthetic_joint_pilot(root)
            trial = randomized_joint_pilot_trials()[0]
            path = root / f"{trial['trial_id']}.metadata.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["condition_id"] = "visible_silence"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "condition_id"):
                load_joint_pilot_trial(root, trial)

    def test_metadata_binding_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_synthetic_joint_pilot(root)
            trial = randomized_joint_pilot_trials()[0]
            path = root / f"{trial['trial_id']}.metadata.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["binding_manifest_sha256"] = "0" * 64
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "binding_manifest_sha256"):
                load_joint_pilot_trial(root, trial)

    def test_multiple_faces_fail_objective_quality(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_synthetic_joint_pilot(root)
            trial = next(
                item
                for item in randomized_joint_pilot_trials()
                if item["condition_id"] == "live_visible_continuous"
            )
            path = root / f"{trial['trial_id']}.csv"
            with path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.reader(handle))
            face_count_index = rows[0].index("face_count")
            rows[1][face_count_index] = "2"
            with path.open("w", encoding="utf-8", newline="") as handle:
                csv.writer(handle, lineterminator="\n").writerows(rows)
            quality = assess_joint_pilot_quality(trial, load_joint_pilot_trial(root, trial))
        self.assertFalse(quality["passed"])
        self.assertIn("MULTIPLE_FACES_OBSERVED", quality["failures"])

    def test_v2_face_scale_gate_accepts_bound_one_metre_geometry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_synthetic_joint_pilot(root)
            trial = next(
                item
                for item in randomized_joint_pilot_trials()
                if item["condition_id"] == "live_visible_continuous"
            )
            path = root / f"{trial['trial_id']}.csv"
            with path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.reader(handle))
            scale_index = rows[0].index("face_scale")
            for row in rows[1:]:
                row[scale_index] = "0.0687"
            with path.open("w", encoding="utf-8", newline="") as handle:
                csv.writer(handle, lineterminator="\n").writerows(rows)
            quality = assess_joint_pilot_quality(trial, load_joint_pilot_trial(root, trial))
        self.assertTrue(quality["passed"])
        self.assertAlmostEqual(quality["median_face_scale"], 0.0687)

    @unittest.skipUnless(shutil.which("node"), "Node.js is required for browser parity")
    def test_browser_and_offline_quality_gates_agree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_synthetic_joint_pilot(root)
            trial = next(
                item
                for item in randomized_joint_pilot_trials()
                if item["condition_id"] == "live_visible_continuous"
            )
            path = root / f"{trial['trial_id']}.csv"
            with path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            for index, row in enumerate(rows):
                row["face_scale"] = "0.0687"
                if index < 11:
                    row["face_count"] = "0"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0], lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
            data = load_joint_pilot_trial(root, trial)
            offline = assess_joint_pilot_quality(trial, data)
            browser_rows = []
            for row in data.rows:
                browser_rows.append(
                    {
                        "timestamp_ms": float(row["timestamp_ms"]),
                        "audio_dbfs": float(row["audio_dbfs"]),
                        "face_count": int(row["face_count"]),
                        "face_heading_estimate_deg": (
                            float(row["face_heading_estimate_deg"])
                            if row["face_heading_estimate_deg"]
                            else None
                        ),
                        "face_scale": float(row["face_scale"]),
                        "lip_aperture": float(row["lip_aperture"]),
                        "doa_valid": row["doa_valid"] == "true",
                        "doa_axis_deg": float(row["doa_axis_deg"]),
                        "doa_speech_detected": row["doa_speech_detected"] == "true",
                        "doa_age_ms": float(row["doa_age_ms"]),
                    }
                )
            payload = {
                "trial": trial,
                "rows": browser_rows,
                "gates": joint_pilot_protocol_payload()["quality_gates"],
            }
            module_uri = (ROOT / "tools" / "joint_pilot_quality.mjs").as_uri()
            script = (
                "import fs from 'node:fs';"
                "const {assessPilotQuality}=await import(process.argv[1]);"
                "const p=JSON.parse(fs.readFileSync(0,'utf8'));"
                "process.stdout.write(JSON.stringify(assessPilotQuality(p.trial,p.rows,p.gates)));"
            )
            completed = subprocess.run(
                [str(shutil.which("node")), "--input-type=module", "-e", script, module_uri],
                input=json.dumps(payload),
                capture_output=True,
                check=True,
                text=True,
            )
            browser = json.loads(completed.stdout)
        self.assertEqual(browser["passed"], offline["passed"])
        self.assertEqual(browser["failures"], offline["failures"])
        self.assertAlmostEqual(browser["median_face_scale"], offline["median_face_scale"])
        self.assertAlmostEqual(browser["single_face_fraction"], offline["single_face_fraction"])

    def test_analysis_module_has_no_capture_network_or_robot_sdk_import(self) -> None:
        path = ROOT / "reachy_stage3v" / "joint_pilot_analysis.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertTrue(
            imported.isdisjoint(
                {"requests", "aiohttp", "cv2", "sounddevice", "reachy_mini"}
            )
        )


if __name__ == "__main__":
    unittest.main()
