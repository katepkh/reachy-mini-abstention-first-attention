# Rejected bounded centring proposal — counterfactual only

## Status

**Hardware verdict: REJECT. This artifact authorizes zero commands.** It is a
counterfactual design and offline planner with no robot transport or execution
function. No threshold below has been validated as a hardware-safety guarantee,
and several choices were proposed after observing the 4.18° historical
start-state error. The completed source-backed review is
[`CENTERING_REVIEW.md`](CENTERING_REVIEW.md). Independent robotics review would
still be required before this decision could be reconsidered.

The original purpose was narrow: establish a measured start pose within the
unchanged 1° V4 neutral gate without using the desktop controller's defective
zero display. The proposal is retained to expose the rejected reasoning. It is
not part of the attention experiment and cannot turn a failed V3 or blocked V4
trial into a pass.

After this draft was written, a second zero-command trace measured a different
settled state: 1.333–1.459° from identity (mean 1.409°), still outside the 1°
gate but materially closer than the earlier 4.159–4.221° trace. The daemon's
released REST response also drops requested target pose/joint fields, so the
stored target cannot be compared with measured state through that surface.
Those findings make a one-offset correction model less, not more, defensible.

## Why a separate protocol is necessary

The 2026-09-01 command-free diagnostic established that:

- daemon matrix, Euler, and streamed pose representations agree;
- one capture measured a stable 4.159–4.221° rotation and 3.73–3.77 mm
  translation from nominal identity;
- a later capture after another start measured a different stable 1.333–1.459°
  rotation and 1.24–1.27 mm translation;
- desktop app v0.9.34 displays false head zeros because it reads a matrix as
  named pose fields;
- nominal identity inverse kinematics differs from the measured joint vector by
  up to 6.19° at Stewart 5;
- the previous 3° physical pilot under-responded and failed.

Using Reset again would neither diagnose nor independently measure the outcome.
Directly commanding identity would request about 4.18°, outside the project's
existing 3° experimental envelope. Treating the current pose as “neutral” would
instead weaken the already frozen 1° gate after seeing the result. Both are
rejected.

## Rejected candidate procedure

The rejected unit was **one separately armed correction session**, never an
automatic loop. The steps below describe what was evaluated, not what may be
performed:

1. Capture a fresh read-only pose/status trace and immutable hash.
2. Require stationary telemetry, daemon 1.9.0, physical hardware, enabled motor
   control, a 40–60 Hz healthy loop, zero loop errors, fresh pose/status, no
   daemon error, and direct operator supervision.
3. Reject starts over 6° rotation or 8 mm translation from identity. The 6°
   ceiling is explicitly post-observation review debt, not a validated limit.
4. Compute the shortest SO(3) path from the measured rotation toward identity.
5. Select only the next waypoint, capped at 1.5°. Preserve the measured
   translation exactly.
6. Present the complete numeric baseline, target, nominal IK deltas, protocol
   fingerprint, and hazards for human review.
7. If a later executor is approved, require a new short-lived exact typed arm
   for this single target. Send head only: no body yaw, antennas, torque, motor
   mode, homing, media, cloud, tracking, or continuous-control operation.
8. Sample the continuous trace during a slow minimum-jerk command, dwell, then
   evaluate the endpoint. Do not chain another target automatically.
9. Hold after the step. If there is grinding, repeated clicking, visible
   shaking, heat, an unexpected direction, or motion outside the bound, the
   operator stops and powers down normally. The draft intentionally does not
   issue an automatic return, because that would be a second unreviewed motion
   from an uncertain state.
10. A fresh session can be considered only after the trace and direct operator
    observations are reviewed. Stop for independent reassessment after at most
    four separately armed sessions, even if the 1° gate has not been reached.

The pure implementation is
[`reachy_stage4/centering_plan.py`](../reachy_stage4/centering_plan.py). It emits
`REVIEWED_REJECTED_FOR_HARDWARE_EXECUTION`, a deterministic fingerprint, one
counterfactual waypoint, rejected candidate bounds, and explicit review debt.
For a pose outside the gate it returns `INDEPENDENT_REVIEW_REQUIRED`. That is a
conservative experiment disposition, not a diagnosis that maintenance is
needed. The module cannot connect to Reachy.

### Offline preview from the live trace

Applying the planner to the final frame of the 2026-09-01 private diagnostic
produced this non-executable review preview:

- input rotation from identity: 4.195800°;
- input translation from identity: 3.771709 mm;
- proposed rotational waypoint: 1.500000° from that captured frame;
- remaining rotation after the ideal waypoint: 2.695800°;
- planned translation change: 0 mm;
- plan fingerprint:
  `b7e7f7c70a946ed3d2c94c10566de3be5b71984ca8523767cf2fa1212c12c331`.

This preview proves only the planner's arithmetic. It is already stale for
physical use: any eventual executor must build a new plan from a fresh pose,
recheck the complete state, and require a new arm after review. Copying this
matrix into a command would violate the draft.

## Rejected candidate numerical bounds

