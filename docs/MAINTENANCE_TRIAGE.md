# Maintenance triage for the repeatable post-wake residual

## Decision

**Keep Reachy powered off and keep V4 physical motion blocked.** The controlled
result is now specific enough to justify an independent gate/target/maintenance
review, but not specific enough to prove that maintenance is needed or to
justify a repair. This document authorizes zero robot commands, zero
configuration writes, and zero disassembly.

The observed condition is a repeatable measured head pose 2.529-2.752 degrees
from the daemon's identity wake endpoint across three controlled physical
starts. It is not yet valid to call that condition a bad calibration, a damaged
motor, a retained software target, or a mechanical obstruction.

## Evidence already available

| Observation | What it establishes | What it does not establish |
|---|---|---|
| Three capture means were 2.529, 2.752, and 2.746 degrees from identity; the between-start range was 0.223 degrees. | The out-of-gate state repeated under the narrow controlled protocol. | Long-term reliability, population prevalence, or cause. |
| Every capture used 20 receive-only frames and recorded zero client sends and zero robot commands. | The diagnostic did not create the measured state. | That no internal daemon target existed. |
| All three captures reported motor control `enabled` before and after sampling, zero control-loop errors, no daemon/backend error, physical backend, and daemon 1.9.0. | Disabled torque and a reported control-loop fault are not good explanations for these traces. | Correct target tracking or mechanical health. |
| No startup app was configured or running; the operator did not touch the controller after startup. | The controlled series removed the known app/controller confounders it measured. | Absence of every possible hidden software or hardware influence. |
| Exact 1.9.0 source defines identity as the final wake target. | Identity is the correct source-defined reference for the project comparison. | The target retained 60 seconds later. |
| Measured joint residuals repeat, largest at Stewart 5 (-4.071 degrees) and Stewart 6 (+3.078 degrees) relative to rounded identity IK. | The Cartesian residual has a repeatable measured-joint counterpart. | Which joint, assembly feature, load, or model parameter is causal. |
| Testbench found motors 10-18 and displayed `OK` for return delay, operating mode, angle limits, homing offset, and shutdown error. | The checked registers matched the configured values. | Horn indexing, motor slot geometry, linkage preload, dynamic cable clearance, joint friction, or Cartesian convergence. |
| Powered-off photographs and operator inspection found no obvious detached/bent rod, missing visible fastener, residue, damage, or clearly taut/trapped cable. | There was no obvious static visual obstruction in the supplied views. | Hidden contact, force, dynamic clearance, preload, wear, or calibration. |
| Released 1.9.0 REST/WebSocket serialization drops requested target fields; the four-field schema repair passes isolated mockup-daemon tests. | The observability defect and minimal schema repair are reproducible without a robot. | The live target on this unit or permission to install the patch. |

The motor mode and zero-error claims above come from the checksum-preserved
private captures. They are not inferred from the desktop controller screenshot.

## Non-probabilistic hypothesis map

The labels below summarize support from this dataset; they are not posterior
probabilities.

