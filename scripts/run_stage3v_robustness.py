#!/usr/bin/env python3
"""Write/check deterministic exploratory Stage 3V trial-level analyses."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any

from reachy_stage3v.robustness import build_robustness_report


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "evidence" / "analysis"
JSON_PATH = OUTPUT_DIR / "stage3v_trial_robustness_v1.json"
REPORT_PATH = OUTPUT_DIR / "stage3v_trial_robustness_v1.md"
ABLATION_PATH = OUTPUT_DIR / "stage3v_trial_robustness_v1_ablations.csv"
SENSITIVITY_PATH = OUTPUT_DIR / "stage3v_trial_robustness_v1_sensitivity.csv"
OPERATING_POINTS_PATH = OUTPUT_DIR / "stage3v_trial_robustness_v1_operating_points.csv"
SIDECAR_PATH = JSON_PATH.with_suffix(JSON_PATH.suffix + ".sha256")


def _pct(value: float) -> str:
    return f"{100.0 * value:.1f}%"


def _interval(value: list[float]) -> str:
    return f"{_pct(value[0])}–{_pct(value[1])}"


def _number(value: Any, digits: int = 0) -> str:
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}"


def render_markdown(report: dict[str, Any]) -> str:
    full = next(item for item in report["ablations"] if item["policy"] == "full_frozen_v3")
    sensitivity = {
        (item["parameter"], float(item["value"])): item
        for item in report["one_at_a_time_sensitivity"]
    }
    lines = [
        "# Stage 3V exploratory trial-level robustness",
        "",
        "> **Status:** post-hoc exploratory replay. The frozen V3 result was held out, but this analysis plan was written after those results were known. It does not authorize motion.",
        "",
        "## The honest headline",
        "",
        f"The frozen policy proposed a target in **{full['positive_trials_with_proposal']}/{full['positive_trials']}** matching trials and **{full['hard_negative_trials_with_proposal']}/{full['hard_negative_trials']}** hard-negative trials. At the trial level, the nominal 95% Wilson intervals are **{_interval(full['positive_coverage_wilson95'])}** for positive coverage and **{_interval(full['hard_negative_false_proposal_wilson95'])}** for the hard-negative false-proposal rate.",
        "",
        "The intervals—not the perfect sample fractions—are the useful caution. Six negative trials are compatible with a substantially larger underlying false-proposal rate. All frames inside one trial are correlated and are not treated as independent evidence.",
        "",
        "## Diagnostic ablations",
        "",
        "| Replay policy | Positive trial coverage | Hard-negative trial proposals | Selective risk among proposed trials | Median first proposal | Max target error |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for item in report["ablations"]:
        risk = item["selective_risk_given_proposal"]
        lines.append(
            f"| `{item['policy']}` | {item['positive_trials_with_proposal']}/{item['positive_trials']} ({_pct(item['positive_coverage'])}) | "
            f"{item['hard_negative_trials_with_proposal']}/{item['hard_negative_trials']} ({_pct(item['hard_negative_false_proposal_rate'])}) | "
            f"{_pct(risk) if risk is not None else '—'} | {_number(item['median_positive_first_proposal_latency_ms'])} ms | "
            f"{_number(item['maximum_positive_target_error_deg'], 3)}° |"
        )
    lines.extend(
        [
            "",
            "Definitions:",
            "",
            "- `full_frozen_v3`: the published V3 policy, unchanged.",
            "- `single_frame_audio_visual`: the same policy with one hit instead of three; this isolates temporal consensus.",
            "- `audio_visual_without_speech_gate`: the same policy with every row counterfactually marked speech-positive; this isolates the VAD latch.",
            "- `visual_only_temporal`: calibrated face direction plus three-hit temporal consensus; no acoustic evidence.",
            "- `audio_only_front_hypothesis`: the front acoustic hypothesis plus speech latch and three-hit consensus; it encodes a front-hemisphere assumption.",
            "",
            "These baselines were defined after data collection, are not matched for information or complexity, and cannot establish causal component importance.",
            "",
            "## Threshold sensitivity",
            "",
            "The machine-readable JSON and CSV files replay one parameter at a time around the frozen point and a 25-point grid over geometry tolerance (6°–14°) and required hits (1–5). These are finite operating points on this dataset, not a calibrated population risk–coverage curve.",
            "",
            f"- One required hit retained 12/12 positive coverage but produced proposals in {sensitivity[('required_hits', 1.0)]['hard_negative_trials_with_proposal']}/6 hard negatives. Four hits reduced coverage to {sensitivity[('required_hits', 4.0)]['positive_trials_with_proposal']}/12; five reduced it to {sensitivity[('required_hits', 5.0)]['positive_trials_with_proposal']}/12.",
            f"- Tightening the geometry envelope from the frozen 10° to 6° reduced positive coverage to {sensitivity[('maximum_geometry_error_deg', 6.0)]['positive_trials_with_proposal']}/12; 8°–14° retained 12/12 and 0/6 at the other frozen settings.",
            f"- Removing the speech latch reduced positive coverage to {sensitivity[('speech_latch_ms', 0.0)]['positive_trials_with_proposal']}/12; 400 ms produced {sensitivity[('speech_latch_ms', 400.0)]['positive_trials_with_proposal']}/12, and 800–1600 ms produced 12/12 on this sample.",
            "- Tested face-offset, consensus-window, heading-tolerance, and disagreement-lockout alternatives did not change trial-level proposal counts at the other frozen settings. That flatness may reflect coarse outcomes and limited conditions, not genuine invariance.",
            "",
            "Leave-one-trial-out deletion is also reported. It measures arithmetic fragility of this small dataset; because it reuses the same site and session, it is not evidence of external generalization.",
            "",
            "## Reproduce",
            "",
            "```bash",
            "python scripts/run_stage3v_robustness.py --check",
            "```",
            "",
            f"The accepted source bundle is content-addressed as `{report['source_bundle_sha256']}`. Exact per-file hashes are in the JSON.",
            "",
            "## Claim boundary",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in report["interpretation_limits"])
    return "\n".join(lines) + "\n"


def render_csv(rows: list[dict[str, Any]]) -> bytes:
    if not rows:
        raise ValueError("Cannot render an empty analysis table.")
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        flattened = {
            key: json.dumps(value, sort_keys=True, separators=(",", ":")) if isinstance(value, (list, dict)) else value
            for key, value in row.items()
        }
        writer.writerow(flattened)
    return stream.getvalue().encode("utf-8")


def render_all() -> dict[Path, bytes]:
    report = build_robustness_report()
    json_bytes = json.dumps(report, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    return {
        JSON_PATH: json_bytes,
        REPORT_PATH: render_markdown(report).encode("utf-8"),
        ABLATION_PATH: render_csv(report["ablations"]),
        SENSITIVITY_PATH: render_csv(report["one_at_a_time_sensitivity"]),
        OPERATING_POINTS_PATH: render_csv(report["risk_coverage_operating_points"]),
        SIDECAR_PATH: f"{hashlib.sha256(json_bytes).hexdigest()}  {JSON_PATH.name}\n".encode("ascii"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    artifacts = render_all()
    if args.write:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        for path, content in artifacts.items():
            path.write_bytes(content)
        print(f"Wrote {len(artifacts)} deterministic Stage 3V robustness artifacts.")
        return 0
    stale = [path.relative_to(PROJECT_ROOT) for path, content in artifacts.items() if not path.is_file() or path.read_bytes() != content]
    if stale:
        print("FAIL: missing or stale Stage 3V robustness artifacts:")
        for path in stale:
            print(f"- {path}")
        return 1
    print("PASS: Stage 3V trial-level robustness artifacts are current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
