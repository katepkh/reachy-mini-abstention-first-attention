# External review packet

## Purpose

This document is a candid briefing for an independent reviewer of the repository [Reachy Mini Abstention-First Attention](https://github.com/katepkh/reachy-mini-abstention-first-attention). It is written to make critical review easier, not to persuade the reviewer that the work is already complete.

The desired audience includes experienced robotics engineers, human-robot interaction (HRI) researchers, multimodal perception researchers, runtime-assurance and safety engineers, and technical leaders at robotics companies or startups.

The reviewer is asked to assess four different things separately:

1. the scientific question and novelty;
2. the experimental design and evidence;
3. the software and safety architecture;
4. the clarity and credibility of the public GitHub presentation.

## Situation and constraints

- One Reachy Mini is available.
- One primary operator performs the robot-side experiments.
- Additional human voices can be incorporated as consented recordings, but additional live experimenters are not presently available.
- The current evidence comes from one site and primarily one room.
- Raw audio, camera images, transcripts, identity labels, and face embeddings are deliberately excluded from the public repository.
- Passive experiments are complete for the published frozen protocols.
- One supervised physical motion trial ran and failed.
- The corrected V4 physical path is currently blocked. After two exploratory command-free captures, a controlled three-power-cycle series measured repeatable mean rotations of 2.529°, 2.752°, and 2.746° from nominal identity, all outside the frozen 1° project gate. Motor mode was enabled and no control-loop error was reported during those captures. The controller's zero display has separately been traced to a matrix/object synchronization defect; target state remains hidden by a reproduced response-schema defect.

These constraints matter. Recorded voices can test acoustic variability and playback hard negatives, but they cannot substitute for a live multi-person HRI study, independent operation, or socially meaningful eye-contact evaluation.

## Goal and evolution of the research question

The longer-term product-like ambition is understandable: when someone speaks, Reachy should orient toward that person and sustain socially appropriate attention. That behavior is not new in broad form, and the official Reachy Mini repository already contains a DoA-driven example that commands the head toward speech.

The stronger current research question is narrower and more defensible:

> How can a social robot keep weak acoustic/visual compatibility, operator arming, and mechanical readiness as separately inspectable boundaries before movement is permitted?

This changes the project from a speaker-following demonstration into a study of selective action. It asks when the robot should refuse to move, not merely whether it can produce a plausible target.

The intended architecture is:

```text
local numeric evidence
        |
        v
selective grounding ------> ABSTAIN / HOLD when unresolved
        |
        v
system-issued visual cue -> TIMEOUT when compatibility is not ready
        |
        |  not yet integrated end to end
        v
typed operator arm + mechanical governor -> BLOCK when not ready or out of bounds
        |
        v
one bounded head command, or no motion
```

The work does not claim that selective prediction, DoA, face detection, active-speaker localization, passive cueing, operator arming, or runtime gating is individually novel. The possible contribution is their auditable staged composition under data-minimizing constraints, combined with hard-negative experiments and preservation of failed physical results. The stages are not yet validated as one end-to-end path.

## Work completed

### Stage 2A: passive acoustic/visual matrix

Fifteen accepted trials covered five conditions with three repetitions each:

1. visible silent face;
2. speech with no visible face;
3. matching visible face and speech;
4. silent visible face with phone speech from the right;
5. partial edge face with speech.

The matrix contains 815 numeric observations, of which 801 had valid DoA responses. No robot command was available in this stage.

Headline observations:

- matching face and speech: 62 confirmations among 71 tracked rows;
- speech with no visible face: 0 among 35 tracked rows;
- silent visible face with spatially separate phone speech: 13 among 63 tracked rows;
- partial edge face: unstable detector availability, including no-face and multiple-face states.

The important finding is negative: spatial agreement is compatible with a visible person being the speaker, but does not prove source ownership.

### Stage 2A: retrospective policy tournament

Five policies were replayed over frozen numeric rows. Repetitions 1–2 were designated development and repetition 3 evaluation. The development-selected 3-hit consensus policy produced 0/37 hard-negative confirmations and 2/31 matching confirmations on the evaluation repetition.

This exposes a genuine safety/coverage frontier. It is not a pristine blind holdout because the full matrix had already been inspected before the split was formalized.

### Stage 3V: fresh passive horizontal off-axis holdout

A revised passive policy was frozen before fresh collection. Eighteen accepted trials from 21 attempts covered positive headings at ±10° and ±20° plus hard negatives.

- 12/12 positive trials produced a passive proposal;
- 0 hard-negative would-move rows;
- 0 wrong-sign moves;
- maximum target error 2.647°;
- safety, direction, coverage, and accuracy gates passed.

This is stronger than the retrospective tournament because the policy was frozen before collection. It remains a small, single-site passive test.

### Stage 3P: association-gated visual-cue boundary

Nine accepted trials from 18 attempts included six associated vertical transitions and three no-cue controls. Superseded attempts were retained.

- all seven predefined cue/integrity/control/direction/bound/coverage gates passed;
- controls timed out fail-closed;
- 0 control adjustments;
- 0 robot requests;
- 0 actuation commands;
- 0 cloud requests.

The fixed test phrase supplied repeated speech only. Stage 3P received no transcript, did not recognize or match phrase content, and could only display a visual instruction to the operator. This is neither arming nor a model of consent or authorization. The separate Stage 4 exact typed phrase is local one-shot arming friction, not identity, intent, consent, or conversational permission.

### Stage 4A V3: supervised physical pilot

One physical trial issued two head-only commands: a target command and automatic return. It produced:

- measured movement from baseline: 1.349887°;
- error to requested target: 2.079459°;
- return-to-baseline error: 1.677847°;
- mechanical gate: **FAIL**.

No body-yaw, antenna, torque, motor-mode, media, or cloud request was issued. The failed record is hash-frozen and was not relabelled after diagnosis.

The diagnostic identified four defects:

1. target pose was sampled before the intended settling dwell;
2. return pose was sampled without a settling dwell;
3. a trace-angle formula was applied directly to slightly non-orthonormal forward-kinematics matrices;
4. an absolute-neutral target did not guarantee a 3° increment from the captured baseline.

### Stage 4A V4: corrected but unvalidated path

The current Stage 4 code changes the target to a captured-baseline-relative 3° increment, projects poses to the nearest rigid transform, measures SO(3) distance after projection, and includes target and return settling intervals. It retains expiring read-only preflight, one-shot consumption, exact direction locking, head-only commands, automatic return, and unchanged acceptance thresholds.

No V4 physical result is published. Initial 2026-09-01 command-free captures resolved the display ambiguity: the daemon's matrix REST, Euler REST, and matrix stream agreed within sampling drift, while desktop app v0.9.34 substituted zeros after reading matrix data as named fields. A later controlled three-power-cycle series found repeatable means of 2.529°, 2.752°, and 2.746°, with motor mode enabled and zero reported loop errors. Motor discovery found 9/9 motors and the inspected configuration fields were valid, but those checks do not validate assembled geometry, friction, cable clearance, or physical neutral. Daemon 1.9.0 also drops requested target head fields from its released `FullState` response, preventing present-versus-target diagnosis through that route. The custom centring proposal is therefore rejected for hardware execution pending independent review of gate validity, target-state observability, and open maintenance hypotheses. The 1° gate is a project threshold, not proof of hardware fault.

### Stage 4A successor: offline progress, still zero authority

A separately versioned successor now contains a receive-only simultaneous present/target recorder, an exact offline 1.9.0 trajectory/IK validator, external-record verification, and a pure split target/return state machine. The offline validator byte-verified the official 1.9.0 wheel and installed source, pinned Rust kinematics 1.0.3, matched official `GotoMove` at every one of 201 ideal samples per leg to a maximum matrix-element difference of `4.44e-16`, and found a 42.706° minimum supplied configured-limit margin across the four 3° outward and nominal-return paths.

A deterministic offline failure rehearsal also exercised four fixed local mock-process cases: start failure, health timeout, state-stream disconnect while the process remained alive, and shutdown hang. All four refused a duplicate lease and kept the mock restoration gate closed until process exit and lease release. This is process-orchestration evidence only; it says nothing about real serial-bus release, torque state, safe physical de-energization, or whether a stock daemon restart is appropriate.

This does not clear physical motion. Analytical collision checking is absent; actual loop timestamps, endpoint writes, tracking, load/current, cables, and the return from a measured post-target pose remain untested. The recorder cannot obtain target fields from the unmodified daemon, and its observational patch is not installed. The owner has confirmed the limited temporary-daemon and restore/verify scope in a private hash-verified record, but no 3° motion permission is inferred and no independent human reviewer has approved the protocol. The successor has no executor and authorizes zero commands. Unlike frozen V4, its design does not automatically return: target success leads to a new return preflight and a different authorization; target failure enters a conditional no-automatic-return response matrix whose unit-specific physical actions remain unapproved.

## Public artifacts produced

### Documentation and presentation

- [`README.md`](../README.md): top-level question, current boundary, result table, claim limits, code map, reproduction commands, and review questions.
- [`RESEARCH_NOTE.md`](RESEARCH_NOTE.md): compact paper-style narrative.
- [`METHODS.md`](METHODS.md): staged experimental design.
- [`RESULTS.md`](RESULTS.md): frozen metrics and fingerprints.
- [`GENERATED_RESULTS.md`](GENERATED_RESULTS.md): deterministic headline table reconstructed from frozen JSON after source-file verification.
- [`THRESHOLD_PROVENANCE.md`](THRESHOLD_PROVENANCE.md): distinguishes development-selected, protocol-fixed, project-fixed, and hardware-bound values.
- [`ATTEMPT_ACCOUNTING.md`](ATTEMPT_ACCOUNTING.md): trial units, uncertainty context, and accepted/superseded attempt flow.
- [`FAILURE_LEDGER.md`](FAILURE_LEDGER.md): preserved failures and responses.
- [`CENTERING_REVIEW.md`](CENTERING_REVIEW.md): source-backed review and rejection of the custom centring proposal for hardware execution.
- [`STARTUP_CHARACTERIZATION.md`](STARTUP_CHARACTERIZATION.md): controlled command-free repeated-start protocol and powered-off inspection boundary.
- [`TARGET_STATE_OBSERVABILITY.md`](TARGET_STATE_OBSERVABILITY.md): released API gap, startup target sequence, and an uninstalled minimal repair proposal.
- [`BASELINE_RELATIVE_SUCCESSOR.md`](BASELINE_RELATIVE_SUCCESSOR.md): separately versioned, non-executable successor draft with post-V4 candidate bounds and explicit review debt.
- [`RECEIVE_ONLY_SUCCESSOR_TRACE.md`](RECEIVE_ONLY_SUCCESSOR_TRACE.md): exact recorder scope, released-schema blocker, and owner-gated capture boundary.
- [`OFFLINE_FAILURE_REHEARSAL.md`](OFFLINE_FAILURE_REHEARSAL.md): four local mock-process failure scenarios and their hardware claim boundary.
- [`SUCCESSOR_TRAJECTORY_REVIEW.md`](SUCCESSOR_TRAJECTORY_REVIEW.md): exact 1.9.0 interpolation/IK cross-check, configured-limit margins, and missing physical assurances.
- [`SPLIT_TARGET_RETURN_PROTOCOL.md`](SPLIT_TARGET_RETURN_PROTOCOL.md): target/return state graph, independent phrases, and fail-to-power-down semantics.
- [`OWNER_SCOPE_REQUEST.md`](OWNER_SCOPE_REQUEST.md): itemized request template; it is explicitly not permission.
- [`RETURN_TO_BORROWED_CONDITION.md`](RETURN_TO_BORROWED_CONDITION.md): baseline, temporary-deployment, rollback, discrepancy, and owner-acceptance requirements for the borrowed unit.
- [`INDEPENDENT_PROTOCOL_REVIEW.md`](INDEPENDENT_PROTOCOL_REVIEW.md): complete human robotics review packet and required verdict format.
- [`SUCCESSOR_REVIEW_MANIFEST.json`](SUCCESSOR_REVIEW_MANIFEST.json): hashes the exact code, documentation, patch, and tests submitted as the successor review packet.
- [`LIMITATIONS.md`](LIMITATIONS.md): supported and unsupported claims.
- [`DATA_CARD.md`](DATA_CARD.md): evidence contents, exclusions, privacy risks, and unsuitable uses.
- [`PRIOR_ART.md`](PRIOR_ART.md): primary-source positioning against Reachy, robot audition, active-speaker detection, selective prediction, runtime assurance, and social gaze.
- [`SAFETY.md`](../SAFETY.md): hardware boundary and stop conditions.
- [`DISCORD_MESSAGE.md`](../DISCORD_MESSAGE.md): expert-group introduction.
- [`figures/architecture.png`](../figures/architecture.png) and [`figures/safety-coverage-frontier.png`](../figures/safety-coverage-frontier.png): public explanatory figures.

### Evidence

The `evidence/` tree contains 187 tracked files. The public verifier checks 171 manifest-listed source files plus frozen headline assertions. It includes derived CSV/JSON rows, trial metadata, compliance records, aggregate reports, protocol/policy manifests, rejected or superseded attempts where retained, and Stage 4 diagnostic records.

It deliberately excludes raw audio, camera pixels, transcripts, face embeddings, identity labels, temporary encrypted audit clips and keys, credentials, and private laboratory paths.

### Software

At the time of this audit the repository contains:

- 120 source Python modules and 20,659 source lines;
- 41 Python test modules;
- 40 explicitly versioned source modules preserving policy/protocol history;
- seven public verification/diagnostic scripts, including the evidence verifier, deterministic public-summary generator, exact 1.9.0 trajectory validator, owner-gated receive-only recorder, and successor packet manifest checker;
- 213 passing self-contained software tests.

The test count must not be mistaken for an experimental sample size.

## Code map for reviewers

### `reachy_doa/`: acoustic acquisition, policy, and evidence foundation

- [`client.py`](../reachy_doa/client.py): GET-only DoA client restricted to a private or loopback IPv4 address, one fixed scheme/port/path, no redirects, bounded timeout, and explicit invalid readings.
- [`angles.py`](../reachy_doa/angles.py): angle wrapping and physical-hypothesis conversion.
- [`models.py`](../reachy_doa/models.py): typed numeric DoA records.
- [`confidence.py`](../reachy_doa/confidence.py): temporal feature windows and reliability envelope.
- [`policies.py`](../reachy_doa/policies.py): example-style and abstention-capable offline policies.
- [`protocol.py`](../reachy_doa/protocol.py): staged acquisition protocol definitions.
- [`recorder.py`](../reachy_doa/recorder.py): numeric evidence recording.
- [`replay.py`](../reachy_doa/replay.py), [`evaluation.py`](../reachy_doa/evaluation.py), and [`analysis.py`](../reachy_doa/analysis.py): offline comparison and summaries.
- [`decisions.py`](../reachy_doa/decisions.py), [`manifest.py`](../reachy_doa/manifest.py), and [`labbook.py`](../reachy_doa/labbook.py): accepted/superseded accounting, hashing, and provenance.
- [`source_validity.py`](../reachy_doa/source_validity.py) and [`source_evaluation.py`](../reachy_doa/source_evaluation.py): source-validity analysis.

Review focus: endpoint assumptions, time/freshness semantics, front/back ambiguity, correlated samples, and whether confidence heuristics have a principled interpretation.

### `reachy_stage2a/`: local face geometry and passive fusion

- [`face_detector.py`](../reachy_stage2a/face_detector.py): YuNet face detection wrapper.
- [`camera_worker.py`](../reachy_stage2a/camera_worker.py): camera lifecycle and current-frame state.
- [`models.py`](../reachy_stage2a/models.py): face observations and fusion decisions.
- [`fusion.py`](../reachy_stage2a/fusion.py): spatial compatibility logic.
- [`stream_client.py`](../reachy_stage2a/stream_client.py): local media transport.
- [`calibration.py`](../reachy_stage2a/calibration.py): geometric mapping.
- [`protocol.py`](../reachy_stage2a/protocol.py), [`recorder.py`](../reachy_stage2a/recorder.py), and [`progress.py`](../reachy_stage2a/progress.py): collection state.
- [`tournament.py`](../reachy_stage2a/tournament.py): counterfactual policy comparison.

Review focus: calibration assumptions, detector bias and boundary instability, time synchronization, false association under reflection/playback, and the distinction between visible compatibility and active-speaker evidence.

### `reachy_stage3a/`: motion shadow

- [`controller.py`](../reachy_stage3a/controller.py): bounded counterfactual target generation.
- [`evaluation.py`](../reachy_stage3a/evaluation.py): passive motion-shadow aggregation.

Review focus: coordinate conventions, bounds, and assurance that no command path exists.

### `reachy_stage3v/`: fresh horizontal off-axis confirmation

- [`revised_policy_v3.py`](../reachy_stage3v/revised_policy_v3.py): selected frozen passive policy.
- [`confirmation_protocol_v3.py`](../reachy_stage3v/confirmation_protocol_v3.py): fresh protocol definition.
- [`confirmation_analysis_v3.py`](../reachy_stage3v/confirmation_analysis_v3.py): evaluation of the accepted holdout.
- [`audit.py`](../reachy_stage3v/audit.py), [`compliance.py`](../reachy_stage3v/compliance.py), and [`result_freeze_v3.py`](../reachy_stage3v/result_freeze_v3.py): compliance and integrity.
- [`camera_health.py`](../reachy_stage3v/camera_health.py), [`live_inputs.py`](../reachy_stage3v/live_inputs.py), [`sampler.py`](../reachy_stage3v/sampler.py), and [`recorder.py`](../reachy_stage3v/recorder.py): collection support.

Earlier unsuffixed/V2/V3 files are preserved development history. Review focus: whether policy changes were fully separated from fresh evaluation and whether rejection criteria could introduce selection bias.

### `reachy_stage3p/`: association-gated cue boundary

- [`association_gated_cue.py`](../reachy_stage3p/association_gated_cue.py): cue/association state transition.
- [`cue_confirmation.py`](../reachy_stage3p/cue_confirmation.py) and [`cue_confirmation_protocol.py`](../reachy_stage3p/cue_confirmation_protocol.py): targeted cue experiment.
- [`policy_v6.py`](../reachy_stage3p/policy_v6.py), [`policy_v6_freeze.py`](../reachy_stage3p/policy_v6_freeze.py), [`analysis_v6.py`](../reachy_stage3p/analysis_v6.py), and [`result_freeze_v6.py`](../reachy_stage3p/result_freeze_v6.py): final frozen vertical association-repair generation feeding the cue study.
- `policy_v2.py` through `policy_v7.py`, corresponding analyses, confirmations, protocols, and freeze modules: preserved development trail.

Review focus: the high number of versions, researcher degrees of freedom, whether every version boundary is auditable, whether passive visual cueing is useful without being mislabeled authorization, and whether controls cover replay and spoofing threats.

### `reachy_stage4/`: narrow command boundary

- [`config.py`](../reachy_stage4/config.py): fixed host, versions, timing, pose bounds, and acceptance thresholds for V4.
- [`safety.py`](../reachy_stage4/safety.py): host/direction validation, relative targets, rigid-pose projection, and rotation/translation distance.
- [`runtime.py`](../reachy_stage4/runtime.py): protocol-compatible robot adapter.
- [`protocol.py`](../reachy_stage4/protocol.py): fingerprinted V4 protocol and explicit prohibited commands.
- [`pilot.py`](../reachy_stage4/pilot.py): read-only preflight, expiring signed session, one-shot execution, automatic restore, result integrity, and operator disposition.
- [`result_freeze_v3.py`](../reachy_stage4/result_freeze_v3.py): verification of the preserved failed V3 result and robust diagnostic reconstruction.
- [`neutral_diagnostic.py`](../reachy_stage4/neutral_diagnostic.py): command-free comparison of matrix, Euler, stream, joint, and daemon-status state.
- [`startup_characterization.py`](../reachy_stage4/startup_characterization.py): checksum-verified private aggregation of controlled physical power-cycle captures; no network or robot transport.
- [`centering_plan.py`](../reachy_stage4/centering_plan.py): zero-authority counterfactual record of the rejected centring design; it is not a hardware procedure.
- [`successor_review.py`](../reachy_stage4/successor_review.py): pure, separately versioned assessment of a possible baseline-relative successor; it imports no transport, accepts no boolean-only review claims, and always authorizes zero commands.
- [`successor_trace.py`](../reachy_stage4/successor_trace.py): bounded full-state receive-only recorder; it has no application `send` or command route and fails closed without real target fields.
- [`trajectory_review.py`](../reachy_stage4/trajectory_review.py): pure 1.9.0 minimum-jerk/yaw-scalar path reconstruction and injected IK margin analysis.
- [`split_authorization.py`](../reachy_stage4/split_authorization.py): pure successor transition system; target authorization cannot authorize return, and failure never enters a software-return state.
- [`external_records.py`](../reachy_stage4/external_records.py): byte-verifies preserved owner/reviewer replies before their structured records can count.

Review focus: whether the custom transport matches official semantics, atomic one-shot behavior, recovery if the target command succeeds but return fails, exception handling, telemetry freshness, coordinate frames, preflight/execute race conditions, and whether a software governor should be called runtime assurance without formal safety guarantees.

### Verification and tests

- [`scripts/verify_results.py`](../scripts/verify_results.py): maps original manifest paths into the public `evidence/` layout, verifies hashes, and checks headline frozen assertions.
- [`scripts/regenerate_public_results.py`](../scripts/regenerate_public_results.py): verifies those sources and reconstructs the committed headline table from frozen machine-readable artifacts.
- [`scripts/validate_successor_trajectory_v190.py`](../scripts/validate_successor_trajectory_v190.py): exact-wheel/source cross-check and offline analytical-IK/configured-margin report; imports no networking stack or command method.
- [`scripts/capture_successor_present_target_trace.py`](../scripts/capture_successor_present_target_trace.py): owner-record-gated receive-only capture entry point; not run on the robot.
- [`scripts/build_successor_review_manifest.py`](../scripts/build_successor_review_manifest.py): deterministic content manifest for the full successor review packet; CI rejects stale hashes.
- [`tests/`](../tests): 213 self-contained unit tests covering numeric logic, policy state, transport mocks, camera lifecycle, recorders, audits, progress state, and Stage 4 protocol/transport safety.
- [`.github/workflows/ci.yml`](../.github/workflows/ci.yml): installs the test extra, runs evidence verification, rejects a stale generated result table, and runs the unit suite on Python 3.11.

Review focus: absent coverage measurement, absent static type/lint checks, dependency reproducibility, missing property/fuzz tests at safety boundaries, and the distinction between unit verification and robot validation.

## What was done well

1. **The negative result changes the question.** The silent-face/phone condition falsified a convenient assumption instead of being hidden as noise.
2. **Abstention is first class.** The code and evaluation allow no-target outcomes rather than forcing a direction.
3. **Hard negatives are explicit.** Silence, no face, spatial mismatch, visibility without centering, and no-cue conditions are represented.
4. **Policy and result freezes are unusually visible for a solo prototype.** Hashes, fingerprints, accepted/superseded state, and immutable failures make post-hoc editing harder.
5. **Passive and physical authority are separated.** Passive success cannot silently enable motion.
6. **The physical failure was preserved.** Thresholds remained unchanged, and the failure was reconstructed with better geometry instead of relabelled.
7. **Data minimization is concrete.** The public evidence excludes media and identity features while retaining numeric auditability.
8. **Safety boundaries exist in code.** Read-only preflight, expiring sessions, one-shot locks, exact direction checks, and bounded relative poses are meaningful engineering controls. The successor also treats return as a separately authorized action rather than assuming an automatic return is always safe.
9. **Claims are cautious.** The repository explicitly rejects identity, intent, generalization, formal safety, and successful physical-validation claims.

## Mistakes, weaknesses, and risks

### Scientific and experimental

1. **The initial association concept was too strong.** Face/DoA geometry was treated as if it might ground a speaker, but it measures compatibility, not ownership. The hard negative exposed this.
2. **The Stage 2A split is retrospective.** The full matrix was seen before development/evaluation assignment, so the evaluation repetition is not a blind holdout.
3. **Rows are correlated.** Dozens of observations inside one short trial do not provide dozens of independent samples. Headline fractions need trial-level uncertainty and hierarchical treatment.
4. **The sample is extremely narrow.** One robot, room, operator, camera placement, microphone geometry, and limited playback stimuli cannot support generalization.
5. **There is no independent evaluator.** The same research process developed policies, accepted trials, diagnosed failures, and wrote the report.
6. **Repeated versioning creates researcher degrees of freedom.** Preservation is better than deletion, but V1–V7 progression can still overfit the local setup. A preregistered independent dataset is necessary.
7. **Controls are incomplete.** Overlapping live speech, room reverberation changes, moving talkers, off-screen speech, multiple visible faces, occlusion, adversarial playback, interruptions, and sensor dropout need systematic testing.
8. **The cue and arming boundaries are narrow.** Stage 3P is a system-issued visual instruction after compatibility, not phrase recognition or authorization. Stage 4's typed arm is local operator confirmation, not consent, speaker intent, conversational turn-taking, or social permission.
9. **No meaningful eye-contact claim exists.** Head orientation is not eye contact; that would require face/eye targeting, temporal behavior, human perception measures, and multiple consenting participants.
10. **The prior-art review is scoped, not systematic.** It now anchors the main boundaries in primary sources across robot audition, active-speaker detection, selective prediction, runtime assurance, and social gaze, but it is not a systematic review and does not establish novelty by itself.
11. **Several thresholds remain calibration debt.** The public provenance table reveals which values came from disclosed development searches and which were simply fixed; many detector, timing, stability, and pilot-safety values still lack sensitivity analysis.

### Mechanical and safety engineering

1. **The first physical protocol had measurement and geometry defects.** Early sampling, no restore dwell, non-orthonormal rotation input, and absolute-neutral targeting invalidated the intended 3° test.
2. **Controller zero was not measured state; the controlled post-wake residual is repeatable but unexplained.** Source inspection and live traces showed that desktop app v0.9.34 stores a matrix pose while its controller sync reads named pose fields and substitutes zero. Three controlled starts later settled at mean rotations of 2.529°, 2.752°, and 2.746°, with enabled motors and zero reported loop errors. Daemon 1.9.0's released response also drops requested target head fields. This correctly blocks V4 against its frozen project gate, but it does not prove a hardware fault; the custom centring proposal was rejected pending gate/target/maintenance review.
3. **Only one physical motion trial exists.** It failed. There is no estimate of repeatability, direction-dependent performance, or safe long-duration behavior.
4. **No single failure response is established as universally safe.** Exceptions, connection loss, daemon failure, motor stalls, or process termination can defeat a software return path; commanding return from an unknown state may add risk, while normal shutdown can initiate sleep motion and hard power removal can permit mechanical movement. The revised design enters `ABORT_NO_AUTOMATIC_RETURN` and classifies the failure without authorizing a response; a Reachy-specific procedure is still missing.
5. **The governor is not formal assurance.** Hashes and checks support auditability, not proof of safety, worst-case timing, or fault containment.

### Software and reproducibility

1. **The public layout is not a turnkey full replay environment.** Public artifacts are under `evidence/`, while preserved modules refer to the original `data/...` laboratory layout. A new command reconstructs and checks the public headline table, but the original policy searches and complete historical analysis pipeline are not directly rerunnable.
2. **The repository is an audit snapshot more than a library.** Forty version-suffixed source files are historically valuable but difficult to navigate, compare, or maintain.
3. **There is no stable command-line interface.** Reviewers must infer entry points from modules and documents.
4. **Dependencies are lower-bounded, not fully locked.** A future installation may resolve different transitive versions.
5. **CI lacks coverage, type checking, linting, and security scanning.** Passing 227 tests says nothing about unexecuted branches.
6. **Hardware and media transport are mock-tested, not publicly integration-tested.** The public suite intentionally has no robot, camera, microphone, or private launcher.
7. **No environment or hardware bill of materials is complete enough for exact independent replication.** Robot/daemon version is fixed, but room geometry, audio firmware/configuration, camera parameters, operating-system details, and timing conditions need a formal reproducibility appendix.
8. **The initial GitHub CI failed because `aiortc` was missing from test dependencies.** This was corrected, and the subsequent workflow passed, but it shows release verification did not initially match CI installation.
9. **The dependency range already exposed API drift.** An earlier isolated Python 3.12 verification passed the then-current 162 tests, but `websockets` 17.1 emitted a deprecation warning for direct `connect()` use in the transport path. That historical run has not been repeated for the current 213-test suite. Lower bounds without a lock or upper compatibility policy make this likely to recur.

### GitHub presentation

Strengths:

- the central question is clear and memorable;
- the failed physical result is visible near the top;
- architecture and safety/coverage figures communicate the design quickly;
- evidence, methods, limitations, data card, licensing, attribution, and CI are present;
- the repository can support a serious technical discussion rather than only a demo video.

Remaining weaknesses:

- the quantity of files can overwhelm a reviewer;
- the version history is not summarized as a single decision log or diagram;
- there is no tagged research-preview release or archival DOI;
- the headline table is now deterministic, but there is still no public workflow that regenerates every historical table and figure from `evidence/`;
- no issue templates guide external protocol, safety, or reproducibility criticism;
- the repository is not yet a polished package that another Reachy owner can run end to end;
- the visual presentation may still appear more mature than the empirical sample unless readers notice the claim boundary.

## Assessment against the intended goals

| Goal | Current assessment |
|---|---|
| Produce something technically interesting to experienced robotics people | **Promising.** The hard-negative result, permission framing, and preserved physical failure are discussion-worthy. |
| Demonstrate something historically unprecedented | **Not established.** The ingredients are known; novelty of the composition requires deeper literature review and independent judgment. |
| Impress robotics companies/startups | **Potentially, if framed honestly.** The strongest signal is disciplined failure handling and safety-oriented system decomposition, not model performance. |
| Produce profound research | **Early-stage.** The question is strong, but the evidence is too narrow for a profound empirical claim. |
| Publish an expert-facing GitHub research preview | **Achieved with caveats.** The repository is public, documented, verified, and now explicitly review-oriented. |
| Make Reachy turn toward the current speaker | **Not achieved.** Passive targets exist; live policy-to-motor integration has not been validated. |
| Maintain socially meaningful eye contact | **Not implemented or evaluated.** Head orientation alone is insufficient. |
| Support incorporation by others | **Partially achieved.** Code and evidence are public, but end-to-end replay and hardware reproducibility remain incomplete. |

The most credible current message is:

> We built and audited a staged permission boundary for robot attention, found that spatial audio/visual agreement does not prove speaker ownership, passed two narrow passive protocols, and preserved a failed physical pilot. We are asking experts to challenge the design before broader data collection or further actuation.

## Roadmap and scheduling boundary

The work is dependency-gated, so calendar promises would currently be misleading. The display bug has a reproducible command-free explanation, and three controlled starts show a repeatable 2.529–2.752° mean post-wake residual under one setup. Whether it reflects ordinary endpoint accuracy relative to an overly conservative project gate, a retained target, tracking error, model/unit geometry, or mechanical load remains unresolved. No V4 or end-to-end date should be quoted until independent gate/target/maintenance review and a newly frozen physical protocol.

| Work package | Dependency | Completion criterion | Schedulable now? |
|---|---|---|---|
| External review and issue triage | Reviewers willing to engage | Critiques logged and classified as claim, method, code, safety, or presentation issues. | Yes; reviewer response time remains external. |
| Headline result regeneration | None | One command reconstructs the committed public table and CI rejects drift. | **Complete.** |
| Full historical replay refactor | None | Public-layout commands rerun the relevant policy searches and regenerate all public tables/figures. | Yes, but effort is not yet estimated from a completed dependency audit. |
| Reproducibility hardening | Replay refactor | Locked environment, coverage report, type/lint checks, and hardware/configuration appendix. | Partly; should be divided into reviewable changes. |
| Read-only neutral diagnosis | Complete | Matrix, Euler, stream, joint state, desktop data flow, and daemon readiness reporting inspected without commands. | **Completed 2026-09-01.** |
| Exact nominal trajectory and configured-limit review | Exact 1.9.0 environment and controlled baseline capture | Official path cross-check and per-sample analytical IK/configured margins for four target/return pairs. | **Offline component complete 2026-09-02; not a physical-safety pass.** |
| Owner scope and independent protocol review | Owner and suitable human reviewer respond | Byte-preserved limited owner scope plus an independent verdict on the complete successor. | Temporary-daemon/restore scope is privately recorded; motion scope and the independent response remain external. |
| Live present/target trace | Owner/reviewer approve observational patch and restart | Bounded command-free trace preserves simultaneous present/target pose, joints, body yaw, status, and timing. | No; recorder code exists but patch is uninstalled. |
| Gate, target, and maintenance review | Controlled command-free starts, static visual inspection, and offline nominal path are complete | Reviewer accepts either the frozen 1° V4 criterion or a separately versioned successor; target state is observable; physical/collision/fault assumptions are resolved; invasive inspection is symptom-led and owner-approved. | Partly; external review and any hardware resolution time are unknown. |
| V4 four-direction mechanical pilot | Neutral issue resolved | Four separately armed directions pass unchanged target/return gates, or failures are frozen. | No. |
| Passive-to-live integration prototype | Mechanical pilot passes and a new protocol is frozen | A bounded passive candidate reaches a separately armed governor under an end-to-end test. | No. |
| Solo multi-room recorded-voice benchmark | Consented recordings, rooms, preregistration, and baseline implementation | Voice- and room-held-out evaluation with trial-level uncertainty and baselines. | Design can begin; collection duration should be estimated only after a pilot. |
| Live multi-speaker HRI and eye-contact study | Additional people, consent, and appropriate protocol/ethics review | Multiple live participants, randomized conditions, behavioral measures, and independent analysis. | Not feasible under the current solo constraint. |

A credible live multi-person eye-contact claim cannot be scheduled under the present single-operator constraint.

## What should happen next

1. Ask reviewers to attack the claim boundary before adding functionality.
2. Convert criticism into public GitHub issues or a review ledger.
3. Extend the now-reproducible headline table into full public policy-search and figure replay before collecting more data.
4. Freeze a preregistered recorded-voice, multi-room protocol with room- and voice-level holdouts.
5. Send the itemized owner request and complete successor packet to distinct human reviewers; preserve their actual responses rather than converting silence or informal encouragement into approval.
6. If both gates approve the observational change, collect one command-free present/target trace, power down, and review it before designing any executor.
7. Keep the custom centring proposal rejected and V4 frozen. Only a newly frozen successor may later run one separately authorized direction; target and return must remain different decisions.
8. Treat live speaker following and eye contact as later studies requiring additional people, not as a final feature toggle.

## Suggested review sequence

For a 30-minute review:

1. read the top-level [`README`](../README.md);
2. inspect [`RESULTS.md`](RESULTS.md) and [`FAILURE_LEDGER.md`](FAILURE_LEDGER.md);
3. run `python scripts/verify_results.py`;
4. inspect [`reachy_stage2a/fusion.py`](../reachy_stage2a/fusion.py), [`reachy_stage3p/association_gated_cue.py`](../reachy_stage3p/association_gated_cue.py), and [`reachy_stage4/pilot.py`](../reachy_stage4/pilot.py);
5. answer one of the prompts in [`REVIEW_PROMPTS.md`](REVIEW_PROMPTS.md).

For a deep review, additionally inspect the manifests, accepted/rejected accounting, protocol version transitions, test suite, current official Reachy Mini transport semantics, and the prior-art boundary.
