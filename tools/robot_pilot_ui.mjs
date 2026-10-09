// Pure condition-aware preflight and canonical microphone-binding helpers.
export function pilotChecks(checks, card) {
  const missingFace = card?.condition_id === "speech_without_usable_face";
  return { ...checks, minimum_single_face_fraction: missingFace ? 0 : 0.95,
    minimum_median_face_scale: 0.06 };
}

export function conditionFailures(card, face, performanceCheck, doa) {
  const failures = [];
  if (!card) return ["collection gate closed"];
  const absent = card.condition_id === "speech_without_usable_face";
  if (absent) {
    if (!face || face.count !== 0 || performanceCheck.singleFraction > 0.05)
      failures.push("keep every face outside Reachy's camera view for five seconds");
  } else {
    if (!face || face.count !== 1) failures.push("show exactly one face to Reachy");
    if (!face || face.scale < 0.06) failures.push("face scale must reach 0.0600");
  }
  if (doa?.valid) {
    if (card.condition_id === "spatial_conflict" && face?.count === 1) {
      const wrap = x => ((x + 180) % 360 + 360) % 360 - 180;
      const first = wrap(90 - Number(doa.axis_deg));
      const second = wrap(180 - first);
      const error = Math.min(Math.abs(wrap(face.robotHeading - first)), Math.abs(wrap(face.robotHeading - second)));
      if (!Number.isFinite(error) || error < 40) failures.push("phone must be on the right-hand conflict mark, not beside your face");
    }
    if (card.condition_id === "visible_silence") {
      if (doa.speech_detected) failures.push("stay silent and stop all playback");
    } else if (!doa.speech_detected) failures.push("the prescribed speech source must be audible to Reachy");
  }
  return failures;
}

export function microphoneBinding(track) {
  const settings = track.getSettings();
  const keys = ["sampleRate", "channelCount", "echoCancellation", "noiseSuppression", "autoGainControl"];
  return { label: track.label, settings: Object.fromEntries(keys.map(k => [k, settings[k] ?? null])) };
}

export function sameMicrophone(actual, expected) {
  return Boolean(actual && expected && actual.label === expected.label &&
    Object.keys(expected.settings).every(k => actual.settings[k] === expected.settings[k]));
}

export async function sha256(text) {
  const buffer = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buffer)].map(x => x.toString(16).padStart(2, "0")).join("");
}
