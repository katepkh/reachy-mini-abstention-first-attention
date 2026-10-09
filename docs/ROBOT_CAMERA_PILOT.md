# Reachy-camera no-motion pilot v1

Status: **DESIGN / EXECUTION FROZEN — PRIVATE SETUP SEALED — ZERO ACCEPTED TRIALS**

Current checkpoint (2026-10-09): collection remains paused while the microphone,
speech/direction and input-reporting blockers are reviewed. The dated preparation
and operator workflow below preserve the frozen design; they are not current
permission to start a pilot or reuse a spent diagnostic launcher. See
`MICROPHONE_HEALTH_DIAGNOSTIC.md` for the latest unresolved evidence.

The collection gate was verified open for scheduled Trial 1 on 2026-10-01.
Live capture still requires the bound microphone and condition-specific
preflight. No pilot capture or robot command was made during preparation.

- Protocol fingerprint: `5f7fbd2960f27ce314f733c61b5d1c921d2f697deb9cf5abf69cf8fa1afef76e`
- Execution fingerprint: `bc44ce18deb949a9b0764ef5c4bc9506ffd8f7afd1f233873fe3b53f626bf2e0`
- Execution covers 35 source/model/runtime files plus Python/dependency versions.
- The original commissioned build remains `166b21b36132fb97681a796d44db67078490166ef21606ecb10ebc92ecf045ac`.

Verification: 387 Python tests passed; the nine affected pilot tests were
rechecked after the final manifest checks. Fourteen JavaScript tests passed.
Headless browser testing used synthetic frames/audio/DoA only, initialized the
pinned landmark worker, exported 251 numeric rows and hash-matched metadata,
and checked microphone matching, recording/reload locks and loss/error gates.
HTTP tests reject mutations and private paths. These are software checks,
not evidence of live pilot discrimination. The private setup and original
stimulus remain ignored by Git; no raw media was copied into the repository.

This is the successor to the paused laptop-camera pilot, not a continuation of
its trials. All commissioning captures and laptop v1/v2 attempts are excluded.
The primary question remains whether the visible live speaker can be selected
while phone-playback hard negatives abstain. No robot motion or response exists
in this instrument.

## Inputs and limits

- **Reachy:** receive-only camera stream and GET-only speech/direction readings.
- **Laptop:** computation and external microphone timing reference; no laptop
  camera. This is not yet a fully robot-native audiovisual sensing system.
- **One iPhone:** the fixed speech recording, used only in playback conditions.
  It moves between the beside-face mark (within 10 degrees) and the 60-degree
  mark to Reachy's right. No second phone or video recording is needed.
- **Output:** numeric CSV and metadata only. Frames/audio remain transient.

The design is executable in `reachy_stage3v/robot_pilot_protocol.py`; canonical
protocol and implementation hashes are frozen under `evidence/manifests/`.
No post-outcome changes to the grid, quality thresholds, labels, order or
timing convention are permitted. A repair requires a new explicit version.

## Design

Three block-randomized repetitions of seven ten-second conditions (seed
20261001): continuous live speech; interrupted live speech; silent face with
beside-face playback; silent deliberate out-of-time mouthing with beside-face
playback; visible silence; live speech outside the camera view; and silent face
with spatially conflicting playback. Each block contains every condition once.
Blocks 1–2 are development; block 3 is internal validation, not confirmation.
Trial IDs are `reachy-camera-pilot-v1-01` through `-21` in schedule order.

The first randomized card is **spatial conflict**: person silent at the front
mark, phone playing at the 60-degree mark to Reachy's right. This order was
fixed before collecting any pilot outcome, not chosen from a successful trial.

For interrupted live speech: speak during seconds 0–3, silence 3–5, speak 5–10.
For every playback trial: restart the same recording from the beginning
immediately before pressing Record; let it play throughout the capture. The
manual onset offset is not measured. Do not speak over playback. Use a different
silent mouth rhythm for the mouthing condition, not lip-sync to the recording.
The on-screen progress bar provides elapsed seconds.

## Acquisition and analysis frozen before collection

Keep the v2 condition-specific acquisition thresholds, including >=95%
single-face rows where a face is required, no multiple-face rows, median face
scale >=0.06, DoA validity >=80%, p95 DoA age <=650 ms, speech fraction >=25%
for speech conditions and <=10% for visible silence. The no-face control
requires <=5% usable-face rows. Conflict requires median disagreement >=40
degrees. Audio/lip variability gates apply only where the condition requires
speech/mouth motion. These thresholds are not fitted to new pilot outcomes.

