# Command-free joint shadow instrument

Status: **REAL OBSERVABILITY COMMISSIONING PASSED — PILOT UNCOLLECTED**

This is the next M5 critical-path instrument. It combines, during one real
event, Reachy's numeric GET-only direction-of-arrival state with locally
derived laptop microphone level, face geometry, and lip aperture. It records
timing quality and availability so missing evidence cannot be mistaken for
successful playback rejection.

It has **no motion or response authority**. It contains no robot SDK, sends no
mutating robot request, uploads nothing, and downloads only numeric CSV plus a
numeric metadata file. Camera frames and microphone samples remain transient in
the local browser. Passing commissioning checks establishes only endpoint
observability, not fusion accuracy or robot behaviour.

## Start

Keep every robot application stopped. Reachy may be powered and Ready only so
its existing read-only DoA endpoint is available. From the repository root run:

```powershell
.\.venv\Scripts\python.exe scripts\run_joint_shadow_instrument.py --robot-ip 192.168.1.251
```

Then open:

`http://127.0.0.1:8766/tools/joint_shadow_recorder.html`

The server exposes only three read-only instrument APIs:

- `GET /api/joint-shadow/config`
- `GET /api/joint-shadow/pilot`
- `GET /api/joint-shadow/doa`

All POST requests are rejected. Static model/runtime assets are served from the
local repository.

## First commissioning capture

1. Use the already-tested fixed laptop placement and align its camera axis with
   Reachy's declared forward axis. The field-of-view value is an explicit
   commissioning estimate, not a calibrated angle.
2. Select `live_visible_interrupted`.
3. Initialize the pinned model, enable the laptop camera/microphone, and confirm
   one face, changing audio, valid DoA, and bounded DoA age.
4. Capture ten seconds. The page downloads one numeric CSV and one metadata
   JSON. Keep both private until their content and device labels are reviewed.
5. Analyse the CSV:

```powershell
.\.venv\Scripts\python.exe scripts\analyze_joint_shadow_commissioning.py "C:\path\to\joint-shadow-....csv"
```

Do not start a study if a check fails. Repair the instrument or placement and
repeat only commissioning. Do not tune the V2 candidate from these observations
or relabel commissioning data as final evidence.

## Timing interpretation

Laptop audio, video inference and scheduling use `performance.now()`. Each DoA
observation is assigned the midpoint of its localhost request, and half the
round-trip time is recorded as clock uncertainty. The robot endpoint does not
provide its sensor-capture timestamp; this limitation is retained explicitly.

## After commissioning

The primary inputs and endpoints passed one real commissioning capture on
26 September 2026. The next step is the frozen
[`joint-shadow no-motion pilot`](JOINT_SHADOW_PILOT.md). It includes live visible
speech, silent-face phone playback, silent mouthing with unrelated playback,
missing-face and spatial-conflict controls, and activity-only baselines without
synchrony. The current 54-trial confirmation remains paused.
