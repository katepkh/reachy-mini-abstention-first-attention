# Command-free startup characterization

## Purpose

This protocol asks a narrower question than calibration:

> After equivalent physical power cycles, does this Reachy Mini settle into a
> repeatable measured head state before any controller or application input?

It does not correct the robot, validate calibration, or authorize V4. The
capture client uses HTTP `GET` plus a receive-only state stream and reports zero
robot commands. The private aggregator also has no network or robot transport.

## Why the controls matter

Released daemon 1.9.0 performs several distinct actions during normal startup:

1. enabling the motors pins joint, antenna, Cartesian-head, and body-yaw targets
   to the present measured state;
2. normal daemon startup then runs `wake_up()`, which targets the initial pose,
   rolls the head, and targets the initial pose again;
3. a configured startup app may launch after wake-up and can subsequently own
   the robot.

See the official 1.9.0
[`daemon.py`](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/daemon/daemon.py),
[`robot/backend.py`](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/daemon/backend/robot/backend.py),
and [`abstract.py`](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/daemon/backend/abstract.py).

This makes wake completion, startup-app state, startup age, and controller
contact potential confounders. The diagnostic now reads both configured and
currently running app state. The aggregator rejects captures with any startup
app configured or running, any controller contact, fewer than 20 frames, a
nonphysical backend, a version mismatch, or a nonzero command/send audit.

## Powered-off visual inspection

Perform this once while Reachy is fully powered off and stationary. Do not
disassemble, lubricate, manually reposition the head, alter homing offsets, or
change motor configuration.

- Verify the robot is on a firm, level surface.
- Check that the USB cable entering the head has visible slack and is not taut,
  pinched, twisted around a linkage, or caught between shells.
- Look for an obvious detached, crossed, bent, or obstructed Stewart rod.
- Look for visible residue or contamination around the spherical joints.
- Check for shell-to-shell contact or another object touching the head.
- Record only observations; do not turn an observation into a repair during
  this protocol.

