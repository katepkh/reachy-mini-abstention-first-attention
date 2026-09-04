# Roadmap

## Immediate: publishable research preview

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

## Next scientific study

- preregister hypotheses, thresholds, exclusion rules, and trial-level analyses;
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
- [x] prepare a complete [`independent robotics review request`](INDEPENDENT_PROTOCOL_REVIEW.md) covering the gate, target observability, exact path, joint margins, maintenance hypotheses, and split failure/return semantics;
- obtain an actual independent human verdict before reconsidering any command-capable centring or baseline-relative successor; a prepared packet, software tests, or AI review does not complete this item;
- [x] draft a non-executable [`baseline-relative successor`](BASELINE_RELATIVE_SUCCESSOR.md) with post-V4 candidate bounds, explicit review debt, split target/return authorization, and a pure zero-authority review helper;
- [x] prototype the minimal four-field daemon 1.9.0 schema repair and reproduce the drop/preserve behavior in an isolated serialization probe;
- [x] run negative-control and patched-positive-control REST/WebSocket integration tests against the actual routes extracted from the official 1.9.0 wheel;
- [x] test released and patched complete daemon application processes with the official 1.9.0 mockup backend under loopback-only enforcement; the released daemon retained 0/4 target fields and the patched daemon retained 4/4 on both REST representations and WebSocket, with zero robot connections or commands;
- [x] prepare an explicit [`robot-owner scope request`](OWNER_SCOPE_REQUEST.md) separating powered observation, daemon modification/restart, physical target/return, and publication;
- [x] specify a review-gated [`return-to-borrowed-condition protocol`](RETURN_TO_BORROWED_CONDITION.md) that prohibits system-wide replacement, calibration, factory reset, log erasure, and undocumented rollback claims;
- [x] preserve the owner's actual acceptance of the limited temporary-daemon and restore/verify request as a hash-verified private artifact; physical target/return permission remains unrequested and must be obtained separately before motion;
- [x] run a deterministic [`offline failure rehearsal`](OFFLINE_FAILURE_REHEARSAL.md) covering start failure, health timeout, state-stream disconnect, shutdown hang, duplicate-start refusal, and restoration blocking; retain the explicit boundary that mock process exit does not prove hardware de-energization;
- [x] replace fragile rotation-angle reconstruction with a numerically robust method in V4;
- [x] guarantee relative 3° increments from the captured baseline in V4;
- [x] add frozen settling dwell before V4 target/return evaluation; continuous trace capture remains missing;
- [x] version and freeze the corrected V4 protocol before observing a V4 hardware outcome;
- [x] implement a bounded receive-only continuous present/target recorder that fails closed on released 1.9.0's missing target fields and requires a byte-verified owner-scope record; no live successor trace exists yet;
- [x] reconstruct the exact daemon 1.9.0 continuous interpolation law offline, cross-check all samples against the official `GotoMove`, and review exact analytical IK against configured joint limits for outward and nominal return legs; the minimum margin was 42.706°, which is not collision or physical-safety evidence;
- [x] replace V4's unconditional return-on-error concept in the design-only successor with a pure state machine requiring fresh return preflight, a distinct phrase, and a fresh authorization identifier; no executor exists;
- freeze a successor only after owner scope and independent robotics review are recorded as hashed artifacts;
- run one direction at a time under direct operator supervision.

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
