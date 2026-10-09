# Reachy-camera command-free commissioning

Status: **SIXTH CAPTURE PASSES OBSERVABILITY — FIVE EARLIER FAILURES RETAINED**

The `2026-10-01T18-26-38-037Z` capture passed every unchanged v1 check on
bridge-timing build v3. The next stage is the separately identified
[`ROBOT_CAMERA_PILOT.md`](ROBOT_CAMERA_PILOT.md), not another commissioning
retry and not the paused laptop-camera v2 pilot. Historical sections below
describe the evidence available at each repair; they are not current requests
to repeat collection.

This instrument replaces the laptop webcam with Reachy Mini's actual camera
stream before any no-motion pilot observation is accepted. It is a short M5
commissioning gate, not a research trial and not evidence that the robot can
select, move toward, attend to, or respond to a live speaker.

## Exact boundary

- Reachy video is consumed through the existing allowlisted, receive-only local
  WebRTC signalling path.
- The server keeps only the latest downsized JPEG in RAM, overwrites it on the
  next analyzed frame, and serves it only on `127.0.0.1`.
- The browser's pinned local landmark model derives face centre, normalized
  face scale, lip aperture, and lip motion.
- Reachy's DoA/speech state is read with GET requests only.
- The laptop microphone is still used transiently as a fine-grained acoustic
  timing reference. This commissioning does **not** establish a fully
  robot-native audio synchrony path.
- The download contains derived numeric CSV and metadata only. It contains no
  pixels, waveform, transcript, face embedding, or identity.
- POST, PUT, PATCH, and DELETE are rejected. Motion and response authority are
  false and the declared mutating-request count is zero.

The current local proxy does not expose an RTP packet-loss counter. The
instrument therefore records transport-frame and analyzed-frame counters,
unique-frame rate, duplicate rows, sequence gaps, frame age, fetch time, and
stalls. These measure application-visible delivery loss; they must not be
reported as exact network packet loss.

## Passing capture — 2026-10-01 18:26 UTC

| Frozen measurement | Result | Gate |
|---|---:|---:|
| Samples / span | 251 / 10,000.7 ms | >=160 / >=7,000 ms |
| Maximum sample gap | 55.0 ms | <=160 ms |
| Transport / distinct analyzed rate | 29.99790 / 16.99881 fps | both >=15 fps |
| Repeated-frame rows | 32.27% | <=50% |
| Single-face / joint spatial rows | 99.20% / 99.20% | >=80% / >=75% |
| Median face scale | 0.0625004 | >=0.02 |
| Audio / lip standard deviation | 5.80149 dB / 0.0991157 | >=0.50 / >=0.002 |
| Median landmark inference | 44.9 ms | <=60 ms |
| Valid DoA / speech rows | 100% / 78.88% | >=80% / >=25% |
| p95 local frame / DoA age | 159.45 / 246.40 ms | <=350 / <=650 ms |
| Median camera–DoA geometry error | 4.66 degrees | <=20 degrees |

There were 170 distinct observed frames, two without a detected face, and no
landmark processing errors. Metadata declares no motion, response or uploads.
All 16 execution source/model/runtime hashes matched the local build.

- CSV SHA-256: `b255610dcf4d56e92ceafc688cf22e623801dcd3b5adc1b8d9a285918f9a9692`
- Metadata SHA-256: `d3f188dce84b0be1fd0fa73f7b191ffac97492241dc2fc46fb7e842696a09a5a`
- Execution fingerprint: `166b21b36132fb97681a796d44db67078490166ef21606ecb10ebc92ecf045ac`
- Unchanged instrument fingerprint: `dbded406d1d271f69eb3652bc0b036cfe0deea734c4db2bf4f7a6979b2d3a95b`

Distinct-frame conversion median/p95 was 7.24/10.30 ms; receipt-to-JPEG
median/p95 was 11.09/14.86 ms. Frame age now includes conversion but still
excludes sensor exposure, robot buffering, network transit and WebRTC decode
queues. It is not end-to-end latency and cannot be pooled directly with older
ages. One passing ten-second capture establishes limited joint observability,
not long-run reliability, fine synchrony, selection accuracy or calibrated
speaker ownership. The five earlier failed attempts remain failed and excluded
from every pilot fit and validation set. Private originals were not rewritten.

