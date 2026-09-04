# Baseline-relative Stage 4A successor: design-only review draft

## Current status

**Do not power Reachy on for this draft.** This is a separately versioned
successor concept, not a modification of V4 and not an executable protocol.
It authorizes zero robot connections and zero commands.

V3 remains failed and V4 remains blocked against its frozen 1-degree identity
gate. A successor may use information learned from those outcomes, but it must
say that its choices are post-V4, freeze them before collecting new hardware
outcomes, and never relabel the earlier results.

## Why a successor is now more defensible than custom centring

Three controlled starts produced a repeatable post-wake measured state near
2.7 degrees from identity, with motors enabled and no reported control-loop
error. The state failed the project's 1-degree V4 gate, but that gate is not a
manufacturer tolerance.

Daemon 1.9.0's normal wake routine already requests identity, a 20-degree roll,
and identity again. The operator observed wake on all three controlled starts.
This establishes that the mechanism executed a built-in motion sequence; it
does not prove exact endpoint accuracy, dynamic clearance, or the safety of a
new command.

The current official troubleshooting page describes nominal head pitch/roll
limits of -40 to +40 degrees and says out-of-range poses are clamped. Exact
1.9.0 analytical IK also uses a bounded safe inverse-kinematics call, but its
`check_collision` argument is unused. These facts support checking a small
baseline-relative candidate against an explicit absolute envelope. They do
not turn a project-selected envelope into a certified safety limit.

## Candidate question

> From a stable, healthy, measured start pose inside a conservative absolute
> envelope, can one head-only 3-degree baseline-relative increment and a
> separately approved return be measured correctly?

This is still manual mechanical characterization. It does not connect acoustic
or visual attention to motors.

## Candidate gates selected before any V5 hardware outcome

These values are **post-V4 design candidates and review debt**:

| Candidate boundary | Draft value | Why it exists | Limitation |
|---|---:|---|---|
| Baseline samples | at least 50 | Five seconds at 10 Hz is more informative than a single frame. | Sampling rate and duration are not validated for faults. |
| Maximum pairwise baseline rotational spread | at most 0.25 degrees | Must be stationary across the entire capture, including drift on opposite sides of the first sample. | Chosen after observing maximum 0.170-degree drift. |
| Maximum pairwise baseline translation spread | at most 1 mm | Reject an unstable platform estimate without anchoring the result to the first sample. | Project-selected, not vendor specified. |
| Absolute roll, pitch, and yaw at baseline and candidate target | at most 10 degrees each | Makes axis excursions visible and bounded. | Euler components are representation-dependent and do not bound combined rotation. |
| Geodesic rotation from identity at baseline and candidate target | at most 10 degrees | Prevents several individually small Euler components from admitting a much larger combined rotation. | Conservative engineering choice; not a collision guarantee. |
| Translation from identity | at most 8 mm | Retains V4's narrow translation neighborhood. | Existing project bound, not a hardware certification. |
| Relative candidate increment | exactly 3 degrees | Preserves the original mechanical mapping question. | Prior V3 under-responded; usefulness remains empirical. |

The pure
[`successor_review.py`](../reachy_stage4/successor_review.py) implements only
these geometry/evidence checks. Even when every record is marked complete, its
status remains `DESIGN_ONLY_NO_COMMAND_AUTHORITY` and it authorizes zero
commands.

For a stable capture, the draft uses the freshest sample as the candidate
baseline and computes stability from the maximum pairwise spread across all
samples. Neither choice establishes endpoint accuracy or hardware safety.

## Review records that remain mandatory

The packet stays blocked until all of the following have real records:

- the frozen V4 outcome is preserved;
- expected post-wake accuracy and the replacement for the 1-degree gate are
  reviewed;
- the retained-target observability strategy is reviewed;
- the complete interpolated path and per-joint limit margins are reviewed;
- failure/return behavior is reviewed;
- the borrowed robot's permitted scope is confirmed for the proposed action;
- an independent robotics reviewer has reviewed the complete protocol.

Boolean fields in a JSON report are not evidence. The helper requires each
record to contain a non-empty `artifact_reference`, a 64-character
`artifact_sha256`, `recorded_by`, and a UTC `recorded_at_utc`; it still cannot
verify that the referenced review is sound.
Each reference must resolve to the corresponding artifact, reviewer record, or
owner authorization before a human reviewer marks the packet complete.

The successor also defines its own 3-degree constant and target construction.
It does not import V4's movement constant or executable pilot.

## Successor implementation status before execution can be proposed

| Requirement | Status | Evidence / remaining boundary |
|---|---|---|
| Observe present and retained target pose/joints together | **Instrument complete; live evidence blocked** | The [`receive-only recorder`](RECEIVE_ONLY_SUCCESSOR_TRACE.md) fails closed on released 1.9.0 because its response schema drops target fields. The tested observational patch is uninstalled. |
| Reconstruct the exact 1.9.0 target and return interpolation | **Offline complete** | [`SUCCESSOR_TRAJECTORY_REVIEW.md`](SUCCESSOR_TRAJECTORY_REVIEW.md) cross-checks 201 samples per leg against official `GotoMove` to `4.44e-16`. Actual live write times remain scheduler-dependent. |
| Run exact 1.9.0 IK and compare configured joint limits | **Offline complete, safety incomplete** | The minimum supplied configured-limit margin was 42.706°. No acceptable-margin threshold, collision, conditioning, load, cable, or enclosure check has been approved. |
| Add a receive-only continuous recorder | **Code complete; not run** | It sends zero client application messages and writes immutable traces, but requires owner-approved patch/restart first. |
| Split target and return authorization | **Design state machine complete; no executor** | [`SPLIT_TARGET_RETURN_PROTOCOL.md`](SPLIT_TARGET_RETURN_PROTOCOL.md) requires a new return trace, phrase, and identifier. Failure leads to supervised power-down, not an automatic second command. |
| Record owner scope and independent robotics approval | **Limited owner lifecycle scope recorded; human review absent** | The private hash-verified owner record covers the temporary observational daemon and restoration, not physical target/return motion. Use [`OWNER_SCOPE_REQUEST.md`](OWNER_SCOPE_REQUEST.md) and [`INDEPENDENT_PROTOCOL_REVIEW.md`](INDEPENDENT_PROTOCOL_REVIEW.md). AI review does not satisfy the independent gate. |
| Freeze a command-capable successor | **Not started** | It cannot begin until the external gates and command-free live trace pass. |

The current V4 executor attempts return in `finally` after any target attempt
and retains only the latest pose. It does not satisfy the successor design and
must not be reused as V5.

## Earliest justified power-on point

Power-on becomes useful only after an independent reviewer approves the
observability plan; the owner has already confirmed the limited powered
temporary-daemon and restore/verify request. The first powered step should
still be command-free:

1. normal startup with the exterior fully reassembled;
2. no controller or app interaction;
3. one checksum-preserved stability capture including motor mode, errors,
   present state, and reviewed target-state telemetry;
4. stop if the state differs materially from the reviewed envelope;
5. power down and review that capture before separately deciding whether one
   `UP` trial is justified.

## Official sources

- Exact 1.9.0
  [`wake_up()`](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/daemon/backend/abstract.py)
  defines the identity/20-degree-roll/identity sequence.
- Exact 1.9.0
  [`AnalyticalKinematics`](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/kinematics/analytical_kinematics.py)
  documents that its collision-check argument is unused.
- The current official
  [troubleshooting page](https://github.com/pollen-robotics/reachy_mini/blob/main/docs/source/troubleshooting.md)
  lists nominal head/body limits. It may postdate daemon 1.9.0 and is not an
  accuracy specification.
