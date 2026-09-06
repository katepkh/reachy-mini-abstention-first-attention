# Online evidence source notes: Reachy Mini v1.9.0 recovery and small-motion protocol

Research date: 2026-09-05 (Europe/London)

## Question searched

For a borrowed Reachy Mini Wireless running daemon v1.9.0:

1. Can a separate temporary daemon be started without persistent changes?
2. Can automatic motor reflashing and other maintenance writes be prevented?
3. If the temporary daemon freezes, loses motor communication, or reports a motor error after backend initialization, should the operator stop it, disable motors, restart the stock daemon, or power off? Are any of those actions contraindicated in particular states?
4. What should be verified after recovery and rollback?
5. Is one supervised, baseline-relative 3-degree head movement mechanically reasonable, and should failure lead to a commanded return or power-down?
6. Is vendor review still needed?

The proposed temporary daemon is narrower than a normal Wireless launch: one daemon only; no intentional motion or torque command; no calibration, firmware, package, or system-wide installation; no startup apps, media, mDNS, or background dataset activity; and read-only exposure of already-existing present/target state.

## Search coverage and limitations

Searches covered Pollen Robotics' official Reachy Mini repository at exact tag `v1.9.0`, current official documentation, the official motor-controller repository at `v1.5.5`, release notes, issues and pull requests, the ROBOTIS XL330 actuator manual, GitHub-wide results, general web results, Reddit, X-indexed results, and publicly indexed Discord pages.

The Pollen Discord is not publicly searchable as a complete archive. General search returned no indexed technical answer to this exact recovery question, and no logged-in Discord history was available to the research browser. Reddit and X searches returned demonstrations and general Reachy Mini discussion, but no authoritative recovery sequence. Therefore this review cannot prove that no private Discord message or unindexed social post exists.

## Claim-to-source ledger

