"""Freeze and evaluate the metadata-only source-validity experiment."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .config import DATA_DIR
from .manifest import FROZEN_MANIFEST, load_manifest, validate_manifest
from .source_validity import (
    SourceValidityModel,
    decision_metrics,
    extract_trial_features,
    fit_development_model,
    model_from_payload,
    predict_source,
    validate_model,
)


MODEL_DIR = (DATA_DIR / "models").resolve()
MODEL_PATH = (MODEL_DIR / "source_validity_v1.json").resolve()
ANALYSIS_DIR = (DATA_DIR / "analysis").resolve()
DEV_CV_PATH = (ANALYSIS_DIR / "source_validity_development_cv_v1.csv").resolve()
EVAL_PATH = (ANALYSIS_DIR / "source_validity_evaluation_v1.csv").resolve()
SUMMARY_PATH = (ANALYSIS_DIR / "source_validity_summary_v1.json").resolve()
REPORT_PATH = (ANALYSIS_DIR / "source_validity_report_v1.md").resolve()


def write_frozen_development_model(path: Path = MODEL_PATH) -> tuple[SourceValidityModel, Path, Path]:
    if path.exists():
        raise FileExistsError("Source-validity model is already frozen; validate it instead of replacing it.")
    manifest = load_manifest(FROZEN_MANIFEST)
    problems = validate_manifest(FROZEN_MANIFEST)
    if problems:
        raise ValueError("Frozen evidence failed validation: " + "; ".join(problems))
    model, cv_rows = fit_development_model(manifest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(model.payload(), indent=2, ensure_ascii=False), encoding="utf-8")
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(cv_rows).to_csv(DEV_CV_PATH, index=False)
    return model, path, DEV_CV_PATH


def load_frozen_model(path: Path = MODEL_PATH) -> SourceValidityModel:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Frozen source-validity model is malformed.")
    return model_from_payload(payload)


def evaluate_frozen_model(
    model_path: Path = MODEL_PATH,
) -> tuple[pd.DataFrame, dict[str, dict[str, float | int]], SourceValidityModel]:
    manifest = load_manifest(FROZEN_MANIFEST)
    model = load_frozen_model(model_path)
    problems = validate_model(model, manifest)
    if problems:
        raise ValueError("Frozen model failed validation: " + "; ".join(problems))
    rows: list[dict[str, object]] = []
    for entry in manifest["entries"]:
        if entry.get("split") != "evaluation":
            continue
        features = extract_trial_features(entry)
        decision = predict_source(model, features)
        rows.append({
            "file": features.file,
            "plan_id": entry.get("plan_id") or "standalone",
            "label": entry.get("label") or "unknown",
            "repetition": entry.get("repetition"),
            "ground_truth": features.ground_truth,
            "decision": decision.decision,
            "live_similarity_score": round(decision.live_similarity_score, 6),
            "raw_margin": round(decision.raw_margin, 6),
            "valid_samples": features.valid_samples,
            "speech_samples": features.speech_samples,
            **{name: getattr(features, name) for name in model.feature_names},
            "reason": decision.reason,
        })
    frame = pd.DataFrame(rows)
    development_cv = dict(model.development_cv_metrics)
    evaluation = decision_metrics(frame.to_dict("records"))
    return frame, {"development_group_cv": development_cv, "held_out_evaluation": evaluation}, model


def write_source_evaluation_artifacts() -> tuple[Path, Path, Path]:
    frame, summary, model = evaluate_frozen_model()
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    frame.to_csv(EVAL_PATH, index=False)
    payload = {
        "version": 1,
        "model_fingerprint": model.model_fingerprint,
        "manifest_fingerprint": model.manifest_fingerprint,
        "training_split": model.training_split,
        "scope": "Held-out repetitions of known controlled conditions; not novel-source generalization.",
        **summary,
    }
    SUMMARY_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    dev = summary["development_group_cv"]
    held = summary["held_out_evaluation"]
    REPORT_PATH.write_text(
        "# Reachy Mini metadata-only source-validity experiment v1\n\n"
        "This offline experiment uses only saved DoA, `speech_detected`, timing and validity metadata. "
        "It stores no audio, images, video or transcripts and makes no robot or cloud request.\n\n"
        "## Guardrail\n\n"
        f"The model was fitted only on {len(model.training_files)} development trials. Its frozen model "
        f"fingerprint is `{model.model_fingerprint}`. Evaluation consists of held-out repetitions of known "
        "controlled conditions; it does not establish generalization to novel sounds, rooms or operators.\n\n"
        "## Development leave-one-condition-group-out cross-validation\n\n"
        f"- Coverage: {dev['coverage_pct']}%\n"
        f"- Selective accuracy: {dev['selective_accuracy_pct']}%\n"
        f"- False-human acceptance: {dev['false_human_acceptance_pct']}%\n"
        f"- Live-human rejection: {dev['live_rejection_pct']}%\n"
        f"- Live-human abstention: {dev['live_abstention_pct']}%\n\n"
        "## Locked held-out evaluation\n\n"
        f"- Trials: {held['trials']} ({held['live_trials']} live-human, {held['non_live_trials']} non-live)\n"
        f"- Coverage: {held['coverage_pct']}%\n"
        f"- Selective accuracy: {held['selective_accuracy_pct']}%\n"
        f"- False-human acceptance: {held['false_human_acceptance_pct']}%\n"
        f"- Live-human rejection: {held['live_rejection_pct']}%\n"
        f"- Live-human abstention: {held['live_abstention_pct']}%\n"
        f"- Non-live rejection: {held['non_live_rejection_pct']}%\n"
        f"- Non-live abstention: {held['non_live_abstention_pct']}%\n\n"
        "## Interpretation\n\n"
        "`LIVE_LIKELY` means only that endpoint dynamics resemble this laboratory's controlled live-human "
        "development trials. It is not proof of a person, identity or intent. High overlap or abstention is "
        "evidence that the metadata endpoint alone is not sufficiently observable for source semantics.\n",
        encoding="utf-8",
    )
    return EVAL_PATH, SUMMARY_PATH, REPORT_PATH
