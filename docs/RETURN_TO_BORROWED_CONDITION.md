# Return-to-borrowed-condition protocol

## Status and claim boundary

**Design only. Not executed.** This protocol does not authorize powering,
patching, restarting, or moving Reachy.

The objective is to restore the robot to the same **practical software,
configuration, and operating condition** in which it was borrowed. Literal
identity is impossible to promise after use: boots and experiments add logs and
timestamps, storage may accumulate ordinary runtime data, and physical motion
adds non-zero mechanical use. Those residuals must be disclosed to and accepted
by the owner rather than erased or described as reversible.

No project action may recalibrate motors, write offsets/limits/PID/baudrate/IDs,
update firmware or the operating system, perform a factory reset, disassemble
the mechanism, or replace the system-wide daemon. The observed post-wake
non-identity pose is part of the borrowed unit's measured baseline; this project
must not attempt to "fix" it.

## Why rollback needs separate review

The proposed four-field patch changes only the daemon's `FullState` response
schema, but observing those fields on the wireless robot still requires running
modified server code and restarting a daemon. Reachy Mini 1.9.0 daemon startup
normally constructs the hardware backend, calls `reflash_motors_if_needed`, and
may enable motors and execute the wake routine. A source-minimal schema change
therefore does **not** make the complete deployment procedure risk-free.

The official development guide recommends a separate local development checkout
for testing without replacing the system-wide installation. That is the only
deployment class considered here. A system-wide forced reinstall and Bluetooth
`SOFTWARE_RESET` are excluded: a factory reinstall is a recovery mechanism, not
evidence that the prior version, configuration, network state, apps, logs, and
calibration have been reproduced exactly.

Primary sources:

- [official separate-development and system-wide installation guidance](https://github.com/pollen-robotics/reachy_mini/blob/main/docs/source/platforms/reachy_mini/install_daemon_from_branch.md);
- [daemon 1.9.0 startup path](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/daemon/daemon.py);
- [daemon 1.9.0 wake implementation](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/daemon/backend/abstract.py).

## Required approvals

Before even the baseline inventory is collected from the powered robot:

1. the owner must define what “returned in the same condition” means to them and
   approve the listed observations, temporary files, daemon stop/start, known
   residual logs, and cleanup method;
2. an independent human robotics reviewer must approve the exact deployment and
   rollback procedure, including daemon-start motor reflash and wake semantics;
3. the operator must accept a written stop rule and must not improvise if any
   baseline field cannot be captured or restored.

Approval of a receive-only network client alone is not approval of daemon
replacement, restart, motor initialization, motion, cleanup, or deletion.

## Phase A — pre-change baseline

Capture immutable, timestamped records before stopping the original service:

| Surface | Minimum record | Acceptance rule after rollback |
|---|---|---|
| Physical exterior | Owner-approved photographs; cable and enclosure observations | No new visible damage or changed assembly |
| Robot identity | Hardware identifier recorded privately | Exact match |
| OS and daemon | OS release; daemon/package version; Python environment/package inventory | Exact values unless owner explicitly accepts a difference |
| Code and configuration | SHA-256 of the installed `reachy_mini` package tree, hardware configuration, daemon service unit and relevant startup configuration | Exact hash match |
| Services | Enabled/running state and exact daemon launch configuration | Exact match |
| Installed/startup apps | Installed-app inventory and configured/running startup app | Exact match |
| Network configuration | Non-secret identifiers and configuration hashes; do not export credentials | Exact match or owner-approved exception |
| Robot status | Daemon status, control mode, reported errors, detected motor IDs and read-only motor health fields | Same expected inventory; no new warning/error |
| Startup behavior | Existing controlled-start evidence plus one owner-approved fresh baseline if required | Same qualitative behavior and preregistered distributional tolerance—not an exact floating-point pose |

Every raw baseline artifact receives a SHA-256 sidecar and remains private.
Missing data is not filled from memory. If an exact baseline cannot be captured,
the corresponding change is prohibited.

## Phase B — bounded temporary deployment

This phase remains prohibited until the two approvals above exist.

1. Verify the exact daemon 1.9.0 source/wheel and the four-field patch against
   the reviewed manifest.
2. Create an isolated, clearly named temporary checkout/environment. Do not
   modify `/venvs/mini_daemon`, its system package, its service unit, hardware
   configuration, installed apps, or motor configuration.
3. Record all files created on the robot and their locations before launch.
4. Stop the original daemon through the reviewed service procedure.
5. Start only the reviewed temporary daemon invocation. The reviewer must first
   resolve whether motor reflashing can occur and whether wake can be suppressed
   without introducing a different unreviewed patch. Unexpected firmware work,
   wake motion, version drift, or startup output terminates the procedure.
6. Run one bounded state-only capture. It may receive present/target state but
   must send no application command or start any robot app.
7. Stop the temporary daemon. Do not combine this phase with a target or return
   motion.

No deletion or rollback command should be assembled dynamically. All paths and
services must be resolved and recorded before the procedure is approved.

## Phase C — rollback

1. Preserve the experiment and daemon logs; never erase evidence to make the
   robot appear unchanged.
2. Stop the temporary daemon and confirm that no temporary process remains.
3. Restart the exact original system daemon/service using its original launch
   configuration.
4. Remove only the enumerated temporary checkout/environment if the owner has
   approved that cleanup. Do not remove caches, logs, or unrelated files.
5. Repeat the complete baseline inventory and hash comparison.
6. Perform an owner-approved cold start and normal Reachy Mini Control check:
   expected daemon version, `Ready`, expected motors, no new warnings, and the
   same documented startup behavior.
7. Produce a signed/dated discrepancy report. Any mismatch is a failed rollback
   until the owner decides how it should be resolved.

`SOFTWARE_RESET`, OS update, factory image reflash, motor setup, and calibration
are not rollback steps under this protocol.

## Return acceptance record

The robot is not described as restored until all of the following are true:

- every required software/configuration/service hash matches its baseline;
- the original daemon and app configuration are active;
- the motor inventory is unchanged and there is no new reported fault;
- no unapproved experimental service, app, or persistent startup entry remains;
- all differences—including new logs, timestamps, temporary-file residue, pose
  variation, or physical observations—are listed rather than hidden; and
- the owner reviews the comparison and explicitly accepts the return condition.

This establishes documented practical equivalence, not literal proof that no
wear or internal state changed.

## Stop conditions

Stop without attempting an improvised fix if any of these occurs:

- baseline backup or hashing is incomplete;
- source, package, service, configuration, app, or firmware identity is
  ambiguous;
- the temporary daemon would write motor firmware or configuration outside the
  separately approved scope;
- the original daemon cannot be restarted exactly;
- a new error, noise, heat, shaking, stale state, unexpected motion, or physical
  discrepancy appears; or
- owner or reviewer approval is absent, expired, conditional in an unmet way,
  or withdrawn.

The default response is safe shutdown, evidence preservation, and owner
notification—not factory reset, calibration, continued experimentation, or
concealment of the difference.
