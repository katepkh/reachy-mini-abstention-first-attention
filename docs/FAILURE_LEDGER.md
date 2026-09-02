# Failure ledger

## Why keep a failure ledger?

An embodied-system result is not trustworthy if unsuccessful attempts disappear, a post-hoc threshold turns red into green, or a new protocol inherits an old label. This ledger makes those boundaries explicit.

## Stage 2A: source ownership failure

**Observed:** a silent visible face plus spatially separate phone speech produced 13 confirmations over 63 tracked rows.

**Meaning:** angular agreement can be caused by reflection, endpoint variation, or coincidence. A visible face spatially compatible with DoA is not proof that the person is speaking.

**Response:** kept the system passive; added stricter temporal consensus and hard-negative selection criteria. No identity claim was introduced.

## Stage 2A: visual boundary degradation

**Observed:** a single face at the image edge frequently appeared as no face or multiple faces.

**Meaning:** detector state is not a stable proxy for the number of people at a boundary.

**Response:** missing, multiple, stale, and boundary-unstable observations lock out passive target confirmation.

## Stage 3P versions before V6

Earlier vertical-policy versions produced wrong-sign, accuracy, coverage, and pre-transition-association failures. Their frozen manifests remain in `evidence/manifests/`. New policy versions were created; old outcomes were not overwritten.

## Stage 4A V3 physical pilot

**Observed:** a requested 3° head-only movement yielded 1.349887° robust measured motion. Target error was 2.079459° and return error was 1.677847°. The mechanical gate failed.

**Diagnostic root causes:**

1. target pose sampled before the frozen settling dwell;
2. return pose sampled with no settling dwell;
3. trace angle applied directly to slightly non-orthonormal forward-kinematics matrices;
4. absolute-neutral targeting did not guarantee a 3° increment from the captured baseline.

**Integrity decision:** the failed trial remains frozen and failed. Thresholds were not weakened, and the same protocol may not be rerun as though fresh. A corrected protocol must receive a new fingerprint and new evidence.

**Current blocker:** after power cycles and visible controller zeroing, read-only preflight still reported the head 2.49°–4.43° from the daemon's nominal identity reference. Motor discovery/configuration diagnostics found all 9 motors and all inspected configuration fields OK.

**2026-09-01 read-only diagnosis:** a command-free 20-frame state capture measured 4.159–4.221° from identity with only 0.092° maximum drift from its first frame. Matrix REST, Euler REST, and matrix-stream representations agreed within sampling drift. Inspection of desktop app v0.9.34 found that it stores matrix pose data but its controller sync reads named pose fields and substitutes zero, explaining the misleading `0.000` display. Nominal identity inverse kinematics also disagreed with the measured joint vector, by up to 6.19° at Stewart 5. The presentation ambiguity is resolved; the physical/calibration neutral-state blocker is not. The immutable private capture hash is `08caf0694662669cb04b072f32bed6bd138ba78fa2229c82014fed17cec9a142`.

**Later zero-command state:** after Reachy was turned on again, a second 20-frame capture measured 1.333–1.459° from identity (mean 1.409°) with 0.088° maximum drift. It again sent 0 commands; its immutable private hash is `1b10ae59156d5d0cae202ead82204edb2a3c3c99eeec4e53d9716bbbfaa624d6`. The two captures are not a controlled repeated-start study and do not identify a cause, but they rule out treating 4.18° as one fixed offset. The newer state also fails the unchanged 1° gate.

**Controlled three-start characterization:** three equivalent physical power cycles with wake observed, a fixed 60-second wait, no controller contact, no configured or running app, and 20 receive-only frames per start produced mean offsets of 2.529°, 2.752°, and 2.746°. The between-start mean range was 0.223°; maximum within-trace drifts were 0.074°, 0.095°, and 0.170°. All three traces failed the unchanged 1° gate. The capture hashes and protocol are recorded in [`STARTUP_CHARACTERIZATION.md`](STARTUP_CHARACTERIZATION.md); the private aggregate report hash is `84b04e976cc38e5773f8bfd8573aa90fde9e925444262adc72b99150f242fc56`.

**Meaning:** this unit exhibited a repeatable non-identity measured start state under this narrow protocol. That does not identify a calibration, mechanical, stored-target, or model cause and is not repair validation or a population estimate. Because 1° is a project gate rather than a vendor tolerance, failing it is not proof that the hardware is faulty.

**Target observability gap:** a read-only daemon 1.9.0 request explicitly asked for target head pose and joints. The route accepts those query flags, but its released `FullState` model has no target fields, so they were absent from the response. Stored-target error therefore remains unknown through this REST surface.

**Integrity decision:** no movement followed any diagnostic or controlled-start capture. A source-backed red-team review rejected the custom centring proposal for hardware execution because its thresholds, collision/path assurance, target observability, and failure response are insufficient. The pure planner remains only as an auditable counterfactual and authorizes zero commands. V4 remains blocked pending independent review of its gate, target observability, and open maintenance hypotheses, followed by a newly frozen protocol.

**2026-09-02 non-actuating successor work:** the exact nominal 1.9.0 target/return trajectories and analytical IK were reconstructed offline, with a minimum 42.706° supplied configured-limit margin. This did not resolve the failure: analytical collision checking, live present/target telemetry, tracking, load/current, cable and enclosure clearance, and an actual return from a measured target remain absent. A receive-only recorder and split target/return state machine were added, but the recorder has not run, the observability patch is uninstalled, no executor exists, and owner/independent approvals are not recorded. Therefore the physical blocker and 0/4 accepted V4 directions remain unchanged.