| Candidate explanation | Current status | Evidence for or against it | Most discriminating next evidence |
|---|---|---|---|
| Motor torque was disabled during the settled captures | **Contradicted for the sampled intervals** | All three captures reported `enabled` before and after sampling; wake motion was observed. | None needed for this dataset; retain mode in future captures. |
| Startup app or controller overwrote the pose | **Disfavoured under the controlled protocol** | No app configured/running and no controller contact; three similar outcomes. | Simultaneous present/target telemetry would test unobserved target state. |
| Random communications or forward-kinematic noise | **Disfavoured as the main explanation** | Small within-trace drift, 0.223-degree between-start range, repeated joint residual structure, zero reported control-loop errors. | A longer receive-only trace can quantify noise but is unlikely to distinguish the remaining causes. |
| Wrong configured motor register values | **Disfavoured, not independently archived as raw values** | Testbench showed all relevant checks `OK` against its expected configuration. | If a maintainer requests it, preserve a read-only raw register dump and versioned expected config; do not reflash. |
| Severe broken/reversed/misidentified motor | **Not supported by the reported symptom pattern** | All motors were detected; no overload, red LED, missing motor, or violent/reversed motion was reported. | Stop immediately and escalate if any of those symptoms appears. |
| Non-identity target remained stored after wake | **Open** | Released source intends identity, but released target fields are lost during response-model serialization. | Independently review the read-only schema patch, then observe target and present state together under a separately approved deployment protocol. |
| Steady-state tracking error under load | **Open** | Enabled motors plus a stable present-pose residual are compatible with it; target was not observable. | Simultaneous present/target joints and pose, without a movement request. |
| Cable load, hidden contact, linkage preload, or spherical-joint friction | **Open** | Official troubleshooting identifies cable slack and joint friction as relevant; still photographs cannot measure force or dynamic clearance. | Owner/maintainer-supervised physical inspection; symptom-specific maintenance only if indicated. |
| Motor arm/horn indexing, slot order, or assembly geometry mismatch | **Open** | Register checks cannot see physical indexing; official motor diagnosis uses physical line-mark alignment when symptoms justify it. | Owner/maintainer-supervised comparison with the official assembly reference. This may require disassembly. |
| Kinematic model-to-unit geometry mismatch | **Open** | Exact 1.9.0 model and measurements disagree repeatably, but there is no independent external pose reference. | Independent pose measurement plus maintainer interpretation of assembly tolerances. |
| The project's 1-degree gate is tighter than ordinary post-wake convergence on this platform | **Open** | The gate is project-selected, not a vendor tolerance. Official issue #1306 reports one enabled+wake observation at 1.9 degrees pitch, but that anecdote is not a calibration specification or a matched experiment. | Ask Pollen/maintainer for expected post-wake pose accuracy and review a future baseline-relative criterion before collecting new hardware outcomes. |
| The target-schema defect caused the physical residual | **Rejected as a causal claim** | The defect removes response fields; it does not issue motion or alter the backend target. | No causal test is warranted. Fix it only for observability. |

## Why the obvious next actions are not safe conclusions

The official Testbench and setup code can read and write EEPROM motor settings.
Because the existing `OK` result only confirms that current values match the
configured values, changing a homing offset would convert an unresolved
diagnosis into an unvalidated calibration intervention.

The official motor-diagnosis guide also describes removing a motor and checking
line marks on its arm/horn, and it asks maintainers to verify cable slack. The
spherical-joint guide describes removing rods, cleaning them, and regreasing
their joints when squeaking or dark dust indicates friction and wear. These are
real maintenance procedures, but they are invasive and symptom-dependent. The
current evidence does not authorize performing them on a borrowed robot.

Therefore do **not**:

- change homing offsets, limits, IDs, baud rate, PID values, or operating mode;
- reflash any motor;
- remove or re-index a motor arm/horn;
- loosen a Stewart rod, manually force the head, or infer stiffness by feel;
- lubricate or clean spherical joints without the relevant symptoms and owner
  approval;
- install the target-schema patch on the robot merely to make V4 proceed;
- relax the project's 1-degree neutral gate or centre the robot with a custom
  command.

## Safest next review package

No further power cycles are needed before review. Send a maintainer or robotics
reviewer these compact facts rather than asking them to read the whole history:

1. Reachy Mini Wireless; desktop app 0.9.34 and daemon 1.9.0.
2. Three physical starts, built-in wake observed each time, no startup app and
   no controller input before capture.
3. Motor mode `enabled`, zero daemon/backend/control-loop errors during all
   captures.
4. Settled rotation from identity: 2.529, 2.752, and 2.746 degrees; frozen
   project gate: 1 degree.
5. Largest repeatable identity-IK joint residuals: Stewart 5 -4.071 degrees and
   Stewart 6 +3.078 degrees.
6. Motors 10-18 detected; Testbench configuration checks all `OK`.
7. Powered-off visual result: no obvious static obstruction, but dynamic
   clearance and physical indexing remain unverified.
