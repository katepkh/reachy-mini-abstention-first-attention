# Reachy Mini v1.9.0: online evidence review for temporary-daemon recovery

Date: 2026-09-05

## Executive conclusion

The public record answers most of the software-mechanics questions, but **does not contain an authoritative Pollen recovery sequence for the exact proposed failure**: a separate, minimally patched v1.9.0 daemon that has initialized the motor backend and then freezes, loses motor communication, or reports a motor error.

The strongest findings are:

- Pollen officially documents stopping the stock service and running a local daemon checkout, so a temporary, non-system-wide development daemon is a supported pattern.
- The exact v1.9.0 Wireless launch is not observationally inert: `--wireless-version` performs maintenance checks that can write local system state, and backend setup reflashes motors by default.
- A normal daemon stop may enable torque, move to sleep, and only then disable torque. In an error state, v1.9.0 skips that motion.
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

Without manufacturer-specific guidance, the conservative protocol remains:

- keep Reachy powered off;
- finish the frozen launch command, single-daemon interlock, baseline/rollback diff, log-preservation procedure, and dry-run evidence;
- treat any later powered capture as a new, explicit owner/operator risk decision;
- do not combine the receive-only capture with the 3-degree motion in the same authorization or session;
- do not perform an automatic return after an uncertain failure.

The detailed source and claim ledger is in [report-source.md](./report-source.md).
