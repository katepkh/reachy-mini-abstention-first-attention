/* Offline browser integration test: synthetic blank frames/DoA/audio only.
 * Requires local pinned model assets and Playwright. Never contacts Reachy. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const http = require("node:http");
const { execFileSync } = require("node:child_process");
const { chromium } = require("playwright");
const root = path.resolve(__dirname, "..");
const python = process.env.TEST_PYTHON || path.join(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const config = JSON.parse(execFileSync(python, ["-c",
  "import json; from pathlib import Path; from reachy_stage3v.robot_camera_commissioning import robot_camera_execution_payload; print(json.dumps(robot_camera_execution_payload(Path.cwd())))"], { cwd: root }));
let blank = null;
let browser;
let forbiddenRequests = [];
let oldConfig = false;
const started = performance.now();
const server = http.createServer((req, res) => {
  const url = new URL(req.url, "http://localhost");
  const send = (type, body, headers = {}) => {
    res.writeHead(200, { "Content-Type": type, "Cache-Control": "no-store",
      "X-Reachy-Server-Queue-Ms": "0.1", "X-Reachy-Server-Handler-Ms": "0.2", ...headers }); res.end(body);
  };
  if (req.method !== "GET") { forbiddenRequests.push(req.method); res.writeHead(405).end(); return; }
  if (url.pathname === "/api/reachy-camera/config") return send("application/json",
    JSON.stringify(oldConfig ? { ...config, pipeline_diagnostics: undefined } : config));
  if (url.pathname === "/api/reachy-camera/doa") return send("application/json", JSON.stringify({ valid: true,
    axis_deg: 90, raw_angle_rad: Math.PI / 2, speech_detected: true, http_status: 200, robot_http_latency_ms: 1 }));
  if (url.pathname === "/api/reachy-camera/frame.jpg" && blank) {
    const sequence = 1 + Math.floor((performance.now() - started) / (1000 / 30));
    return send("image/png", blank, { "X-Reachy-Frame-Sequence": sequence,
      "X-Reachy-Transport-Frames": sequence, "X-Reachy-Analysis-Frames": sequence,
      "X-Reachy-Frame-Age-Ms": 5, "X-Reachy-Frame-Width": 640,
      "X-Reachy-Frame-Height": 360, "X-Reachy-Frame-Encode-Ms": 1,
      "X-Reachy-Conversion-Queue-Ms": 0.5, "X-Reachy-Conversion-Ms": 2,
      "X-Reachy-Receive-Interval-Ms": 33, "X-Reachy-Bridge-Total-Ms": 3.5,
      "X-Reachy-Bridge-Publish-Interval-Ms": 33,
      "X-Reachy-Source-Width": 1280, "X-Reachy-Source-Height": 720 });
  }
  if (url.pathname === "/favicon.ico") return res.writeHead(404).end();
  const allowed = config.execution_build.files_sha256;
  const file = url.pathname.slice(1);
  if (!Object.hasOwn(allowed, file) || !(file.startsWith("tools/") || file.startsWith("models/"))) {
    forbiddenRequests.push(url.pathname); res.writeHead(404).end(); return;
  }
  const type = file.endsWith(".html") ? "text/html" : file.endsWith(".wasm") ? "application/wasm" :
    /\.(mjs|js)$/.test(file) ? "text/javascript" : "application/octet-stream";
  send(type, fs.readFileSync(path.join(root, file)));
});
(async () => {
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  try {
    browser = await chromium.launch({ headless: true, channel: process.env.TEST_BROWSER_CHANNEL || "msedge" });
    const context = await browser.newContext({ acceptDownloads: true });
    await context.route("**/*", route => {
      if (route.request().url().startsWith(origin + "/")) return route.continue();
      forbiddenRequests.push(route.request().url()); return route.abort();
    });
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", msg => { if (msg.type() === "error") console.log("Browser diagnostic:", msg.text()); });
    blank = Buffer.from(await page.evaluate(async () => {
      const canvas = new OffscreenCanvas(640, 360);
      const ctx = canvas.getContext("2d"); ctx.fillStyle = "#333"; ctx.fillRect(0, 0, 640, 360);
      return Array.from(new Uint8Array(await (await canvas.convertToBlob({ type: "image/png" })).arrayBuffer()));
    }));
    await page.goto(origin + "/tools/robot_camera_commissioning.html");
    await page.locator("#initialize").click();
    await page.waitForFunction(() => document.querySelector("#backendMetric").textContent.includes("worker") ||
      document.querySelector("#status").textContent.includes("failed"), null, { timeout: 45000 });
    assert.ok((await page.locator("#backendMetric").textContent()).includes("worker"), await page.locator("#status").textContent());
    console.log("Initialized native worker:", await page.locator("#backendMetric").textContent());
    await page.waitForFunction(() => document.querySelector("#faceMetric").textContent === "0 face(s)" ||
      document.querySelector("#status").textContent.includes("Recording is blocked"));
    assert.equal(await page.locator("#faceMetric").textContent(), "0 face(s)", await page.locator("#status").textContent());
    assert.equal(await page.locator("#record").isDisabled(), true);
    console.log("Pinned native model on synthetic blank frames:", await page.locator("#backendMetric").textContent());
    await page.close();

    // Exercise real page/recorder logic with deterministic worker outputs. No
    // real face, microphone, sensor permission, motor, or waveform is involved.
    const simulated = await context.newPage();
    simulated.on("pageerror", error => errors.push(error.message));
    await simulated.addInitScript(() => {
      window.__faceCount = 1;
      window.__failWorker = false;
      window.Worker = class {
        postMessage(data) {
          setTimeout(() => {
            if (data.type === "initialize") return this.onmessage?.({ data: { id: data.id, delegate: "GPU", fallback: false } });
            data.bitmap?.close();
            if (window.__failWorker) return this.onmessage?.({ data: { id: data.id, error: "LANDMARK_INFERENCE_FAILED" } });
            this.onmessage?.({ data: { id: data.id, face: { count: window.__faceCount,
              centerX: 0.5, centerY: 0.5, cameraRight: 0, robotHeading: 0, scale: 0.1,
              lip: 0.1 + 0.01 * Math.sin(data.observedMs / 100), lipMotion: 0.01,
              inferenceMs: 20, observedMs: data.observedMs, dots: [],
              bounds: { left: 0.3, top: 0.2, right: 0.7, bottom: 0.8 } } } });
          }, data.type === "initialize" ? 1 : 20);
        }
        terminate() {}
      };
      navigator.mediaDevices.getUserMedia = async options => {
        if (options.video !== false) throw Error("Laptop camera requested");
        return { getTracks: () => [{ stop() {} }] };
      };
      window.AudioContext = class {
        get currentTime() { return performance.now() / 1000; }
        createMediaStreamSource() { return { connect() {} }; }
        createAnalyser() { return { fftSize: 2048, getFloatTimeDomainData(a) { a.fill(0.1 + 0.05 * Math.sin(performance.now() / 100)); } }; }
        async close() {}
      };
    });
    await simulated.goto(origin + "/tools/robot_camera_commissioning.html");
    await simulated.locator("#initialize").click();
    await simulated.locator("#microphone").click();
    await simulated.waitForFunction(() => !document.querySelector("#record").disabled, { timeout: 15000 });
    const downloads = [];
    let downloadsComplete;
    const downloadsReady = new Promise(resolve => { downloadsComplete = resolve; });
    simulated.on("download", download => { downloads.push((async () => {
      const stream = await download.createReadStream(); const chunks = [];
      for await (const chunk of stream) chunks.push(chunk);
      return { name: download.suggestedFilename(), text: Buffer.concat(chunks).toString() };
    })()); if (downloads.length === 2) downloadsComplete(); });
    await simulated.locator("#record").click();
    await simulated.waitForFunction(() => document.querySelector("#status").textContent.startsWith("Commissioning capture complete"), { timeout: 15000 });
    let downloadTimer;
    try {
      await Promise.race([downloadsReady, new Promise((_, reject) => {
        downloadTimer = setTimeout(() => reject(Error(`Expected two downloads, received ${downloads.length}`)), 5000);
      })]);
    } finally { clearTimeout(downloadTimer); }
    const results = await Promise.all(downloads);
    assert.equal(results.length, 2);
    const metadata = JSON.parse(results.find(x => x.name.endsWith(".json")).text);
    assert.equal(metadata.execution_build.fingerprint, config.execution_build.fingerprint);
    assert.equal(metadata.motion_commands, 0);
    assert.equal(metadata.pipeline_diagnostics.schema, "reachy-camera-pipeline-timing-v2");
    assert.equal(metadata.execution_build.schema, "reachy-camera-bridge-timing-build-v3");
    assert.equal(metadata.pipeline_diagnostics.http_workers, 2);
    const csv = results.find(x => x.name.endsWith(".csv")).text.trim().split("\n");
    const cols = csv.shift().split(",");
    const rows = csv.map(line => Object.fromEntries(line.split(",").map((x, i) => [cols[i], x])));
    assert.equal(rows.length, metadata.sample_count);
    assert.ok(rows.length >= 240);
    assert.ok(Math.max(...rows.map(r => Number(r.sample_gap_ms))) < 160);
    assert.ok(rows.every(r => r.landmark_backend === "GPU" && !r.landmark_error_code));
    for (const name of ["frame_server_queue_ms", "frame_server_handler_ms", "frame_draw_ms",
      "landmark_worker_roundtrip_ms", "landmark_worker_overhead_ms", "frame_pipeline_ms",
      "frame_loop_gap_ms", "frame_publish_interval_ms", "robot_frame_conversion_queue_ms",
      "robot_frame_conversion_ms", "robot_frame_receive_interval_ms", "robot_frame_bridge_total_ms",
      "robot_frame_bridge_publish_interval_ms", "robot_frame_source_width_px", "robot_frame_source_height_px"]) {
      assert.ok(rows.every(r => r[name] !== "" && Number.isFinite(Number(r[name])) && Number(r[name]) >= 0), name);
    }
    assert.ok(rows.every(r => Number(r.frame_server_queue_ms) === 0.1));
    assert.ok(rows.every(r => Number(r.robot_frame_conversion_ms) === 2));
    assert.ok(rows.every(r => Number(r.robot_frame_conversion_queue_ms) === 0.5));
    assert.ok(rows.every(r => Number(r.robot_frame_bridge_total_ms) === 3.5));
    assert.ok(rows.every(r => Number(r.robot_frame_source_width_px) === 1280));
    assert.equal(await simulated.locator("#conversionMetric").textContent(), "2.0 ms / 0.5 ms");
    assert.ok(rows.every(r => Number(r.frame_pipeline_ms) >= Number(r.landmark_worker_roundtrip_ms)));
    await simulated.evaluate(() => { window.__faceCount = 0; });
    await simulated.waitForFunction(() => document.querySelector("#record").disabled);
    await simulated.evaluate(() => { window.__failWorker = true; });
    await simulated.waitForFunction(() => document.querySelector("#status").textContent.includes("LANDMARK_INFERENCE_FAILED"));
    assert.equal(await simulated.locator("#record").isDisabled(), true);
    assert.equal(await simulated.locator("#faceMetric").textContent(), "—");
    await simulated.evaluate(() => { window.__failWorker = false; });
    await simulated.locator("#initialize").click();
    await simulated.waitForFunction(() => document.querySelector("#status").textContent.includes("Microphone remains active"));
    assert.equal(await simulated.locator("#microphone").isDisabled(), true);
    await simulated.locator("#stop").click();
    assert.equal(await simulated.locator("#record").isDisabled(), true);
    await simulated.close();
    oldConfig = true;
    const oldPage = await context.newPage();
    await oldPage.goto(origin + "/tools/robot_camera_commissioning.html");
    await oldPage.waitForFunction(() => document.querySelector("#status").textContent.includes("bridge-timing build"));
    assert.equal(await oldPage.locator("#record").isDisabled(), true);
    await oldPage.close();
    assert.deepEqual(errors, []);
    assert.deepEqual(forbiddenRequests, []);
    console.log(`PASS: ${rows.length} synthetic rows; model worker, downloads, build identity, loss/error gates; no robot access.`);
  } finally {
    await browser?.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
