"""Privacy-preserving source-validity experiment using endpoint metadata only.

The model operates at whole-trial level.  It never receives audio, images,
video, transcripts or semantic content.  Its output is deliberately
abstaining: a positive score is evidence that a trial resembles the controlled
live-human development trials, not proof that a human is present.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from statistics import mean, median
from typing import Iterable

from .angles import percentile
from .config import DATA_DIR
from .replay import ReplayObservation, load_replay


FEATURE_NAMES = (
    "speech_rate",
    "speech_bursts_per_s",
    "longest_speech_run_fraction",
    "speech_transition_rate_hz",
    "positive_angle_mad_norm",
    "positive_angle_iqr_norm",
    "positive_step_median_norm",
    "positive_step_p90_norm",
)
LIVE_HUMAN = "LIVE_HUMAN"
NON_LIVE = "NON_LIVE"
LIVE_LIKELY = "LIVE_LIKELY"
NON_LIVE_LIKELY = "NON_LIVE_LIKELY"
ABSTAIN_NO_EVIDENCE = "ABSTAIN_NO_EVIDENCE"
ABSTAIN_AMBIGUOUS = "ABSTAIN_AMBIGUOUS"
MIN_SPEECH_SAMPLES = 2


@dataclass(slots=True, frozen=True)
class TrialFeatures:
    file: str
    ground_truth: str
    group: str
    valid_samples: int
    speech_samples: int
    duration_s: float
    speech_rate: float
    speech_bursts_per_s: float
    longest_speech_run_fraction: float
    speech_transition_rate_hz: float
    positive_angle_mad_norm: float
    positive_angle_iqr_norm: float
    positive_step_median_norm: float
    positive_step_p90_norm: float

    def vector(self) -> tuple[float, ...]:
        return tuple(float(getattr(self, name)) for name in FEATURE_NAMES)


@dataclass(slots=True, frozen=True)
class SourceValidityModel:
    version: int
    manifest_fingerprint: str
    training_split: str
    training_files: tuple[str, ...]
    feature_names: tuple[str, ...]
    means: tuple[float, ...]
    scales: tuple[float, ...]
    live_centroid: tuple[float, ...]
    non_live_centroid: tuple[float, ...]
    abstain_margin: float
    min_speech_samples: int
    development_cv_metrics: dict[str, float | int]
    model_fingerprint: str = ""

    def payload(self, include_fingerprint: bool = True) -> dict[str, object]:
        payload = asdict(self)
        payload["training_files"] = list(self.training_files)
        payload["feature_names"] = list(self.feature_names)
        for name in ("means", "scales", "live_centroid", "non_live_centroid"):
            payload[name] = [round(float(value), 12) for value in payload[name]]
        if not include_fingerprint:
            payload.pop("model_fingerprint", None)
        return payload


@dataclass(slots=True, frozen=True)
class SourceValidityDecision:
    decision: str
    live_similarity_score: float
    raw_margin: float
    reason: str


def source_ground_truth(entry: dict[str, object]) -> str:
    """Return protocol truth; never infer truth from endpoint observations."""
    plan_id = entry.get("plan_id")
    label = str(entry.get("label") or "").lower()
    if plan_id == "non-speech-confusion" or label == "silence":
        return NON_LIVE
    return LIVE_HUMAN


def source_group(entry: dict[str, object]) -> str:
    return f"{entry.get('plan_id') or 'standalone'}:{entry.get('label') or 'unknown'}"


def _runs(flags: Iterable[bool]) -> list[int]:
    lengths: list[int] = []
    current = 0
    for flag in flags:
        if flag:
            current += 1
        elif current:
            lengths.append(current)
            current = 0
    if current:
        lengths.append(current)
    return lengths


def extract_trial_features(
    entry: dict[str, object], observations: tuple[ReplayObservation, ...] | None = None
) -> TrialFeatures:
    observations = observations or load_replay(DATA_DIR / str(entry["file"]))
    valid = [item for item in observations if item.valid]
    if observations:
        duration_s = max(0.2, (observations[-1].elapsed_ms - observations[0].elapsed_ms) / 1000.0)
    else:
        duration_s = 0.2
    flags = [item.speech_detected is True for item in valid]
    speech = [item for item in valid if item.speech_detected is True and item.angle_deg is not None]
    angles = [float(item.angle_deg) for item in speech]
    run_lengths = _runs(flags)
    transitions = sum(left != right for left, right in zip(flags, flags[1:]))
    steps: list[float] = []
    previous: ReplayObservation | None = None
    for item in valid:
        if item.speech_detected is True and item.angle_deg is not None:
            if (
                previous is not None
                and previous.speech_detected is True
                and previous.angle_deg is not None
                and item.elapsed_ms - previous.elapsed_ms <= 600.0
            ):
                steps.append(abs(float(item.angle_deg) - float(previous.angle_deg)))
        previous = item
    centre = median(angles) if angles else 0.0
    mad = median(abs(value - centre) for value in angles) if angles else 0.0
    q10 = percentile(angles, 0.10) or 0.0
    q90 = percentile(angles, 0.90) or 0.0
    return TrialFeatures(
        file=str(entry["file"]),
        ground_truth=source_ground_truth(entry),
        group=source_group(entry),
        valid_samples=len(valid),
        speech_samples=len(speech),
        duration_s=duration_s,
        speech_rate=len(speech) / len(valid) if valid else 0.0,
        speech_bursts_per_s=len(run_lengths) / duration_s,
        longest_speech_run_fraction=max(run_lengths, default=0) / len(valid) if valid else 0.0,
        speech_transition_rate_hz=transitions / duration_s,
        positive_angle_mad_norm=mad / 90.0,
        positive_angle_iqr_norm=max(0.0, q90 - q10) / 180.0,
        positive_step_median_norm=(median(steps) if steps else 0.0) / 180.0,
        positive_step_p90_norm=(percentile(steps, 0.90) or 0.0) / 180.0,
    )


def _fit_parameters(rows: list[TrialFeatures]) -> tuple[tuple[float, ...], ...]:
    eligible = [row for row in rows if row.speech_samples >= MIN_SPEECH_SAMPLES]
    if not eligible:
        raise ValueError("No speech-positive development trials are available.")
    if {row.ground_truth for row in eligible} != {LIVE_HUMAN, NON_LIVE}:
        raise ValueError("Both live-human and non-live development classes are required.")
    columns = list(zip(*(row.vector() for row in eligible)))
    means = tuple(mean(column) for column in columns)
    scales = tuple(
        max(0.02, math.sqrt(sum((value - centre) ** 2 for value in column) / len(column)))
        for column, centre in zip(columns, means)
    )

    def standardise(row: TrialFeatures) -> tuple[float, ...]:
        return tuple((value - centre) / scale for value, centre, scale in zip(row.vector(), means, scales))

    live = [standardise(row) for row in eligible if row.ground_truth == LIVE_HUMAN]
    non_live = [standardise(row) for row in eligible if row.ground_truth == NON_LIVE]
    live_centroid = tuple(mean(column) for column in zip(*live))
    non_live_centroid = tuple(mean(column) for column in zip(*non_live))
    return means, scales, live_centroid, non_live_centroid


def _raw_margin(
    row: TrialFeatures,
    means: tuple[float, ...],
    scales: tuple[float, ...],
    live_centroid: tuple[float, ...],
    non_live_centroid: tuple[float, ...],
) -> float:
    vector = tuple((value - centre) / scale for value, centre, scale in zip(row.vector(), means, scales))
    live_distance = mean((value - centre) ** 2 for value, centre in zip(vector, live_centroid))
    non_live_distance = mean((value - centre) ** 2 for value, centre in zip(vector, non_live_centroid))
    return non_live_distance - live_distance


def _decision_from_margin(raw_margin: float, abstain_margin: float) -> str:
    if raw_margin > abstain_margin:
        return LIVE_LIKELY
    if raw_margin < -abstain_margin:
        return NON_LIVE_LIKELY
    return ABSTAIN_AMBIGUOUS


def decision_metrics(rows: list[dict[str, object]]) -> dict[str, float | int]:
    live = [row for row in rows if row["ground_truth"] == LIVE_HUMAN]
    non_live = [row for row in rows if row["ground_truth"] == NON_LIVE]
    decided = [row for row in rows if row["decision"] in {LIVE_LIKELY, NON_LIVE_LIKELY}]

    def rate(items: list[dict[str, object]], decision: str) -> float:
        return 100.0 * sum(row["decision"] == decision for row in items) / len(items) if items else 0.0

    correct = sum(
        (row["ground_truth"] == LIVE_HUMAN and row["decision"] == LIVE_LIKELY)
        or (row["ground_truth"] == NON_LIVE and row["decision"] == NON_LIVE_LIKELY)
        for row in decided
    )
    return {
        "trials": len(rows),
        "live_trials": len(live),
        "non_live_trials": len(non_live),
        "coverage_pct": round(100.0 * len(decided) / len(rows), 3) if rows else 0.0,
        "selective_accuracy_pct": round(100.0 * correct / len(decided), 3) if decided else 0.0,
        "live_acceptance_pct": round(rate(live, LIVE_LIKELY), 3),
        "live_rejection_pct": round(rate(live, NON_LIVE_LIKELY), 3),
        "live_abstention_pct": round(100.0 - rate(live, LIVE_LIKELY) - rate(live, NON_LIVE_LIKELY), 3),
        "non_live_rejection_pct": round(rate(non_live, NON_LIVE_LIKELY), 3),
        "false_human_acceptance_pct": round(rate(non_live, LIVE_LIKELY), 3),
        "non_live_abstention_pct": round(100.0 - rate(non_live, LIVE_LIKELY) - rate(non_live, NON_LIVE_LIKELY), 3),
    }


def _cross_validated_rows(rows: list[TrialFeatures], abstain_margin: float) -> list[dict[str, object]]:
    predictions: list[dict[str, object]] = []
    for held_group in sorted({row.group for row in rows}):
        training = [row for row in rows if row.group != held_group]
        held = [row for row in rows if row.group == held_group]
        parameters = _fit_parameters(training)
        for row in held:
            if row.speech_samples < MIN_SPEECH_SAMPLES:
                decision, raw = ABSTAIN_NO_EVIDENCE, 0.0
            else:
                raw = _raw_margin(row, *parameters)
                decision = _decision_from_margin(raw, abstain_margin)
            predictions.append({
                "file": row.file,
                "group": row.group,
                "ground_truth": row.ground_truth,
                "decision": decision,
                "raw_margin": raw,
            })
    return predictions


def select_development_margin(rows: list[TrialFeatures]) -> tuple[float, dict[str, float | int]]:
    candidates = [index / 10.0 for index in range(0, 31)]
    evaluated: list[tuple[float, dict[str, float | int]]] = []
    for margin in candidates:
        metrics = decision_metrics(_cross_validated_rows(rows, margin))
        evaluated.append((margin, metrics))
    safe = [
        item for item in evaluated
        if float(item[1]["false_human_acceptance_pct"]) == 0.0
        and float(item[1]["live_rejection_pct"]) == 0.0
    ]
    pool = safe or evaluated
    # Safety-first operating point: among thresholds with no observed cross-validated
    # false-human acceptance and no live-human rejection, retain maximum coverage.
    selected = max(
        pool,
        key=lambda item: (
            float(item[1]["coverage_pct"]),
            float(item[1]["non_live_rejection_pct"]),
            float(item[1]["live_acceptance_pct"]),
            -item[0],
        ),
    )
    return selected


def _fingerprint(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def fit_development_model(manifest: dict[str, object]) -> tuple[SourceValidityModel, list[dict[str, object]]]:
    entries = [entry for entry in manifest["entries"] if entry.get("split") == "development"]
    rows = [extract_trial_features(entry) for entry in entries]
    margin, cv_metrics = select_development_margin(rows)
    parameters = _fit_parameters(rows)
    cv_rows = _cross_validated_rows(rows, margin)
    model = SourceValidityModel(
        version=1,
        manifest_fingerprint=str(manifest["fingerprint"]),
        training_split="development only",
        training_files=tuple(sorted(row.file for row in rows)),
        feature_names=FEATURE_NAMES,
        means=parameters[0],
        scales=parameters[1],
        live_centroid=parameters[2],
        non_live_centroid=parameters[3],
        abstain_margin=margin,
        min_speech_samples=MIN_SPEECH_SAMPLES,
        development_cv_metrics=cv_metrics,
    )
    fingerprint = _fingerprint(model.payload(include_fingerprint=False))
    model = SourceValidityModel(**{**model.payload(include_fingerprint=False), "training_files": model.training_files,
                                   "feature_names": model.feature_names, "means": model.means, "scales": model.scales,
                                   "live_centroid": model.live_centroid, "non_live_centroid": model.non_live_centroid,
                                   "model_fingerprint": fingerprint})
    return model, cv_rows


def predict_source(model: SourceValidityModel, features: TrialFeatures) -> SourceValidityDecision:
    if features.speech_samples < model.min_speech_samples:
        return SourceValidityDecision(
            ABSTAIN_NO_EVIDENCE, 0.5, 0.0,
            "Fewer than two speech-positive endpoint samples; source type is unobservable.",
        )
    raw = _raw_margin(
        features, model.means, model.scales, model.live_centroid, model.non_live_centroid
    )
    decision = _decision_from_margin(raw, model.abstain_margin)
    clipped = max(-60.0, min(60.0, raw))
    score = 1.0 / (1.0 + math.exp(-clipped))
    if decision == LIVE_LIKELY:
        reason = "Endpoint dynamics resemble the controlled live-human development trials. This is not identity proof."
    elif decision == NON_LIVE_LIKELY:
        reason = "Endpoint dynamics resemble the controlled non-live development trials."
    else:
        reason = "Live-human and non-live endpoint dynamics overlap; abstain rather than force a label."
    return SourceValidityDecision(decision, score, raw, reason)


def model_from_payload(payload: dict[str, object]) -> SourceValidityModel:
    return SourceValidityModel(
        version=int(payload["version"]),
        manifest_fingerprint=str(payload["manifest_fingerprint"]),
        training_split=str(payload["training_split"]),
        training_files=tuple(str(item) for item in payload["training_files"]),
        feature_names=tuple(str(item) for item in payload["feature_names"]),
        means=tuple(float(item) for item in payload["means"]),
        scales=tuple(float(item) for item in payload["scales"]),
        live_centroid=tuple(float(item) for item in payload["live_centroid"]),
        non_live_centroid=tuple(float(item) for item in payload["non_live_centroid"]),
        abstain_margin=float(payload["abstain_margin"]),
        min_speech_samples=int(payload["min_speech_samples"]),
        development_cv_metrics=dict(payload["development_cv_metrics"]),
        model_fingerprint=str(payload["model_fingerprint"]),
    )


def validate_model(model: SourceValidityModel, manifest: dict[str, object]) -> list[str]:
    problems: list[str] = []
    development_files = sorted(
        str(entry["file"]) for entry in manifest["entries"] if entry.get("split") == "development"
    )
    evaluation_files = {
        str(entry["file"]) for entry in manifest["entries"] if entry.get("split") == "evaluation"
    }
    if model.manifest_fingerprint != manifest.get("fingerprint"):
        problems.append("Model manifest fingerprint does not match frozen evidence.")
    if model.training_split != "development only":
        problems.append("Model training split is not development only.")
    if list(model.training_files) != development_files:
        problems.append("Model training files do not exactly match the development split.")
    if evaluation_files & set(model.training_files):
        problems.append("Evaluation file leaked into model training.")
    expected = _fingerprint(model.payload(include_fingerprint=False))
    if model.model_fingerprint != expected:
        problems.append("Model fingerprint does not match frozen parameters.")
    if model.feature_names != FEATURE_NAMES:
        problems.append("Model feature schema is not recognized.")
    return problems