The official [motor diagnosis guide](https://github.com/pollen-robotics/reachy_mini/blob/main/docs/source/troubleshooting/motors_diagnosis.md)
and [general troubleshooting guide](https://github.com/pollen-robotics/reachy_mini/blob/main/docs/source/troubleshooting.md)
motivate the cable/joint checks. They do not establish that any listed issue is
present on this unit.

### 2026-09-01 operator inspection record

With Reachy powered off, the operator supplied nine close-up photographs and
reported: no cable appeared stretched tight or trapped beneath a rod; all six
rods appeared connected at both ends; and no residue, damage, or loose part was
noticed. Image review found no obvious detached or severely bent rod, missing
visible fastener, or clear shell/linkage contact. Wiring remains visually
crowded and close to the mechanism, so still images cannot establish dynamic
clearance, hidden contact, preload, or friction.

**Disposition:** `NO_OBVIOUS_VISUAL_OBSTRUCTION`; this is an operator-assisted
visual observation, not mechanical clearance or calibration certification.

## Controlled capture sequence

Use at least three complete physical power cycles. Five would describe this one
unit better, but three is the minimum before the aggregator stops labeling the
series insufficient.

For each index:

1. Power Reachy down using the same normal shutdown method used previously and
   wait until it is fully off.
2. Do not manually reposition its head or antennas.
3. Power it on once and observe whether the normal wake animation completes.
4. Do not touch Reset, any controller control, an application `Start` button,
   the head, body, or antennas.
5. Wait a fixed 60 seconds after the wake animation finishes. If the wake did
   not occur, record `no`; if uncertain, record `unknown` and do not silently
   recode it later.
6. Run one capture, replacing `N` with the startup index:

```bash
python -m reachy_stage4.neutral_diagnostic \
  --frames 20 \
  --frequency 10 \
  --label cold_start_N \
  --startup-kind physical_power_cycle \
  --startup-index N \
  --startup-age-seconds 60 \
  --wake-animation-observed yes \
  --startup-app-observed no \
  --controller-touched-since-start no
```

The `startup-app-observed` field is an operator annotation. Independently, the
capture reads `/api/apps/startup-app` and `/api/apps/current-app-status`; the
aggregator requires both to be empty.

After all captures, build a private checked report by listing the exact JSON
paths:

```bash
python -m reachy_stage4.startup_characterization \
  --capture data/private/stage4a_neutral_diagnostic_v2/<cold-start-1>.json \
  --capture data/private/stage4a_neutral_diagnostic_v2/<cold-start-2>.json \
  --capture data/private/stage4a_neutral_diagnostic_v2/<cold-start-3>.json
```

The report verifies each adjacent SHA-256 sidecar, orders unique startup
indices, reports capture-mean spread and whole-trace 1° gate outcomes, and
authorizes zero V4 commands.

## Result: three controlled starts on 2026-09-01

Three equivalent physical power cycles completed the minimum series. In every
case the operator observed the wake animation, waited 60 seconds, did not touch
the controller or robot, and observed no application running. The capture also
read no configured startup app and no current app. Each trace contained 20
receive-only state frames; across the complete series the clients sent zero
WebSocket messages and zero robot commands.

The daemon status reported motor control `enabled` both before and after every
capture. All six before/after status observations reported zero control-loop
errors and no daemon or backend error. This rules out disabled torque during
the sampled intervals as an explanation for these traces; it does not prove
that the retained target was identity or that the mechanism was unloaded.

| Start | Rotation from identity, min–max | Mean | Maximum within-trace drift | Capture SHA-256 |
|---|---:|---:|---:|---|
| 1 | 2.470–2.538° | 2.529° | 0.074° | `ccf0fbeef4c0f3e39edab4b79d58a1e5ffc98741ea40c54f94b1d95641fec99e` |
| 2 | 2.693–2.768° | 2.752° | 0.095° | `45245e06d4890b9e79ea68ba9e97405311276557a2af8d8e507fa86e538047fe` |
| 3 | 2.704–2.795° | 2.746° | 0.170° | `020e8840421bcb464e93b9ffe3ac9cbd35c2a58db77b3485fe6076d71d6dcc93` |

The capture means span 2.529–2.752° (range 0.223°, overall mean 2.676°).
All three complete traces were outside the frozen 1° neutral gate, so the
aggregator returned `START_STATE_OUTSIDE_GATE` and authorized zero V4 commands.
The checksum-verified private aggregate report has SHA-256
`84b04e976cc38e5773f8bfd8573aa90fde9e925444262adc72b99150f242fc56`.

**Disposition:** the narrow result is a repeatable non-identity measured start
state for this unit under this three-start protocol. It is evidence against
treating the earlier 4.18° state as a fixed offset, but it does not distinguish
geometric calibration, stored target, kinematic model, assembly preload,
friction, cabling, or another cause. The 1° gate remains unchanged and V4
physical motion remains blocked.

The follow-up [`post-wake identity-reference audit`](POST_WAKE_REFERENCE_AUDIT.md)
confirms that identity is daemon 1.9.0's source-defined wake endpoint and finds
the same repeatable residual in measured joint space. It still cannot observe
the retained live target or assign a mechanical/calibration cause.
The source-backed [`maintenance triage`](MAINTENANCE_TRIAGE.md) maps the
remaining explanations to discriminating evidence and explicitly excludes
configuration writes or disassembly without owner/maintainer approval.

## Interpretation boundary

- Different settled states establish startup variability but do not identify
  its mechanical or software cause.
- Repeatable non-neutral states may motivate maintenance investigation but are
  not an independently measured geometric calibration.
- Three or five starts describe this robot under one setup; they are not a
  population sample or long-term reliability estimate.
- Even three all-pass captures would not automatically authorize V4. Target
  observability, maintenance disposition, and a newly reviewed frozen motion
  protocol remain separate gates.
