# Temporary daemon lifecycle review

## Verdict

**Changes requested; design repaired but not deployed.** Exact Reachy Mini
v1.9.0 source shows that the official local-development approach is not by
itself sufficient to claim a non-persistent observation session on a borrowed
Wireless unit. The project now contains a second, separate lifecycle patch and
a pure invocation-plan builder. Neither has been installed or run on Reachy.

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

## Go/no-go boundary

Before the temporary daemon can start, the exact stock daemon must report no
hardware error; its reviewed normal shutdown must reach the torque-disable path
without an error; both patches and the baseline inventory must verify; and the
operator must remain clear. This is log/path evidence, not an independent
post-close torque measurement. Any mismatch is a no-go.

After temporary startup, capture is prohibited unless the API is loopback-only,
media is disabled, the daemon is healthy, and motor control reports disabled.
The receive-only client then sends zero application messages or commands.

This procedure still needs review by someone familiar with Reachy hardware,
principally because controller construction can conditionally reboot a faulty
motor and no reviewed v1.9.0 path proves safe torque removal after a daemon
crash. It is an auditable reduction of risk, not a safety certification.
