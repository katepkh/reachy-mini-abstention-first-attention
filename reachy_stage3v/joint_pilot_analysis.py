"""Frozen offline analysis for the command-free joint shadow pilot.

The module reads derived numeric CSV/metadata pairs only. It opens no media,
network, robot, or output device and has no motion or response authority.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import asdict, dataclass, replace
from itertools import product
from pathlib import Path
from statistics import median
from typing import Any

import numpy as np

from reachy_avsync.synchrony import NumericSeries, SynchronySpec, evaluate_synchrony
from reachy_doa.angles import doa_to_physical_hypotheses
from reachy_stage2a.calibration import circular_distance_degrees

from .joint_instrument import JOINT_INSTRUMENT_SPEC_V1, JOINT_REQUIRED_COLUMNS
from .joint_pilot_execution import build_execution_payload, sha256_file
from .joint_pilot_protocol import joint_pilot_protocol_payload, randomized_joint_pilot_trials


VISIBLE_CONDITIONS = frozenset(
    {
        "live_visible_continuous",
        "live_visible_interrupted",
        "silent_face_phone_playback",
        "silent_mouthing_unrelated_playback",
        "visible_silence",
        "spatial_conflict",
    }
)
SPEECH_REQUIRED_CONDITIONS = frozenset(
    {
        "live_visible_continuous",
        "live_visible_interrupted",
        "silent_face_phone_playback",
        "silent_mouthing_unrelated_playback",
        "speech_without_usable_face",
        "spatial_conflict",
    }
)
MOUTH_MOTION_REQUIRED_CONDITIONS = frozenset(
    {
        "live_visible_continuous",
        "live_visible_interrupted",
        "silent_mouthing_unrelated_playback",
    }
)
NEGATIVE_ROLES = frozenset(
    {
        "primary_hard_negative",
        "synchrony_hard_negative",
        "negative_control",
        "unavailable_face_control",
        "conflicting_cue_control",
    }
)


@dataclass(frozen=True, slots=True)
class JointPilotInput:
    rows: tuple[dict[str, str], ...]
    metadata: dict[str, Any]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _number(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _integer(value: object) -> int | None:
    result = _number(value)
    if result is None or int(result) != result:
        return None
    return int(result)


def _truth(value: object) -> bool:
    return value is True or str(value).strip().lower() == "true"


def _percentile(values: list[float], fraction: float) -> float | None:
    return float(np.percentile(values, fraction * 100.0)) if values else None


def _smooth(values: np.ndarray, samples: int) -> np.ndarray:
    if samples <= 1:
        return values.copy()
    left = samples // 2
    right = samples - 1 - left
    padded = np.pad(values, (left, right), mode="edge")
    return np.convolve(padded, np.ones(samples) / samples, mode="valid")


def _binding_context(input_dir: Path) -> dict[str, str]:
    root = input_dir.resolve()
    private_root = root.parent if (root.parent / "binding_manifest.json").is_file() else root
    manifest_path = private_root / "binding_manifest.json"
    setup_path = private_root / "setup.json"
    sidecar = manifest_path.with_suffix(manifest_path.suffix + ".sha256")
    if not manifest_path.is_file() or not setup_path.is_file() or not sidecar.is_file():
        raise ValueError("Pilot input is not accompanied by a sealed private binding.")
    manifest_hash = sha256_file(manifest_path)
    expected_sidecar = f"{manifest_hash}  {manifest_path.name}\n"
    if sidecar.read_text(encoding="ascii") != expected_sidecar:
        raise ValueError("Private binding manifest hash is invalid.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    execution = build_execution_payload()
    expected = {
        "schema": "reachy-joint-shadow-pilot-private-binding-manifest-v1",
        "status": "SEALED_BEFORE_TRIAL_1",
        "protocol_fingerprint": joint_pilot_protocol_payload()["fingerprint"],
        "execution_fingerprint": execution["fingerprint"],
        "setup_sha256": sha256_file(setup_path),
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise ValueError(f"Private binding manifest has stale {key}.")
    return {
        "execution_fingerprint": execution["fingerprint"],
        "binding_manifest_sha256": manifest_hash,
    }


def load_joint_pilot_trial(input_dir: Path, trial: dict[str, Any]) -> JointPilotInput:
    """Load and bind one exact CSV/metadata pair to its frozen trial card."""

    root = input_dir.resolve()
    trial_id = str(trial["trial_id"])
    csv_path = (root / f"{trial_id}.csv").resolve()
    metadata_path = (root / f"{trial_id}.metadata.json").resolve()
    if csv_path.parent != root or metadata_path.parent != root:
        raise ValueError("Pilot path escaped its input directory.")
    if not csv_path.is_file() or not metadata_path.is_file():
        raise FileNotFoundError(f"Missing CSV/metadata pair for {trial_id}.")
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != JOINT_REQUIRED_COLUMNS:
            raise ValueError(f"{csv_path.name}: columns do not match the frozen instrument.")
        rows = tuple(reader)
    if not rows:
        raise ValueError(f"{csv_path.name}: no observations.")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    protocol = joint_pilot_protocol_payload()
    binding = _binding_context(root)
    expected = {
        "schema": "reachy-joint-shadow-pilot-trial-v1",
        "trial_id": trial_id,
        "instrument_fingerprint": JOINT_INSTRUMENT_SPEC_V1.payload()["fingerprint"],
        "pilot_protocol_fingerprint": protocol["fingerprint"],
        "execution_fingerprint": binding["execution_fingerprint"],
        "binding_manifest_sha256": binding["binding_manifest_sha256"],
        "condition_id": trial["condition_id"],
        "role": trial["role"],
        "schedule_index": trial["schedule_index"],
        "repetition": trial["repetition"],
        "split": trial["split"],
    }
    for key, value in expected.items():
        if metadata.get(key) != value:
            raise ValueError(f"{metadata_path.name}: {key} does not match the frozen schedule.")
    for key in ("uploads", "actuation_commands", "response_commands"):
        if metadata.get(key) != 0:
            raise ValueError(f"{metadata_path.name}: {key} must equal zero.")
    for key in ("contains_pixels", "contains_waveform", "contains_transcript", "contains_identity_embedding"):
        if metadata.get(key) is not False:
            raise ValueError(f"{metadata_path.name}: {key} must be false.")
    return JointPilotInput(rows, metadata)


def _numeric_column(data: JointPilotInput, key: str) -> np.ndarray:
    values = [_number(row.get(key)) for row in data.rows]
    if any(value is None for value in values):
        raise ValueError(f"Non-finite value in required numeric column {key}.")
    return np.asarray([float(value) for value in values if value is not None], dtype=float)


def _spatial_errors(data: JointPilotInput) -> list[float]:
    errors: list[float] = []
    for row in data.rows:
        if _integer(row.get("face_count")) != 1 or not _truth(row.get("doa_valid")):
            continue
        face = _number(row.get("face_heading_estimate_deg"))
        doa = _number(row.get("doa_axis_deg"))
        if face is None or doa is None:
            continue
        hypotheses = doa_to_physical_hypotheses(doa)
        errors.append(min(circular_distance_degrees(face, item) for item in hypotheses))
    return errors


def assess_joint_pilot_quality(trial: dict[str, Any], data: JointPilotInput) -> dict[str, Any]:
    """Apply only frozen, condition-specific acquisition/manipulation checks."""

    gates = joint_pilot_protocol_payload()["quality_gates"]
    timestamps = _numeric_column(data, "timestamp_ms")
    gaps = np.diff(timestamps)
    raw_face_count = _numeric_column(data, "face_count")
    if any(int(value) != value or value < 0 or value > 2 for value in raw_face_count):
        raise ValueError("face_count must be an integer from zero to two.")
    face_count = raw_face_count.astype(int)
    face_scale = _numeric_column(data, "face_scale")
    audio = _numeric_column(data, "audio_dbfs")
    lip = _numeric_column(data, "lip_aperture")
    doa_valid = np.asarray([_truth(row.get("doa_valid")) for row in data.rows])
    doa_speech = np.asarray([_truth(row.get("doa_speech_detected")) for row in data.rows])
    doa_ages = [
        value
        for row in data.rows
        if (value := _number(row.get("doa_age_ms"))) is not None
    ]
    condition = str(trial["condition_id"])
    failures: list[str] = []
    if len(timestamps) < int(gates["minimum_samples"]):
        failures.append("INSUFFICIENT_SAMPLES")
    if len(timestamps) < 2 or (gaps <= 0.0).any():
        failures.append("TIMESTAMPS_NOT_STRICTLY_INCREASING")
    span = float(timestamps[-1] - timestamps[0]) if len(timestamps) >= 2 else 0.0
    if span < float(gates["minimum_span_ms"]):
        failures.append("SPAN_TOO_SHORT")
    maximum_gap = float(gaps.max(initial=0.0))
    if maximum_gap > float(gates["maximum_sample_gap_ms"]):
        failures.append("SAMPLE_GAP_EXCESSIVE")
    doa_valid_fraction = float(doa_valid.mean())
    if doa_valid_fraction < float(gates["minimum_doa_valid_fraction"]):
        failures.append("DOA_AVAILABILITY_TOO_LOW")
    p95_age = _percentile(doa_ages, 0.95)
    if p95_age is None or p95_age > float(gates["maximum_p95_doa_age_ms"]):
        failures.append("DOA_AGE_TOO_HIGH")

    single = face_count == 1
    single_fraction = float(single.mean())
    multiple_rows = int((face_count > 1).sum())
    if multiple_rows > int(gates["multiple_face_rows_allowed"]):
        failures.append("MULTIPLE_FACES_OBSERVED")
    if condition in VISIBLE_CONDITIONS:
        if single_fraction < float(gates["minimum_single_face_fraction_when_required"]):
            failures.append("SINGLE_FACE_FRACTION_TOO_LOW")
        valid_scales = face_scale[single]
        median_scale = float(np.median(valid_scales)) if len(valid_scales) else 0.0
        if median_scale < float(gates["minimum_median_face_scale_when_required"]):
            failures.append("FACE_SCALE_TOO_SMALL")
    else:
        median_scale = None
        if single_fraction > float(gates["maximum_usable_face_fraction_for_unavailable_face_control"]):
            failures.append("USABLE_FACE_PRESENT_IN_UNAVAILABLE_CONTROL")

    audio_std = float(np.std(audio))
    speech_fraction = float(doa_speech.mean())
    if condition in SPEECH_REQUIRED_CONDITIONS:
        if audio_std < float(gates["minimum_audio_dbfs_std_when_speech_required"]):
            failures.append("AUDIO_DYNAMIC_RANGE_TOO_LOW")
        if speech_fraction < float(gates["minimum_doa_speech_fraction_when_speech_required"]):
            failures.append("SPEECH_ACTIVITY_TOO_LOW")
    elif speech_fraction > float(gates["maximum_doa_speech_fraction_for_visible_silence"]):
        failures.append("SPEECH_ACTIVITY_TOO_HIGH_FOR_SILENCE")

    valid_lip = lip[single]
    lip_std = float(np.std(valid_lip)) if len(valid_lip) else 0.0
    if (
        condition in MOUTH_MOTION_REQUIRED_CONDITIONS
        and lip_std < float(gates["minimum_lip_aperture_std_when_motion_required"])
    ):
        failures.append("LIP_DYNAMIC_RANGE_TOO_LOW")
    spatial_errors = _spatial_errors(data)
    median_spatial_error = median(spatial_errors) if spatial_errors else None
    if condition == "spatial_conflict" and (
        median_spatial_error is None
        or median_spatial_error < float(gates["minimum_spatial_conflict_deg"])
    ):
        failures.append("SPATIAL_CONFLICT_NOT_REALIZED")

    return {
        "trial_id": trial["trial_id"],
        "condition_id": condition,
        "split": trial["split"],
        "role": trial["role"],
        "passed": not failures,
        "failures": failures,
        "sample_count": len(timestamps),
        "span_ms": span,
        "maximum_sample_gap_ms": maximum_gap,
        "single_face_fraction": single_fraction,
        "multiple_face_rows": multiple_rows,
        "median_face_scale": median_scale,
        "doa_valid_fraction": doa_valid_fraction,
        "doa_speech_fraction": speech_fraction,
        "p95_doa_age_ms": p95_age,
        "audio_dbfs_std": audio_std,
        "lip_aperture_std": lip_std,
        "median_spatial_error_deg": median_spatial_error,
    }


def joint_pilot_candidate_specs() -> list[tuple[SynchronySpec, int, float]]:
    payload = joint_pilot_protocol_payload()
    grid = payload["candidate_grid"]
    gates = payload["quality_gates"]
    return [
        (
            replace(
                SynchronySpec(),
                min_correlation=float(correlation),
                max_abs_lag_ms=float(lag),
                min_audio_std=float(gates["minimum_audio_dbfs_std_when_speech_required"]),
                min_mouth_std=float(gates["minimum_lip_aperture_std_when_motion_required"]),
            ),
            int(smoothing),
            float(spatial),
        )
        for correlation, lag, smoothing, spatial in product(
            grid["minimum_synchrony_correlation"],
            grid["maximum_absolute_lag_ms"],
            grid["moving_average_samples"],
            grid["maximum_median_spatial_error_deg"],
        )
    ]


def _trial_features(
    trial: dict[str, Any],
    data: JointPilotInput,
    quality: dict[str, Any],
    spec: SynchronySpec,
    smoothing: int,
    maximum_spatial_error_deg: float,
) -> dict[str, Any]:
    gates = joint_pilot_protocol_payload()["quality_gates"]
    condition = str(trial["condition_id"])
    visible = condition in VISIBLE_CONDITIONS
    speech_active = quality["doa_speech_fraction"] >= float(
        gates["minimum_doa_speech_fraction_when_speech_required"]
    )
    mouth_active = quality["lip_aperture_std"] >= float(
        gates["minimum_lip_aperture_std_when_motion_required"]
    )
    spatial_error = quality["median_spatial_error_deg"]
    spatial_supported = bool(
        visible
        and spatial_error is not None
        and spatial_error <= maximum_spatial_error_deg
    )
    synchrony_status = "ABSTAIN"
    synchrony_reason = "QUALITY_OR_FACE_UNAVAILABLE"
    correlation = None
    lag_ms = None
    if quality["passed"] and visible:
        valid = np.asarray([_integer(row.get("face_count")) == 1 for row in data.rows])
        timestamps = _numeric_column(data, "timestamp_ms")[valid]
        audio = _smooth(_numeric_column(data, "audio_dbfs")[valid], smoothing)
        lip = _smooth(_numeric_column(data, "lip_aperture")[valid], smoothing)
        score = evaluate_synchrony(
            NumericSeries.from_sequences(timestamps, audio),
            NumericSeries.from_sequences(timestamps, lip),
            spec,
        )
        synchrony_status = score.status
        synchrony_reason = score.reason
        correlation = score.correlation
        lag_ms = score.lag_ms
    synchrony_supported = synchrony_status == "CANDIDATE"
    proposal = bool(
        quality["passed"]
        and visible
        and speech_active
        and spatial_supported
        and synchrony_supported
    )
    baselines = {
        "acoustic_only": bool(quality["passed"] and speech_active),
        "visual_activity_only": bool(quality["passed"] and visible and mouth_active),
        "speech_plus_mouth_activity": bool(
            quality["passed"] and visible and speech_active and mouth_active
        ),
        "spatial_only": bool(
            quality["passed"] and visible and speech_active and spatial_supported
        ),
        "synchrony_only": bool(
            quality["passed"] and visible and synchrony_supported
        ),
        "non_abstaining_visible_face": bool(quality["passed"] and visible),
        "fused_abstaining": proposal,
    }
    return {
        "trial_id": trial["trial_id"],
        "condition_id": condition,
        "split": trial["split"],
        "role": trial["role"],
        "expected_positive": trial["role"] == "matching_positive",
        "proposal": proposal,
        "speech_active": speech_active,
        "mouth_active": mouth_active,
        "spatial_supported": spatial_supported,
        "synchrony_status": synchrony_status,
        "synchrony_reason": synchrony_reason,
        "correlation": correlation,
        "lag_ms": lag_ms,
        "baselines": baselines,
    }


def _evaluate_setting(
    spec: SynchronySpec,
    smoothing: int,
    spatial: float,
    loaded: list[tuple[dict[str, Any], JointPilotInput, dict[str, Any]]],
) -> dict[str, Any]:
    trials = [
        _trial_features(trial, data, quality, spec, smoothing, spatial)
        for trial, data, quality in loaded
    ]
    development = [trial for trial in trials if trial["split"] == "development"]
    positives = [trial for trial in development if trial["role"] == "matching_positive"]
    negatives = [trial for trial in development if trial["role"] in NEGATIVE_ROLES]
    positive_count = sum(trial["proposal"] for trial in positives)
    negative_count = sum(trial["proposal"] for trial in negatives)
    quality_passed = all(
        quality["passed"]
        for trial, _, quality in loaded
        if trial["split"] == "development"
    )
    return {
        "synchrony_spec": asdict(spec),
        "moving_average_samples": smoothing,
        "maximum_median_spatial_error_deg": spatial,
        "development_positive_proposals": positive_count,
        "development_positive_trials": len(positives),
        "development_negative_proposals": negative_count,
        "development_negative_trials": len(negatives),
        "development_quality_passed": quality_passed,
        "eligible": quality_passed and negative_count == 0 and positive_count >= 3,
        "trials": trials,
    }


def _selection_key(setting: dict[str, Any]) -> tuple[float, ...]:
    spec = setting["synchrony_spec"]
    return (
        float(setting["development_positive_proposals"]),
        float(spec["min_correlation"]),
        -float(setting["maximum_median_spatial_error_deg"]),
        -float(spec["max_abs_lag_ms"]),
        -float(setting["moving_average_samples"]),
    )


def _metrics(trials: list[dict[str, Any]], key: str) -> dict[str, Any]:
    predictions = [bool(trial["baselines"][key]) for trial in trials]
    labels = [bool(trial["expected_positive"]) for trial in trials]
    pairs = list(zip(predictions, labels, strict=True))
    tp = sum(prediction and label for prediction, label in pairs)
    fp = sum(prediction and not label for prediction, label in pairs)
    tn = sum(not prediction and not label for prediction, label in pairs)
    fn = sum(not prediction and label for prediction, label in pairs)
    return {
        "true_positive": tp,
        "false_positive": fp,
        "true_negative": tn,
        "false_negative": fn,
        "proposal_fraction": sum(predictions) / len(predictions) if predictions else None,
        "positive_recall": tp / (tp + fn) if tp + fn else None,
        "negative_rejection": tn / (tn + fp) if tn + fp else None,
    }


def analyze_joint_pilot(input_dir: Path) -> dict[str, Any]:
    """Select on development only, then evaluate internal validation once."""

    root = input_dir.resolve()
    binding = _binding_context(root)
    loaded: list[tuple[dict[str, Any], JointPilotInput, dict[str, Any]]] = []
    sources: list[dict[str, str]] = []
    for trial in randomized_joint_pilot_trials():
        data = load_joint_pilot_trial(root, trial)
        quality = assess_joint_pilot_quality(trial, data)
        loaded.append((trial, data, quality))
        for suffix in (".csv", ".metadata.json"):
            path = root / f"{trial['trial_id']}{suffix}"
            sources.append({"file": path.name, "sha256": _sha256(path)})

    development_loaded = [item for item in loaded if item[0]["split"] == "development"]
    validation_loaded = [item for item in loaded if item[0]["split"] == "internal_validation"]
    settings = [
        _evaluate_setting(spec, smoothing, spatial, development_loaded)
        for spec, smoothing, spatial in joint_pilot_candidate_specs()
    ]
    eligible = [setting for setting in settings if setting["eligible"]]
    selected = max(eligible, key=_selection_key) if eligible else None
    validation = None
    baselines = None
    if selected is not None:
        selected_spec = SynchronySpec(**selected["synchrony_spec"])
        validation_trials = [
            _trial_features(
                trial,
                data,
                quality,
                selected_spec,
                int(selected["moving_average_samples"]),
                float(selected["maximum_median_spatial_error_deg"]),
            )
            for trial, data, quality in validation_loaded
        ]
        positives = [trial for trial in validation_trials if trial["role"] == "matching_positive"]
        negatives = [trial for trial in validation_trials if trial["role"] in NEGATIVE_ROLES]
        quality_passed = all(
            quality["passed"]
            for _, _, quality in validation_loaded
        )
        positive_count = sum(trial["proposal"] for trial in positives)
        negative_count = sum(trial["proposal"] for trial in negatives)
        validation = {
            "quality_passed": quality_passed,
            "positive_proposals": positive_count,
            "positive_trials": len(positives),
            "negative_proposals": negative_count,
            "negative_trials": len(negatives),
            "passed": bool(
                quality_passed
                and positive_count == 2
                and negative_count == 0
            ),
            "trials": validation_trials,
        }
        evaluated_trials = [*selected["trials"], *validation_trials]
        baselines = {
            split: {
                name: _metrics(
                    [trial for trial in evaluated_trials if trial["split"] == split],
                    name,
                )
                for name in evaluated_trials[0]["baselines"]
            }
            for split in ("development", "internal_validation")
        }

    if selected is None:
        status = "PILOT_REJECTED_NO_DEVELOPMENT_SETTING"
    elif not validation or not validation["passed"]:
        status = "PILOT_CANDIDATE_FAILED_INTERNAL_VALIDATION"
    else:
        status = "PILOT_PASSED_INTERNAL_VALIDATION_NOT_CONFIRMATION"
    bundle = "\n".join(f"{item['file']}:{item['sha256']}" for item in sources).encode("utf-8")
    return {
        "schema": "reachy-joint-shadow-no-motion-pilot-result-v1",
        "status": status,
        "protocol_fingerprint": joint_pilot_protocol_payload()["fingerprint"],
        "execution_fingerprint": binding["execution_fingerprint"],
        "binding_manifest_sha256": binding["binding_manifest_sha256"],
        "source_bundle_sha256": hashlib.sha256(bundle).hexdigest(),
        "sources": sources,
        "trial_quality": [quality for _, _, quality in loaded],
        "candidate_count": len(settings),
        "eligible_development_candidate_count": len(eligible),
        "selected_candidate": selected,
        "internal_validation": validation,
        "internal_validation_passed": bool(validation and validation["passed"]),
        "baseline_metrics": baselines,
        "all_candidates": [
            {key: value for key, value in setting.items() if key != "trials"}
            for setting in settings
        ],
        "robot_connections": 0,
        "actuation_commands": 0,
        "response_commands": 0,
        "claim_boundary": (
            "A pass is an engineering pilot result in one bound setup. It is not "
            "confirmation, safe-motion evidence, speaker identity, liveness, or "
            "end-to-end robot validation."
        ),
    }
