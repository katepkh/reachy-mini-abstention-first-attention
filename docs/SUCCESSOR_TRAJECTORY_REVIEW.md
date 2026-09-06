# Offline daemon 1.9.0 trajectory and joint-margin review

## Result

The proposed four baseline-relative 3° motions were reconstructed entirely
offline for both the outward target leg and the reverse **nominal** return leg.
No robot connection or command was made or authorized.

The validator used:

- the official `reachy_mini-1.9.0-py3-none-any.whl`, SHA-256
  `9d3f8551c42bd12b43f47a1f3fe5e8c39ca0c2ff6d02c27b094ed0f5586c7655`;
- an installed source tree byte-equal to that wheel for interpolation,
  `GotoMove`, analytical kinematics, backend playback, hardware configuration,
  and kinematics data;
- `reachy-mini-rust-kinematics==1.0.3`, the dependency installed with this
  exact environment;
- the final frame of controlled startup capture 3, whose sidecar hash was
  verified before use; and
- 201 samples per two-second leg (an inclusive 100 Hz ideal grid).

Our reconstruction agreed with the official 1.9.0 `GotoMove.evaluate()` result
to a maximum absolute pose-matrix element difference of
`4.44e-16` across all evaluated paths.

| Direction | Outward minimum margin | Nominal return minimum margin | Limiting joint / side |
|---|---:|---:|---|
| Up | 43.156° | 43.156° | Stewart 1 / upper |
| Down | 42.706° | 42.706° | Stewart 4 / lower |
| Left | 43.656° | 43.656° | Stewart 1 / upper |
| Right | 43.745° | 43.745° | Stewart 4 / lower |

The private immutable report is
`20260902T065914Z_nominal_four_direction_review.json`, SHA-256
`86de6de717649569ad3d78b36adc88d62f2620c57b8c46039df54fcf7f003cd5`.
It retains every sampled pose, IK solution, per-joint margin, source hash, and
the recorded-versus-exact-IK baseline residual. The public repository does not
include the private startup capture or derived full trace.

## What “exact” means here

Daemon 1.9.0 applies the normalized minimum-jerk polynomial
`10t³ − 15t⁴ + 6t⁵`, then uses `linear_pose_interpolation` with
`yaw_as_scalar=True`: yaw is interpolated as a signed scalar, residual
roll/pitch rotation uses a rotation vector, and translation is linear. These
behaviors are in the official
[`interpolation.py`](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/utils/interpolation.py)
and
[`goto.py`](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/motion/goto.py).
The validator cross-checks rather than merely assuming that equivalence.

The configured Stewart limits were derived from the exact raw values in the
official
[`hardware_config.yaml`](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/assets/config/hardware_config.yaml):
ticks relative to 2048, converted at 4096 ticks per revolution. Body yaw used
the ±160° safe bound passed by the official analytical IK. The official
[`AnalyticalKinematics`](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/kinematics/analytical_kinematics.py)
passes each pose to the Rust `inverse_kinematics_safe` solver.

## What it does **not** establish

This is a geometric path/configured-limit result, not a safety certificate.
It does not validate:

- collisions—the analytical implementation ignores `check_collision`;
- load, torque, current, heat, backlash, singularity conditioning, cable
  routing, or enclosure clearance;
- actual tracking error or the cause of the observed non-identity start pose;
- scheduler timing or the exact final target write; or
- a real return path from a measured target state.

The last two distinctions matter. The official
[`play_move`](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/daemon/backend/abstract.py)
evaluates wall-clock time while `elapsed < duration`; real write timestamps and
whether an endpoint is explicitly written depend on runtime scheduling. Also,
a safe return proposal must begin from the newly measured state after the
outward leg, not assume the nominal target was reached. This is why the return
is now separately preflighted and authorized.

## Reproduction

Run the validator only in an isolated environment containing the exact
official wheel and dependencies:

```bash
python scripts/validate_successor_trajectory_v190.py \
  --wheel /path/to/reachy_mini-1.9.0-py3-none-any.whl \
  --baseline-capture /private/path/to/startup_capture.json \
  --output /private/path/to/new_immutable_report.json
```

[`trajectory_review.py`](../reachy_stage4/trajectory_review.py) is pure numeric
code. The validator rejects a different wheel hash, different installed Rust
kinematics version, installed source bytes that differ from the wheel, an
invalid baseline sidecar, or a reconstruction mismatch above `1e-12`.
