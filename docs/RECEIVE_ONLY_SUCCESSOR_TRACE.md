# Receive-only present/target trace

## Status

The recorder is implemented and tested, but **no live successor trace has been
captured**. Reachy should remain powered down. The released daemon 1.9.0 drops
the requested target fields from its `FullState` response, so the parser
deliberately returns `TARGET_STATE_UNAVAILABLE` unless the separately reviewed
four-field observability patch is installed.

This is an instrument, not evidence that target state has been observed.

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

The CLI in
[`capture_successor_present_target_trace.py`](../scripts/capture_successor_present_target_trace.py)
also refuses to start without both a byte-verified owner-scope record and a
byte-verified independent-review approval. The owner record must cover:

1. powered receive-only capture;
2. installation of the target-state observability patch; and
3. daemon restart for that patch.

## Why it cannot run yet

Daemon 1.9.0 already accepts `with_target_*` flags and prepares target values,
but released [`FullState`](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/daemon/app/models.py)
does not declare those members. Both the REST and WebSocket full-state routes
therefore serialize them away. The route behavior is visible in the official
[`state.py`](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/daemon/app/routers/state.py).
The repository patch passes isolated route and complete mock-daemon tests, but
it remains uninstalled on the borrowed robot.

## Conditions before any capture

- The owner explicitly approves all three actions above and any conditions.
- The external reply and a structured record are preserved and hashed.
- The patch is independently reviewed before installation.
- Installation and restart are treated as a change to experimental state.
- The first run is state capture only: no target, torque, tracking, antenna,
  body-yaw, media, or app-start command.

Passing the recorder tests does not authorize powering, patching, restarting,
or moving Reachy.