## Coordinate contract

The visual bearing uses Pollen's Reachy Mini Wireless camera intrinsics. Raw
image-right is camera-right positive. The robot/room heading is front `0°`,
robot-right positive, so the recorded face heading negates the camera-right
bearing. No outcome-derived angular offset is applied. Reachy's linear DoA
axis (`0°=left`, `90°=front/back`, `180°=right`) is converted to its two
physical heading hypotheses before the nearest error is computed.

This defines the relationship; it does not establish a calibrated offset.
Passing requires a median face/DoA error no greater than the predeclared 20°
commissioning bound while the speaker is at the fixed front mark.

## Run

Keep Reachy Mini Control connected and Ready, with every robot application
stopped. On Windows, double-click `start_robot_camera_commissioning.cmd` in the
repository root and keep its terminal window open until both output files are
downloaded. This user-owned launcher remains alive across Codex replies.

Alternatively, run this from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts\run_robot_camera_commissioning.py --robot-ip 192.168.1.251
```

Open:

`http://127.0.0.1:8767/tools/robot_camera_commissioning.html`

The receive-only camera session remains bounded to 15 minutes. If it expires
before the short check is recorded, reload this page to start one new bounded
camera session; reloading does not authorize movement or a response.

The page cannot request the laptop camera. Initialize the pinned model, enable
the laptop microphone timing reference, stand at the fixed one-metre front
mark, face Reachy, and speak naturally. Record only after the live preflight is
green. The commissioning capture lasts ten seconds; do not play phone audio.

Analyze the private numeric CSV:

```powershell
.\.venv\Scripts\python.exe scripts\analyze_robot_camera_commissioning.py "C:\path\to\reachy-camera-commissioning.csv"
```

## Predeclared commissioning checks

- at least 160 numeric rows over at least 7 seconds;
- maximum numeric sample gap 160 ms;
- at least 15 delivered transport frames/s and 15 unique analyzed frames/s;
- p95 robot-frame age no greater than 350 ms;
- no more than 50% duplicate numeric rows;
- exactly one face in at least 80% of rows and median face scale at least 0.02;
- laptop-audio standard deviation at least 0.50 dB and lip-aperture standard
  deviation at least 0.002 while speaking;
- median landmark inference no greater than 60 ms;
- valid DoA in at least 80% of rows, p95 DoA age no greater than 650 ms, and
  speech present in at least 25% of valid DoA rows;
- joint face/DoA geometry in at least 75% of rows and median geometry error no
  greater than 20°; and
- zero motion, response, upload, or mutating robot requests.

These are infrastructure/observability checks fixed before the first numeric
commissioning capture. They are not pilot selection thresholds.

## 2026-10-01 commissioning outcomes and processing repair

Both ten-second captures remain failed commissioning attempts, not pilot trials.
The original CSVs and metadata remain in the operator's private Downloads; no
raw media was retained or imported into this repository.

| Original capture (UTC filename suffix) | 01-44-45-817Z | 01-45-29-538Z |
|---|---:|---:|
| Rows | 251 | 251 |
| Received frames/s | 30.10 | 29.80 |
| Distinct analyzed frames/s (required >=15) | 9.40 | 9.80 |
| Single-face rows (required >=80%) | 100% | 58.17% |
| Repeated-frame rows (required <=50%) | 62.55% | 60.96% |
| Median inference (required <=60 ms) | 63.5 ms | 62.8 ms |
| Valid DoA rows | 100% | 100% |

CSV SHA-256, in the same order:

- `6775eb4b71e807d4654dff0d173cbcff156049a458cd91794ce4acfe5fdf06d6`
- `32b8878277b98e00458ae016986e1af0a10badfe80951fcedca6d7546d75e591`

