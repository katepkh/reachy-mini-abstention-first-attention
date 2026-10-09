import assert from "node:assert/strict";
import { test } from "node:test";
import { pilotChecks, conditionFailures, microphoneBinding, sameMicrophone } from "../tools/robot_pilot_ui.mjs";

test("silence needs no speech while live trials do", () => {
  const face = { count: 1, scale: 0.1 };
  const performance = { singleFraction: 1 };
  const doa = { valid: true, speech_detected: false };
  assert.deepEqual(conditionFailures({ condition_id: "visible_silence" }, face, performance, doa), []);
  assert.equal(conditionFailures({ condition_id: "live_visible_continuous" }, face, performance, doa).length, 1);
});
test("unavailable-face control does not require a face", () => {
  const card = { condition_id: "speech_without_usable_face" };
  assert.equal(pilotChecks({}, card).minimum_single_face_fraction, 0);
  assert.deepEqual(conditionFailures(card, { count: 0 }, { singleFraction: 0 }, { valid: true, speech_detected: true }), []);
  assert.ok(conditionFailures(card, { count: 1 }, { singleFraction: 1 }, null).length);
});
test("conflict geometry is condition-specific", () => {
  const card = { condition_id: "spatial_conflict" }, face = { count: 1, scale: 0.1, robotHeading: 0 };
  assert.deepEqual(conditionFailures(card, face, { singleFraction: 1 }, { valid: true, axis_deg: 30, speech_detected: true }), []);
  assert.ok(conditionFailures(card, face, { singleFraction: 1 }, { valid: true, axis_deg: 90, speech_detected: true }).length);
});
test("microphone binding excludes per-origin device IDs and rejects missing settings", () => {
  const settings = { sampleRate: 48000, channelCount: 2, echoCancellation: false, noiseSuppression: false, autoGainControl: false };
  const expected = { label: "synthetic", settings };
  assert.deepEqual(microphoneBinding({ label: "synthetic", getSettings: () => ({ ...settings, deviceId: "private" }) }), expected);
  assert.ok(sameMicrophone(expected, expected));
  assert.equal(sameMicrophone({ ...expected, label: "different" }, expected), false);
  assert.equal(sameMicrophone({ ...expected, settings: {} }, expected), false);
});
