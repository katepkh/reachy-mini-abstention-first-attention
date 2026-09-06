"""Frozen, isolated silent-VAD diagnostic for the passive Stage 3P pipeline."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from typing import Any

from reachy_stage2a.config import PROJECT_ROOT
from reachy_stage3v.analysis import load_rows, summarise_rows
from reachy_stage3v.config import ANALYSIS_DIR, DATA_DIR, REPORT_PATH, RESULT_CSV_PATH, RESULT_JSON_PATH


@dataclass(frozen=True, slots=True)
class SilentVadStep:
    index: int
    condition_id: str
    role: str
    repetition: int
    initial_pitch_deg: float
    target_pitch_deg: float
    face_yaw_deg: float
    sound_yaw_deg: float | None
    transition_at_s: float | None
    title: str
    instruction: str
    countdown_s: int = 5
    duration_s: int = 20

    def run_id(self, date_prefix: str) -> str:
        return (
            f"{date_prefix}_stage3p-vad_{self.index:02d}-of-03_"
            f"silent-face-centre_take{self.repetition:02d}"
        )


SILENT_VAD_STEPS = tuple(
    SilentVadStep(
        index=index,
        condition_id="silent-face-centre",
        role="silent_vad_diagnostic",
        repetition=index,
        initial_pitch_deg=0.0,
        target_pitch_deg=0.0,
        face_yaw_deg=0.0,
        sound_yaw_deg=None,
        transition_at_s=None,
        title="Audited silence at centre eye-line",
        instruction=(
            "Stay at the front 0° mark, exactly 1 m horizontally from Reachy, with your eye "
            "line on the camera optical-centre mark. Keep one complete face visible and remain "
            "completely silent. Silence phones, playback and other intentional sound sources."
        ),
    )
    for index in range(1, 4)
)

SUCCESS_CRITERIA = {
    "instrumentation_quality": {
        "minimum_samples": 75,
        "minimum_valid_doa_pct": 90.0,
        "minimum_fresh_single_face_pct": 90.0,
    },
    "diagnostic_interpretation_predeclared": {
        "clean_max_false_positive_pct": 1.0,
        "elevated_max_false_positive_pct": 5.0,
        "persistent_episode_minimum_ms": 600.0,
    },
}


def protocol_payload() -> dict[str, Any]:
    core = {
        "schema": "reachy-stage3p-silent-vad-diagnostic-v1",
        "status": "FROZEN_DIAGNOSTIC_NOT_POLICY_SELECTION_NOT_AUTHORISED_FOR_ACTUATION",
        "purpose": (
            "Measure the binary DoA endpoint's false speech-positive rate during audited silence "
            "before developing the Stage 3P speaking-face association policy."
        ),
        "parent_calibration_protocol_fingerprint": (
            "f6d0f15e352740b8f1d3c7e25a96e81f060b757246817b813c23d439615cf3a8"
        ),
        "steps": [asdict(step) for step in SILENT_VAD_STEPS],
        "success_criteria": SUCCESS_CRITERIA,
        "required_data_mode": "development_audit",
        "acceptance_independent_of_speech_outcome": True,
        "audit_retention": (
            "Encrypted clips remain local until aggregate VAD diagnosis is reviewed; they are "
            "then deleted manually or by the selected expiry."
        ),
        "privacy": {
            "numeric_dataset_contains_pixels": False,
            "numeric_dataset_contains_audio": False,
            "numeric_dataset_contains_transcript": False,
            "audit_clip_is_separate_encrypted_local_and_bounded": True,
        },
        "actuation_commands": 0,
        "cloud_requests": 0,
    }
    encoded = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**core, "fingerprint": hashlib.sha256(encoded).hexdigest()}


def quality_issues(_step: SilentVadStep, summary: dict[str, float | int]) -> tuple[str, ...]:
    limits = SUCCESS_CRITERIA["instrumentation_quality"]
    issues: list[str] = []
    if int(summary.get("samples", 0)) < int(limits["minimum_samples"]):
        issues.append("fewer than 75 numeric observations")
    if float(summary.get("valid_pct", 0.0)) < float(limits["minimum_valid_doa_pct"]):
        issues.append("fewer than 90% valid DoA responses")
    if float(summary.get("fresh_single_face_pct", 0.0)) < float(
        limits["minimum_fresh_single_face_pct"]
    ):
        issues.append("a fresh single face was not present in at least 90% of samples")
    return tuple(issues)


def _truth(value: object) -> bool:
    return value is True or str(value).strip().lower() == "true"


def _number(value: object) -> float | None:
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def _positive_episodes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    episodes: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for row in rows:
        if _truth(row.get("speech_detected")):
            current.append(row)
        elif current:
            episodes.append(current)
            current = []
    if current:
        episodes.append(current)
    elapsed = [value for row in rows if (value := _number(row.get("elapsed_ms"))) is not None]
    intervals = [right - left for left, right in zip(elapsed, elapsed[1:]) if right > left]
    nominal_interval = median(intervals) if intervals else 0.0
    result: list[dict[str, Any]] = []
    for episode in episodes:
        times = [value for row in episode if (value := _number(row.get("elapsed_ms"))) is not None]
        angles = [value for row in episode if (value := _number(row.get("raw_angle_deg"))) is not None]
        duration = 0.0 if not times else max(0.0, times[-1] - times[0] + nominal_interval)
        result.append({
            "samples": len(episode),
            "duration_ms": duration,
            "start_elapsed_ms": times[0] if times else None,
            "end_elapsed_ms": times[-1] if times else None,
            "median_doa_deg": median(angles) if angles else None,
        })
    return result


def evaluate_vad_trial(step: SilentVadStep, rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary = summarise_rows(rows)
    episodes = _positive_episodes(rows)
    positives = int(summary.get("speech_positive", 0))
    persistent_ms = float(
        SUCCESS_CRITERIA["diagnostic_interpretation_predeclared"][
            "persistent_episode_minimum_ms"
        ]
    )
    return {
        "step": step.index,
        "condition": step.condition_id,
        "role": step.role,
        "repetition": step.repetition,
        "target_pitch_deg": step.target_pitch_deg,
        "rows": len(rows),
        "valid_pct": float(summary.get("valid_pct", 0.0)),
        "fresh_single_face_pct": float(summary.get("fresh_single_face_pct", 0.0)),
        "speech_positive": positives,
        "speech_positive_pct": 100.0 * positives / len(rows) if rows else 0.0,
        "positive_episodes": len(episodes),
        "persistent_positive_episodes": sum(
            float(episode["duration_ms"]) >= persistent_ms for episode in episodes
        ),
        "longest_positive_episode_ms": max(
            (float(episode["duration_ms"]) for episode in episodes), default=0.0
        ),
        "positive_episode_details": episodes,
        "would_adjust_rows": 0,
        "first_target_pitch_deg": None,
        "wrong_sign_adjustments": 0,
    }


def _classification(false_positive_pct: float) -> str:
    limits = SUCCESS_CRITERIA["diagnostic_interpretation_predeclared"]
    if false_positive_pct <= float(limits["clean_max_false_positive_pct"]):
        return "CLEAN"
    if false_positive_pct <= float(limits["elevated_max_false_positive_pct"]):
        return "ELEVATED"
    return "HIGH"


def evaluate_saved_files(csv_files: list[str]) -> dict[str, Any]:
    if len(csv_files) != len(SILENT_VAD_STEPS):
        raise ValueError("A complete silent-VAD diagnostic requires three accepted files.")
    trials: list[dict[str, Any]] = []
    for step, filename in zip(SILENT_VAD_STEPS, csv_files):
        path = (DATA_DIR / filename).resolve()
        if path.parent != DATA_DIR or not path.is_file():
            raise ValueError(f"Silent-VAD diagnostic file is missing: {filename}")
        rows = load_rows(path)
        issues = quality_issues(step, summarise_rows(rows))
        if issues:
            raise ValueError(f"Silent-VAD file fails quality: {filename}: {'; '.join(issues)}")
        compliance = path.with_name(path.stem + "_compliance.json")
        if not compliance.is_file() or json.loads(compliance.read_text(encoding="utf-8")).get(
            "verdict"
        ) != "COMPLIANT":
            raise ValueError(f"Silent-VAD file lacks a compliant audit: {filename}")
        trials.append({**evaluate_vad_trial(step, rows), "file": filename})
    samples = sum(int(trial["rows"]) for trial in trials)
    positives = sum(int(trial["speech_positive"]) for trial in trials)
    false_positive_pct = 100.0 * positives / samples if samples else 0.0
    return {
        "schema": "reachy-stage3p-silent-vad-diagnostic-result-v1",
        "status": "DIAGNOSTIC_ONLY_NOT_POLICY_SELECTION_NOT_AUTHORISED_FOR_ACTUATION",
        "protocol_fingerprint": protocol_payload()["fingerprint"],
        "collection_complete": True,
        "total_samples": samples,
        "speech_false_positive_samples": positives,
        "speech_false_positive_pct": false_positive_pct,
        "classification": _classification(false_positive_pct),
        "persistent_positive_episodes": sum(
            int(trial["persistent_positive_episodes"]) for trial in trials
        ),
        "trials": trials,
        "audit_media_retained_for_diagnosis": True,
        "contains_pixels": False,
        "contains_audio": False,
        "contains_transcript": False,
        "robot_requests": 0,
        "cloud_requests": 0,
        "actuation_commands": 0,
    }


def write_results(csv_files: list[str]) -> dict[str, Any]:
    result = evaluate_saved_files(csv_files)
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_JSON_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    flat_trials = [
        {key: value for key, value in trial.items() if key != "positive_episode_details"}
        for trial in result["trials"]
    ]
    with RESULT_CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(flat_trials[0]))
        writer.writeheader()
        writer.writerows(flat_trials)
    REPORT_PATH.write_text(
        "\n".join([
            "# Stage 3P silent-VAD diagnostic",
            "",
            f"Protocol fingerprint: `{result['protocol_fingerprint']}`",
            "",
            f"- Samples: **{result['total_samples']}**",
            f"- Speech false positives: **{result['speech_false_positive_samples']} "
            f"({result['speech_false_positive_pct']:.2f}%)**",
            f"- Predeclared classification: **{result['classification']}**",
            f"- Persistent positive episodes: **{result['persistent_positive_episodes']}**",
            "",
            "> Diagnostic only. Acceptance was independent of speech outcome; no policy was selected and no movement was authorized.",
        ]) + "\n",
        encoding="utf-8",
    )
    return result


def analyse_existing_calibration_silence() -> dict[str, Any]:
    progress_path = PROJECT_ROOT / "data/stage3p_calibration/progress.json"
    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    source_dir = progress_path.parent
    trials = []
    for step, filename in zip(SILENT_VAD_STEPS * 3, progress["accepted_csv_files"]):
        rows = load_rows(source_dir / filename)
        # The existing nine calibration trials have their own sequence; only
        # the speech/episode calculations from the diagnostic evaluator apply.
        observed = evaluate_vad_trial(step, rows)
        trials.append({**observed, "file": filename})
    samples = sum(int(trial["rows"]) for trial in trials)
    positives = sum(int(trial["speech_positive"]) for trial in trials)
    false_positive_pct = 100.0 * positives / samples if samples else 0.0
    payload = {
        "schema": "reachy-stage3p-existing-calibration-silence-observation-v1",
        "source_protocol_fingerprint": progress["protocol_fingerprint"],
        "accepted_source_files": list(progress["accepted_csv_files"]),
        "total_samples": samples,
        "speech_false_positive_samples": positives,
        "speech_false_positive_pct": false_positive_pct,
        "classification_under_predeclared_vad_diagnostic_scale": _classification(false_positive_pct),
        "persistent_positive_episodes": sum(
            int(trial["persistent_positive_episodes"]) for trial in trials
        ),
        "trials": trials,
        "limitation": (
            "Audit clips were verified and deleted after acceptance, so numeric endpoint flags "
            "cannot distinguish detector false positives from quiet environmental sound."
        ),
        "actuation_commands": 0,
        "cloud_requests": 0,
    }
    destination = PROJECT_ROOT / "data/analysis/stage3p_calibration_silent_vad_observation_v1.json"
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def write_manifest(path: Path | None = None) -> dict[str, Any]:
    destination = path or (PROJECT_ROOT / "data/manifests/stage3p_silent_vad_diagnostic_v1.json")
    payload = protocol_payload()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


if len(SILENT_VAD_STEPS) != 3:
    raise ValueError("Silent-VAD diagnostic must contain exactly three trials.")
