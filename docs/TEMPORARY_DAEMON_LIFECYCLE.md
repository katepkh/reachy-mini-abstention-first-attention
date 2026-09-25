# Temporary daemon lifecycle review

## Verdict

**A bounded live observation completed and the stock service was restored.**
Exact Reachy Mini v1.9.0 source and the powered work show that the official
local-development approach is not sufficient to call the whole session
command-free: controller construction writes configured PID gains even when the
trace client is receive-only. The project contains a lifecycle patch, a pure
invocation-plan builder, an exact-v1.9.0 health gate, and an offline-only
lifecycle executor. The executor ships no hardware adapter and authorizes no
powered use.

On 2026-09-18, two contained fail-closed runs exposed a patch-staging error and
a client deadline-handling error. Neither entered a movement stage; each ended
with the stock service restored. After both defects were repaired and retested,
the final temporary API remained loopback-only, motor control remained disabled,
and the control loop stayed fresh at approximately 50 Hz with zero reported
errors. The receive-only client retained 193 frames over 10 seconds, all with a
coherent `UNSET` target, and sent zero application messages and zero robot
commands. The temporary process then exited and released its listener and serial
resource. The exact stock service was restored with one process/listener/serial
owner, no active app, motors disabled, and fresh error-free telemetry.

## Source findings

1. `--wireless-version` enters startup-maintenance code that can change `/venvs`
   ownership, Bluetooth and daemon launcher files, the apps/restore environments,
   and `~/.asoundrc`. The observation plan therefore omits that flag and names
   `/dev/ttyAMA3` explicitly. This intentionally forgoes Wireless-only IMU and
   management surfaces, which the present/target trace does not need.
2. `Daemon._setup_backend` already accepts `reflash_motors_on_start=False`, but
   released `Daemon.start()` and the CLI cannot select it. When enabled, the
   helper can write motor IDs, baud rate, homing offsets, limits, shutdown
   configuration, return delay, and operating mode when configuration differs.
3. Motor-controller 1.5.5 construction still conditionally reboots a motor with
   a pre-existing non-voltage hardware error. Suppressing the reflash helper is
   therefore **not** a promise of zero motor-side effects.
4. Normal daemon stop may execute a sleep trajectory. Disabling that behavior
   avoids the trajectory, but the motor-controller `close()` path does not itself
   issue a torque-disable command. A crash or close must not be described as
   proof of de-energization.
5. DYNAMIXEL XL330 Bus Watchdog is disabled at its documented initial value of
   zero, and no v1.9.0 Reachy configuration path reviewed here enables it. Loss
   of daemon communication must not be assumed to remove torque.
6. `RobotBackend` construction writes the configured PID gains to the motor
   controllers. This occurs even when reflash, wake/sleep motion, torque enable,
   applications, media, and the trace client's commands are all suppressed.
   The trace client can be receive-only; the enclosing controller lifecycle
   cannot honestly be called command-free.
7. Exact v1.9.0 updates an internal ready event and `last_alive` clock without
   copying either into the serialized backend status. A false serialized
   `ready` and null `last_alive` are therefore not usable health gates for this
   version. Two advancing full-state timestamps plus healthy loop statistics
   are used instead.

Primary sources:

