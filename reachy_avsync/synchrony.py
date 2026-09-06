"""Command-free numeric audio–mouth synchrony prototype.

The input is already-derived audio energy and mouth-motion values.  This file
cannot capture media, open a connection, identify a person, or command a robot.
Synchrony is treated as a candidate-association signal only.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Mapping, Sequence

import numpy as np


@dataclass(frozen=True, slots=True)
class NumericSeries:
    timestamps_ms: tuple[float, ...]
    values: tuple[float, ...]

    @classmethod
    def from_sequences(
        cls,
        timestamps_ms: Sequence[float],
        values: Sequence[float],
    ) -> "NumericSeries":
        return cls(tuple(float(item) for item in timestamps_ms), tuple(float(item) for item in values))


@dataclass(frozen=True, slots=True)
class SynchronySpec:
    """Exploratory engineering defaults; these are not calibrated thresholds."""

    min_samples: int = 30
    min_overlap_ms: float = 1200.0
    max_sample_gap_ms: float = 160.0
    resample_period_ms: float = 40.0
    max_abs_lag_ms: float = 240.0
    min_audio_std: float = 0.05
    min_mouth_std: float = 0.05
    min_correlation: float = 0.55
    min_face_margin: float = 0.08
    max_clock_drift_fraction: float = 0.03
    required_stable_windows: int = 3
    max_consensus_gap_ms: float = 800.0


@dataclass(frozen=True, slots=True)
class SynchronyScore:
    status: str
    reason: str
    correlation: float | None
    lag_ms: float | None
    aligned_samples: int
    overlap_ms: float

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SynchronyDecision:
    status: str
    reason: str
    candidate_face_id: str | None
    correlation: float | None
    lag_ms: float | None
    stable_windows: int = 0

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def audio_energy_envelope(
    waveform: Sequence[float],
    sample_rate_hz: float,
    *,
    frame_ms: float = 40.0,
    hop_ms: float = 40.0,
    start_ms: float = 0.0,
) -> NumericSeries:
    """Derive a local RMS-energy series from an already-loaded mono waveform."""

    values = np.asarray(waveform, dtype=float)
    if values.ndim != 1 or not np.isfinite(values).all():
        raise ValueError("The waveform must be one finite mono numeric sequence.")
    if sample_rate_hz <= 0.0 or frame_ms <= 0.0 or hop_ms <= 0.0:
        raise ValueError("Sample rate, frame length, and hop length must be positive.")
    frame = max(1, int(round(sample_rate_hz * frame_ms / 1000.0)))
    hop = max(1, int(round(sample_rate_hz * hop_ms / 1000.0)))
    if len(values) < frame:
        raise ValueError("The waveform is shorter than one energy frame.")
    timestamps: list[float] = []
    energy: list[float] = []
    for offset in range(0, len(values) - frame + 1, hop):
        chunk = values[offset : offset + frame]
        chunk = chunk - float(np.mean(chunk))
        energy.append(float(np.sqrt(np.mean(np.square(chunk)))))
        timestamps.append(float(start_ms + 1000.0 * (offset + frame / 2.0) / sample_rate_hz))
    return NumericSeries.from_sequences(timestamps, energy)


def mouth_motion_envelope(
    timestamps_ms: Sequence[float],
    upper_lip_xy: Sequence[Sequence[float]],
    lower_lip_xy: Sequence[Sequence[float]],
    face_scale: Sequence[float],
) -> NumericSeries:
    """Derive scale-normalized frame-to-frame lip-aperture change.

    Coordinates must already come from one consented local face track.  This
    helper performs no detection, media capture, storage, or identification.
    """

    timestamps = np.asarray(timestamps_ms, dtype=float)
    upper = np.asarray(upper_lip_xy, dtype=float)
    lower = np.asarray(lower_lip_xy, dtype=float)
    scale = np.asarray(face_scale, dtype=float)
    count = len(timestamps)
    if upper.shape != (count, 2) or lower.shape != (count, 2) or scale.shape != (count,):
        raise ValueError("Lip coordinates must be N×2 and face_scale must contain N values.")
    if count < 2 or not all(np.isfinite(item).all() for item in (timestamps, upper, lower, scale)):
        raise ValueError("Mouth motion requires at least two finite observations.")
    if (np.diff(timestamps) <= 0.0).any() or (scale <= 0.0).any():
        raise ValueError("Timestamps must increase and every face scale must be positive.")
    aperture = np.linalg.norm(upper - lower, axis=1) / scale
    motion = np.empty(count, dtype=float)
    motion[0] = 0.0
    motion[1:] = np.abs(np.diff(aperture))
    return NumericSeries.from_sequences(timestamps, motion)


def _validate_series(series: NumericSeries, label: str, spec: SynchronySpec) -> str | None:
    if len(series.timestamps_ms) != len(series.values):
        return f"{label.upper()}_LENGTH_MISMATCH"
    if len(series.values) < spec.min_samples:
        return f"{label.upper()}_INSUFFICIENT_SAMPLES"
    timestamps = np.asarray(series.timestamps_ms, dtype=float)
    values = np.asarray(series.values, dtype=float)
    if not np.isfinite(timestamps).all() or not np.isfinite(values).all():
        return f"{label.upper()}_NONFINITE"
    gaps = np.diff(timestamps)
    if (gaps <= 0.0).any():
        return f"{label.upper()}_TIMESTAMPS_NOT_STRICTLY_INCREASING"
    if float(gaps.max(initial=0.0)) > spec.max_sample_gap_ms:
        return f"{label.upper()}_SAMPLE_GAP_EXCESSIVE"
    return None


def _abstain(reason: str, overlap_ms: float = 0.0) -> SynchronyScore:
    return SynchronyScore("ABSTAIN", reason, None, None, 0, max(0.0, overlap_ms))


def evaluate_synchrony(
    audio_energy: NumericSeries,
    mouth_motion: NumericSeries,
    spec: SynchronySpec | None = None,
) -> SynchronyScore:
    """Score positive cross-correlation over a small bounded lag window."""

    spec = spec or SynchronySpec()
    for series, label in ((audio_energy, "audio"), (mouth_motion, "mouth")):
        issue = _validate_series(series, label, spec)
        if issue:
            return _abstain(issue)

    audio_t = np.asarray(audio_energy.timestamps_ms, dtype=float)
    mouth_t = np.asarray(mouth_motion.timestamps_ms, dtype=float)
    audio_v = np.asarray(audio_energy.values, dtype=float)
    mouth_v = np.asarray(mouth_motion.values, dtype=float)
    audio_span = float(audio_t[-1] - audio_t[0])
    mouth_span = float(mouth_t[-1] - mouth_t[0])
    span_denominator = max(audio_span, mouth_span, 1.0)
    if abs(audio_span - mouth_span) / span_denominator > spec.max_clock_drift_fraction:
        return _abstain("CLOCK_DRIFT_EXCESSIVE")

    start = max(float(audio_t[0]), float(mouth_t[0]))
    end = min(float(audio_t[-1]), float(mouth_t[-1]))
    overlap_ms = end - start
    if overlap_ms < spec.min_overlap_ms:
        return _abstain("OVERLAP_TOO_SHORT", overlap_ms)
    if float(np.std(audio_v)) < spec.min_audio_std:
        return _abstain("AUDIO_DYNAMIC_RANGE_TOO_LOW", overlap_ms)
    if float(np.std(mouth_v)) < spec.min_mouth_std:
        return _abstain("MOUTH_DYNAMIC_RANGE_TOO_LOW", overlap_ms)

    grid = np.arange(start, end + 0.5 * spec.resample_period_ms, spec.resample_period_ms)
    audio = np.interp(grid, audio_t, audio_v)
    mouth = np.interp(grid, mouth_t, mouth_v)
    max_shift = int(spec.max_abs_lag_ms // spec.resample_period_ms)
    best: tuple[float, int, int] | None = None
    for shift in range(-max_shift, max_shift + 1):
        if shift < 0:
            x = audio[-shift:]
            y = mouth[:shift]
        elif shift > 0:
            x = audio[:-shift]
            y = mouth[shift:]
        else:
            x = audio
            y = mouth
        if len(x) < spec.min_samples or float(np.std(x)) == 0.0 or float(np.std(y)) == 0.0:
            continue
        correlation = float(np.corrcoef(x, y)[0, 1])
        if not math.isfinite(correlation):
            continue
        candidate = (correlation, shift, len(x))
        if best is None or candidate[0] > best[0]:
            best = candidate
    if best is None:
        return _abstain("CORRELATION_UNAVAILABLE", overlap_ms)
    correlation, shift, aligned_samples = best
    lag_ms = shift * spec.resample_period_ms
    if correlation < spec.min_correlation:
        return SynchronyScore(
            "ABSTAIN",
            "CORRELATION_BELOW_EXPLORATORY_THRESHOLD",
            correlation,
            lag_ms,
            aligned_samples,
            overlap_ms,
        )
    return SynchronyScore(
        "CANDIDATE",
        "SYNCHRONY_CANDIDATE_NOT_IDENTITY",
        correlation,
        lag_ms,
        aligned_samples,
        overlap_ms,
    )


def select_face_candidate(
    audio_energy: NumericSeries,
    mouth_tracks: Mapping[str, NumericSeries],
    spec: SynchronySpec | None = None,
) -> SynchronyDecision:
    """Select at most one synchronous track, or abstain on weak/close scores."""

    spec = spec or SynchronySpec()
    if not mouth_tracks:
        return SynchronyDecision("ABSTAIN", "NO_FACE_TRACKS", None, None, None)
    scored = [
        (face_id, evaluate_synchrony(audio_energy, series, spec))
        for face_id, series in sorted(mouth_tracks.items())
    ]
    candidates = sorted(
        (
            (face_id, score)
            for face_id, score in scored
            if score.status == "CANDIDATE" and score.correlation is not None
        ),
        key=lambda item: (-float(item[1].correlation or -math.inf), item[0]),
    )
    if not candidates:
        reasons = ",".join(f"{face_id}:{score.reason}" for face_id, score in scored)
        return SynchronyDecision("ABSTAIN", f"NO_SYNCHRONOUS_FACE[{reasons}]", None, None, None)
    best_id, best = candidates[0]
    if len(candidates) > 1:
        second_id, second = candidates[1]
        assert best.correlation is not None and second.correlation is not None
        if best.correlation - second.correlation < spec.min_face_margin:
            return SynchronyDecision(
                "CONFLICT",
                f"SYNCHRONY_AMBIGUOUS[{best_id},{second_id}]",
                None,
                best.correlation,
                best.lag_ms,
            )
    return SynchronyDecision(
        "CANDIDATE",
        "SYNCHRONY_CANDIDATE_NOT_IDENTITY",
        best_id,
        best.correlation,
        best.lag_ms,
    )


class SynchronyConsensus:
    """Require stable face-track association across consecutive windows."""

    def __init__(self, spec: SynchronySpec | None = None) -> None:
        self.spec = spec or SynchronySpec()
        self._candidate: str | None = None
        self._hits = 0
        self._last_elapsed_ms: float | None = None

    def update(self, elapsed_ms: float, decision: SynchronyDecision) -> SynchronyDecision:
        elapsed_ms = float(elapsed_ms)
        stale = (
            self._last_elapsed_ms is not None
            and elapsed_ms - self._last_elapsed_ms > self.spec.max_consensus_gap_ms
        )
        self._last_elapsed_ms = elapsed_ms
        if stale or decision.status != "CANDIDATE" or decision.candidate_face_id is None:
            self._candidate = None
            self._hits = 0
            return SynchronyDecision(
                "ABSTAIN" if decision.status != "CONFLICT" else "CONFLICT",
                "CONSENSUS_RESET:" + decision.reason,
                None,
                decision.correlation,
                decision.lag_ms,
                0,
            )
        if decision.candidate_face_id != self._candidate:
            self._candidate = decision.candidate_face_id
            self._hits = 1
        else:
            self._hits += 1
        if self._hits < self.spec.required_stable_windows:
            return SynchronyDecision(
                "ABSTAIN",
                "SYNCHRONY_CONSENSUS_PENDING",
                None,
                decision.correlation,
                decision.lag_ms,
                self._hits,
            )
        return SynchronyDecision(
            "SUPPORTED_CANDIDATE",
            "STABLE_SYNCHRONY_CANDIDATE_NOT_IDENTITY",
            self._candidate,
            decision.correlation,
            decision.lag_ms,
            self._hits,
        )


def run_synthetic_fault_suite() -> dict[str, object]:
    """Exercise declared fail-closed cases with deterministic synthetic arrays."""

    spec = SynchronySpec()
    rng = np.random.default_rng(74021)
    count = 60
    timestamps = np.arange(count, dtype=float) * spec.resample_period_ms
    speech = rng.normal(0.0, 1.0, count)
    distractor = rng.normal(0.0, 1.0, count)
    audio = NumericSeries.from_sequences(timestamps, speech)
    aligned = NumericSeries.from_sequences(timestamps, speech + rng.normal(0.0, 0.05, count))
    unrelated = NumericSeries.from_sequences(timestamps, distractor)

    cases: list[dict[str, object]] = []

    def add(name: str, expected: str, decision: SynchronyScore | SynchronyDecision) -> None:
        observed = decision.status
        cases.append(
            {
                "name": name,
                "expected_status": expected,
                "observed_status": observed,
                "passed": observed == expected,
                "decision": decision.as_dict(),
            }
        )

    add("aligned_single_face", "CANDIDATE", evaluate_synchrony(audio, aligned, spec))
    silence = NumericSeries.from_sequences(timestamps, np.zeros(count))
    add("silence", "ABSTAIN", evaluate_synchrony(silence, aligned, spec))
    add("static_mouth", "ABSTAIN", evaluate_synchrony(audio, silence, spec))
    add("unrelated_motion", "ABSTAIN", evaluate_synchrony(audio, unrelated, spec))
    gapped_timestamps = timestamps.copy()
    gapped_timestamps[30:] += 300.0
    gapped = NumericSeries.from_sequences(gapped_timestamps, speech)
    add("stale_frame_gap", "ABSTAIN", evaluate_synchrony(audio, gapped, spec))
    drifted = NumericSeries.from_sequences(timestamps * 1.08, speech)
    add("clock_drift", "ABSTAIN", evaluate_synchrony(audio, drifted, spec))
    add(
        "two_equally_synchronous_faces",
        "CONFLICT",
        select_face_candidate(audio, {"face_a": aligned, "face_b": aligned}, spec),
    )
    mixed_audio = NumericSeries.from_sequences(timestamps, speech + distractor)
    face_a = NumericSeries.from_sequences(timestamps, speech)
    face_b = NumericSeries.from_sequences(timestamps, distractor)
    add(
        "overlapping_sources",
        "CONFLICT",
        select_face_candidate(mixed_audio, {"face_a": face_a, "face_b": face_b}, spec),
    )
    consensus = SynchronyConsensus(spec)
    a = SynchronyDecision("CANDIDATE", "synthetic", "face_a", 0.9, 0.0)
    b = SynchronyDecision("CANDIDATE", "synthetic", "face_b", 0.9, 0.0)
    consensus.update(0.0, a)
    consensus.update(200.0, a)
    switched = consensus.update(400.0, b)
    add("rapid_face_switch", "ABSTAIN", switched)
    return {
        "schema": "reachy-av-synchrony-synthetic-fault-suite-v1",
        "status": "OFFLINE_SYNTHETIC_ONLY_THRESHOLDS_UNCALIBRATED",
        "spec": asdict(spec),
        "cases": cases,
        "all_passed": all(bool(case["passed"]) for case in cases),
        "robot_connections": 0,
        "media_captures": 0,
        "actuation_commands": 0,
        "claim_boundary": "Synthetic behavior tests software branches; it does not validate real audiovisual association.",
    }