The first capture fails analysis rate, duplicate fraction, and inference time.
The second also fails single-face and joint-spatial coverage. Of its 98 distinct
observed frames, 44 returned zero faces and 54 returned one; none reported two.
This is intermittent non-detection, not a demonstrated second-person problem.
Without retained images these data cannot distinguish pose, lighting, occlusion,
or detector failure. Do not replace missing faces with previous landmarks or
reduce the two-face limit/confidence thresholds to make the capture pass.

The old browser loop added 30 ms after synchronous inference and blocked the
audio/telemetry event loop. The repaired implementation:

- moves inference into a single-flight worker, with no backlog of images;
- prefers GPU, explicitly reports an initialization-only CPU fallback, and
  warms kernels on a synthetic blank before declaring the model ready;
- retains the pinned model, VIDEO mode, two-face limit, and default `0.5`
  detection/presence/tracking confidences;
- subtracts processing time from the existing 30-ms pacing target;
- publishes each completed frame and its features atomically on the browser
  clock; worker-clock timestamps are not mixed with browser-clock timestamps;
- blocks recording until a five-second window meets the existing analysis-rate,
  repeated-frame, single-face and inference thresholds, plus the existing
  momentary sensor/DoA gates;
- terminates a failed/timed-out worker and clears its face result; an explicit
  processing error in a new capture also fails offline analysis;
- adds backend, decode time, error and numeric face-bound diagnostics without
  persisting images, raw landmarks, waveforms, or identity; and
- records a separate source/model/runtime execution-build fingerprint while
  keeping the frozen v1 check fingerprint unchanged.

Google documents that `detectForVideo` blocks its calling thread and recommends
workers for this purpose: [Face Landmarker Web guide](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/web_js).

After an implementation update, stop the old commissioning server with Ctrl+C,
restart the same launcher, and reload the page. No robot firmware update,
application start, motor change, or threshold edit is needed. The page refuses
an old server configuration rather than silently mixing builds. If the five-
second rate/coverage checks do not become ready, report the displayed backend,
rate, coverage, and error instead of collecting repeated failed captures.

In the worker and bounded-server builds, frame age started at local JPEG
preparation, after pixel conversion. The bridge-timing build described below
corrects that origin to decoded-frame receipt before conversion. Neither origin
measures total sensor-exposure-to-browser latency. Passing these checks still
does not prove fine audio-lip synchrony or full geometric calibration.

Verification of the repair: 364 repository Python tests and eight dedicated
JavaScript tests passed. A headless Edge smoke test loaded the pinned model in
a GPU worker on synthetic blank frames, then tested a 251-row simulated capture,
both downloads, execution identity, and face-loss/worker-failure blocking. It
used no robot, real microphone, or human video. This does not establish live
throughput or resolve the visual cause of the second capture's face gaps.

