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

## Minimal upstream repair prototype—not persistently installed

The repair requires two coordinated changes: adding optional target members to
`FullState` matching the keys the route already produces, and preserving an
explicitly unset target pose instead of passing `None` to pose conversion:

```python
target_head_pose: AnyPose | None = None
target_head_joints: list[float] | None = None
target_body_yaw: float | None = None
target_antennas_position: list[float] | None = None
```

The route must return `None` when the backend target pose is `None`; it must not
substitute the present pose or synthesize any other target. An upstream-quality
change should also add REST and WebSocket tests that request
each flag individually and together, exercise matrix and xyz/RPY modes, and
verify omitted flags remain `None` or excluded according to the intended API
contract.

This proposal was not installed into the stock service or persistent runtime.
After isolated validation, it was used from a bounded temporary checkout for a
single live observation and then removed from the robot. The unchanged stock
v1.9.0 service was restored afterward.

The repository now includes the version-pinned
[`reachy-mini-v1.9.0-target-state-observability.patch`](../patches/reachy-mini-v1.9.0-target-state-observability.patch).
It adds exactly those four optional members and the null-preserving route
branch. It applies cleanly to the reviewed exact v1.9.0 source.

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

This historical result closed serialization for defined targets in the first
patch version. It did **not** exercise an explicitly null target. The current
patch supersedes those bytes, so the historical report and hash do not validate
the revised patch.

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

This historical result closed complete-process serialization for defined
targets under mockup isolation. It did not cover the null-target startup state,
and its patch hash belongs to the superseded patch. It is still not an on-robot
deployment, a physical target measurement, unit confirmation, calibration
repair, concurrent-update stress test, or motion authorization.

### Powered observation finding and revised semantic contract

An initial bounded 2026-09-18 observation attempt reached a healthy temporary
control loop with motors disabled, then failed closed at the target route
because all three requested target values were null. A revised route preserved
that coherent null state instead of trying to convert it to a pose. A later
bounded live capture retained 193 frames over 10 seconds; all 193 reported
`target_state=UNSET`, with zero target-state transitions, zero trace-client
application messages, and zero robot commands. No movement stage followed, and
the stock service was restored healthy with motors disabled.

The revised trace contract therefore distinguishes:

- **absent keys**: the schema repair is unavailable, so fail closed;
- **all target values null**: preserve a coherent `UNSET` target state;
- **all target values defined**: validate and preserve a `DEFINED` state; and
- **partially null values**: fail as inconsistent.

Present state is never copied into target state. The observation-only protocol
may explicitly accept `UNSET`; a later motion-specific protocol must require an
observed `UNSET -> DEFINED` transition or another predeclared defined-target
criterion. The revised endpoint validator adds released-source and patched
null-target controls. A complete official-v1.9.0 mock-daemon follow-up also
passed: both processes exited cleanly, the patched process returned HTTP 200
with all target keys and an explicit null target pose, and the loopback guard
observed no non-loopback attempt. The mock control loop repopulated some other
targets concurrently, so the extracted-route test—not the full-process
result—is the atomic all-null assertion. The immutable private full-process
report has SHA-256
`ab2726275ccd74a708da98edff6821c5e86c37ae6fd8bfd6a755ff5816763f7d`.
Both validators record zero robot connections and zero commands. Together with
the bounded live result, this closes the null-route and observation-trace gates.
It does not establish a defined target or close any motion-specific gate.

## Present project decision

The bounded live diagnostic recorded present and target state in the same
frames without inference. The observed target remained coherently `UNSET`
throughout, so the result cannot validate target tracking or a return path. The
patch is not persistently installed; V4 and the rejected custom centring
proposal remain blocked, and this document authorizes zero robot commands.

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