| Claim | Evidence | Source quality | Limits |
| --- | --- | --- | --- |
| Pollen documents a local-checkout daemon workflow that does not replace the system installation. | Stop `reachy-mini-daemon`, run a local checkout, then restart the stock service; the guide says the stock service starts again on reboot. | First-party documentation: [install a daemon from a branch](https://github.com/pollen-robotics/reachy_mini/blob/main/docs/source/platforms/reachy_mini/install_daemon_from_branch.md) | The guide is for developers/testers and its Wireless command uses `--wireless-version`, which has side effects in v1.9.0. |
| In v1.9.0, `--wireless-version` is not read-only. | It checks/fixes `/venvs` ownership, Bluetooth service, Wireless launcher, apps SDK, restore venv, and may write `~/.asoundrc`. | First-party exact-tag source: [`main.py`](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/daemon/app/main.py#L792-L819) | These checks may be no-ops on a healthy robot, but they are not guaranteed no-write operations. |
| v1.9.0 already exposes flags to suppress wake, sleep-on-stop, app autostart, media, and dataset updating, but does not expose a stock CLI flag to suppress motor reflashing. | CLI definitions and daemon setup. | First-party exact-tag source: [`main.py`](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/daemon/app/main.py#L677-L735), [`daemon.py`](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/daemon/daemon.py#L710-L765) | A separate reviewed patch or direct construction path is needed to guarantee no reflash. |
| Backend construction reflashes by default. | `_setup_backend(..., reflash_motors_on_start=True)` calls `reflash_motors_if_needed`. | First-party exact-tag source: [`daemon.py`](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/daemon/daemon.py#L710-L765) | “Reflash” includes persistent actuator configuration changes when a mismatch is detected. |
| Restarting the stock daemon can write motor configuration if a mismatch is detected. | Official motor diagnosis says the daemon will reflash all motors on restart if configuration is not correct. The setup path writes ID, baud rate, homing offset, angle limits, return delay, mode, and shutdown settings. | First-party docs/code: [motor diagnosis](https://github.com/pollen-robotics/reachy_mini/blob/main/docs/source/troubleshooting/motors_diagnosis.md), [`setup_motor.py`](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/tools/setup_motor.py) | A temporary daemon that performs no persistent writes should not create a mismatch, but the restart is still not intrinsically read-only. |
| A normal v1.9.0 stop can move the robot before disabling torque. | With `goto_sleep_on_stop`, stop sets `Enabled`, runs `goto_sleep()`, then sets `Disabled`. | First-party exact-tag source: [`daemon.py`](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/daemon/daemon.py#L379-L460) | Therefore a normal graceful stop is not command-free unless sleep-on-stop is suppressed. |
| In an error state, v1.9.0 skips the sleep/return motion. | `ERROR` or `STOPPING` forces `goto_sleep_on_stop=False`. | First-party exact-tag source: [`daemon.py`](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/daemon/daemon.py#L407-L449) | This is implementation behavior, not a vendor-authored operator safety protocol. |
| Closing the v1.5.5 low-level controller does not itself send `DisableTorque`. | `close()` sets a stop signal and joins the loop. Torque disable is a separate motor command. | First-party exact-tag source: [`control_loop.rs`](https://github.com/pollen-robotics/reachy-mini-motor-controller/blob/v1.5.5/src/control_loop.rs#L617-L636), [explicit torque commands](https://github.com/pollen-robotics/reachy-mini-motor-controller/blob/v1.5.5/src/control_loop.rs#L487-L516) | Consequently process termination alone is not proof that torque is off. GitHub's rendered line mapping may differ from the raw file, but the source functions are unambiguous. |
| Backend initialization may reboot motors that report an error. | The control-loop constructor calls a broadcast reboot with the comment “Reboot all motors on error status.” | First-party exact-tag source: [`control_loop.rs`](https://github.com/pollen-robotics/reachy-mini-motor-controller/blob/v1.5.5/src/control_loop.rs) | This is distinct from reflashing, but it means backend initialization is not observationally inert at the actuator level. |
| Loss of controller communication is not proven to remove torque automatically. | XL330 has a configurable Bus Watchdog, with `0` meaning disabled. No Reachy v1.9.0 source reference to configuring Bus Watchdog was found. | Primary actuator manual: [XL330 Bus Watchdog](https://emanual.robotis.com/docs/en/dxl/x/xl330-m288/#bus-watchdog98); negative code-search result across exact v1.9.0 tree | Absence of a code reference is not a readback of the borrowed robot's actual register. |
| A hardware power reset normally starts XL330 torque off, but this has a configurable exception. | Torque Enable defaults to 0; Startup Configuration can request torque-on at startup; RAM restore is also configurable. | Primary actuator manual: [Torque Enable](https://emanual.robotis.com/docs/en/dxl/x/xl330-m288/#torque-enable64), [Startup Configuration](https://emanual.robotis.com/docs/en/dxl/x/xl330-m288/#startup-configuration60) | This describes the actuator, not every part of the complete Wireless robot. The borrowed unit's registers have not been independently read and frozen. |
| Pollen's general troubleshooting treats whole-robot power cycling as ordinary recovery. | “Press OFF, wait 5 seconds, then press ON”; thermal-protection guidance also says turn off/on. | First-party current docs: [troubleshooting](https://github.com/pollen-robotics/reachy_mini/blob/main/docs/source/troubleshooting.md) | This is generic troubleshooting, not an exact answer for a patched v1.9.0 daemon with an initialized backend. |
| A healthy 50 Hz control loop and zero errors do not establish motor state or posture. | v1.9.0 Wireless reproduction shows fresh daemon and `wake_up()` can remain disabled and unmoved; `enable_motors()` is separate. | Public issue with exact-version reproduction: [#1306](https://github.com/pollen-robotics/reachy_mini/issues/1306) | Issue author is not identified as a Pollen maintainer; behavior is consistent with official current troubleshooting. |
| Motor communication errors have occurred publicly without a published recovery answer. | Reports include endpoint failures and unresponsive daemons. | Public user reports: [#591](https://github.com/pollen-robotics/reachy_mini/issues/591), [#623](https://github.com/pollen-robotics/reachy_mini/issues/623) | Reports are not vendor guidance; #623 is Lite and an older version. |
| Public reports show that motor errors and competing motion sources can produce hazards, but they do not prove the proposed read-only protocol will do so. | An exact-v1.9.0 Wireless report says overlapping dances can cause tip-inducing motion; another Wireless report associates a motor-communication error with uncommanded head motion. | Public user reports: [#1284](https://github.com/pollen-robotics/reachy_mini/issues/1284), [#1129](https://github.com/pollen-robotics/reachy_mini/issues/1129) | #1284 involves active overlapping motion; #1129 involved a long-running app, Wireless launcher behavior, and `--wireless-version`. Neither is the proposed isolated recorder. |
| Three degrees is numerically small relative to published examples and configured limits. | Exact v1.9.0 demo uses 10-degree head motion over 1 second; current examples use 5–10 degrees over 1 second; current docs list ±40-degree pitch/roll limits. | First-party examples/docs: [v1.9.0 minimal demo](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/examples/minimal_demo.py), [interpolation playground](https://github.com/pollen-robotics/reachy_mini/blob/main/examples/goto_interpolation_playground.py), [troubleshooting limits](https://github.com/pollen-robotics/reachy_mini/blob/main/docs/source/troubleshooting.md) | This does not prove collision clearance, calibration, return accuracy, or safety on this borrowed unit. |
| Analytical kinematics does not perform collision checking in v1.9.0. | The exact-tag source states the `check_collision` parameter is unused. | First-party exact-tag source: [`analytical_kinematics.py`](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/kinematics/analytical_kinematics.py#L69-L107) | Joint-limit margin is not collision or physical-safety validation. |
| Published angle limits do not guarantee no shell contact. | Pollen's current troubleshooting explicitly says the head may touch the body during some official motions. | First-party current docs: [troubleshooting](https://github.com/pollen-robotics/reachy_mini/blob/main/docs/source/troubleshooting.md#the-head-may-touch-the-body-during-some-official-motions) | This is not evidence that the proposed 3-degree path will touch; it shows why a numerical joint-limit margin alone is insufficient. |

## What the online record answers

1. **Temporary daemon isolation:** Yes, Pollen supports a local-checkout development workflow, provided the stock service is stopped and only one daemon owns the motor bus.
2. **Persistent-write prevention:** Not with the unmodified v1.9.0 Wireless launch command alone. `--wireless-version` performs maintenance checks/writes, and backend setup reflashes by default. The proposed suppression patch addresses a real gap, but the exact patch remains project code rather than vendor-reviewed code.
3. **Normal shutdown:** If the daemon and motor bus are healthy, explicit motor disable is the software operation that turns torque off. A default normal daemon stop may first command a sleep motion. For a command-free capture, sleep-on-stop must remain suppressed.
4. **Error shutdown:** v1.9.0 itself avoids the sleep motion when already in `ERROR`, but closing the control loop is not proof of torque-off. If communication has failed, an explicit disable command may not reach the motors.
5. **Small movement:** Three degrees is small compared with official examples and documented angle limits. It is not independently validated for this unit; Pollen notes that even some official motions can involve head/body contact, and the project's prior target/return gate failure remains directly relevant.
6. **Rollback:** Restoring the untouched stock service is structurally plausible, but stock restart may run motor configuration reconciliation. A rollback claim therefore needs before/after version, service, configuration, motor-state, posture, and error evidence—not only “the stock daemon started.”

## What remains unanswered online

No authoritative Pollen source found in this search specifies the exact priority order after a temporary v1.9.0 daemon becomes unresponsive **after motor backend initialization**. In particular, the public record does not answer:

- whether to attempt `disable_motors()` before stopping the process when communication is degraded;
- when to use the robot's OFF control immediately rather than attempting a daemon restart;
- whether any whole-robot state makes restart or power-off undesirable;
- whether Pollen wants logs/register state preserved before any restart;
- whether a stock restart's motor reconciliation is acceptable after a failed temporary-daemon session;
- the approved post-recovery verification list for the Wireless unit;
- whether a failed 3-degree target should lead to a commanded return, torque disable, or immediate power-down.

## Evidence-based interim interpretation (not vendor approval)

- Do not run the stock and temporary daemons simultaneously.
- Do not treat “process exited” as “torque is off.”
- Do not treat 50 Hz / zero controller errors as proof that motors are disabled or posture is nominal; check `motor_control_mode` and physical posture explicitly.
- If the temporary daemon remains responsive and communication is healthy, an explicit disable confirmation before closing is stronger evidence than closing alone.
- If the daemon is unresponsive, communication is lost, a hardware error appears, or unexpected motion/noise/heat/red LEDs occur, starting the stock daemon in parallel is not justified. Pollen's general documentation supports whole-robot power cycling as ordinary recovery, and the actuator manual says power reset normally clears torque, but this exact scenario still lacks a vendor-approved sequence.
- The project's existing “on target failure, do not automatically return; power down” rule is consistent with v1.9.0 skipping sleep motion in `ERROR`, but it remains a conservative project rule rather than a Pollen instruction.

## Bottom line

The online evidence substantially narrows the uncertainty, but it does not eliminate the reason for the support question. It confirms that the planned no-reflash/no-wake/no-autostart patch is technically motivated, that a mere daemon close does not prove torque-off, and that 3 degrees is numerically modest. It does **not** provide a Pollen-approved recovery sequence for the exact failure state. Until that answer arrives, the defensible work is offline/laptop-only; physical execution should remain a separately accepted risk decision by the owner/operator, not something represented as vendor-cleared.