Developer commands (browser smoke additionally needs locally installed
Playwright and the pinned model/runtime assets):

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
node --test tests/robot_camera_pipeline.test.mjs
node tests/robot_camera_browser_smoke.cjs
```

## Follow-up captures and bounded-server repair (2026-10-01)

Two captures on the GPU-worker build remain failed under the same frozen v1
contract. The operator confirmed facing Reachy's camera. The later capture was
reported as without the hat; no causal claim about the earlier face losses is
justified by this one comparison. Original private files are unchanged.

| Capture UTC suffix | 14-05-12-051Z | 15-03-25-519Z (no hat) |
|---|---:|---:|
| Rows / distinct analyzed frames | 251 / 150 | 251 / 140 |
| Received frames/s | 30.09 | 29.90 |
| Distinct analyzed frames/s | 14.99745 | 13.99916 |
| Single-face rows | 66.53% | 100% |
| Joint spatial rows | 66.53% | 100% |
| Repeated-frame rows | 40.24% | 44.22% |
| Median inference (frozen row-weighted gate) | 41.2 ms | 45.8 ms |
| Failed checks | Analysis rate, single-face coverage, joint spatial coverage | Analysis rate only |

The 14.99745 result is below 15, not a rounded pass. Both captures declare GPU
without fallback and the same execution fingerprint:
`bddf04eb20ce73d7c8d211e35861a4f85b4ca03f1067fbb06ae5506328b659d9`.
Their CSV SHA-256 hashes, in table order, are:

- `73ca4c9fb6336d7626cb5dcf0bf166b7c23223189bd69ec68630c62c5a21aa64`
- `f8996df8a677985897277077bc0b8e382bb400b447026bf99f582c81afc06fee`

The no-hat capture's distinct-frame diagnostics show a mean receipt interval of
71.61 ms, versus a 66.67-ms budget for 15 fps. Mean inference was 47.57 ms,
frame fetch 12.15 ms and body-transfer/decode 4.36 ms. These are descriptive
timing measurements, not independent experimental trials or new thresholds.
All eight recorded fetches of at least 30 ms started within a reconstructed DoA
request interval. The single-threaded server performed its robot DoA GET
synchronously, preventing a concurrent frame response. A loopback-only test
with fake sensors reproduced a median 152.25-ms frame wait during an artificial
150-ms DoA wait. This demonstrates one bottleneck, not attribution of all
missing throughput to that bottleneck.

The second repair keeps the browser's single-flight inference and adds:

- Two reusable HTTP workers with at most four pending accepted requests. An
  excess connection is closed rather than queued indefinitely. It never creates
  a new thread per frame request. Socket IO retains a two-second timeout.
- Single-flight DoA access. A concurrent DoA request returns an explicit invalid
  503 result, freeing the other worker for frames; no stale result is cached or
  relabelled fresh. The existing one-second robot HTTP timeout remains.
- Serialized camera start/stop so simultaneous page loads cannot create two
  receiver threads. Shutdown signals admitted sockets and joins the HTTP pool
  before closing the DoA client.
- Numeric server queue/handler durations, drawing time, browser-measured worker
  round trip/overhead, fetch-to-feature completion time, loop gap and completed-
  frame interval. Missing historical fields stay unavailable, not zero.
- Distinct-frame timing summaries in the offline analyzer and four live timing
  readouts. These diagnostics do not replace the frozen row-weighted gates.
- A separately hashed `reachy-camera-bounded-server-build-v2` execution manifest
  and `reachy-camera-pipeline-timing-v1` definitions. The page refuses a server
  lacking this diagnostic contract. The original v1 fingerprint is unchanged.

Queue duration covers socket acceptance to worker start, not browser/OS backlog.
Handler duration ends at response headers, not body completion. Worker round trip
includes inference, feature reduction and messaging; its overhead is not a pure
thread-queue measurement. All cross-stage browser timestamps use the browser
clock. No source exposure timestamp or end-to-end camera latency is claimed.

In five synthetic requests during the same artificial 150-ms DoA wait, the new
pool's frame response had a median of 3.16 ms. This is an isolated server result,
not a real camera fps claim. Regression tests also check concurrent DoA rejection,
bounded overload, reuse of two workers across 100 additional requests, shutdown,
and unchanged GET/mutation boundaries. Browser tests check numeric timing export
and rejection of old server configuration. All 370 Python tests, 10 JavaScript
tests and the headless Edge integration check passed. The browser loaded the
pinned GPU model on synthetic blank frames and exported 251 simulated rows with
the new numeric timing fields. No robot or real microphone was accessed by those
tests. The subsequent live result is recorded below; it did not open the pilot.

## Fifth capture and conversion repair (2026-10-01)

The `15-54-58-987Z` capture used bounded-server build
`57c9f74552e43cb52e11aea7e68ab718e4de602382a42567b4911280f6e81a8f`.
Its CSV SHA-256 is
`dccab98ce4cd44687d49d4303d588fcc73492bb9397b369988a13e899aec8e6c`.
The private original CSV and metadata are unchanged and remain a failed
commissioning attempt, not a pilot trial.

- 252 rows over 10039.7 ms, with 149 distinct observed frames: **14.84108 fps**,
  below the unchanged 15-fps minimum.
- Single-face, valid DoA and joint-spatial coverage were all 100%. Every other
  frozen check passed under that build's recorded timing definition.
- Distinct-frame HTTP queue duration averaged 0.29 ms and frame fetches peaked
  at 21.1 ms. This capture no longer showed the former long HTTP waits.
- Ten completed-feature intervals exceeded 100 ms, with a maximum of 304.7 ms.
  The longest interval connects consecutive bridge sequences. Reconstructing
  their encoding-start times from frame ages gives approximately 305 ms apart
  (subject to HTTP midpoint uncertainty), although their JPEG preparation took
  only 4.48 and 6.79 ms. This locates a gap upstream of browser inference, but
  cannot isolate network, WebRTC decode, scheduling or pixel conversion.

Code inspection found `VideoFrame.to_ndarray` on the receiver's event loop,
before the old frame-age origin. An offline injection of 100 ms at that step
stalled the event-loop heartbeat by about 101 ms while the synthetic encoding
callback still averaged about 3.6 ms. This reproduced a timing blind spot; it
did not identify the cause of the live 305-ms gap.

The third repair moves conversion into the existing single-flight worker along
with the downstream callback. The receive loop continues draining decoded
frames, skipping analysis while that one job is busy. There is no application
queue of conversion jobs, additional model, changed landmark setting or changed
numeric threshold. Legacy one-argument consumers remain supported. Cancellation
discards a conversion result that has not reached its callback; the bridge also
checks stop/error/expiry state before and after encoding so a late JPEG cannot
restore a usable terminal snapshot.

New provenance: `reachy-camera-bridge-timing-build-v3`, with
`reachy-camera-pipeline-timing-v2` definitions. The original v1 check fingerprint
is unchanged. **The implementation's frame-age origin is corrected**, not
retrospectively applied to old captures: it now starts when a decoded frame is
returned by `track.recv`, before worker dispatch and pixel conversion. The same
350-ms freshness gate therefore includes more of the local delay. Sensor
exposure, robot buffering, network transit and pre-receipt WebRTC decode/queue
remain outside the measurement. Do not pool historical ages without this build
distinction or call this end-to-end latency.

Added per-frame numeric fields and browser readouts:

- conversion waiting time (receipt to conversion start) and conversion duration;
- total bridge preparation (receipt to completed JPEG bytes, before the
  publication lock) and interval between completed JPEGs;
- interval from the preceding drained frame to the selected frame; and
- input image dimensions before the unchanged maximum-width resize.

Timing travels with its frame and features. The receive interval is not a
network-arrival or loss measurement. Browser sampling can miss intermediate
JPEGs, so these values do not reconstruct every transport event. First intervals
and missing historical fields stay unavailable, not zero. No raw media is added
to downloads or repository evidence. The browser still uses one fetch/analysis
at a time; overlapping that path is outside this repair.

Verification: 378 Python tests, 10 JavaScript tests and the headless Edge check
passed. Tests cover receiver progress during blocked conversion, single-flight
ownership, cancellation, conversion errors, native PyAV pixel conversion,
pre-conversion age, atomic timing/sequence publication, terminal-state rejection,
HTTP header propagation and 251-row simulated browser export. The browser loaded
the actual pinned model on synthetic blank frames. Tests accessed no real robot
or microphone. Live throughput improvement is **unverified**.

Next operator step: stop the old server with Ctrl+C, run the same launcher and
reload the recorder. The terminal should include `bridge timing v2 (conversion
off receiver)`. Keep the existing marked geometry and no-hat setup. Face Reachy
and speak naturally without phone playback. Only if the five-second preflight
is green, record one ten-second check and supply both files. If it stays red,
send the rate, coverage, conversion/wait and bridge timing readouts instead of
collecting repeated failed captures. Pilot, motion and response remain blocked.

## Decision after commissioning

If every check passes, create a separately fingerprinted successor no-motion
pilot that uses Reachy's camera. Do not rename or reuse laptop-camera v1/v2
attempts.

If robot video cannot sustain the frame/freshness/landmark gates, stop and
improve that path before collection. If visual timing passes but the laptop
microphone remains necessary, record that external-sensor dependency
explicitly and decide whether to build robot-audio access or narrow the system
claim. Do not silently call a laptop-audio system fully robot-native.