Every condition also requires the commissioned robot path: >=15 transport and
distinct analyzed fps, <=50% repeated rows, p95 local frame age <=350 ms and
median inference <=60 ms. Require >=160 rows over >=7 seconds, sample gaps
<=160 ms, no processing errors, unchanged camera resolution and uninterrupted
matching microphone settings. Objective failures are unavailable captures,
not successful abstentions. Report them separately and retain their originals.

The experimental unit is one trial. Camera duplicates are not independent lip
observations. Lip timestamps use the first observation of each distinct frame
minus its corrected local frame age. Audio timestamps use the telemetry clock
minus half the 2048-sample RMS window at the declared audio-context rate.
Align only common support, reject nonmonotonic times and gaps >160 ms before
linear interpolation to 40-ms bins, then apply the declared smoothing.
These estimates exclude exposure/robot/network/decode latency, so a recovered
lag is a pipeline association measurement, not true sensor-exposure synchrony.

The inherited 300-setting grid varies correlation, lag window, smoothing and
spatial threshold. Use development only: all ten negatives must abstain and at
least three of four positives must propose. Maximize positive coverage, then
prefer higher correlation, tighter spatial gate, narrower lag and less smoothing.
Freeze the selected setting and all fourteen source hashes before opening block
3. A selected proposal at the allowed lag boundary stops for timing investigation;
do not widen the grid after observing outcomes. If no candidate qualifies, stop.

Evaluate validation once with the frozen setting: both positives must propose,
all five negatives must abstain, and acquisition must pass. Compare acoustic,
visual activity, speech-plus-mouth activity without synchrony, spatial,
synchrony-only, non-abstaining visible-face and fused-abstaining baselines.
An internal-validation pass remains single-setup engineering evidence. If fine
timing fails, choose a new robot sensing/timing repair or explicitly approve a
narrower external-sensor objective; do not silently claim robot-native success.

## Collection gate and attempt accounting

The new private setup is separate from the historical seals. Bind the existing
room/marks, current fixed volume and stimulus hash, Reachy source resolution,
and normalized microphone label/settings. Browser device/group IDs are not
carried between origins. The recorder verifies the microphone after permission;
a mismatch closes capture rather than silently rebinding it.

The page exposes only the next scheduled card. One capture produces a hash-bound
CSV/metadata pair and then locks Record until offline review. Every imported
attempt has a separate immutable private folder; the first quality-passing
attempt is accepted. At most two acquisition attempts per scheduled trial,
then stop for repair/new version. Outcome-based retries are forbidden.
The browser retains a local started-attempt lock across reloads. If a tab closes
or downloads are lost, report the abort; the explicit offline `record-abort`
operation records it and consumes one attempt. Never clear that lock to obtain
an uncounted retry. This is operator-assisted accounting, not tamper-proof
monitoring across different browsers/devices.

The final block cannot open until `freeze-development` writes its immutable
setting and source list. `validate` refuses to overwrite a prior evaluation.
Original commissioning and laptop files/seals remain untouched.

## Operator workflow

1. Stop the old commissioning server with Ctrl+C. Keep robot applications stopped.
2. Run `start_robot_camera_pilot.cmd`; keep its terminal window open.
3. Open `http://127.0.0.1:8768/tools/robot_camera_pilot.html`.
4. Read the displayed card, initialize the model, enable the bound laptop
   microphone, and arrange only the phone/person as instructed.
5. When preflight is green, capture **one** ten-second trial. Stop the microphone
   and send both downloaded files. Do not retry or advance on your own.

All setup/import/selection operations use the offline CLI:

```powershell
.\.venv\Scripts\python.exe scripts\robot_camera_pilot.py status
.\.venv\Scripts\python.exe scripts\robot_camera_pilot.py import "capture.csv" "capture.metadata.json"
.\.venv\Scripts\python.exe scripts\robot_camera_pilot.py freeze-development
.\.venv\Scripts\python.exe scripts\robot_camera_pilot.py validate
```

The server cannot write attempts, change a protocol, operate motors, play audio
or accept a trial. It serves allowlisted local assets and read-only sensor APIs.
No GitHub publication or firmware change is part of this step.
