# Reachy Mini v1.9.0: online evidence review for temporary-daemon recovery

Date: 2026-09-05

## 2026-09-17 design disposition

The public-source findings below remain unchanged: they do not by themselves
constitute manufacturer authorization for the proposed run. The project has
nevertheless removed the previously ambiguous recovery branch from its design.
The current zero-authority planner now requires:

1. fresh `Disabled` state: stop the temporary daemon and verify process exit
   plus serial-resource release;
2. fresh responsive `Enabled` state: one predeclared motor-disable safety
   action, a new fresh `Disabled` confirmation, then stop and verify release;
3. unresponsive, stale, or unknown state: no replacement daemon and no return
   trajectory; stay clear and use the separately accepted physical-power-off
   procedure with the Stewart-platform drop zone clear; and
4. stock restoration only after the temporary process and serial lease are
   gone and the robot is stable, followed by explicit inventory, error, mode,
   posture, version, and persistent-surface checks.

This is still an unexecuted project protocol, not proof of physical safety. No
correspondence, reviewer identity, or external response is retained here.

## 2026-09-25 version clarification

Current unversioned Pollen documentation describes a newer platform-owned
lifecycle contract: a 1.5-second idle-reset debounce, daemon-side
`reset_to_sleep()` after an unexpected session drop, and cancellation during a
successor handoff. Those guarantees must not be back-ported by assumption to
the borrowed robot's exact daemon v1.9.0.

The byte-verified v1.9.0 source used by this project contains no
`request_idle_reset()`, `reset_to_sleep()`, or slot-free callback that invokes
such a backstop. On an app-process crash it releases the application lock, but
that release alone does not run the newer reset contract. In contrast, the
second reported property is present in v1.9.0: enabling motors first copies the
measured joint positions into the targets and writes those present positions
before enabling torque, reducing stale-target snap risk.

Therefore the newer lifecycle page is useful design evidence but does not
change the v1.9.0 recovery conclusion below. The project must continue to use
exact-tag behavior for claims about the tested robot.

## Executive conclusion

The public record answers most of the software-mechanics questions, but **does not contain an authoritative Pollen recovery sequence for the exact proposed failure**: a separate, minimally patched v1.9.0 daemon that has initialized the motor backend and then freezes, loses motor communication, or reports a motor error.

The strongest findings are:

- Pollen officially documents stopping the stock service and running a local daemon checkout, so a temporary, non-system-wide development daemon is a supported pattern.
- The exact v1.9.0 Wireless launch is not observationally inert: `--wireless-version` performs maintenance checks that can write local system state, and backend setup reflashes motors by default.
- A normal daemon stop may enable torque, move to sleep, and only then disable torque. In an error state, v1.9.0 skips that motion.
- Current unversioned documentation describes an automatic idle-reset backstop, but exact v1.9.0 does not contain that implementation; it cannot be relied on for the tested unit.
- Exact v1.9.0 does pin targets to measured joint positions before enabling torque, so the stale-target snap mitigation is source-supported.
- Closing the low-level control loop does not itself send the explicit torque-disable command. A killed or frozen process therefore cannot be assumed to leave motors limp.
- ROBOTIS documents a bus watchdog, but no v1.9.0 Reachy source was found configuring it. Loss of daemon communication therefore cannot be assumed to trigger an automatic motor stop.
- Power reset normally starts XL330 torque off, but actuator startup behavior is configurable and the borrowed robot's actual persistent register values have not been independently frozen.
- A 3-degree move is numerically small compared with official 5–10-degree examples and ±40-degree pitch/roll limits. That is not a mechanical guarantee, collision proof, or answer to this unit's prior target/return failure; Pollen's current troubleshooting even notes that some official motions can produce head/body contact.

## Direct answers

| Question | Best evidence-based answer | Confidence |
| --- | --- | --- |
| Can the temporary daemon be run without replacing the stock installation? | Yes. Stop the stock service, run a separate local checkout, then restore the stock service. Never run both. | High |
| Does stock v1.9.0 guarantee no persistent changes? | No. Wireless startup and default motor setup contain write-capable maintenance paths. | High |
| Can reflashing be prevented without a patch? | Not through an exposed stock v1.9.0 CLI flag. The project patch/direct-construction change is needed and must be verified. | High |
| Is graceful daemon exit equivalent to disabling motors? | No. Torque disable is an explicit separate command. | High |
| Is stock restart always the first recovery action? | Not established. It can reopen the bus, reboot errored motors, and run configuration reconciliation. | High that the uncertainty is real |
| Is power-off a recognized recovery action? | Yes, in Pollen's general troubleshooting and ROBOTIS actuator guidance. The exact priority and exceptions for this patched-daemon state are not documented. | Medium |
| Is 3 degrees mechanically reasonable? | It is numerically conservative relative to published examples and limits, but not validated for this specific robot/path. | Medium |
| Should failure trigger an automatic return? | Public sources do not approve that. v1.9.0 skips sleep movement in `ERROR`, and reports of stale/competing targets argue against inventing a return under uncertain state. | Medium |
| Is vendor input still useful? | Yes—for the precise recovery ordering, contraindications, post-recovery checks, and acceptability of stock reflash reconciliation. | High |

## Why manufacturer-specific guidance would matter

This is not because the proposed read-only capture is inherently extreme. It is because three recovery mechanisms have materially different effects:

1. **Explicit motor disable** is the cleanest software action when the daemon and bus still respond, but may fail precisely when communication is degraded.
2. **Stopping/killing the daemon** releases the process and serial resource, but does not prove an explicit torque-off reached the motors.
3. **Powering the robot off** physically removes drive power and is ordinary documented troubleshooting, but loses volatile diagnostic state and the exact whole-robot restart conditions have not been specified for this experiment.

Starting the stock daemon is a fourth action, not merely “restoration”: v1.9.0 may reboot errored motors and reconcile their persistent configuration. That may be desirable recovery, but it should not be silently equated with a read-only rollback.

## Practical consequence for the current project

The online search supports continuing all offline work and validates the technical rationale of the suppression patch. It does not justify describing a powered hardware run as Pollen-approved.

The current conservative protocol is:

- keep Reachy powered off until owner scope and the existing private review
  gates are satisfied;
- use the frozen launch command, single-daemon interlock, baseline/rollback
  diff, log-preservation procedure, and dry-run evidence;
- use the three-branch terminal state machine above rather than treating daemon
  exit as torque removal;
- treat any later powered capture as a new, explicit owner/operator risk decision;
- do not combine the receive-only capture with the 3-degree motion in the same authorization or session;
- do not perform an automatic return after an uncertain failure.

The detailed source and claim ledger is in [report-source.md](./report-source.md).
