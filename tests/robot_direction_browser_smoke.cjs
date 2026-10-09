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
const { createHash } = require("node:crypto");
config.diagnostic = {
  schema: "reachy-direction-diagnostic-v1", purpose: "DIAGNOSTIC_NOT_PILOT",
  build: { fingerprint: "synthetic-diagnostic-build" }, binding_fingerprint: "synthetic-binding",
  stimulus_sha256: "s".repeat(64), playback_volume_percent: 50,
  positions: [
    {id:"front",label:"FRONT",heading_left_positive_deg:0,expected_axis_deg:90},
    {id:"left60",label:"60° to Reachy's LEFT",heading_left_positive_deg:60,expected_axis_deg:30},
    {id:"right60",label:"60° to Reachy's RIGHT",heading_left_positive_deg:-60,expected_axis_deg:150},
  ],
  coordinate_contract: { frame: "robot-left positive" },
  instruction: "Synthetic diagnostic only", claim_boundary: "Excluded from pilot",
  extra_columns: ["position_id","expected_axis_deg","phone_heading_left_positive_deg",
    "direction_doa_fresh","direction_usable","direction_bearing_left_positive_deg",
    "expected_axis_error_deg","face_sound_separation_deg","direction_warning_codes","microphone_continuous"],
  microphone: { label: "synthetic", settings: { sampleRate: 48000, channelCount: 2,
    echoCancellation: false, noiseSuppression: false, autoGainControl: false } },
};
let doaMode = "no_speech";
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
  if (url.pathname === "/api/reachy-camera/doa") {
    if (doaMode === "missing") return res.writeHead(503).end();
    return send("application/json", JSON.stringify({ valid: true, axis_deg: 77,
      raw_angle_rad: 77 * Math.PI / 180, speech_detected: doaMode === "wrong_direction",
      http_status: 200, robot_http_latency_ms: 1 }));
  }
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
  const allowed = { ...config.execution_build.files_sha256, "tools/robot_direction_diagnostic.html": "test", "tools/robot_direction_ui.mjs": "test", "tools/robot_diagnostic_ui.mjs": "test", "tools/robot_pilot_ui.mjs": "test" };
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
  const errors = [];
  try {
    browser = await chromium.launch({ headless: true, channel: process.env.TEST_BROWSER_CHANNEL || "msedge" });
    const context = await browser.newContext({ acceptDownloads: true });
    await context.route("**/*", route => {
      if (route.request().url().startsWith(origin + "/")) return route.continue();
      forbiddenRequests.push(route.request().url()); return route.abort();
    });
    const seed = await context.newPage();
    blank = Buffer.from(await seed.evaluate(async () => {
      const canvas = new OffscreenCanvas(640, 360);
      canvas.getContext("2d").fillRect(0, 0, 640, 360);
      return Array.from(new Uint8Array(await (await canvas.convertToBlob({ type: "image/png" })).arrayBuffer()));
    }));
    await seed.close();
    async function openPage(reset = true, initialize = true) {
      const page = await context.newPage();
      page.on("pageerror", error => errors.push(error.message));
      await page.addInitScript(reset => {
      if (reset) for (const key of Object.keys(localStorage)) if (key.startsWith("reachy-direction-v1:")) localStorage.removeItem(key);
      window.__faceCount = 1; window.__micMismatch = false; window.__micStops = 0;
      window.__failWorker = false;
      window.Worker = class {
        postMessage(data) {
          setTimeout(() => {
            if (data.type === "initialize") return this.onmessage?.({ data: { id: data.id, delegate: "GPU", fallback: false } });
            data.bitmap?.close();
            if (window.__failWorker) return this.onmessage?.({ data: { id: data.id, error: "LANDMARK_INFERENCE_FAILED" } });
            this.onmessage?.({ data: { id: data.id, face: { count: window.__faceCount,
              centerX: 0.5, centerY: 0.5, cameraRight: 0, robotHeading: -6, scale: 0.081,
              lip: 0.1 + 0.01 * Math.sin(data.observedMs / 100), lipMotion: 0.01,
              inferenceMs: 20, observedMs: data.observedMs, dots: [],
              bounds: { left: 0.3, top: 0.2, right: 0.7, bottom: 0.8 } } } });
          }, data.type === "initialize" ? 1 : 20);
        }
        terminate() {}
      };
      navigator.mediaDevices.getUserMedia = async options => {
        if (options.video !== false) throw Error("Laptop camera requested");
        const track = { label: window.__micMismatch ? "wrong microphone" : "synthetic", stop() { window.__micStops++; }, addEventListener() {}, getSettings: () => ({
          sampleRate: 48000, channelCount: 2, echoCancellation: false, noiseSuppression: false, autoGainControl: false
        }) };
        return { getTracks: () => [track], getAudioTracks: () => [track] };
      };
      window.AudioContext = class {
        sampleRate = 48000;
        state = "running";
        async resume() { this.state = "running"; }
        get currentTime() { return performance.now() / 1000; }
        createMediaStreamSource() { return { connect() {} }; }
        createAnalyser() { return { fftSize: 2048, getFloatTimeDomainData(a) { a.fill(0.1 + 0.05 * Math.sin(performance.now() / 100)); } }; }
        async close() { this.state = "closed"; }
      };
    }, reset);
      await page.goto(origin + "/tools/robot_direction_diagnostic.html");
      await page.waitForFunction(() => document.querySelector("#contract").textContent.includes("reachy-direction-diagnostic-v1"));
      await page.evaluate(() => localStorage.setItem("robot-pilot:sentinel", "unchanged"));
      if (!initialize) return page;
      await page.locator("#phoneDistance").fill("100");
      await page.locator("#initialize").click();
      await page.waitForFunction(() => !document.querySelector("#microphone").disabled);
      return page;
    }
    async function enable(page) {
      await page.locator("#microphone").click();
      await page.locator("#confirmPlayback").check();
      await page.waitForFunction(() => !document.querySelector("#record").disabled, null, {timeout:15000});
    }
    async function downloads(page, action) {
      const received = [];
      let complete;
      const ready = new Promise(resolve => { complete = resolve; });
      const callback = download => {
        received.push((async () => {
          const stream = await download.createReadStream(), chunks = [];
          for await (const chunk of stream) chunks.push(chunk);
          return { name: download.suggestedFilename(), text: Buffer.concat(chunks).toString() };
        })());
        if(received.length === 2) complete();
      };
      page.on("download", callback);
      await action();
      let timer;
      try { await Promise.race([ready, new Promise((_, reject) => {
        timer = setTimeout(() => reject(Error("Diagnostic downloads missing")), 18000);
      })]); } finally { clearTimeout(timer); }
      page.off("download", callback);
      return Promise.all(received);
    }

    const page = await openPage();
    await page.locator("#microphone").click();
    await page.waitForTimeout(5500);
    assert.equal(await page.locator("#record").isDisabled(),true);
    await page.locator("#confirmPlayback").check();
    await page.waitForFunction(()=>!document.querySelector("#record").disabled);
    if (process.env.TEST_SCREENSHOT) await page.screenshot({path:process.env.TEST_SCREENSHOT,fullPage:true});
    const allMeta = [];
    for (let i=0;i<3;i++) {
      doaMode = ["no_speech", "wrong_direction", "missing"][i];
      const warning = ["SPEECH_NOT_DETECTED", "nominal mark value 30", "DOA_MISSING_OR_STALE"][i];
      await page.waitForFunction(w=>document.querySelector("#diagnosticWarning").textContent.includes(w),warning);
      assert.equal(await page.locator("#record").isDisabled(),false, "Diagnostic condition cannot block");
      const results = await downloads(page,()=>page.locator("#record").click());
      await page.waitForFunction(()=>document.querySelector("#status").textContent.includes("complete"));
      const meta=JSON.parse(results.find(r=>r.name.endsWith(".json")).text);
      const csv=results.find(r=>r.name.endsWith(".csv")).text;
      const rows=JSON.parse(execFileSync(python,["-c","import csv,json,sys; print(json.dumps(list(csv.DictReader(sys.stdin))))"],{input:csv}));
      allMeta.push(meta);
      assert.equal(meta.schema,"reachy-direction-diagnostic-capture-v1");
      assert.equal(meta.phone_position.id,config.diagnostic.positions[i].id);
      assert.equal(meta.horizontal_phone_distance_cm,100);
      assert.equal(meta.position_index,i);
      assert.equal(meta.pilot_eligible,false); assert.equal(meta.trial_id,null);
      assert.equal(meta.capture_complete,true);
      assert.equal(meta.csv_sha256,createHash("sha256").update(csv).digest("hex"));
      assert.equal(rows.length,meta.sample_count); assert.ok(rows.length>=240);
      assert.ok(rows.every(r=>r.position_id===meta.phone_position.id));
      assert.equal(meta.motion_commands,0); assert.equal(meta.response_commands,0);
      assert.equal(meta.contains_pixels,false); assert.equal(meta.contains_waveform,false);
      assert.equal(await page.locator("#savedFiles a").count(),2*(i+1));
      assert.equal(await page.locator("#record").isDisabled(),true);
      if(i===0) {
        assert.equal(meta.summary.speech_direction_rows,0);
        assert.ok(rows.every(r=>r.direction_usable==="false" && r.expected_axis_error_deg===""));
      }
      if(i===1) {
        assert.ok(meta.summary.speech_direction_rows>200);
        assert.equal(meta.summary.median_expected_axis_error_deg,47);
      }
      if(i===2) assert.equal(meta.summary.speech_direction_rows,0);
      if(i<2) {
        await page.locator("#nextPosition").click();
        assert.equal(await page.locator("#confirmPlayback").isChecked(),false);
        assert.equal(await page.locator("#phoneDistance").isDisabled(),true);
        assert.equal(await page.locator("#record").isDisabled(),true);
        await enable(page);
      }
    }
    assert.equal(new Set(allMeta.map(m=>m.session_id)).size,1);
    assert.equal(new Set(allMeta.map(m=>m.diagnostic_id)).size,3);
    assert.equal(await page.locator("#nextPosition").isVisible(),false);
    assert.equal(await page.evaluate(()=>localStorage.getItem("robot-pilot:sentinel")),"unchanged");
    await page.close();
    const recovered=await openPage(false,false);
    await recovered.waitForFunction(()=>document.querySelector("#status").textContent.includes("already complete"));
    assert.equal(await recovered.locator("#savedFiles a").count(),6);
    assert.equal(await recovered.locator("#initialize").isDisabled(),true);
    assert.equal(await recovered.locator("#record").isDisabled(),true);
    await recovered.close();
    const partial = await openPage();
    await enable(partial);
    const partialResults = await downloads(partial, async () => {
      await partial.locator("#record").click();
      await partial.waitForTimeout(200);
      await partial.locator("#stop").click();
    });
    const stopped = JSON.parse(partialResults.find(r=>r.name.endsWith(".json")).text);
    assert.equal(stopped.capture_complete, false);
    assert.equal(stopped.stop_reason, "operator_stop");
    assert.ok(stopped.sample_count > 0 && stopped.actual_duration_ms < 1000);
    assert.equal(stopped.microphone_uninterrupted, false);
    assert.equal(await partial.locator("#nextPosition").isVisible(),false);
    await partial.close();

    const mismatch = await openPage();
    await mismatch.evaluate(() => { window.__micMismatch = true; });
    await mismatch.locator("#microphone").click();
    await mismatch.waitForFunction(() => document.querySelector("#status").textContent.includes("differs from the sealed binding"));
    assert.equal(await mismatch.locator("#record").isDisabled(), true);
    assert.ok(await mismatch.evaluate(() => window.__micStops > 0));
    await mismatch.close();
    oldConfig = true;
    const wrong = await context.newPage();
    await wrong.goto(origin + "/tools/robot_direction_diagnostic.html");
    await wrong.waitForFunction(() => document.querySelector("#status").textContent.includes("separate three-position direction diagnostic launcher"));
    assert.equal(await wrong.locator("#record").isDisabled(), true);
    assert.equal(await wrong.locator("#initialize").isDisabled(), true);
    await wrong.close();
    assert.deepEqual(errors, []);
    assert.deepEqual(forbiddenRequests, []);
    console.log("PASS: front/left/right sequence, six hash-bound downloads, no-speech and unexpected/missing direction capture, recovery without repeat, partial stop, microphone mismatch, unchanged pilot storage; synthetic only.");
  } finally {
    await browser?.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
