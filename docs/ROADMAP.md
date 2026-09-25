# Roadmap

The authoritative objective and status are maintained in [`PROJECT_CHARTER.md`](PROJECT_CHARTER.md) and [`MILESTONE_MATRIX.md`](MILESTONE_MATRIX.md). This roadmap preserves completed supporting work but does not promote it above the real-world behaviour.

## Immediate: integrated real-world behaviour

- [ ] implement one deterministic shadow-only orchestrator that emits `SELECT`, `ABSTAIN`, or `HOLD` with reason codes from existing acoustic, face, and synchrony inputs;
- [ ] replay saved live-speech and phone-playback hard negatives through that same interface;
- [ ] freeze and run a small no-motion live-versus-phone shadow test before adding robot authority;
- [ ] define a new baseline-relative, one-leg physical orientation protocol with numeric abort limits and no automatic return after failure;
- [ ] define and test bounded face-directed hold metrics in replay/simulation;
- [ ] gate a minimal audible response so playback abstention permits neither motion nor response;
- [ ] integrate those paths into one explicit state machine; and
- [ ] freeze a held-out end-to-end protocol and required baselines only after every endpoint is measurable.

## Historical supporting work: evidence and manuscript infrastructure

- [x] Curate code and numeric evidence into a media-free repository.
- [x] Preserve protocol/policy fingerprints and failed outcomes.
- [x] Add a one-command integrity verifier.
- [x] Add a deterministic, CI-checked reconstruction of the public headline result table.
- [x] Publish threshold provenance and expose calibration debt.
- [x] Expand prior-art boundaries using primary sources from robot audition, active-speaker detection, selective prediction, runtime assurance, and HRI gaze.
- [x] Obtain an initial external review of claims, protocol, and threat model.
- [x] Correct the horizontal/vertical stage map and separate passive cueing from operator arming.
- [x] Replace placeholder repository URL.
- [x] Confirm public author metadata.
- [x] Consolidate the research note into a venue-neutral manuscript with Abstract, Introduction, Related Work, Methods, Results, Discussion, Ethics/Safety, Threats to Validity, and Reproducibility sections.
- [x] Regenerate every table and figure used by the manuscript from hash-bound frozen evidence.
- [x] Add a locked test environment, hardware/software inventory, and one-command deterministic paper-verification log.
- [x] Add an explicit threats-to-validity table and document that external authorization is outside the repository.

## Deferred supporting study: AV-synchrony confirmation

- [x] add post-hoc trial-level Wilson intervals, ablations, threshold sensitivity, leave-one-trial-out deletion, and finite risk/coverage operating points for Stage 3V, while labelling them exploratory;
- [x] freeze the hypotheses, conditions, exclusions, trial units, outcomes, stopping rule, and analysis structure for an audio–mouth synchrony falsification study;
- [x] implement a 12-trial laptop-only development pilot, local numeric browser recorder, fixed 240-candidate search, and synthetic end-to-end dry run;
- [x] run the real development pilot and inspect its instrumentation; all 240 settings failed the selection rule, so reject the fixed mouth-box signal and select no threshold;
- [x] implement and pre-freeze a separately versioned V2 pilot using tracked, face-normalized lip aperture, pinned local model/runtime assets, uniform objective signal-quality gates, and a development/internal-validation split; preserve all recorder revisions without changing a quality or selection gate;
- [x] complete V2 with 12 canonical trials from 23 attempts, pass the predeclared development and internal-validation rules, retain all 11 failed attempts, and freeze the selected thresholds plus exact code/model/runtime/input hashes;
- [x] freeze the candidate-bound 54-trial confirmation schedule with three room slots, balanced voice allocation, exact centred-person opposite playback, unchanged V2 gates, outcome-blind exclusions, and a fixed analysis plan;
- [x] identify before Trial 1 that the five-column recorder cannot reproduce the frozen Stage 3V spatial comparator or independent heading-error endpoints;
- [x] pause collection with zero confirmation trials captured; retain partial Room A preparation privately as protocol-development material only;
- decide between adding validated acoustic-direction capture and refreezing the execution contract, or narrowing and refreezing the study as synchrony-only exploratory work;
- only after that decision, complete the exact private room, voice, camera, microphone, browser, playback, and position records before opening confirmation collection;
- collect in at least three acoustically different rooms;
- use multiple consented recorded voices with the single on-site operator, and label them as stimuli rather than participants;
- randomize speaker position, playback position, silence, occlusion, and overlapping speech;
- hold out rooms and people, not merely repetitions;
- report selective risk versus coverage with trial-level uncertainty;
- compare against the official-style Reachy DoA-following behavior, acoustic-only, vision-only, and non-abstaining baselines.

