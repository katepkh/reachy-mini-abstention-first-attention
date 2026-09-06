# Safety boundary

The passive stages in this repository do not authorize physical robot movement.

The Stage 4 code is an experimental, operator-supervised pilot. Before hardware use:

1. Stabilize the robot on a clear surface and keep people, hair, cables, phones, and loose objects outside the motion envelope.
2. Use the official daemon-matched transport and confirm Reachy Mini Control reports Ready with no warning.
3. Run the read-only preflight immediately before each one-shot command. Never bypass a failed readiness or neutral-pose check.
4. Before any motion, preregister the Reachy-specific response for a healthy daemon, stale telemetry, daemon loss, and unexpected movement. Watch the robot, not the laptop, during motion.
5. Stop for grinding, repeated clicking, visible shaking, heat, unexpected motion, or motion beyond the displayed bound.
6. Do not weaken a threshold after observing a failure. Version and freeze any corrected protocol before another attempt.

Automatic return is prohibited in the successor design. A connection loss,
daemon/process failure, or motor fault can prevent it, while normal shutdown may
itself initiate a sleep trajectory and hard power removal may permit mechanical
movement. Enter `ABORT_NO_AUTOMATIC_RETURN`, remain clear, preserve evidence,
and follow only the failure-class response approved for this unit. Do not
improvise another software trajectory.

The included Stage 4 physical pilot failed its mechanical gate and must not be presented as successful motion validation.

## Offline failure rehearsal boundary

The Stage 4A offline failure rehearsal starts only fixed local Python mock
processes. A passing duplicate-start or restoration-interlock result must not be
interpreted as evidence that a real daemon released its serial connection,
disabled torque, or made restart or power removal safe. It authorizes no
hardware action.