8. Released target telemetry is absent because of a reproduced schema defect;
   the proposed four-field repair has been tested only in isolated mockup
   processes and is not installed.

Ask the reviewer to answer three bounded questions:

1. Is a 1-degree identity gate a reasonable readiness criterion for this
   platform, or should a new, preregistered protocol use a stable captured
   baseline plus an independently justified absolute mechanical envelope?
2. Does this pattern justify checking cable travel, horn/arm index marks, motor
   slot order, or another assembly reference before any more commanded motion?
3. Is there a manufacturer-approved, read-only way on daemon 1.9.0 to observe
   retained target joints/pose, servo load/current, or raw positions without
   changing configuration?
4. If an inspection or telemetry patch is warranted, exactly which procedure
   should be used, what must be backed up first, and what abort conditions apply?

## Branches after independent review

### A. Observability review approves a target-state deployment

Create a separate, reversible deployment protocol. Pin and back up the exact
daemon/configuration, verify the patch artifact, install no other change, and
capture simultaneous present/target state without issuing a movement request.
That protocol requires fresh review because installing software changes the
experimental system.

### B. Mechanical review requests an official inspection

Follow only the named official procedure, with the lender's permission. Record
before/after photographs and configuration, change one thing at a time, and do
not combine cable routing, arm indexing, offsets, and lubrication in one
intervention.

### C. Neither intervention is approved

Leave V4 blocked. Continue the speaker-selection research offline, in
simulation, and with passive sensing. A blocked actuator study is an honest
result; it does not invalidate the already frozen passive experiments.

### D. Gate review supports a baseline-relative successor protocol

Do not reinterpret or relabel V3/V4: they remain failed/blocked against their
frozen thresholds. Specify a new protocol version before seeing new hardware
results. It must preserve an absolute mechanical envelope, use a fresh captured
baseline for the 3-degree increment and return, and state why its readiness and
tracking bounds are appropriate. Independent review is still required before
execution.

## Conditions for reconsidering V4

Physical motion is not reopened merely because one suspected issue is changed.
At minimum, require:

- a documented maintenance disposition or cause-specific repair;
- exact software/configuration provenance after the intervention;
- simultaneous target and present state, or a reviewed justification for its
  absence;
- three fresh, equivalent, command-free starts entirely within the unchanged
  1-degree V4 gate, **or** a separately versioned and preregistered successor
  criterion accepted in independent review without relabeling V4;
- motor mode enabled, no reported hardware/control-loop error, and no active or
  configured startup app;
- a newly reviewed and frozen V4 protocol with the existing stop conditions;
- then one direction only, at 3 degrees, under direct supervision.

Passing these conditions would authorize reconsideration, not prove safety or
calibration.

## Official sources and scope

- Reachy Mini 1.9.0
  [`daemon.py`](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/daemon/daemon.py),
  [`abstract.py`](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/daemon/backend/abstract.py),
  [`robot/backend.py`](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/daemon/backend/robot/backend.py),
  [`setup_motor.py`](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/tools/setup_motor.py),
  and [`hardware_config.yaml`](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/assets/config/hardware_config.yaml).
- Current official
  [motor-diagnosis guide](https://github.com/pollen-robotics/reachy_mini/blob/main/docs/source/troubleshooting/motors_diagnosis.md)
  and
  [spherical-joint maintenance guide](https://github.com/pollen-robotics/reachy_mini/blob/main/docs/source/troubleshooting/spherical_joints_maintenance.md).
- Official issue
  [#1306](https://github.com/pollen-robotics/reachy_mini/issues/1306)
  documents the otherwise easy-to-miss disabled-motor-mode failure pattern and
  reports one enabled+wake observation at 1.9 degrees pitch. That single report
  is context, not a vendor tolerance or a matched reference dataset.

The version-pinned source supports claims about the unit's exact runtime. The
current troubleshooting pages supply maintenance guidance but may postdate
daemon 1.9.0. Neither source establishes the cause on this particular robot.
