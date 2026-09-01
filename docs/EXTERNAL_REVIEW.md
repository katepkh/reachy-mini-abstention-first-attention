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
- The corrected V4 physical path is currently blocked because the controller can display zero while the daemon reports the head more than the frozen 1° neutral tolerance from its own reference.

These constraints matter. Recorded voices can test acoustic variability and playback hard negatives, but they cannot substitute for a live multi-person HRI study, independent operation, or socially meaningful eye-contact evaluation.

## Goal and evolution of the research question

The longer-term product-like ambition is understandable: when someone speaks, Reachy should orient toward that person and sustain socially appropriate attention. That behavior is not new in broad form, and the official Reachy Mini repository already contains a DoA-driven example that commands the head toward speech.

The stronger current research question is narrower and more defensible:

> How can a social robot combine weak acoustic and visual evidence so that movement occurs only after target compatibility, explicit authorization, and mechanical readiness have passed independently inspectable gates?

This changes the project from a speaker-following demonstration into a study of selective action. It asks when the robot should refuse to move, not merely whether it can produce a plausible target.

The intended architecture is:

```text
local numeric evidence
        |
        v
selective grounding ------> ABSTAIN / HOLD when unresolved
        |
        v
explicit operator cue ----> BLOCK when absent
        |
        v
mechanical governor ------> BLOCK when not ready or out of bounds
        |
        v
one bounded head command, or no motion
```

The work does not claim that selective prediction, DoA, face detection, active-speaker localization, runtime assurance, or explicit authorization is individually novel. The possible contribution is their auditable composition under data-minimizing constraints, combined with hard-negative experiments and preservation of failed physical results.

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

### Stage 3V: fresh passive vertical holdout

A revised passive policy was frozen before fresh collection. Eighteen accepted trials from 21 attempts covered positive headings at ±10° and ±20° plus hard negatives.

- 12/12 positive trials produced a passive proposal;
- 0 hard-negative would-move rows;
- 0 wrong-sign moves;
- maximum target error 2.647°;
- safety, direction, coverage, and accuracy gates passed.

This is stronger than the retrospective tournament because the policy was frozen before collection. It remains a small, single-site passive test.

### Stage 3P: explicit cue boundary

Nine accepted trials from 18 attempts included six associated vertical transitions and three no-cue controls. Superseded attempts were retained.

- all seven predefined cue/integrity/control/direction/bound/coverage gates passed;
- controls timed out fail-closed;
- 0 authorized control adjustments;
- 0 robot requests;
- 0 actuation commands;
- 0 cloud requests.

The fixed test phrase was a narrow laboratory arming primitive. It should not be presented as a deployment-ready model of consent or authorization.

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

No V4 physical result is published. Repeated read-only preflights remain blocked because daemon neutral and the controller's displayed zero do not agree inside the frozen tolerance. Motor discovery found 9/9 motors and the inspected motor configuration fields were reported as valid, which distinguishes bus/configuration health from coordinate-frame agreement but does not resolve the discrepancy.

## Public artifacts produced

### Documentation and presentation

- [`README.md`](../README.md): top-level question, current boundary, result table, claim limits, code map, reproduction commands, and review questions.
- [`RESEARCH_NOTE.md`](RESEARCH_NOTE.md): compact paper-style narrative.
- [`METHODS.md`](METHODS.md): staged experimental design.
- [`RESULTS.md`](RESULTS.md): frozen metrics and fingerprints.
- [`FAILURE_LEDGER.md`](FAILURE_LEDGER.md): preserved failures and responses.
- [`LIMITATIONS.md`](LIMITATIONS.md): supported and unsupported claims.
- [`DATA_CARD.md`](DATA_CARD.md): evidence contents, exclusions, privacy risks, and unsuitable uses.
- [`PRIOR_ART.md`](PRIOR_ART.md): initial positioning against Reachy, selective prediction, runtime assurance, and audiovisual localization.
- [`SAFETY.md`](../SAFETY.md): hardware boundary and stop conditions.
- [`DISCORD_MESSAGE.md`](../DISCORD_MESSAGE.md): expert-group introduction.
- [`figures/architecture.png`](../figures/architecture.png) and [`figures/safety-coverage-frontier.png`](../figures/safety-coverage-frontier.png): public explanatory figures.

### Evidence

The `evidence/` tree contains 187 tracked files. The public verifier checks 171 manifest-listed source files plus frozen headline assertions. It includes derived CSV/JSON rows, trial metadata, compliance records, aggregate reports, protocol/policy manifests, rejected or superseded attempts where retained, and Stage 4 diagnostic records.

It deliberately excludes raw audio, camera pixels, transcripts, face embeddings, identity labels, temporary encrypted audit clips and keys, credentials, and private laboratory paths.

### Software

At the time of this audit the repository contains:

