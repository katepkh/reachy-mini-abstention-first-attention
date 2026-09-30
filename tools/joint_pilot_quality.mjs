"use strict";

// Browser-side mirror of reachy_stage3v.joint_pilot_analysis.assess_joint_pilot_quality.
// It is deliberately pure so the same frozen fixtures can verify both implementations.

const VISIBLE_CONDITIONS = new Set([
  "live_visible_continuous",
  "live_visible_interrupted",
  "silent_face_phone_playback",
  "silent_mouthing_unrelated_playback",
  "visible_silence",
  "spatial_conflict",
]);
const SPEECH_REQUIRED_CONDITIONS = new Set([
  "live_visible_continuous",
  "live_visible_interrupted",
  "silent_face_phone_playback",
  "silent_mouthing_unrelated_playback",
  "speech_without_usable_face",
  "spatial_conflict",
]);
const MOUTH_MOTION_REQUIRED_CONDITIONS = new Set([
  "live_visible_continuous",
  "live_visible_interrupted",
  "silent_mouthing_unrelated_playback",
]);

function mean(values) {
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0;
}

function stddev(values) {
  if (!values.length) return 0;
  const average = mean(values);
  return Math.sqrt(mean(values.map(value => (value - average) ** 2)));
}

function percentile(values, fraction) {
  if (!values.length) return null;
  const ordered = [...values].sort((first, second) => first - second);
  const position = (ordered.length - 1) * fraction;
  const lower = Math.floor(position);
  const upper = Math.ceil(position);
  const part = position - lower;
  return ordered[lower] * (1 - part) + ordered[upper] * part;
}

function wrapDegrees(angle) {
  const wrapped = ((angle + 180) % 360 + 360) % 360 - 180;
  return Object.is(wrapped, -0) ? 0 : wrapped;
}

function circularDistance(first, second) {
  return Math.abs(wrapDegrees(first - second));
}

function spatialError(row) {
  if (Number(row.face_count) !== 1 || row.doa_valid !== true) return null;
  const face = Number(row.face_heading_estimate_deg);
  const doa = Number(row.doa_axis_deg);
  if (!Number.isFinite(face) || !Number.isFinite(doa) || doa < 0 || doa > 180) return null;
  const first = wrapDegrees(90 - doa);
  const second = wrapDegrees(180 - first);
  return Math.min(circularDistance(face, first), circularDistance(face, second));
}

export function assessPilotQuality(trial, rows, gates) {
  const conditionId = String(trial.condition_id);
  const timestamps = rows.map(row => Number(row.timestamp_ms));
  const gaps = timestamps.slice(1).map((value, index) => value - timestamps[index]);
  const span = rows.length >= 2 ? timestamps.at(-1) - timestamps[0] : 0;
  const maximumGap = Math.max(0, ...gaps);
  const singleRows = rows.filter(row => Number(row.face_count) === 1);
  const singleFaceFraction = singleRows.length / Math.max(rows.length, 1);
  const multipleFaceRows = rows.filter(row => Number(row.face_count) > 1).length;
  const faceScales = singleRows.map(row => Number(row.face_scale)).filter(Number.isFinite);
  const medianFaceScale = VISIBLE_CONDITIONS.has(conditionId)
    ? (percentile(faceScales, .5) ?? 0)
    : null;
  const doaValidFraction = rows.filter(row => row.doa_valid === true).length / Math.max(rows.length, 1);
  const doaSpeechFraction = rows.filter(row => row.doa_speech_detected === true).length / Math.max(rows.length, 1);
  const doaAges = rows.map(row => row.doa_age_ms).filter(value => Number.isFinite(value));
  const p95DoaAge = percentile(doaAges, .95);
  const audioStd = stddev(rows.map(row => Number(row.audio_dbfs)));
  const lipStd = stddev(singleRows.map(row => Number(row.lip_aperture)));
  const spatialErrors = rows.map(spatialError).filter(value => value !== null);
  const medianSpatialError = percentile(spatialErrors, .5);
  const failures = [];

  if (rows.length < gates.minimum_samples) failures.push("INSUFFICIENT_SAMPLES");
  if (rows.length < 2 || gaps.some(gap => gap <= 0)) failures.push("TIMESTAMPS_NOT_STRICTLY_INCREASING");
  if (span < gates.minimum_span_ms) failures.push("SPAN_TOO_SHORT");
  if (maximumGap > gates.maximum_sample_gap_ms) failures.push("SAMPLE_GAP_EXCESSIVE");
  if (doaValidFraction < gates.minimum_doa_valid_fraction) failures.push("DOA_AVAILABILITY_TOO_LOW");
  if (p95DoaAge === null || p95DoaAge > gates.maximum_p95_doa_age_ms) failures.push("DOA_AGE_TOO_HIGH");
  if (multipleFaceRows > gates.multiple_face_rows_allowed) failures.push("MULTIPLE_FACES_OBSERVED");

  if (VISIBLE_CONDITIONS.has(conditionId)) {
    if (singleFaceFraction < gates.minimum_single_face_fraction_when_required) failures.push("SINGLE_FACE_FRACTION_TOO_LOW");
    if (medianFaceScale < gates.minimum_median_face_scale_when_required) failures.push("FACE_SCALE_TOO_SMALL");
  } else if (singleFaceFraction > gates.maximum_usable_face_fraction_for_unavailable_face_control) {
    failures.push("USABLE_FACE_PRESENT_IN_UNAVAILABLE_CONTROL");
  }

  if (SPEECH_REQUIRED_CONDITIONS.has(conditionId)) {
    if (audioStd < gates.minimum_audio_dbfs_std_when_speech_required) failures.push("AUDIO_DYNAMIC_RANGE_TOO_LOW");
    if (doaSpeechFraction < gates.minimum_doa_speech_fraction_when_speech_required) failures.push("SPEECH_ACTIVITY_TOO_LOW");
  } else if (doaSpeechFraction > gates.maximum_doa_speech_fraction_for_visible_silence) {
    failures.push("SPEECH_ACTIVITY_TOO_HIGH_FOR_SILENCE");
  }

  if (MOUTH_MOTION_REQUIRED_CONDITIONS.has(conditionId) && lipStd < gates.minimum_lip_aperture_std_when_motion_required) {
    failures.push("LIP_DYNAMIC_RANGE_TOO_LOW");
  }
  if (conditionId === "spatial_conflict" && (medianSpatialError === null || medianSpatialError < gates.minimum_spatial_conflict_deg)) {
    failures.push("SPATIAL_CONFLICT_NOT_REALIZED");
  }

  return {
    trial_id: trial.trial_id,
    condition_id: conditionId,
    split: trial.split,
    role: trial.role,
    passed: failures.length === 0,
    failures,
    sample_count: rows.length,
    span_ms: span,
    maximum_sample_gap_ms: maximumGap,
    single_face_fraction: singleFaceFraction,
    multiple_face_rows: multipleFaceRows,
    median_face_scale: medianFaceScale,
    doa_valid_fraction: doaValidFraction,
    doa_speech_fraction: doaSpeechFraction,
    p95_doa_age_ms: p95DoaAge,
    audio_dbfs_std: audioStd,
    lip_aperture_std: lipStd,
    median_spatial_error_deg: medianSpatialError,
  };
}
