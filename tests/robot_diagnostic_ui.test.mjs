import assert from "node:assert/strict";
import { test } from "node:test";
import { diagnosticSignals, diagnosticStartFailures, diagnosticSummary } from "../tools/robot_diagnostic_ui.mjs";
import { conditionFailures } from "../tools/robot_pilot_ui.mjs";

const face = { count: 1, scale: 0.081, robotHeading: -6 };
const ready = { modelReady: true, cameraFresh: true, face, performanceFailures: [],
  microphoneMatches: true, audioRunning: true, confirmed: true, captured: false, recording: false };

test("reported screenshot is recordable diagnostically, still blocked for pilot", () => {
  const doa = { valid: true, axis_deg: 77, speech_detected: false };
  const observation = diagnosticSignals(face, doa, 181);
  assert.deepEqual(observation.codes, ["SPEECH_NOT_DETECTED"]);
  assert.equal(observation.directionUsable, false);
  assert.equal(observation.error, null);
  assert.deepEqual(diagnosticStartFailures(ready), []);
  assert.equal(conditionFailures({ condition_id: "spatial_conflict" }, face, { singleFraction: 1 }, doa).length, 2);
});

test("unexpected speech direction is a diagnostic observation, not a start gate", () => {
  const observation = diagnosticSignals(face, { valid: true, axis_deg: 77, speech_detected: true }, 181);
  assert.equal(observation.error, 19);
  assert.deepEqual(observation.codes, ["MEASURED_CONFLICT_BELOW_40_DEG"]);
  assert.deepEqual(diagnosticStartFailures(ready), []);
});

test("missing, stale or nonnumeric DoA cannot turn into a trusted direction", () => {
  for (const doa of [null, { valid: false }, { valid: true, axis_deg: 150, speech_detected: true }]) {
    assert.equal(diagnosticSignals(face, doa, 900).directionUsable, false);
  }
  assert.equal(diagnosticSignals(face, { valid: true, axis_deg: null, speech_detected: true }, 100).error, null);
  assert.equal(diagnosticSignals(face, { valid: true, axis_deg: 77, speech_detected: true }, 100, 650, false).directionUsable, false);
});

test("technical setup, confirmation, stop and completed capture still block", () => {
  for (const change of [{ modelReady: false }, { cameraFresh: false }, { face: null },
    { microphoneMatches: false }, { audioRunning: false }, { confirmed: false },
    { captured: true }, { recording: true }, { performanceFailures: ["low fps"] }]) {
    assert.ok(diagnosticStartFailures({ ...ready, ...change }).length, JSON.stringify(change));
  }
});

test("summary distinguishes detector negatives from missing observations", () => {
  assert.deepEqual(diagnosticSummary([
    { diagnostic_doa_fresh: true, doa_speech_detected: false },
    { diagnostic_doa_fresh: false, doa_speech_detected: true },
    { diagnostic_doa_fresh: true, doa_speech_detected: true, diagnostic_direction_usable: true, diagnostic_direction_error_deg: 19 },
  ]), { telemetry_rows: 3, fresh_doa_rows: 2, speech_detected_rows: 1,
    direction_usable_rows: 1, below_40_deg_rows: 1,
    note: "Counts are repeated telemetry samples, not independent observations or a pilot result." });
});
