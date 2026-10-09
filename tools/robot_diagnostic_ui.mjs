// Diagnostic-only observations. None of these warnings disables capture.
export function diagnosticSignals(face, doa, ageMs, maxAgeMs = 650, faceFresh = true) {
  const fresh = Boolean(doa?.valid) && Number.isFinite(ageMs) && ageMs <= maxAgeMs;
  const speech = fresh && doa.speech_detected === true;
  const directionUsable = speech && faceFresh && face?.count === 1 &&
    Number.isFinite(face.robotHeading) && Number.isFinite(doa.axis_deg);
  let error = null;
  const codes = [];
  if (!fresh) codes.push("DOA_MISSING_OR_STALE");
  else if (!speech) codes.push("SPEECH_NOT_DETECTED");
  if (!faceFresh || face?.count !== 1) codes.push("FACE_MISSING_OR_STALE");
  if (directionUsable) {
    const wrap = x => ((x + 180) % 360 + 360) % 360 - 180;
    const first = wrap(90 - doa.axis_deg), second = wrap(180 - first);
    error = Math.min(Math.abs(wrap(face.robotHeading - first)), Math.abs(wrap(face.robotHeading - second)));
    if (error < 40) codes.push("MEASURED_CONFLICT_BELOW_40_DEG");
  }
  return { fresh, directionUsable, error, codes };
}

export function diagnosticStartFailures({ modelReady, cameraFresh, face, performanceFailures,
  microphoneMatches, audioRunning, confirmed, captured, recording }) {
  const failures = [...performanceFailures];
  if (!modelReady) failures.push("initialize the landmark model");
  if (!cameraFresh) failures.push("wait for fresh Reachy camera frames");
  if (face?.count !== 1 || !Number.isFinite(face?.scale) || face.scale < 0.06)
    failures.push("keep one usable face visible to Reachy");
  if (!microphoneMatches || !audioRunning) failures.push("enable the matching laptop microphone");
  if (!confirmed) failures.push("confirm the playback setup below");
  if (captured) failures.push("diagnostic finished; send both files for review");
  if (recording) failures.push("diagnostic capture in progress");
  return failures;
}

export function diagnosticSummary(rows) {
  const valid = rows.filter(r => r.diagnostic_doa_fresh);
  const usable = rows.filter(r => r.diagnostic_direction_usable);
  return { telemetry_rows: rows.length, fresh_doa_rows: valid.length,
    speech_detected_rows: valid.filter(r => r.doa_speech_detected === true).length,
    direction_usable_rows: usable.length,
    below_40_deg_rows: usable.filter(r => r.diagnostic_direction_error_deg < 40).length,
    note: "Counts are repeated telemetry samples, not independent observations or a pilot result." };
}
