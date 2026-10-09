// Separate direction audit. No fitting, calibration, pilot state or commands.
export const POSITIONS = Object.freeze([
  Object.freeze({ id: "front", label: "FRONT", heading_left_positive_deg: 0, expected_axis_deg: 90 }),
  Object.freeze({ id: "left60", label: "60° to Reachy's LEFT", heading_left_positive_deg: 60, expected_axis_deg: 30 }),
  Object.freeze({ id: "right60", label: "60° to Reachy's RIGHT", heading_left_positive_deg: -60, expected_axis_deg: 150 }),
]);

export function directionSignals(position, face, doa, ageMs, maxAgeMs = 650, faceFresh = true) {
  const fresh = Boolean(doa?.valid) && Number.isFinite(ageMs) && ageMs >= 0 && ageMs <= maxAgeMs;
  const angleValid = Number.isFinite(doa?.axis_deg) && doa.axis_deg >= 0 && doa.axis_deg <= 180;
  const usable = fresh && angleValid && doa.speech_detected === true;
  const faceUsable = usable && faceFresh && face?.count === 1 && Number.isFinite(face.robotHeading);
  const codes = [];
  if (!fresh) codes.push("DOA_MISSING_OR_STALE");
  else {
    if (!angleValid) codes.push("DOA_ANGLE_INVALID");
    if (doa.speech_detected !== true) codes.push("SPEECH_NOT_DETECTED");
  }
  if (!faceFresh || face?.count !== 1) codes.push("FACE_MISSING_OR_STALE");
  const bearing = usable ? 90 - doa.axis_deg : null;
  const wrap = a => ((a + 180) % 360 + 360) % 360 - 180;
  const separation = faceUsable ? Math.min(...[bearing, wrap(180 - bearing)]
    .map(a => Math.abs(wrap(face.robotHeading - a)))) : null;
  return { fresh, usable, bearing, separation, codes,
    expectedError: usable ? doa.axis_deg - position.expected_axis_deg : null };
}

function median(values) {
  if (!values.length) return null;
  const v = [...values].sort((a, b) => a - b), n = v.length;
  return n % 2 ? v[(n - 1) / 2] : (v[n / 2 - 1] + v[n / 2]) / 2;
}

export function directionSummary(rows) {
  const usable = rows.filter(r => r.direction_usable === true && Number.isFinite(r.doa_axis_deg));
  const axes = usable.map(r => r.doa_axis_deg), center = median(axes);
  return { telemetry_rows: rows.length, fresh_doa_rows: rows.filter(r => r.direction_doa_fresh).length,
    speech_direction_rows: usable.length, median_raw_axis_deg: center,
    raw_axis_min_deg: axes.length ? Math.min(...axes) : null,
    raw_axis_max_deg: axes.length ? Math.max(...axes) : null,
    raw_axis_median_absolute_deviation_deg: center === null ? null : median(axes.map(a => Math.abs(a - center))),
    median_expected_axis_error_deg: median(usable.map(r => r.expected_axis_error_deg).filter(Number.isFinite)),
    note: "Speech-active fresh samples only for direction statistics; correlated telemetry, not independent trials. Descriptive only: no calibration fit or pass/fail." };
}

export function newJournal(sessionId) {
  return { schema: "reachy-direction-journal-v1", session_id: sessionId,
    records: [], in_progress: null, stopped: false, horizontal_distance_cm: null };
}

export function validateJournal(journal) {
  if (journal?.schema !== "reachy-direction-journal-v1" || typeof journal.session_id !== "string" ||
      !Array.isArray(journal.records) || journal.records.length > 3 || typeof journal.stopped !== "boolean")
    throw Error("Invalid saved direction session. Stop and request review; do not clear it to repeat captures.");
  for (const [i, record] of journal.records.entries()) {
    if (record.position_id !== POSITIONS[i].id || typeof record.csv !== "string" ||
        typeof record.metadata !== "string" || typeof record.base !== "string")
      throw Error("Saved direction sequence is invalid; stop for review.");
  }
  return journal;
}

export function claimPosition(journal, positionIndex, captureId, distanceCm) {
  validateJournal(journal);
  if (journal.stopped || journal.in_progress || positionIndex !== journal.records.length || positionIndex >= 3)
    throw Error("This position was already started or the session is stopped. Reload for saved files; do not repeat it.");
  if (!Number.isFinite(distanceCm) || distanceCm <= 0) throw Error("Enter the measured horizontal phone distance in centimetres.");
  if (journal.horizontal_distance_cm !== null && journal.horizontal_distance_cm !== distanceCm)
    throw Error("Keep the same phone distance for all three positions.");
  return { ...journal, horizontal_distance_cm: distanceCm,
    in_progress: { position_id: POSITIONS[positionIndex].id, capture_id: captureId } };
}

export function finishPosition(journal, record, complete) {
  validateJournal(journal);
  if (!journal.in_progress || journal.in_progress.position_id !== record.position_id ||
      journal.in_progress.capture_id !== JSON.parse(record.metadata).diagnostic_id)
    throw Error("Capture does not match the reserved position. Stop for review.");
  return { ...journal, records: [...journal.records, record], in_progress: null, stopped: !complete };
}
