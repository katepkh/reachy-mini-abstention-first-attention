# Receive-only present/target trace

## Status

A valid bounded live successor trace was captured on 2026-09-18 after two
contained fail-closed rehearsals exposed and repaired a patch-staging error and
a client deadline-handling error. The final capture retained 193 frames over
10 seconds. Every frame reported the coherent target state `UNSET`; no
`UNSET -> DEFINED` transition occurred. The trace client sent zero application
messages and zero robot commands.

The temporary daemon passed its opening and terminal health gates with motors
disabled, a fresh approximately 50 Hz state stream, and zero reported loop or
hardware errors. It then exited and released its listener and serial resource.
The unchanged stock v1.9.0 service was restored with one process, listener, and
serial owner; a final independent check again found motors disabled, fresh
telemetry, and zero reported errors. No movement stage was entered.

This is evidence of a valid observation trace, not evidence that a defined
target state has been observed and not authorization to move the robot.

At the requested 20 Hz trace rate, the 193 frames spanned 9.921 seconds. The
median, 95th-percentile, and maximum inter-frame intervals were 51.439 ms,
53.597 ms, and 58.289 ms. Relative to the first frame, maximum measured pose
drift was 0.090 degrees and 0.054 mm; maximum drift in any reported head joint
was 0.088 degrees. These are descriptive disabled-motor baseline measurements,
not approved tracking tolerances or motion abort thresholds.

“Receive-only” describes the trace client's application traffic. The enclosing
daemon lifecycle now permits one separate, predeclared motor-disable safety
action only if fresh responsive telemetry unexpectedly reports motor control
enabled at shutdown. That contingent safety action is not an experimental
trace command and does not make the recorder command-capable.

External authorization and technical review remain outside this repository. No
correspondence, identity, reply, or approval artifact is retained here.

## What it records

[`successor_trace.py`](../reachy_stage4/successor_trace.py) opens only the
daemon's `/api/state/ws/full` state stream and requests, in the same frames:

- present and target head pose;
- present and target seven-joint vector;
- present and target body yaw;
- daemon timestamp and control mode; and
- local receive time.

It performs one WebSocket handshake, calls `recv`, and writes an immutable JSON
file plus SHA-256 sidecar. It has no application-level `send`, task route,
motor-mode write, camera/microphone request, or robot-command method. A
WebSocket handshake is still protocol traffic; “receive-only” means zero
client **application messages** after that handshake, not zero packets.

Trace schema v2 preserves three distinct cases without substituting present
state for target state:

- all target keys absent: fail with `TARGET_FIELDS_ABSENT`;
- all three target values explicitly null: retain `target_state=UNSET`; and
- all three target values present: validate and retain
  `target_state=DEFINED`.

A partially null target fails as inconsistent. A later protocol may require at
least one defined target or an observed `UNSET -> DEFINED` transition; the
observation-only rehearsal permits `UNSET` explicitly.

The CLI in
[`capture_successor_present_target_trace.py`](../scripts/capture_successor_present_target_trace.py)
also refuses to start without both a byte-verified owner-scope record and a
byte-verified independent-review approval. The owner record must cover:

1. powered receive-only capture;
2. installation of the target-state observability patch; and
3. daemon restart for that patch.

## Validation preceding the successful capture

Daemon 1.9.0 already accepts `with_target_*` flags and prepares target values,
but released [`FullState`](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/daemon/app/models.py)
does not declare those members. Both the REST and WebSocket full-state routes
therefore serialize them away. The route behavior is visible in the official
[`state.py`](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/daemon/app/routers/state.py).
The first patch version passed isolated route and complete mock-daemon tests
for defined targets, but did not cover a route receiving an explicit null
target. The revised patch makes the route preserve that null value, and the
endpoint validator includes null-target negative and positive controls. The
revised combination passed extracted-route and complete official-v1.9.0
mock-daemon validation, including an explicit null target pose. A separate
lifecycle patch exposed explicit no-reflash, no-startup-app, and no-mDNS
controls and passed an exact-source offline validator. Both patches were used
from an isolated temporary checkout and were not persistently installed; see the
[`temporary-daemon lifecycle review`](TEMPORARY_DAEMON_LIFECYCLE.md).

The attempt also showed that backend construction writes configured PID gains
to the motor controllers even when wake, reflash, torque enable, and movement
are suppressed. Accordingly, “receive-only” applies only to the trace client's
application traffic. The enclosing controller lifecycle is not command-free.

## Conditions enforced for the completed capture

- Any required external authorization is obtained and managed outside this
  repository; no message, reply, identity, or response hash is stored here.
- The patch is independently reviewed before installation.
- The separate lifecycle patch and exact loopback-only invocation are reviewed.
- The offline mock-process failure rehearsal passes; this is already satisfied,
  but it does not prove real serial, torque, or gravity-drop behavior.
- The stock service reports no motor error before shutdown and motor control
  disabled after shutdown; otherwise controller construction is prohibited.
- The terminal lifecycle is preaccepted: fresh `Disabled` stops and verifies
  release; fresh `Enabled` permits one safety-disable and verification;
  unresponsive/stale/unknown state starts no new daemon and takes the physical
  power-off branch with the Stewart-platform drop zone clear.
- Installation and restart are treated as a change to experimental state.
- Backend construction PID writes are declared and accepted as part of the
  controller lifecycle; they may not be described as read-only.
- The first run is state capture only: no target, torque, tracking, antenna,
  body-yaw, media, or app-start command.

Completing this observation does not authorize the later 3-degree movement,
automatic return, calibration, firmware change, or any further powered run.
