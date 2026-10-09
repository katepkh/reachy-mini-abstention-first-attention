import assert from "node:assert/strict";
import { test } from "node:test";
import { LandmarkWorkerClient, ProcessingWindow, remainingFrameDelay, summarizeFace,
  numericTimingHeader, framePipelineTiming } from "../tools/robot_camera_pipeline.mjs";

test("missing server timing stays unavailable, never converted to zero", () => {
  for (const raw of [null, "", "bad", "-1", "Infinity"]) {
    assert.equal(numericTimingHeader({ get: () => raw }, "test"), null);
  }
  assert.equal(numericTimingHeader({ get: () => "0" }, "test"), 0);
  assert.equal(numericTimingHeader({ get: () => "1.25" }, "test"), 1.25);
});

test("pipeline diagnostics separate worker round trip, inference and pacing", () => {
  const input = { started: 100, received: 108, decoded: 112, drawn: 114,
    workerStarted: 115, completed: 165, inferenceMs: 45,
    previousLoopFinished: 95, previousPublished: 90 };
  assert.deepEqual(framePipelineTiming(input), { drawMs: 2, workerRoundtripMs: 50,
    workerOverheadMs: 5, pipelineMs: 65, loopGapMs: 5, publishIntervalMs: 75 });
  const first = framePipelineTiming({ ...input, previousLoopFinished: null, previousPublished: null });
  assert.equal(first.loopGapMs, null);
  assert.equal(first.publishIntervalMs, null);
});

test("frame pacing subtracts work instead of adding a 30-ms sleep", () => {
  assert.equal(remainingFrameDelay(0, 70, 30), 0);
  assert.equal(remainingFrameDelay(0, 10, 30), 20);
});
test("missing or multiple faces are not imputed", () => {
  for (const faces of [[], [[], []]]) {
    const face = summarizeFace(faces, 0.2, 40, 1234);
    assert.equal(face.count, faces.length);
    assert.equal(face.scale, 0);
    assert.equal(face.lip, 0);
    assert.equal(face.bounds, null);
    assert.equal(face.observedMs, 1234);
  }
});
test("same face geometry and lip normalization, with bounds only as diagnostics", () => {
  const points = Array.from({ length: 468 }, () => ({ x: 0.5, y: 0.5 }));
  points[33] = { x: 0.4, y: 0.4 }; points[263] = { x: 0.6, y: 0.4 };
  points[13] = { x: 0.5, y: 0.55 }; points[14] = { x: 0.5, y: 0.57 };
  const face = summarizeFace([points], null, 12, 100);
  assert.ok(Math.abs(face.lip - 0.1) < 1e-10);
  assert.equal(face.robotHeading, -face.cameraRight);
  assert.equal(face.lipMotion, 0);
  assert.equal(face.dots.length, 4);
  assert.equal(face.bounds.top, 0.4);
});
function fakeWorker() {
  return { stopped: false, posted: [], postMessage(data) { this.posted.push(data); },
    terminate() { this.stopped = true; } };
}
test("one outstanding inference only; mismatched/late results cannot replace it", async () => {
  const worker = fakeWorker(); const client = new LandmarkWorkerClient(worker);
  const request = client.request({ type: "analyze" });
  await assert.rejects(client.request({ type: "analyze" }), /BUSY/);
  worker.onmessage({ data: { id: 99, face: "wrong" } });
  assert.ok(client.pending);
  worker.onmessage({ data: { id: 1, face: "right" } });
  assert.equal((await request).face, "right");
  client.close();
});
test("worker timeout terminates it and blocks subsequent work", async () => {
  const worker = fakeWorker(); const client = new LandmarkWorkerClient(worker);
  await assert.rejects(client.request({ type: "analyze" }, [], 5), /TIMEOUT/);
  assert.equal(worker.stopped, true);
  await assert.rejects(client.request({ type: "analyze" }), /CLOSED/);
});
test("worker failure is explicit, not reused prior landmarks", async () => {
  const worker = fakeWorker(); const client = new LandmarkWorkerClient(worker);
  const pending = client.request({ type: "analyze" });
  worker.onmessage({ data: { id: 1, error: "LANDMARK_INFERENCE_FAILED" } });
  await assert.rejects(pending, /INFERENCE_FAILED/);
  assert.equal(worker.stopped, true);
});
const checks = { minimum_unique_analyzed_fps: 15, maximum_median_landmark_inference_ms: 60,
  maximum_duplicate_row_fraction: 0.5, minimum_single_face_fraction: 0.8 };
test("healthy five-second processing window opens, then ages out on a stall", () => {
  const window = new ProcessingWindow();
  for (let t = 0; t <= 5000; t += 40) window.add(t, { sequence: 1 + t / 40 }, { count: 1, inferenceMs: 20 });
  assert.deepEqual(window.assess(5000, checks).failures, []);
  for (let t = 5040; t <= 9000; t += 40) window.add(t, { sequence: 126 }, { count: 1, inferenceMs: 20 });
  assert.ok(window.assess(9000, checks).failures.length > 0);
});
test("slow or intermittent tracking is blocked before collecting a repeat", () => {
  const window = new ProcessingWindow();
  for (let t = 0; t <= 5000; t += 40) window.add(t, { sequence: 1 + Math.floor(t / 100) },
    { count: t % 200 < 100 ? 1 : 0, inferenceMs: 63 });
  const result = window.assess(5000, checks);
  assert.ok(result.fps < 15);
  assert.ok(result.failures.some(x => x.includes("intermittent")));
  assert.ok(result.failures.some(x => x.includes("60 ms")));
  window.clear();
  assert.ok(window.assess(5000, checks).failures.length);
});
