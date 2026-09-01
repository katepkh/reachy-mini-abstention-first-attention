# Safety boundary

The passive stages in this repository do not authorize physical robot movement.

The Stage 4 code is an experimental, operator-supervised pilot. Before hardware use:

1. Stabilize the robot on a clear surface and keep people, hair, cables, phones, and loose objects outside the motion envelope.
2. Use the official daemon-matched transport and confirm Reachy Mini Control reports Ready with no warning.
3. Run the read-only preflight immediately before each one-shot command. Never bypass a failed readiness or neutral-pose check.
4. Keep the normal stop/power-down control immediately available and watch the robot, not the laptop, during motion.
5. Stop for grinding, repeated clicking, visible shaking, heat, unexpected motion, or motion beyond the displayed bound.
6. Do not weaken a threshold after observing a failure. Version and freeze any corrected protocol before another attempt.

The included Stage 4 physical pilot failed its mechanical gate and must not be presented as successful motion validation.

