# Target-state observability gap

## Finding

Reachy Mini daemon 1.9.0 internally stores target head pose and target head
joints, but no released read-only remote surface found in this review returns
those values intact.

- The [`/api/state/full` implementation](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/daemon/app/routers/state.py)
  accepts `with_target_head_pose` and `with_target_head_joints` and adds those
  keys to a result dictionary.
- It then validates the result through
  [`FullState`](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/daemon/app/models.py),
  whose released schema has no target fields. Pydantic therefore drops them.
- `/api/state/ws/full` calls the same `get_full_state()` function and serializes
  the same model, so its target flags have the same defect.
- The SDK WebSocket's read-only `GetStateCmd` response returns present head
  pose, present antennas, body yaw, motor mode, recording/move status, and face
  target—but not stored motor or Cartesian targets.

A live GET on 2026-09-01 requested target pose and joints and confirmed that
both fields were absent. No robot command was sent.

## Why this blocks interpretation

The backend's
[`enable_motors()`](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/daemon/backend/robot/backend.py)
pins targets to present state before enabling torque. Normal daemon startup then
calls
[`wake_up()`](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/daemon/backend/abstract.py),
which requests the initial pose, performs a roll, and requests the initial pose
again. A configured startup app may run afterward.

Source inspection therefore describes intended target transitions, but it does
not prove the target stored at the exact time of a later measurement. Without
present and target values in the same timestamped observation, we cannot
distinguish:

- a non-neutral stored target;
- a neutral target with steady-state tracking error;
- a later application/controller target;
- or initialization/mechanical variability.

## Minimal upstream repair prototype—not installed

The smallest read-only repair appears to be adding optional target members to
`FullState` matching the keys the route already produces:

```python
target_head_pose: AnyPose | None = None
target_head_joints: list[float] | None = None
target_body_yaw: float | None = None
target_antennas_position: list[float] | None = None
```

An upstream-quality change should also add REST and WebSocket tests that request
each flag individually and together, exercise matrix and xyz/RPY modes, and
verify omitted flags remain `None` or excluded according to the intended API
contract.

This proposal has **not** been installed on Reachy. Modifying the robot's daemon
during an unresolved mechanical study would change the experimental software
state. It should first be tested in an isolated environment and reviewed as a
separate upstream fix.

The repository now includes the version-pinned
[`reachy-mini-v1.9.0-target-state-observability.patch`](../patches/reachy-mini-v1.9.0-target-state-observability.patch).
It adds exactly those four optional members and applies cleanly to
`models.py` extracted from the released 1.9.0 wheel.

An isolated Pydantic reproduction in
[`target_schema_probe.py`](../reachy_stage4/target_schema_probe.py) verifies
that:

- the released `FullState` field set drops all four route-produced target keys;
- the patched field set preserves all four;
- both matrix and xyz/RPY target-pose representations survive serialization;
- omitted target flags do not synthesize values; and
- the probe has no Reachy import, network transport, or command surface.

### Extracted-route integration result

The follow-up
[`validate_target_schema_endpoints.py`](../scripts/validate_target_schema_endpoints.py)
tested the actual `models.py` and `state.py` extracted from the official 1.9.0
wheel. It used a non-hardware stub backend and FastAPI `TestClient`; it neither
imported the Reachy SDK nor opened a robot or network connection.

The test first ran the **unmodified released source as a negative control** and
then applied only the four-field patch to a separate extracted copy:

| Surface | Released 1.9.0 | Patched copy |
|---|---|---|
| REST `/state/full`, matrix pose | 0/4 target fields retained | 4/4 retained |
| REST `/state/full`, xyz/RPY pose | 0/4 target fields retained | 4/4 retained |
| WebSocket `/state/ws/full`, matrix pose | 0/4 target fields retained | 4/4 retained |

The validator also checked that the patch applies cleanly to the extracted
wheel source. The immutable private report has SHA-256
`8c148646266e58ca15c72a2aaf272f135eceaa89f436c50794aeba5f4d9e643a`;
the tested wheel hash is
`9d3f8551c42bd12b43f47a1f3fe5e8c39ca0c2ff6d02c27b094ed0f5586c7655`
and the patch hash is
`7b5c07f1cfef9d56406398d2d288080dafed8e12a8894be05406c38da5cf2cbd`.
Robot connections, commands sent, and commands authorized were all zero.

This closes the REST/WebSocket serialization question for the extracted 1.9.0
routes. It does not prove the runtime target on this unit, validate concurrent
target updates, or authorize changing the robot.

### Complete isolated daemon-process result

The stronger follow-up
[`validate_target_schema_daemon.py`](../scripts/validate_target_schema_daemon.py)
started two complete Reachy Mini daemon application processes from the same
official 1.9.0 wheel source: an unmodified negative control and a copy with only
the four-field patch applied. Both ran the official mockup backend. The harness
bound the HTTP/WebSocket server to `127.0.0.1`, rejected non-loopback INET
traffic, disabled media, mDNS, configured startup apps, and dataset updates,
and shut each daemon down through its health-check timeout.

| Complete daemon surface | Released 1.9.0 | Patched copy |
|---|---|---|
| REST `/api/state/full`, matrix pose | 0/4 target fields retained | 4/4 retained |
| REST `/api/state/full`, xyz/RPY pose | 0/4 target fields retained | 4/4 retained |
| WebSocket `/api/state/ws/full`, matrix pose | 0/4 target fields retained | 4/4 retained |

Both processes reported daemon version 1.9.0, `mockup_sim_enabled=true`,
`simulation_enabled=false`, and `no_media=true`; both exited cleanly with code
zero. No non-loopback attempt was observed, and robot connections, commands
sent, and commands authorized were all zero. Before process launch, the
validator also byte-compared the released source files with the supplied wheel
and reverse-checked the patched tree against the supplied patch. The immutable
private report has SHA-256
`cf6a0f9920fcaab31b6cee176196c32b100278e89a535249f9891e333b5576ea`;
it records wheel SHA-256
`9d3f8551c42bd12b43f47a1f3fe5e8c39ca0c2ff6d02c27b094ed0f5586c7655`
and patch SHA-256
`7b5c07f1cfef9d56406398d2d288080dafed8e12a8894be05406c38da5cf2cbd`.

This closes the complete-process serialization question under mockup isolation.
It is still not an on-robot deployment, a physical target measurement, unit
confirmation, calibration repair, concurrent-update stress test, or motion
authorization.

## Present project decision

The current diagnostic records configured/running app context and present
pose/joints only. It does not infer target state. The isolated patch remains
uninstalled; V4 and the rejected custom centring proposal remain blocked, and
this document authorizes zero robot commands.

To reproduce the endpoint test in an isolated environment:

```bash
python -m pip install -e ".[upstream-test]"
python scripts/validate_target_schema_endpoints.py \
  --wheel /path/to/reachy_mini-1.9.0-py3-none-any.whl
```

The output path is private and immutable by default. A Git executable is also
required to apply-check the patch against the extracted source.

The complete-process validator additionally requires a Python environment with
the official Reachy Mini 1.9.0 wheel and all of its runtime dependencies
installed. Extract the official wheel twice, apply the repository patch to one
copy (strip the wheel source prefix when necessary), and run:

```bash
python scripts/validate_target_schema_daemon.py \
  --released-source /path/to/released-wheel-root \
  --patched-source /path/to/patched-wheel-root \
  --wheel /path/to/reachy_mini-1.9.0-py3-none-any.whl \
  --patch patches/reachy-mini-v1.9.0-target-state-observability.patch
```

The validator refuses non-loopback daemon traffic, uses the mockup backend, and
writes an immutable private report by default.