## Before additional physical motion

- treat the completion date as unknown until the blocker below is diagnosed;
- [x] use the command-free [`neutral-frame diagnostic`](NEUTRAL_FRAME_DIAGNOSTIC.md) to compare the daemon's matrix, xyz/RPY, and state-stream representations;
- [x] establish that the desktop controller's zero display is caused by a matrix/object synchronization mismatch and is not measured-pose evidence;
- [x] verify the nominal identity measurement frame and identity joint solution against official daemon 1.9.0 behavior in a deterministic [`post-wake reference audit`](POST_WAKE_REFERENCE_AUDIT.md);
- [x] design a non-executable [`bounded centring protocol draft`](CENTERING_PROTOCOL_DRAFT.md) with a pure one-waypoint planner and explicit review debt;
- [x] complete a [`source-backed red-team review`](CENTERING_REVIEW.md) and reject the custom centring proposal for hardware execution;
- [x] implement a checksum-verified, zero-authority [`startup characterization`](STARTUP_CHARACTERIZATION.md) aggregator and record the wake/app/controller confounders required for each new capture;
- [x] audit released target telemetry and document the [`target-state observability gap`](TARGET_STATE_OBSERVABILITY.md); do not install the proposed daemon schema repair during this study;
- [x] characterize command-free start-state repeatability across three explicitly labeled physical power cycles before touching the controller; all three traces failed the unchanged 1° gate, while capture means spanned only 0.223°;
- [x] complete a powered-off operator-assisted visual inspection of cable slack and Stewart joints using the official motor/troubleshooting guidance; record `NO_OBVIOUS_VISUAL_OBSTRUCTION` without treating still images as clearance or calibration proof;
- [x] publish a source-backed [`maintenance triage`](MAINTENANCE_TRIAGE.md) that records motor mode/error evidence, ranks remaining explanations without assigning false probabilities, and forbids writes or disassembly without owner/maintainer approval;
- keep any external authorization or technical-review process outside the repository; no messages, replies, identities, or response hashes are retained as research evidence;
- do not reconsider command-capable centring or a baseline-relative successor until the external gates are satisfied independently; software tests do not complete this item;
- [x] draft a non-executable [`baseline-relative successor`](BASELINE_RELATIVE_SUCCESSOR.md) with post-V4 candidate bounds, explicit review debt, split target/return authorization, and a pure zero-authority review helper;
- [x] prototype the minimal four-field daemon 1.9.0 schema repair and reproduce the drop/preserve behavior in an isolated serialization probe;
- [x] run negative-control and patched-positive-control REST/WebSocket integration tests against the actual routes extracted from the official 1.9.0 wheel;
- [x] test released and patched complete daemon application processes with the official 1.9.0 mockup backend under loopback-only enforcement; the released daemon retained 0/4 target fields and the patched daemon retained 4/4 on both REST representations and WebSocket, with zero robot connections or commands;
- [x] specify a review-gated [`return-to-borrowed-condition protocol`](RETURN_TO_BORROWED_CONDITION.md) that prohibits system-wide replacement, calibration, factory reset, log erasure, and undocumented rollback claims;
- [x] run a deterministic [`offline failure rehearsal`](OFFLINE_FAILURE_REHEARSAL.md) covering start failure, health timeout, state-stream disconnect, shutdown hang, duplicate-start refusal, and restoration blocking; retain the explicit boundary that mock process exit does not prove hardware de-energization;
- [x] replace the ambiguous observation shutdown rule with a pure three-branch terminal planner: fresh-disabled stop and release verification, one safety-disable for fresh responsive enabled state, or physical power-off with a clear platform drop zone for unresponsive/stale/unknown state; no branch authorizes execution or automatic return;
- [x] replace fragile rotation-angle reconstruction with a numerically robust method in V4;
- [x] guarantee relative 3° increments from the captured baseline in V4;
- [x] add frozen settling dwell before V4 target/return evaluation; the later bounded observation captured a continuous trace, but no defined-target movement trace exists;
- [x] version and freeze the corrected V4 protocol before observing a V4 hardware outcome;
- [x] implement a bounded receive-only continuous present/target recorder that fails closed on missing or inconsistent target fields and preserves a coherent all-null target as `UNSET` without inference;
- [x] preserve two contained fail-closed observation rehearsals: one exposed an unpatched temporary checkout and required the physical-power terminal branch; the next exposed client deadline handling and restored stock automatically; neither entered movement;
- [x] repair the null-target route offline and add an exact-v1.9.0 two-sample health gate plus a mock-only lifecycle executor with fail-closed rollback branches;
- [x] reconstruct the exact daemon 1.9.0 continuous interpolation law offline, cross-check all samples against the official `GotoMove`, and review exact analytical IK against configured joint limits for outward and nominal return legs; the minimum margin was 42.706°, which is not collision or physical-safety evidence;
- [x] replace V4's unconditional return-on-error concept in the design-only successor with a pure state machine requiring fresh return preflight, a distinct phrase, and a fresh authorization identifier; no hardware executor exists;
- [x] complete a new isolated full-process validation of the revised null-target patch; both mock daemons exited cleanly, and the patched process preserved an explicit null target pose with zero non-loopback attempts or robot commands;
- [x] capture one valid bounded live receive-only trace: 193 frames over 10 seconds, all targets coherently `UNSET`, zero target transitions, zero trace-client application messages, zero robot commands, and healthy stock restoration with motors disabled;
- keep external scope and technical review outside the repository; no correspondence, identity, reply, or approval record is retained here;
- keep the 3-degree target/return executor blocked until movement-specific abort
  thresholds, clearance/load evidence, and a fresh split-leg review exist; the
  observation lifecycle repair does not clear motion;
