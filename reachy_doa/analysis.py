"""Local-only validation and statistical comparison of DoA trial files."""

from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import median

import pandas as pd

from .angles import doa_radians_to_degrees, percentile, physical_heading_to_expected_doa
from .config import DATA_DIR
from .decisions import disposition_for


SUMMARY_COLUMNS = [
    "run_id", "file", "condition", "true_position_deg", "expected_doa_deg",
    "sample_count", "valid_count", "invalid_count", "valid_rate_pct",
    "speech_positive_count", "speech_positive_rate_pct", "median_doa_deg",
    "median_abs_error_deg", "median_latency_ms", "p95_latency_ms",
    "duration_seconds", "coordinate_source", "disposition", "status", "findings",
]


def _bool_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().eq("true")


def _metadata_for(csv_path: Path) -> dict[str, object]:
    metadata_path = csv_path.with_name(f"{csv_path.stem}_metadata.json")
    if not metadata_path.exists():
        return {}
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def analyse_frame(
    frame: pd.DataFrame,
    metadata: dict[str, object] | None = None,
    filename: str = "in-memory",
) -> dict[str, object]:
    metadata = metadata or {}
    sample_count = len(frame)
    findings: list[str] = []
    if sample_count == 0:
        return {column: None for column in SUMMARY_COLUMNS} | {
            "run_id": str(metadata.get("run_id", "unknown")),
            "file": filename,
            "sample_count": 0,
            "valid_count": 0,
            "invalid_count": 0,
            "status": "INVALID",
            "findings": "No samples were recorded.",
        }

    valid_mask = _bool_series(frame["valid"]) if "valid" in frame else pd.Series(False, index=frame.index)
    valid = frame[valid_mask].copy()
    valid_count = len(valid)
    invalid_count = sample_count - valid_count
    valid_rate = 100.0 * valid_count / sample_count

    coordinate_source = "raw_angle_rad · Reachy v1.9 0–180°"
    if "raw_angle_rad" in valid:
        radians = pd.to_numeric(valid["raw_angle_rad"], errors="coerce")
        valid["analysis_doa_deg"] = radians.map(
            lambda value: doa_radians_to_degrees(value) if pd.notna(value) else math.nan
        )
    else:
        coordinate_source = "legacy raw_angle_deg"
        valid["analysis_doa_deg"] = pd.to_numeric(valid.get("raw_angle_deg"), errors="coerce")

    legacy_negative = False
    if "raw_angle_deg" in valid:
        recorded_degrees = pd.to_numeric(valid["raw_angle_deg"], errors="coerce")
        legacy_negative = bool((recorded_degrees < 0).any())
    if legacy_negative:
        findings.append("Legacy CSV degree column wraps the right edge negative; analysis used raw radians.")

    speech_mask = _bool_series(valid["speech_detected"]) if "speech_detected" in valid else pd.Series(False, index=valid.index)
    speech = valid[speech_mask]
    speech_count = len(speech)
    speech_rate = 100.0 * speech_count / valid_count if valid_count else 0.0
    doa_values = pd.to_numeric(speech.get("analysis_doa_deg"), errors="coerce").dropna().tolist()
    median_doa = median(doa_values) if doa_values else None

    true_position = metadata.get("true_position_deg")
    if true_position is None and "true_position_deg" in frame:
        positions = pd.to_numeric(frame["true_position_deg"], errors="coerce").dropna()
        true_position = float(positions.iloc[0]) if not positions.empty else None
    try:
        true_position = float(true_position) if true_position is not None else None
    except (TypeError, ValueError):
        true_position = None
    expected_doa = physical_heading_to_expected_doa(true_position) if true_position is not None else None
    errors = [abs(value - expected_doa) for value in doa_values] if expected_doa is not None else []
    median_abs_error = median(errors) if errors else None

    latencies = pd.to_numeric(valid.get("http_latency_ms"), errors="coerce").dropna().tolist()
    median_latency = percentile(latencies, 0.5)
    p95_latency = percentile(latencies, 0.95)
    elapsed = pd.to_numeric(frame.get("elapsed_ms"), errors="coerce").dropna()
    duration = (float(elapsed.max()) / 1000.0) if not elapsed.empty else 0.0
    condition = str(metadata.get("condition") or (frame["condition"].iloc[0] if "condition" in frame else ""))
    run_id = str(metadata.get("run_id") or (frame["run_id"].iloc[0] if "run_id" in frame else Path(filename).stem))

    if invalid_count:
        findings.append(f"{invalid_count} invalid or missing HTTP responses.")
    if valid_rate < 95.0:
        findings.append("Valid response rate is below 95%.")
    condition_lower = condition.lower()
    non_speech_condition = any(
        token in condition_lower
        for token in ("silence", "clap", "keys", "music", "television", "tone", "mechanical", "phone playback")
    )
    guided = metadata.get("guided_trial", {})
    guided = guided if isinstance(guided, dict) else {}
    is_single_phrase_calibration = (
        guided.get("plan_id") == "direction-calibration"
        and float(guided.get("duration_target_seconds", 0.0)) == 6.0
    )
    if "silence" in condition_lower and speech_rate > 5.0:
        findings.append(f"Unexpected speech-positive rate during silence: {speech_rate:.1f}%.")
    elif non_speech_condition and speech_rate > 20.0:
        findings.append(f"Speech flag activated for non-speech input: {speech_rate:.1f}%.")
    elif is_single_phrase_calibration and valid_count and speech_rate < 15.0:
        findings.append(f"Low speech-positive rate for one-phrase calibration: {speech_rate:.1f}%.")
    elif not non_speech_condition and not is_single_phrase_calibration and valid_count and speech_rate < 40.0:
        findings.append(f"Low speech-positive rate for intended speech: {speech_rate:.1f}%.")
    if median_abs_error is not None and median_abs_error > 20.0:
        findings.append(f"Median directional error exceeds 20°: {median_abs_error:.1f}°.")
    if p95_latency is not None and p95_latency > 200.0:
        findings.append(f"P95 HTTP latency exceeds 200 ms: {p95_latency:.1f} ms.")
    if speech_count < 3 and not non_speech_condition:
        findings.append("Fewer than three speech-positive samples; direction estimate is weak.")

    status = "PASS" if not findings else "FLAG"
    if valid_count == 0:
        status = "INVALID"
        findings.append("No valid endpoint responses.")

    disposition = disposition_for(filename)
    if disposition == "standalone" and guided.get("plan_id"):
        disposition = "unreviewed"
    return {
        "run_id": run_id,
        "file": filename,
        "condition": condition,
        "true_position_deg": true_position,
        "expected_doa_deg": expected_doa,
        "sample_count": sample_count,
        "valid_count": valid_count,
        "invalid_count": invalid_count,
        "valid_rate_pct": round(valid_rate, 2),
        "speech_positive_count": speech_count,
        "speech_positive_rate_pct": round(speech_rate, 2),
        "median_doa_deg": round(median_doa, 2) if median_doa is not None else None,
        "median_abs_error_deg": round(median_abs_error, 2) if median_abs_error is not None else None,
        "median_latency_ms": round(median_latency, 2) if median_latency is not None else None,
        "p95_latency_ms": round(p95_latency, 2) if p95_latency is not None else None,
        "duration_seconds": round(duration, 2),
        "coordinate_source": coordinate_source,
        "disposition": disposition,
        "status": status,
        "findings": " ".join(findings) if findings else "No automatic threshold was exceeded.",
    }