- 110 source Python modules and 18,827 source lines;
- 28 Python test modules and 2,059 test lines;
- 40 explicitly versioned source modules preserving policy/protocol history;
- one public evidence-verification script;
- 142 passing self-contained software tests.

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

### `reachy_stage3v/`: fresh vertical confirmation

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

Review focus: the high number of versions, researcher degrees of freedom, whether every version boundary is auditable, whether the phrase is authorization or simply a test cue, and whether controls cover replay and spoofing threats.

### `reachy_stage4/`: narrow command boundary

- [`config.py`](../reachy_stage4/config.py): fixed host, versions, timing, pose bounds, and acceptance thresholds for V4.
- [`safety.py`](../reachy_stage4/safety.py): host/direction validation, relative targets, rigid-pose projection, and rotation/translation distance.
- [`runtime.py`](../reachy_stage4/runtime.py): protocol-compatible robot adapter.
- [`protocol.py`](../reachy_stage4/protocol.py): fingerprinted V4 protocol and explicit prohibited commands.
- [`pilot.py`](../reachy_stage4/pilot.py): read-only preflight, expiring signed session, one-shot execution, automatic restore, result integrity, and operator disposition.
- [`result_freeze_v3.py`](../reachy_stage4/result_freeze_v3.py): verification of the preserved failed V3 result and robust diagnostic reconstruction.

Review focus: whether the custom transport matches official semantics, atomic one-shot behavior, recovery if the target command succeeds but return fails, exception handling, telemetry freshness, coordinate frames, preflight/execute race conditions, and whether a software governor should be called runtime assurance without formal safety guarantees.

### Verification and tests

- [`scripts/verify_results.py`](../scripts/verify_results.py): maps original manifest paths into the public `evidence/` layout, verifies hashes, and checks headline frozen assertions.
- [`tests/`](../tests): 142 self-contained unit tests covering numeric logic, policy state, transport mocks, camera lifecycle, recorders, audits, progress state, and Stage 4 protocol/transport safety.
- [`.github/workflows/ci.yml`](../.github/workflows/ci.yml): installs the test extra, runs evidence verification, and runs the unit suite on Python 3.11.

Review focus: absent coverage measurement, absent static type/lint checks, dependency reproducibility, missing property/fuzz tests at safety boundaries, and the distinction between unit verification and robot validation.

## What was done well

1. **The negative result changes the question.** The silent-face/phone condition falsified a convenient assumption instead of being hidden as noise.
2. **Abstention is first class.** The code and evaluation allow no-target outcomes rather than forcing a direction.
3. **Hard negatives are explicit.** Silence, no face, spatial mismatch, visibility without centering, and no-cue conditions are represented.
4. **Policy and result freezes are unusually visible for a solo prototype.** Hashes, fingerprints, accepted/superseded state, and immutable failures make post-hoc editing harder.
5. **Passive and physical authority are separated.** Passive success cannot silently enable motion.
6. **The physical failure was preserved.** Thresholds remained unchanged, and the failure was reconstructed with better geometry instead of relabelled.
7. **Data minimization is concrete.** The public evidence excludes media and identity features while retaining numeric auditability.
8. **Safety boundaries exist in code.** Read-only preflight, expiring sessions, one-shot locks, exact direction checks, bounded relative poses, and automatic return are meaningful engineering controls.
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
8. **The authorization cue has weak ecological validity.** A fixed phrase in a laboratory is not equivalent to consent, speaker intent, conversational turn-taking, or social permission.
9. **No meaningful eye-contact claim exists.** Head orientation is not eye contact; that would require face/eye targeting, temporal behavior, human perception measures, and multiple consenting participants.
10. **The prior-art review is preliminary.** It establishes that the ingredients are not individually novel but does not yet constitute a systematic review of active-speaker detection, audiovisual localization, turn-taking, gaze control, selective prediction, or runtime assurance.

### Mechanical and safety engineering

1. **The first physical protocol had measurement and geometry defects.** Early sampling, no restore dwell, non-orthonormal rotation input, and absolute-neutral targeting invalidated the intended 3° test.
2. **Controller zero and daemon neutral disagree.** This unresolved coordinate-frame problem correctly blocks V4 but also shows that the software safety model depends on platform semantics not yet fully understood.
3. **Only one physical motion trial exists.** It failed. There is no estimate of repeatability, direction-dependent performance, or safe long-duration behavior.
4. **Automatic return is not guaranteed under all faults.** Exceptions, connection loss, daemon failure, motor stalls, or process termination can defeat a software return path.
5. **The governor is not formal assurance.** Hashes and checks support auditability, not proof of safety, worst-case timing, or fault containment.

### Software and reproducibility