- if the unresolved movement-specific gates are ever closed under a newly frozen protocol, run one direction at a time under direct operator supervision.

The display discrepancy is diagnosed. An initial uncontrolled pair of
command-free observations differed, while the subsequent controlled three-start
series found repeatable 2.529–2.752° mean offsets; every trace remained outside
the 1° gate. The cause is not established, the target state is not observable
through the released REST response, and custom centring has been rejected. No
V4 command should be sent and no 1° threshold should be weakened until
independent review addresses gate validity, target state, and the open
mechanical hypotheses. A separately versioned future protocol may use a
reviewed baseline-relative criterion, but it must not retroactively convert V4
into a pass. See [`CENTERING_REVIEW.md`](CENTERING_REVIEW.md) and
[`MAINTENANCE_TRIAGE.md`](MAINTENANCE_TRIAGE.md).

## Reproducibility engineering

- make the historical policy searches consume the public `evidence/` layout directly;
- regenerate every published table and figure, not only the headline summary;
- add a locked or otherwise reproducibly resolved dependency environment;
- add coverage, static analysis, and property tests at the numeric safety boundaries;
- create a hardware/software bill of materials and room/acquisition appendix;
- centralize current reference entry points without erasing the versioned audit trail.

## Longer term

- investigate conversational authorization and consent primitives separately from test speech, visual instructions, and typed operator arming;
- model temporal uncertainty rather than threshold only point estimates;
- test recovery when sensors disagree or disappear mid-transition;
- evaluate social acceptability of abstention and explicit cues with a consented participant protocol;
- define a production-grade command-boundary threat model.
