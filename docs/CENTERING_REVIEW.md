# Source-backed review of the centring proposal

## Decision

**REJECT physical execution of the custom centring proposal in its current
form.** Keep the planner as a command-free counterfactual artifact, but do not
write or run an executor from it.

This is a second-pass engineering review against released Reachy Mini sources,
official troubleshooting guidance, two zero-command traces, the failed V3
trial, and primary Stewart-platform calibration literature. It is not an
independent human safety sign-off or a certified risk assessment.

The reason for rejection is not that the SO(3) waypoint arithmetic is wrong.
It is that the observed state has not been diagnosed well enough for a pose
command to count as calibration, repair, or a controlled experiment. The
current evidence cannot distinguish a stored-target problem, initialization
state, encoder/offset issue, geometric calibration error, compliance/friction,
or another mechanical constraint. A small command would change the mechanism
without identifying which explanation is true.

## Evidence reviewed

### 1. What the official Testbench result does and does not establish

The official [motor diagnosis guide](https://github.com/pollen-robotics/reachy_mini/blob/main/docs/source/troubleshooting/motors_diagnosis.md)
uses motor scan to establish that motors are detected and then asks for
`Check all motors` when problems remain. The released setup code's
[`check_configuration`](https://github.com/pollen-robotics/reachy_mini/blob/main/src/reachy_mini/tools/setup_motor.py)
reads and compares motor ID/presence, return-delay time, operating mode, raw
angle limits, homing offset, and shutdown configuration.

Therefore the observed `9 / 9 motors found` and `Config Status: ALL OK` are
valuable: they argue against a missing motor and against those stored
configuration fields being wrong. They do **not** compare requested and
measured Cartesian motion, validate the assembled Stewart geometry, measure
joint friction or cable restriction, or calibrate the physical neutral frame.
They cannot turn the current offset into a known-safe correction problem.

The same official guide identifies two physical checks relevant when motors
are detected but head motion still fails: motor/arm placement under the guide's
specific inversion symptoms, and sufficient USB-cable slack so the head can
move freely. The general [Reachy troubleshooting guide](https://github.com/pollen-robotics/reachy_mini/blob/main/docs/source/troubleshooting.md)
also treats squeaking/friction and residue at Stewart spherical joints as a
maintenance condition. None of these causes has been established on this
robot; they are inspection hypotheses, not findings.

### 2. Desktop zeros are not measured neutral

Inspection used Reachy Mini Control v0.9.34, released at commit
[`467ad30`](https://github.com/pollen-robotics/reachy-mini-desktop-app/releases/tag/v0.9.34).
At that exact tag:

- [`useRobotStateWebSocket.ts`](https://github.com/pollen-robotics/reachy-mini-desktop-app/blob/v0.9.34/src/hooks/robot/useRobotStateWebSocket.ts)
  asks for `use_pose_matrix=true`, unwraps `{m}` and stores the flattened 4x4
  matrix as `head_pose`;
- [`useControllerSync.ts`](https://github.com/pollen-robotics/reachy-mini-desktop-app/blob/v0.9.34/src/views/active-robot/controller/hooks/useControllerSync.ts)
  casts the same value as an object with `x`, `y`, `z`, `pitch`, `yaw`, and
  `roll`, then substitutes zero for every missing field;
- [`globalResetSmoothing.ts`](https://github.com/pollen-robotics/reachy-mini-desktop-app/blob/v0.9.34/src/utils/globalResetSmoothing.ts)
  sets a zero head/body/antenna target and can transmit target commands. It is
  not a measurement operation.

The controller's six `0.000` head fields therefore cannot show that the
measured head is neutral. The reset action also cannot serve as an independent
test of whether a neutral target was reached.

### 3. The current target is not observable through the released REST model

The released daemon is
[`reachy-mini==1.9.0`](https://github.com/pollen-robotics/reachy_mini/releases/tag/v1.9.0).
Its [`/api/state/full` route](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/daemon/app/routers/state.py)
accepts `with_target_head_pose` and `with_target_head_joints`, constructs those
keys, and then validates the result through `FullState`. But the released
[`FullState` model](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/daemon/app/models.py)
contains present pose/joints only and has no target fields. A live read-only
request on 2026-09-01 confirmed that the requested target fields were absent.

Consequently, this public REST surface cannot answer the decisive diagnostic
question: is the controller already storing a neutral target that the measured
mechanism is failing to reach, or is the stored target itself non-neutral?
Sending another neutral command before answering that question would repeat an
operation, not isolate a cause.

### 4. The first uncontrolled observations were not one fixed offset

Two private, immutable, zero-command captures on the same date produced
different settled states:

| Capture | Rotation from identity | Translation from identity | Maximum drift from first frame | Commands |
|---|---:|---:|---:|---:|
| Earlier controller-open capture | 4.159–4.221° (mean 4.183°) | 3.73–3.77 mm | 0.092° | 0 |
| Later source-review capture | 1.333–1.459° (mean 1.409°) | 1.24–1.27 mm | 0.088° | 0 |

The later capture SHA-256 is
`1b10ae59156d5d0cae202ead82204edb2a3c3c99eeec4e53d9716bbbfaa624d6`.
It used 6 HTTP GETs and 20 server-to-client state messages, with 0 WebSocket
messages sent and 0 robot commands. The daemon remained physical, running,
motor-enabled, error-free, and near 49.35 Hz.

These observations do not prove why the state changed; they were not a
controlled repeated-start study. They do prove that a single 4.18° correction
plan is stale and that “the offset” should not yet be modeled as one stable
calibration constant. The later state still fails the unchanged 1° V4 gate.

A subsequent controlled three-power-cycle series supersedes that repeatability
question for the defined startup protocol: the means were 2.529°, 2.752°, and
2.746° (range 0.223°), with motor mode enabled and zero reported control-loop
errors in every capture. This establishes a repeatable measured post-wake
residual for this unit under that protocol. It does not establish that the
residual is a calibration constant or hardware fault; the retained target was
not observable, and the 1° gate is a project threshold rather than a vendor
tolerance. See [`STARTUP_CHARACTERIZATION.md`](STARTUP_CHARACTERIZATION.md) and
[`MAINTENANCE_TRIAGE.md`](MAINTENANCE_TRIAGE.md).

### 5. The previous physical response weakens the proposed controller model

The only V3 physical pilot requested 3° but measured 1.350° of motion, with a
2.079° target error and 1.678° return error. Some measurement defects were
diagnosed afterward, but the result still provides no empirical basis for the
draft's 1.5° waypoint, 2° measured-step envelope, 0.25° progress floor, or four
attempt allowance. Those values were engineering guesses, several selected
after seeing the 4.18° case.

### 6. Reachability is not collision or calibration assurance

The official desktop technical context lists the default
`AnalyticalKinematics` engine as having no collision check; collision checking
is associated with the Placo engine, not the default. See the official
[`CONTEXT.md`](https://github.com/pollen-robotics/reachy-mini-desktop-app/blob/v0.9.34/CONTEXT.md).
Nominal analytical IK returning six joint values therefore does not establish
collision freedom, cable clearance, calibrated geometry, current margin, or a
safe continuous path on this physical unit.

Primary Stewart-platform work explains the deeper problem. Ibaraki et al.
note that platform pose is only indirectly estimated from servo angles and
that high-accuracy control requires calibration of geometric parameters such
as strut reference lengths and base-joint locations; their calibration uses
independent trajectory measurement over the workspace
([paper](https://skoge.folk.ntnu.no/prost/proceedings/acc04/Papers/0250_WeP03.2.pdf)).
Song et al. similarly attribute pose error to manufacturing tolerances, link
offsets, and other sources, and acquire measured point corrections before
building a compensator
([paper](https://wrap.warwick.ac.uk/id/eprint/167833/1/WRAP-Calibration-Stewart-platform-designing-robust-joint-compensator-neural-networks-22.pdf)).

The implication is narrow: commanding the nominal identity and observing the
daemon's own FK estimate move closer to identity is not independent physical
calibration. Both the command and measurement depend on the same nominal model.

## Red-team findings

| Review question | Finding | Consequence |
|---|---|---|
| Is 6° an eligible start bound? | No evidence supports it; it was chosen after observing 4.18°. | Reject as a hardware bound. |
| Is 1.5° a validated safe/useful step? | No; the only motion trial under-responded and no deadband/current study exists. | Reject as an execution parameter. |
| Are endpoint checks sufficient? | No; the draft samples pose but has no joint-current, temperature, torque, or cable-load trace and no certified path monitor. | Endpoint pass cannot imply path safety. |
| Is there a software abort? | The existing task adapter waits for task completion/timeout and exposes no verified mid-task cancel path. | Do not claim active abort protection. |
| Is fail-hold safer than rollback? | Unknown; either can be wrong for different fault modes. | No automatic failure response is justified. |
| Does analytical IK protect the mechanism? | No collision check in the default engine, and no unit-specific calibration proof. | IK success is insufficient. |
| Can target tracking be diagnosed? | Not from the released REST `FullState`, which drops target fields. | Do not repeat commands until observability improves. |
| Would centring preserve experimental independence? | It would add a post-hoc intervention before V4 and could alter the unit's state. | Treat maintenance and experiment as separate protocols. |

## What should happen instead

### Safe now: diagnosis without robot commands

1. Keep V4 blocked at its unchanged 1° gate. Review that gate before designing
   any separately versioned successor protocol; do not relabel V4.
2. **Completed:** repeat the same 20-frame command-free capture across three
   explicitly labeled cold starts before touching the controller, recording
   startup age, wake, app state, motor mode, and errors.
3. **Completed at static visual resolution:** perform a power-off inspection guided by the official documents:
   cable slack through the head, obvious rod/joint restriction or residue, and
   the specific arm-placement symptoms in the motor guide. Do not disassemble
   or change homing offsets without a model-specific procedure.
4. Preserve the Testbench result as configuration evidence, not motion proof.
5. If possible in a later software build or instrumented diagnostic, expose
   present and target pose/joints together so steady-state target error can be
   observed without issuing a new command.

### Work that can continue without physical head motion

- replay and simulation of abstention policies;
- a baseline comparison against non-abstaining DoA following;
- preregistration of multi-room, multi-voice stimulus trials;
- trial-level uncertainty and selective-risk/coverage analysis;
- a patch or issue describing the desktop matrix/object sync defect and the
  daemon target-field serialization gap;
- design of an instrumented motion protocol that remains dormant until the
  maintenance blocker is resolved.

### Minimum evidence required to reconsider one physical command

All of the following should be available before the rejection is revisited:

- a repeatable neutral/start distribution or an explained initialization
  state, not one selected capture;
- present-versus-target pose and joint telemetry;
- unit-specific joint target deltas checked against configured limits;
- continuous joint/pose telemetry at a justified rate, including available
  motor error/current/temperature signals;
- an actually tested stop/cancel behavior, plus a defined physical emergency
  procedure;
- collision/cable-clearance reasoning for the exact path;
- thresholds frozen before a fresh hardware result;
- independent robotics review of the new command-capable protocol.

## Final disposition

The counterfactual planner is worth keeping because it documents what was
considered and why it was rejected. Its arithmetic tests are not safety tests.
Under this review it authorizes **zero hardware commands** and returns
`INDEPENDENT_REVIEW_REQUIRED` for a pose outside the neutral gate. This label
does not assert that the robot needs maintenance.

This rejection sharpens rather than weakens the research claim: abstention is
being applied to the research process itself. When mechanical readiness is
not observable enough to justify motion, the correct system-level outcome is
`HOLD`.