def analyse_csv(csv_path: Path) -> dict[str, object]:
    resolved = csv_path.resolve()
    if resolved.parent != DATA_DIR and DATA_DIR not in resolved.parents:
        raise ValueError("Analysis is restricted to the project data folder.")
    frame = pd.read_csv(resolved)
    return analyse_frame(frame, _metadata_for(resolved), resolved.name)


def analyse_all(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    resolved = data_dir.resolve()
    if resolved != DATA_DIR and DATA_DIR not in resolved.parents:
        raise ValueError("Analysis is restricted to the project data folder.")
    rows = [analyse_csv(path) for path in sorted(resolved.glob("*.csv"))]
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def write_analysis_artifacts(data_dir: Path = DATA_DIR) -> tuple[Path, Path]:
    resolved = data_dir.resolve()
    if resolved != DATA_DIR and DATA_DIR not in resolved.parents:
        raise ValueError("Analysis artifacts must remain inside the project data folder.")
    output_dir = (resolved / "analysis").resolve()
    if DATA_DIR not in output_dir.parents:
        raise ValueError("Analysis artifacts must remain inside the project data folder.")
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = analyse_all(resolved)
    csv_path = output_dir / "latest_trial_summary.csv"
    md_path = output_dir / "latest_trial_summary.md"
    summary.to_csv(csv_path, index=False)
    display = summary.fillna("—")
    selected = [
        "run_id", "condition", "disposition", "valid_rate_pct", "speech_positive_rate_pct",
        "median_abs_error_deg", "median_latency_ms", "p95_latency_ms", "status", "findings",
    ]
    markdown_lines = [
        "| " + " | ".join(selected) + " |",
        "| " + " | ".join("---" for _ in selected) + " |",
    ]
    for row in display[selected].itertuples(index=False, name=None):
        cells = [str(value).replace("|", "\\|").replace("\n", " ") for value in row]
        markdown_lines.append("| " + " | ".join(cells) + " |")
    md_path.write_text(
        "# Reachy Acoustic Lab — automatic trial summary\n\n"
        "Generated locally from sensor metadata. Threshold flags are screening signals, not diagnoses.\n\n"
        + "\n".join(markdown_lines)
        + "\n",
        encoding="utf-8",
    )
    return csv_path, md_path