1. **The public layout is not a turnkey replay environment.** Public artifacts are under `evidence/`, while preserved modules refer to the original `data/...` laboratory layout. The verifier compensates, but the complete analysis pipeline is not directly rerunnable.
2. **The repository is an audit snapshot more than a library.** Forty version-suffixed source files are historically valuable but difficult to navigate, compare, or maintain.
3. **There is no stable command-line interface.** Reviewers must infer entry points from modules and documents.
4. **Dependencies are lower-bounded, not fully locked.** A future installation may resolve different transitive versions.
5. **CI lacks coverage, type checking, linting, and security scanning.** Passing 142 tests says nothing about unexecuted branches.
6. **Hardware and media transport are mock-tested, not publicly integration-tested.** The public suite intentionally has no robot, camera, microphone, or private launcher.
7. **No environment or hardware bill of materials is complete enough for exact independent replication.** Robot/daemon version is fixed, but room geometry, audio firmware/configuration, camera parameters, operating-system details, and timing conditions need a formal reproducibility appendix.
8. **The initial GitHub CI failed because `aiortc` was missing from test dependencies.** This was corrected, and the subsequent workflow passed, but it shows release verification did not initially match CI installation.
9. **The current dependency range already exposes API drift.** The isolated Python 3.12 verification passed all 142 tests with current dependencies, but `websockets` 17.1 emitted a deprecation warning for direct `connect()` use in the transport path. Lower bounds without a lock or upper compatibility policy make this likely to recur.

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
- there is no public notebook/report that regenerates all tables and figures from `evidence/`;
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

## Realistic roadmap and timeline

These are effort ranges for one operator, not promises. Hardware faults, access to rooms, voice-recording consent, and reviewer availability can extend them.

| Work package | Dependency | Focused effort | Realistic elapsed time | Completion criterion |
|---|---|---:|---:|---|
| External review and issue triage | Reviewers willing to engage | 1–2 days of author work | 2–7 days | Critiques logged and classified as claim, method, code, safety, or presentation issues. |
| Public replay refactor | None | 2–4 days | 3–7 days | One command rebuilds public tables/figures from `evidence/`; CI tests it. |
| Reproducibility hardening | Replay refactor | 2–4 days | 3–7 days | Locked environment, coverage report, type/lint checks, hardware/configuration appendix. |
| Read-only neutral-coordinate diagnosis | Reachy consistently available | 1–3 days if software-only | 2–7 days; indeterminate if hardware/daemon support is needed | Controller and daemon frames agree reproducibly without bypassing the 1° gate. |
| V4 four-direction mechanical pilot | Neutral issue resolved | 0.5–1 day | 1–3 days | Four separately authorized directions pass unchanged target/return gates, or failures are frozen. |
| Passive-to-live integration prototype | Mechanical pilot passes | 3–5 days | 1–2 weeks | A newly frozen protocol connects only authorized, bounded policy output to the governor. |
| Solo multi-room recorded-voice benchmark | Consented recordings and at least three rooms | 7–12 days | 2–4 weeks | Preregistered voice- and room-held-out evaluation with trial-level uncertainty and baselines. |
| Strong expert-facing research report | New benchmark complete | 3–5 days | About 1 week | Updated figures, statistics, threat model, limitations, and reproducible report. |
| Live multi-speaker HRI and eye-contact study | Additional people, consent, protocol/ethics review | Not feasible solo | At least 6–12 weeks once collaborators exist | Multiple live participants, randomized conditions, behavioral measures, and independent analysis. |

Optimistic path to a stronger engineering milestone: approximately **2–3 weeks**, assuming the neutral-coordinate issue is software-only and recorded-voice collection proceeds smoothly.

Realistic path to a defensible multi-room research result: approximately **4–8 weeks**.

A credible live multi-person eye-contact claim cannot be scheduled under the present single-operator constraint.

## What should happen next

1. Ask reviewers to attack the claim boundary before adding functionality.
2. Convert criticism into public GitHub issues or a review ledger.
3. Make public analysis replayable from `evidence/` before collecting more data.
4. Freeze a preregistered recorded-voice, multi-room protocol with room- and voice-level holdouts.
5. Resolve the coordinate-frame disagreement read-only; do not widen the tolerance to make V4 pass.
6. Run V4 one direction at a time only after consistent preflight success.
7. Treat live speaker following and eye contact as later studies requiring additional people, not as a final feature toggle.

## Suggested review sequence

For a 30-minute review:

1. read the top-level [`README`](../README.md);
2. inspect [`RESULTS.md`](RESULTS.md) and [`FAILURE_LEDGER.md`](FAILURE_LEDGER.md);
3. run `python scripts/verify_results.py`;
4. inspect [`reachy_stage2a/fusion.py`](../reachy_stage2a/fusion.py), [`reachy_stage3p/association_gated_cue.py`](../reachy_stage3p/association_gated_cue.py), and [`reachy_stage4/pilot.py`](../reachy_stage4/pilot.py);
5. answer one of the prompts in [`REVIEW_PROMPTS.md`](REVIEW_PROMPTS.md).

For a deep review, additionally inspect the manifests, accepted/rejected accounting, protocol version transitions, test suite, current official Reachy Mini transport semantics, and the prior-art boundary.
