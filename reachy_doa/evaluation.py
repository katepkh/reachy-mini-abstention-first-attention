"""Deterministic policy comparison on the frozen offline evidence split."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .analysis import analyse_csv
from .confidence import ReliabilityEnvelope, fit_reliability_envelope
from .config import DATA_DIR
from .manifest import FROZEN_MANIFEST, load_manifest, validate_manifest
from .policies import make_policies, run_policy
from .replay import load_replay


ANALYSIS_DIR = (DATA_DIR / "analysis").resolve()
POLICY_COMPARISON_CSV = ANALYSIS_DIR / "shadow_policy_comparison_v1.csv"
TRIAL_METRICS_CSV = ANALYSIS_DIR / "shadow_trial_metrics_v1.csv"
POLICY_REPORT_MD = ANALYSIS_DIR / "shadow_policy_evaluation_v1.md"
RELIABILITY_JSON = ANALYSIS_DIR / "shadow_reliability_v1.json"


def reliability_from_manifest(manifest: dict[str, object]) -> ReliabilityEnvelope:
    entries = manifest.get("entries", [])
    return fit_reliability_envelope([entry for entry in entries if isinstance(entry, dict)])


def trajectory_frame(entry: dict[str, object], policy_name: str, reliability: ReliabilityEnvelope) -> pd.DataFrame:
    observations = load_replay(DATA_DIR / str(entry["file"]))
    policies = {policy.name: policy for policy in make_policies(reliability)}
    if policy_name not in policies:
        raise ValueError(f"Unknown shadow policy: {policy_name}")
    decisions = run_policy(policies[policy_name], observations)
    rows = []
    for observation, decision in zip(observations, decisions):
        rows.append(
            {
                "file": entry["file"],
                "sequence": observation.sequence,
                "elapsed_ms": observation.elapsed_ms,
                "observed_angle_deg": observation.angle_deg,
                "speech_detected": observation.speech_detected,
                "valid": observation.valid,
                "latency_ms": observation.latency_ms,
                "state": decision.state,
                "axis_deg": decision.axis_deg,
                "hypothesis_a_deg": decision.hypothesis_a_deg,
                "hypothesis_b_deg": decision.hypothesis_b_deg,
                "confidence": decision.confidence,
                "valid_rate": decision.valid_rate,
                "speech_evidence": decision.speech_evidence,
                "stability": decision.stability,
                "reliability_prior": decision.reliability_prior,
                "p95_latency_ms": decision.p95_latency_ms,
                "front_back_ambiguous": decision.front_back_ambiguous,
                "would_attend_axis": decision.would_attend_axis,
                "would_propose_physical_target": decision.would_propose_physical_target,
                "reason": decision.reason,
            }
        )
    return pd.DataFrame(rows)


def _rising_edges(values: list[bool]) -> int:
    count = 0
    previous = False
    for value in values:
        if value and not previous:
            count += 1
        previous = value
    return count


def _switches(frame: pd.DataFrame, threshold_deg: float = 20.0) -> int:
    axes = pd.to_numeric(frame.loc[frame["would_attend_axis"], "axis_deg"], errors="coerce").dropna().tolist()
    return sum(abs(current - previous) > threshold_deg for previous, current in zip(axes, axes[1:]))


def _duration_minutes(frame: pd.DataFrame) -> float:
    elapsed = pd.to_numeric(frame["elapsed_ms"], errors="coerce").dropna()
    if elapsed.empty:
        return 0.0
    return max(0.001, (float(elapsed.max()) - float(elapsed.min())) / 60000.0)


def evaluate_trial(
    entry: dict[str, object], policy_name: str, reliability: ReliabilityEnvelope
) -> dict[str, object]:
    frame = trajectory_frame(entry, policy_name, reliability)
    summary = analyse_csv(DATA_DIR / str(entry["file"]))
    duration_minutes = _duration_minutes(frame)
    plan_id = str(entry.get("plan_id") or "")
    label = str(entry.get("label") or "")
    non_live_challenge = plan_id == "non-speech-confusion" or "silence" in label
    static_source = plan_id in {
        "direction-calibration", "endfire-diagnostic", "orientation-swap-control"
    } or (plan_id == "front-back-ambiguity" and "only" in label)
    front_back_challenge = plan_id == "front-back-ambiguity"
    speech_rows = frame[(frame["valid"] == True) & (frame["speech_detected"] == True)]  # noqa: E712
    attention_values = frame["would_attend_axis"].astype(bool).tolist()
    false_triggers = _rising_edges(attention_values) if non_live_challenge else 0
    switch_count = _switches(frame) if static_source else 0
    first_speech = speech_rows["elapsed_ms"].min() if not speech_rows.empty else None
    attended_after = frame[
        (frame["would_attend_axis"] == True)  # noqa: E712
        & (frame["elapsed_ms"] >= first_speech if first_speech is not None else False)
    ]
    acquisition = (
        float(attended_after["elapsed_ms"].min() - first_speech)
        if first_speech is not None and not attended_after.empty else None
    )
    tracking_coverage = (
        100.0 * float(speech_rows["would_attend_axis"].mean()) if not speech_rows.empty else 0.0
    )
    abstain_states = {"ABSTAIN", "CANDIDATE", "COMPETING_SOURCES", "NETWORK_DEGRADED"}
    abstention = (
        100.0 * float(speech_rows["state"].isin(abstain_states).mean()) if not speech_rows.empty else 0.0
    )
    ambiguous_rows = frame[frame["front_back_ambiguous"] == True]  # noqa: E712
    unresolved = (
        100.0 * float((ambiguous_rows["would_propose_physical_target"] == False).mean())  # noqa: E712
        if front_back_challenge and not ambiguous_rows.empty else None
    )
    expected = summary.get("expected_doa_deg")
    attended_axes = pd.to_numeric(
        frame.loc[frame["would_attend_axis"], "axis_deg"], errors="coerce"
    ).dropna()
    axis_error = (
        float((attended_axes - float(expected)).abs().median())
        if expected is not None and not attended_axes.empty else None
    )
    invalid_rows = frame[frame["valid"] == False]  # noqa: E712
    network_recall = (
        100.0 * float(invalid_rows["state"].isin({"NETWORK_DEGRADED", "NETWORK_ERROR"}).mean())
        if not invalid_rows.empty else None
    )
    return {
        "policy": policy_name,
        "file": entry["file"],
        "plan_id": plan_id or "standalone",
        "label": label,
        "condition": entry.get("condition", ""),
        "duration_minutes": round(duration_minutes, 6),
        "valid_samples": int(frame["valid"].sum()),
        "speech_positive_samples": len(speech_rows),
        "axis_tracking_coverage_pct": round(tracking_coverage, 3),
        "abstention_pct": round(abstention, 3),
        "false_attention_triggers": false_triggers,
        "false_attention_triggers_per_min": round(false_triggers / duration_minutes, 3),
        "static_switches": switch_count,
        "static_switches_per_min": round(switch_count / duration_minutes, 3),
        "acquisition_delay_ms": round(acquisition, 3) if acquisition is not None else None,
        "median_axis_error_deg": round(axis_error, 3) if axis_error is not None else None,
        "ambiguous_correctly_unresolved_pct": round(unresolved, 3) if unresolved is not None else None,
        "network_error_recognition_pct": round(network_recall, 3) if network_recall is not None else None,
        "unsafe_physical_proposals": int(
            ((frame["front_back_ambiguous"] == True) & (frame["would_propose_physical_target"] == True)).sum()  # noqa: E712
        ),
        "non_live_challenge": non_live_challenge,
        "front_back_challenge": front_back_challenge,
        "static_source": static_source,
    }


def evaluate_manifest(path: Path = FROZEN_MANIFEST) -> tuple[pd.DataFrame, pd.DataFrame, ReliabilityEnvelope]:
    problems = validate_manifest(path)
    if problems:
        raise ValueError("Frozen evidence failed validation: " + "; ".join(problems))
    manifest = load_manifest(path)
    reliability = reliability_from_manifest(manifest)
    evaluation_entries = [
        entry for entry in manifest["entries"]
        if isinstance(entry, dict) and entry.get("split") == "evaluation"
    ]
    trial_rows: list[dict[str, object]] = []
    for entry in evaluation_entries:
        for policy in make_policies(reliability):
            trial_rows.append(evaluate_trial(entry, policy.name, reliability))
    trials = pd.DataFrame(trial_rows)
    policy_rows: list[dict[str, object]] = []
    for policy_name, group in trials.groupby("policy", sort=False):
        negative = group[group["non_live_challenge"] == True]  # noqa: E712
        static = group[group["static_source"] == True]  # noqa: E712
        ambiguous = group[group["front_back_challenge"] == True]  # noqa: E712
        total_negative_minutes = float(negative["duration_minutes"].sum())
        total_static_minutes = float(static["duration_minutes"].sum())
        acquisitions = pd.to_numeric(group["acquisition_delay_ms"], errors="coerce").dropna()
        errors = pd.to_numeric(group["median_axis_error_deg"], errors="coerce").dropna()
        unresolved = pd.to_numeric(ambiguous["ambiguous_correctly_unresolved_pct"], errors="coerce").dropna()
        network = pd.to_numeric(group["network_error_recognition_pct"], errors="coerce").dropna()
        policy_rows.append(
            {
                "policy": policy_name,
                "evaluation_trials": len(group),
                "axis_tracking_coverage_pct": round(float(group["axis_tracking_coverage_pct"].mean()), 3),
                "abstention_pct": round(float(group["abstention_pct"].mean()), 3),
                "false_attention_triggers_per_min": round(
                    float(negative["false_attention_triggers"].sum()) / max(0.001, total_negative_minutes), 3
                ),
                "static_switches_per_min": round(
                    float(static["static_switches"].sum()) / max(0.001, total_static_minutes), 3
                ),
                "median_acquisition_delay_ms": round(float(acquisitions.median()), 3) if not acquisitions.empty else None,
                "median_axis_error_deg": round(float(errors.median()), 3) if not errors.empty else None,
                "ambiguous_correctly_unresolved_pct": round(float(unresolved.mean()), 3) if not unresolved.empty else None,
                "network_error_recognition_pct": round(float(network.mean()), 3) if not network.empty else None,
                "unsafe_physical_proposals": int(group["unsafe_physical_proposals"].sum()),
            }
        )
    return pd.DataFrame(policy_rows), trials, reliability


def write_evaluation_artifacts(path: Path = FROZEN_MANIFEST) -> tuple[Path, Path, Path, Path]:
    comparison, trials, reliability = evaluate_manifest(path)
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(POLICY_COMPARISON_CSV, index=False)
    trials.to_csv(TRIAL_METRICS_CSV, index=False)
    RELIABILITY_JSON.write_text(
        json.dumps(
            {
                "source_split": "development only",
                "method": "0.25 validity + 0.35 phrase coverage + 0.40 exp(-median_error/30°)",
                "axis_scores": reliability.as_dict(),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    selected = [
        "policy", "axis_tracking_coverage_pct", "abstention_pct",
        "false_attention_triggers_per_min", "static_switches_per_min",
        "median_acquisition_delay_ms", "median_axis_error_deg",
        "ambiguous_correctly_unresolved_pct", "unsafe_physical_proposals",
    ]
    lines = [
        "| " + " | ".join(selected) + " |",
        "| " + " | ".join("---" for _ in selected) + " |",
    ]
    for row in comparison[selected].fillna("—").itertuples(index=False, name=None):
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    POLICY_REPORT_MD.write_text(
        "# Reachy Mini offline shadow-attention evaluation v1\n\n"
        "The evaluation replays only frozen numerical DoA metadata. It sends no robot request. "
        "Evaluation files were not used to fit the directional reliability envelope.\n\n"
        + "\n".join(lines)
        + "\n\n`unsafe_physical_proposals` counts cases where a policy chose one side of an "
        "unresolved front/back pair. The confidence-aware controller may track an acoustic axis "
        "while still refusing to propose a physical target.\n",
        encoding="utf-8",
    )
    return POLICY_COMPARISON_CSV, TRIAL_METRICS_CSV, POLICY_REPORT_MD, RELIABILITY_JSON
