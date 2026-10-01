# Reachy-camera command-free commissioning

Status: **REAL RECEIVE-ONLY TRANSPORT WORKING — LANDMARK COMMISSIONING REQUIRED**

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
stopped. From the repository root:

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

## Decision after commissioning

If every check passes, create a separately fingerprinted successor no-motion
pilot that uses Reachy's camera. Do not rename or reuse laptop-camera v1/v2
attempts.

If robot video cannot sustain the frame/freshness/landmark gates, stop and
improve that path before collection. If visual timing passes but the laptop
microphone remains necessary, record that external-sensor dependency
explicitly and decide whether to build robot-audio access or narrow the system
claim. Do not silently call a laptop-audio system fully robot-native.