- [official local-development guide](https://github.com/pollen-robotics/reachy_mini/blob/main/docs/source/platforms/reachy_mini/install_daemon_from_branch.md);
- [v1.9.0 daemon application lifecycle](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/daemon/app/main.py);
- [v1.9.0 Wireless startup checks](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/utils/wireless_version/startup_check.py);
- [v1.9.0 backend construction and shutdown](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/daemon/daemon.py);
- [v1.9.0 motor reflash helper](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/tools/reflash_motors.py);
- [motor-controller 1.5.5 control loop](https://github.com/pollen-robotics/reachy-mini-motor-controller/blob/v1.5.5/src/control_loop.rs); and
- [ROBOTIS XL330 Bus Watchdog](https://emanual.robotis.com/docs/en/dxl/x/xl330-m077/#bus-watchdog98).

## Lifecycle patch

[`reachy-mini-v1.9.0-observation-lifecycle.patch`](../patches/reachy-mini-v1.9.0-observation-lifecycle.patch)
adds three default-on settings and corresponding negative CLI flags:

- `--no-reflash-motors-on-start` bypasses only
  `reflash_motors_if_needed`; a daemon restart retains the setting;
- `--no-startup-app` prevents installation, launch, and antenna watching of a
  configured startup app; and
- `--no-mdns` prevents service advertisement.

All upstream defaults remain unchanged when the flags are absent. The patch
does not modify motor firmware, motor-controller Rust code, shutdown behavior,
motion code, calibration, kinematics, or the system service.

The offline validator binds the patch to exact reviewed v1.9.0 source hashes,
applies and reverse-checks it in a temporary directory, compiles both modified
files, and verifies CLI-to-backend and restart plumbing:

```bash
python scripts/validate_daemon_lifecycle_patch.py --source-root /path/to/reachy_mini-1.9.0
```

It starts no daemon and creates no robot or network connection.

## Exact proposed observation invocation

[`daemon_lifecycle.py`](../reachy_stage4/daemon_lifecycle.py) constructs—but
cannot execute—the reviewed command. Its material arguments are:

```text
reachy-mini-daemon
  --serialport /dev/ttyAMA3
  --hardware-config-filepath <reviewed-checkout>/src/reachy_mini/assets/config/hardware_config.yaml
  --no-media
  --no-wake-up-on-start
  --no-goto-sleep-on-stop
  --no-reflash-motors-on-start
  --no-startup-app
  --no-mdns
  --no-preload-datasets
  --dataset-update-interval 0
  --fastapi-host 127.0.0.1
  --timeout-health-check 60
```

The actual checkout, log, PID, `UV_CACHE_DIR`, and `XDG_CACHE_HOME` must all be
inside one enumerated session directory. Access from another computer would use
a separately reviewed SSH loopback tunnel; the daemon must not bind its
unauthenticated API to the LAN.

## Receive-only boundary

Before the temporary daemon can start, the exact stock daemon must report no
hardware error and motor control disabled before process exit; both patches and
the baseline inventory must verify; the physical power control must be
immediately accessible; and the space beneath and around the Stewart platform
must be clear. Any mismatch is a no-go.

After temporary startup, capture is prohibited unless the API is loopback-only,
media is disabled, the daemon is healthy, and motor control reports disabled.
The trace client sends zero application messages or experimental commands.
This is therefore a **receive-only trace client inside a configuration-writing
controller lifecycle, with a predeclared safety-disable exception**. It is not
an unconditional claim that the daemon sends no motor-bus writes.

[`observation_health.py`](../reachy_stage4/observation_health.py) implements the
pure two-sample health gate. It requires exact version, advancing state time,
finite pose/joints/yaw, coherent motor mode, expected media/Wireless mode, a
40–60 Hz loop, maximum observed interval no greater than 0.1 seconds, zero loop
errors, and no active app or held app lock. It records but deliberately excludes
the broken serialized `ready` and `last_alive` fields for exact v1.9.0.

[`observation_executor.py`](../reachy_stage4/observation_executor.py) rehearses
the complete phase order and rollback behavior using only an injected
offline-only adapter. The project provides no process, network, serial, HTTP,
WebSocket, or Reachy implementation for that adapter. It therefore cannot be
used as a hardware runner by default and reports
`hardware_execution_authorized=false` even when every mock gate passes.

## Terminal state machine

[`plan_observation_shutdown`](../reachy_stage4/daemon_lifecycle.py) is pure
review logic; it cannot contact the robot. It freezes these mutually exclusive
branches:

| Last trustworthy state | Planned terminal action | Forbidden action |
|---|---|---|
| daemon responsive, telemetry fresh, motor mode `Disabled` | Preserve the fresh state, stop the temporary daemon without sleep motion, then verify process exit and serial-resource release. | Do not send a disable or start another daemon before release is proved. |
| daemon responsive, telemetry fresh, motor mode `Enabled` | Issue exactly one predeclared motor-disable **safety** action, verify a new fresh `Disabled` report, then stop and verify release. | Do not send any target, return, wake, sleep, calibration, or retry trajectory. |
| daemon unresponsive, telemetry stale, or motor mode unknown | Stay clear, start no replacement daemon, keep the drop zone clear, and use the separately accepted physical-power-off procedure. Expect passive loss of support rather than a commanded landing. | Do not attempt a software return, reconnect, or stock-daemon takeover. |

Process exit is never treated as evidence of disabled torque. Physical
power-off is a fault-containment branch, not a claim that hard power removal is
universally safe in every robot state.

## Stock restoration gate

The untouched stock daemon may be considered for restoration only after the
temporary process has exited, released the serial resource, the mechanism is
stable, and any physical-power-off branch has completed. Restoration then
requires recording the exact stock service/version, single-daemon ownership,
expected motor inventory, error-free daemon/controller status, motor-control
mode and posture before optional motion, and a before/after persistent-surface
inventory. A stock restart is not itself authorization to wake or move.

The powered observation closes only the bounded receive-only trace gate. It does
not clear another observation attempt or the later 3-degree motion stage. The
observed target remained `UNSET`, so target tracking and the return path remain
unvalidated. Controller construction can still reboot a motor with a
pre-existing non-voltage error and writes PID gains during startup. The protocol
is an auditable reduction of risk, not a safety certification.
