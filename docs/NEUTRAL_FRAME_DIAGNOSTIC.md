# Read-only neutral-frame diagnostic

## Why this exists

Stage 4 V4 remains blocked because its preflight compares Reachy's measured
4×4 head pose with the daemon's documented neutral pose (identity), while the
desktop controller showed all head fields as `0.000`. Repeated preflights
measured 2.35–4.43° from identity. The 1° gate must not be weakened to make the
disagreement disappear.

Inspection of the official sources explains why the screen is not decisive:

- daemon 1.9.0 computes `present_head_pose` from forward kinematics of present
  head-joint positions and defines the initial/forward neutral pose as identity;
- desktop app v0.9.34 requests the full state with `use_pose_matrix=true` and
  stores `head_pose` as a flattened 4×4 matrix;
- its controller-sync hook then reads that stored value as though it were an
  object with `x`, `y`, `z`, `pitch`, `yaw`, and `roll` properties, replacing
  missing properties with zero;
- the controller reset is not read-only: it interpolates toward a zero target
  and transmits target commands. A zeroed widget therefore cannot be treated as
  independent measured-pose evidence.

The source comparison used the released desktop tag `v0.9.34` (commit
`467ad30e00855cd5051c8483fed00b4e00b57d1a`) and the installed daemon wheel
`reachy-mini==1.9.0`.

Daemon 1.9.0 has a second reporting defect relevant to preflight: the real
backend loop sets its internal `ready` event, but the serialized
`RobotBackendStatus.ready` member is initialized `false` and is not refreshed
by `get_status()`. Successful access to `/api/state/...` is stronger evidence
that the internal event is set because those routes reject requests unless it
is set. The frozen V4 protocol already excludes this serialized field and
requires fresh pose/status telemetry, a healthy control-loop frequency and
interval, zero loop errors, enabled control mode, and no daemon error instead.

## What the diagnostic reads

[`reachy_stage4/neutral_diagnostic.py`](../reachy_stage4/neutral_diagnostic.py)
uses only:

1. HTTP `GET /api/daemon/status`;
2. HTTP `GET /api/apps/startup-app` and
   `GET /api/apps/current-app-status` to record configured/running application
   confounders;
3. HTTP `GET /api/state/present_head_pose` in both matrix and xyz/RPY forms;
4. the server-to-client `/api/state/ws/full` stream with present pose, present
   joints, body yaw, and antenna positions.

It does not import the command-capable Stage 4 adapter. It contains no WebSocket
send, HTTP write method, target endpoint, movement call, torque operation,
homing operation, motor-mode write, camera request, or microphone request. The
test suite audits that transport surface with the Python AST as well as fakes
that expose only `GET` and `recv`.

## Running it

Reachy may remain stationary. Do not press reset or move a controller while the
capture is running. From the repository's installed Python environment:

```bash
python -m reachy_stage4.neutral_diagnostic \
  --frames 20 \
  --frequency 10 \
  --label controller_open_stationary \
  --controller-display-observation "all six head fields appeared as 0.000"
```

The optional UI observation is explicitly stored as operator-reported rounded
text, not telemetry. New structured-startup captures and SHA-256 sidecars are
written immutably under `data/private/stage4a_neutral_diagnostic_v2/`, which is
excluded from Git. The two earlier v1 captures remain immutable historical
diagnostics and cannot be silently relabeled as controlled starts because they
lack the new wake/app/controller context.

## Interpretation

The capture compares three views of the measured pose:

- matrix REST representation;
- xyz/RPY REST representation reconstructed as a matrix;
- matrix state-stream samples, which are the data shape used by the desktop
  app's current state hook.

If those agree while the controller displays zeros, the discrepancy is in the
desktop presentation/synchronization path, not in the daemon's pose frames.
If the daemon representations disagree, Stage 4 remains blocked and the raw
numeric trace should be examined before any motion. Even if all representations
agree, V4 may proceed only when the measured rotation from identity is within
the unchanged 1° preflight limit consistently; this diagnostic does not arm or
authorize motion.

## 2026-09-01 live results

One stationary, command-free capture completed against physical Reachy Mini
hardware with daemon 1.9.0:

- 6 HTTP GETs, 20 state-stream messages received, 0 WebSocket messages sent,
  and 0 robot commands;
- daemon state remained `running`, simulation and mockup simulation were both
  false, motor control was enabled, and the measured control-loop mean was
  49.565 Hz with zero recorded errors;
- stream rotation from identity was 4.159–4.221° (mean 4.183°), with maximum
  drift of 0.092° from the first frame;
- the REST matrix and independently serialized REST Euler pose agreed at the
  first observation; the largest later comparison gap was 0.081°, within the
  observed between-sample drift;
- measured orientation was approximately roll +3.23°, pitch +2.41°, yaw
  −1.08° at the final sample;
- SHA-256 of the immutable private capture is
  `08caf0694662669cb04b072f32bed6bd138ba78fa2229c82014fed17cec9a142`.

The official 1.9.0 analytical inverse-kinematics solution for identity is
approximately `[0, +35.899, -35.898, +35.898, -35.898, +35.898, -35.898]`
degrees for body yaw and Stewart motors 1–6. Relative to the first captured
joint frame, the differences were `[-0.35, -0.74, +2.85, -2.24, +0.83,
-6.19, +3.91]` degrees. This establishes that the non-identity pose is also
present at the joint-state level; it does not by itself distinguish encoder
offset, mechanical calibration, or an unapplied centring target.

Later, after Reachy was turned on again, a second stationary capture used the
same read-only transport:

- stream rotation from identity was 1.333–1.459° (mean 1.409°), with 0.088°
  maximum drift from its first frame;
- translation was 1.24–1.27 mm from identity;
- daemon state remained physical, running, motor-enabled, error-free, and near
  49.35 Hz;
- 6 HTTP GETs and 20 state messages were received, with 0 WebSocket messages
  sent and 0 robot commands;
- the immutable private capture hash is
  `1b10ae59156d5d0cae202ead82204edb2a3c3c99eeec4e53d9716bbbfaa624d6`.

The first captured joint frame differed from nominal identity IK by
approximately `[+0.26, +2.15, -0.39, +0.83, -0.92, +1.80, -1.62]` degrees
for body yaw and Stewart motors 1–6. This is materially different from the
earlier maximum 6.19° discrepancy.

The two captures were not a controlled repeated-start study, so their
difference cannot identify a cause. It does establish that the measured state
should not be treated as one fixed 4.18° offset. Both captures still fail the
unchanged 1° V4 gate.

A separate read-only request asked daemon 1.9.0 for target pose and target
joint fields. The route accepts those flags, but the released `FullState`
response model omits target fields, so they were dropped from the response.
The target-versus-measured error therefore remains unobservable through this
REST surface.

**Decision:** the display/representation ambiguity is resolved, but the
physical-protocol gate failure is not explained. The unchanged 1° preflight
still fails and no V4 movement is authorized. This is not proof of a calibration
fault. The custom centring proposal was subsequently
[rejected for hardware execution](CENTERING_REVIEW.md).
The later controlled three-start result and the more cautious gate/target/
maintenance interpretation are documented in
[`STARTUP_CHARACTERIZATION.md`](STARTUP_CHARACTERIZATION.md) and
[`MAINTENANCE_TRIAGE.md`](MAINTENANCE_TRIAGE.md).