| Quantity | Draft value | Rationale and limitation |
|---|---:|---|
| V4 neutral gate | ≤1.0° | Unchanged existing gate; not adjusted after the live result. |
| Eligible start rotation | ≤6.0° | Two existing 3° envelopes, but selected after observing 4.18°; requires external criticism. |
| Eligible start translation | ≤8.0 mm | Reuses the frozen V4 translation bound. |
| Planned rotational waypoint | ≤1.5° | Half the existing 3° test increment, trading smaller motion against possible motor deadband. |
| Measured endpoint step | ≤2.0° | Allows 0.5° endpoint margin; continuous-path proof is still absent. |
| Endpoint target error | ≤1.0° | Stricter than V4's 1.5° target-error gate because this is calibration, not directional mapping. |
| Translation drift per step | ≤2.0 mm | Target translation is unchanged; a larger change is treated as unexpected. |
| Minimum progress | ≥0.25° | Prevents repeated ineffective commands; near the final gate, reaching ≤1° supersedes it. |
| Separately armed sessions | ≤4 | Exposure cap, not evidence that four attempts will centre the robot. |

These values are deliberately separable so the rejected assumptions remain
auditable. None is approved for physical use.

## Endpoint assessment

An endpoint can become **eligible for operator review** only if all apply:

- measured step ≤2°;
- target error ≤1°;
- translation drift ≤2 mm;
- the pose either reaches the unchanged ≤1° neutral gate or improves by at
  least 0.25°.

Passing these calculations does not authorize another command. The continuous
trace and operator observations must also show correct direction, smoothness,
no abnormal sound/heat/shaking, and a stable final hold.

## Hazards that remain open

1. **Post-hoc eligibility:** 6° and four sessions were selected with knowledge
   of the current 4.18° result.
2. **Prior under-response:** a smaller Cartesian command may fall into
   deadband, increase session count, or again differ from the requested target.
3. **Path observability:** endpoint bounds do not prove the interpolated Stewart
   platform path remained within them; the executor would need live trace
   capture and explicit abort handling.
4. **No collision proof:** nominal analytical IK reachability is not collision
   checking or a calibrated hardware model.
5. **Fail-hold choice:** holding avoids an automatic second command but may be
   inferior to bounded rollback under some failure modes.
6. **Calibration ambiguity:** encoder offset, assembly calibration, compliance,
   and unapplied targets have not been distinguished.
7. **Emergency behavior:** software cannot replace the operator's immediate
   physical stop/power-down capability.

## Review questions before implementation

1. Is a 1.5° Cartesian waypoint appropriate given the failed 3° response, or
   would a joint-space diagnostic be safer and more informative?
2. Is the 6° eligibility ceiling defensible, or should any start outside 3° be
   escalated as maintenance/calibration rather than corrected experimentally?
3. Is fail-hold safer than automatic rollback for this mechanism?
4. What continuous trace rate and abort threshold are adequate when the daemon
   task API does not expose a formally interruptible safety controller?
5. Should nominal IK joint deltas receive explicit per-motor bounds before a
   Cartesian command is eligible?
6. Is external inspection or a hardware calibration workflow required before
   any movement, particularly because Stewart 5 is 6.19° from nominal identity
   IK?
7. Does performing centring compromise the scientific independence of the
   later V4 pilot, and if so should V4 be redesigned or preregistered again?

Until those questions are answered, the correct action is **hold**.

## Internal adversarial review

**What is defensible now:** the planner is deterministic, operates on measured
SE(3) input, follows the shortest SO(3) path, preserves translation, emits only
one bounded waypoint, cannot connect to the robot, never authorizes a next
step, and exposes rather than hides its post-observation design choices.

**What is not defensible yet:** there is no validated reason that 6° is a safe
eligibility ceiling; endpoint geometry is not continuous-path assurance; no
per-motor target/current/limit margin is checked; fail-hold is not established
as safer than rollback; and the underlying encoder/mechanical/calibration cause
has not been isolated. The failed V3 response also makes the assumed usefulness
of a 1.5° Cartesian command uncertain.

**Internal verdict:** mathematically reviewable, experimentally transparent,
and appropriately command-free—but **rejected for hardware execution**. The
full source-backed review found that gate/target/maintenance review and
target-state observability must precede any new command-capable design.

## Ready-to-send request to reconsider the rejection

> I have a Reachy Mini whose daemon produced two materially different stable
> command-free start-state captures (means 4.183° and 1.409° from nominal
> identity), while the desktop controller displays false zeros due to a
> matrix/object state-sync defect. Daemon 1.9.0 also drops requested target head
> fields from its released REST response. The matrix, Euler, stream, and
> joint-state diagnosis is documented here, and no command followed it. I have
> drafted and then rejected a non-executable centring proposal that considered
> one fresh, separately
> armed, head-only 1.5° SO(3) waypoint toward identity, preserves translation,
> forbids automatic chaining/return, and keeps the existing 1° V4 gate.
>
> Could you review this specifically as a robot-control and experimental-safety
> rejection? I would value blunt criticism of: (1) whether any start over 3° should
> be treated as maintenance rather than experimentally centred; (2) the
> post-hoc 6° eligibility ceiling; (3) Cartesian versus joint-space correction;
> (4) per-motor and continuous-path bounds; (5) fail-hold versus rollback; and
> (6) whether centring would compromise the later V4 experiment. The draft is
> not authorization to move the robot, and I will not add an executor until the
> unresolved hazards have been reviewed. The current artifact authorizes zero
> hardware commands.
