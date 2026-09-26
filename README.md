# Reachy Mini Abstention-First Attention

[![Evidence and tests](https://github.com/katepkh/reachy-mini-abstention-first-attention/actions/workflows/ci.yml/badge.svg)](https://github.com/katepkh/reachy-mini-abstention-first-attention/actions/workflows/ci.yml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](pyproject.toml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)

## Primary objective and current status

Build a real Reachy Mini interaction in which a live visible speaker causes one bounded orientation, face-directed attention, and an audible response, while a silent visible person beside phone playback causes no socially directed movement and no conversational response.

**That behaviour does not yet exist end to end.** The repository now contains one deterministic fused-shadow decision interface, a command-free joint recorder and commissioning analysis, and pure attention-hold/interaction shadow contracts, but no joint real spatial/synchrony capture has passed commissioning. It also contains valuable passive perception results, a promising but unconfirmed live-speech/playback instrument, extensive fail-closed motion work, and one preserved failed physical trial. It does not contain a command-capable integrated controller, physically validated attention hold, actual gated audio output, or successful end-to-end robot study.

The governing records are the [`project charter`](docs/PROJECT_CHARTER.md), [`milestone matrix`](docs/MILESTONE_MATRIX.md), [`decision log`](docs/DECISION_LOG.md), [`novelty and claims ledger`](docs/NOVELTY_CLAIMS_LEDGER.md), and [`strategy gate`](docs/STRATEGY_GATE.md). Read them before interpreting an intermediate artifact as the project objective.

The supporting research question remains: **when should a social robot refuse to look?** The system treats a false social or physical movement as more costly than abstention. Local direction of arrival (DoA), ephemeral face geometry, temporal agreement, operator interaction, and mechanical readiness remain separately inspectable until they can be deliberately integrated. Missing, stale, ambiguous, or conflicting evidence produces `ABSTAIN` or `HOLD`, not a guessed target.

## Current physical-motion protocol blocker

**Physical validation is suspended.** The first supervised 3° motion trial failed its unchanged mechanical gate. The corrected V4 path then failed read-only preflight because the daemon reported the head outside the unchanged 1° neutral gate.

- **Impact:** 0 of 4 V4 directions have been accepted; no V4 motion command has been sent.
- **Decision:** do not retroactively weaken or bypass the 1° neutral preflight gate. Diagnose the measured start pose and review whether a future protocol needs a different preregistered readiness criterion; 1° is a conservative project choice, not a vendor tolerance.
- **Diagnostic finding:** an initial pair of uncontrolled command-free observations found 4.159–4.221° and 1.333–1.459° from identity. A subsequent controlled three-power-cycle series measured means of 2.529°, 2.752°, and 2.746° (between-start range 0.223°); every complete trace remained outside 1°. All three captures reported motor control `enabled` before and after sampling, zero control-loop errors, and no daemon/backend error. Daemon 1.9.0 source confirms that identity is the intended final wake pose, while the controlled joint states show a repeatable residual dominated by Stewart 5 (−4.071° mean from rounded identity IK) and Stewart 6 (+3.078°). This establishes a repeatable non-identity start state for this unit under the narrow protocol, not its cause. Matrix REST, Euler REST, and the matrix state stream agreed within sampling drift. Desktop app v0.9.34 streams a matrix pose but its controller-sync hook reads object fields and substitutes zeros, so the widget's `0.000` values are a presentation defect rather than measured-pose evidence; see the [`read-only neutral-frame diagnostic`](docs/NEUTRAL_FRAME_DIAGNOSTIC.md), [`controlled startup characterization`](docs/STARTUP_CHARACTERIZATION.md), [`post-wake reference audit`](docs/POST_WAKE_REFERENCE_AUDIT.md), and [`maintenance triage`](docs/MAINTENANCE_TRIAGE.md).
- **Review verdict:** reject the custom centring proposal for hardware execution. Motor scan/configuration does not establish geometric calibration; daemon 1.9.0 drops requested target-state fields from its REST response; default analytical IK has no collision check; and the proposed bounds, path monitoring, and failure response are unvalidated. A four-field schema repair now applies cleanly to the released source and passes negative-control/positive-control tests through both extracted routes and complete isolated daemon application processes. The daemon-process result used the official 1.9.0 mockup backend, loopback-only socket enforcement, no media, no mDNS, and zero robot connections or commands. The patch remains uninstalled on the robot and does not establish the cause. The counterfactual planner and schema tests authorize zero commands; see the [`source-backed centring review`](docs/CENTERING_REVIEW.md) and [`target-state observability analysis`](docs/TARGET_STATE_OBSERVABILITY.md).
- **Successor work:** after two contained fail-closed rehearsals exposed a patch-staging error and a client deadline-handling error, a bounded powered observation on 2026-09-18 retained 193 simultaneous present/target frames over 10 seconds. Every target state was coherently `UNSET`; the trace client sent zero application messages and zero robot commands. The temporary process released its listener and serial resource, and exact stock v1.9.0 was restored healthy with motors disabled. Startup also proved to write configured PID gains, so only the trace client—not the controller lifecycle—is receive-only. A pure exact-v1.9.0 health gate and an offline-only lifecycle executor rehearse resource release, terminal branching, and rollback with no hardware adapter or command authority. Offline trajectory review still shows a 42.706° supplied configured-limit margin, but no defined-target transition, collision, load, tracking, or safety validation. External authorization remains outside this repository with no correspondence retained. No successor motion command has been sent, and the 3° executor remains blocked; see the [`trace status`](docs/RECEIVE_ONLY_SUCCESSOR_TRACE.md), [`temporary-daemon lifecycle review`](docs/TEMPORARY_DAEMON_LIFECYCLE.md), [`offline failure rehearsal`](docs/OFFLINE_FAILURE_REHEARSAL.md), [`trajectory review`](docs/SUCCESSOR_TRAJECTORY_REVIEW.md), and [`split authorization design`](docs/SPLIT_TARGET_RETURN_PROTOCOL.md).
- **Forecast:** unknown. There is no defensible completion date until the reference-frame mismatch is understood.

Passive validation passed only for the frozen single-site conditions below. It does not validate physical motion or erase the failed Stage 4 result.

> **Integration boundary:** Stage 3V validates horizontal passive proposals; Stage 3P validates a system-issued visual `MOVE` cue and has no command path; Stage 4 separately validates typed operator arming and mechanical readiness. These stages have **not** been connected and validated end to end.

![System architecture](figures/architecture.svg)

## Start here

| If you want to... | Read... |
|---|---|
| Recover the authoritative objective | [`docs/PROJECT_CHARTER.md`](docs/PROJECT_CHARTER.md) |
| See every capability gap and next experiment | [`docs/MILESTONE_MATRIX.md`](docs/MILESTONE_MATRIX.md) |
| Audit which decisions govern current work | [`docs/DECISION_LOG.md`](docs/DECISION_LOG.md) |
| Check what may and may not be claimed as novel | [`docs/NOVELTY_CLAIMS_LEDGER.md`](docs/NOVELTY_CLAIMS_LEDGER.md) |
| Gate the next substantial task | [`docs/STRATEGY_GATE.md`](docs/STRATEGY_GATE.md) |
| Inspect the M5 fused shadow interface and its exact claim boundary | [`docs/FUSED_SHADOW_CONTROLLER.md`](docs/FUSED_SHADOW_CONTROLLER.md) |
| Commission the M5 joint numeric recorder | [`docs/JOINT_SHADOW_INSTRUMENT.md`](docs/JOINT_SHADOW_INSTRUMENT.md) |
| Read the working evidence manuscript | [`docs/MANUSCRIPT.md`](docs/MANUSCRIPT.md) |
| Review the whole project critically | [`docs/EXTERNAL_REVIEW.md`](docs/EXTERNAL_REVIEW.md) |
| Reuse a rigorous review prompt | [`docs/REVIEW_PROMPTS.md`](docs/REVIEW_PROMPTS.md) |
| Read the compact paper-style account | [`docs/RESEARCH_NOTE.md`](docs/RESEARCH_NOTE.md) |
| Audit methods and frozen results | [`docs/METHODS.md`](docs/METHODS.md) and [`docs/RESULTS.md`](docs/RESULTS.md) |
| Check novelty and adjacent fields | [`docs/PRIOR_ART.md`](docs/PRIOR_ART.md) |
| Check trial units, uncertainty, and superseded attempts | [`docs/ATTEMPT_ACCOUNTING.md`](docs/ATTEMPT_ACCOUNTING.md) |
| Inspect trial-level uncertainty, sensitivity, and ablations | [`evidence/analysis/stage3v_trial_robustness_v1.md`](evidence/analysis/stage3v_trial_robustness_v1.md) |
| Review the next audio–mouth synchrony falsification study | [`docs/AV_SYNCHRONY_FALSIFICATION_PROTOCOL.md`](docs/AV_SYNCHRONY_FALSIFICATION_PROTOCOL.md) |
| Inspect the rejected V1 laptop-only instrument | [`docs/AV_SYNCHRONY_PILOT_GUIDE.md`](docs/AV_SYNCHRONY_PILOT_GUIDE.md) |
| Inspect why the first synchrony instrument was rejected | [`docs/AV_SYNCHRONY_PILOT_RESULT.md`](docs/AV_SYNCHRONY_PILOT_RESULT.md) |
| Inspect the completed V2 face-landmark pilot | [`docs/AV_SYNCHRONY_PILOT_V2_RESULT.md`](docs/AV_SYNCHRONY_PILOT_V2_RESULT.md) |
| Review the candidate-bound 54-trial confirmation | [`docs/AV_SYNCHRONY_CONFIRMATION_PROTOCOL.md`](docs/AV_SYNCHRONY_CONFIRMATION_PROTOCOL.md) |
| Rebuild the public result table | [`docs/GENERATED_RESULTS.md`](docs/GENERATED_RESULTS.md) and [`scripts/regenerate_public_results.py`](scripts/regenerate_public_results.py) |
| Rebuild every manuscript table and figure | [`scripts/build_paper_artifacts.py`](scripts/build_paper_artifacts.py) and [`docs/paper/generated/ARTIFACT_MANIFEST.json`](docs/paper/generated/ARTIFACT_MANIFEST.json) |
| Run the complete offline paper verification | [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md) and [`scripts/verify_paper_artifacts.py`](scripts/verify_paper_artifacts.py) |
| Audit where thresholds came from | [`docs/THRESHOLD_PROVENANCE.md`](docs/THRESHOLD_PROVENANCE.md) |
| Inspect what failed and why | [`docs/FAILURE_LEDGER.md`](docs/FAILURE_LEDGER.md) |
| Diagnose the controller/daemon neutral mismatch | [`docs/NEUTRAL_FRAME_DIAGNOSTIC.md`](docs/NEUTRAL_FRAME_DIAGNOSTIC.md) |
| Run the controlled command-free startup series | [`docs/STARTUP_CHARACTERIZATION.md`](docs/STARTUP_CHARACTERIZATION.md) |
| Check whether identity is the correct 1.9.0 wake reference | [`docs/POST_WAKE_REFERENCE_AUDIT.md`](docs/POST_WAKE_REFERENCE_AUDIT.md) |
| Audit the missing target telemetry | [`docs/TARGET_STATE_OBSERVABILITY.md`](docs/TARGET_STATE_OBSERVABILITY.md) |
| Review the evidence and safe maintenance branches | [`docs/MAINTENANCE_TRIAGE.md`](docs/MAINTENANCE_TRIAGE.md) |
| Inspect the non-executable baseline-relative successor | [`docs/BASELINE_RELATIVE_SUCCESSOR.md`](docs/BASELINE_RELATIVE_SUCCESSOR.md) |
| Audit the receive-only present/target recorder | [`docs/RECEIVE_ONLY_SUCCESSOR_TRACE.md`](docs/RECEIVE_ONLY_SUCCESSOR_TRACE.md) |
| Review the temporary-daemon lifecycle and no-reflash patch | [`docs/TEMPORARY_DAEMON_LIFECYCLE.md`](docs/TEMPORARY_DAEMON_LIFECYCLE.md) |
| Inspect the offline mock-process fault rehearsal | [`docs/OFFLINE_FAILURE_REHEARSAL.md`](docs/OFFLINE_FAILURE_REHEARSAL.md) |
| Review exact 1.9.0 trajectory and joint margins | [`docs/SUCCESSOR_TRAJECTORY_REVIEW.md`](docs/SUCCESSOR_TRAJECTORY_REVIEW.md) |
| Review separately authorized target and return legs | [`docs/SPLIT_TARGET_RETURN_PROTOCOL.md`](docs/SPLIT_TARGET_RETURN_PROTOCOL.md) |
| Audit restoration of the borrowed robot | [`docs/RETURN_TO_BORROWED_CONDITION.md`](docs/RETURN_TO_BORROWED_CONDITION.md) |
| Verify the exact successor review packet | [`docs/SUCCESSOR_REVIEW_MANIFEST.json`](docs/SUCCESSOR_REVIEW_MANIFEST.json) and [`scripts/build_successor_review_manifest.py`](scripts/build_successor_review_manifest.py) |
| Read the hardware verdict on custom centring | [`docs/CENTERING_REVIEW.md`](docs/CENTERING_REVIEW.md) |
| Audit the rejected counterfactual centring proposal | [`docs/CENTERING_PROTOCOL_DRAFT.md`](docs/CENTERING_PROTOCOL_DRAFT.md) |
| Check claim boundaries and data contents | [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) and [`docs/DATA_CARD.md`](docs/DATA_CARD.md) |

## Supporting research question

The official Reachy Mini ecosystem already demonstrates how to read DoA and command the robot to look toward sound in its [`sound_doa.py`](https://github.com/pollen-robotics/reachy_mini/blob/main/examples/sound_doa.py) example. This project begins at the unresolved permission boundary:

> How can weak acoustic and visual evidence justify a candidate for attention without being mistaken for speaker identity, human authorization, or mechanical readiness?

The intended architecture separates three decisions, but the public experiments validate them separately:

```text
observation -> {candidate, abstain}
stable centred compatibility -> {visual operator instruction, timeout}
typed operator arm + mechanical readiness -> {bounded command, block}
```

Stage 3P does not recognize the spoken test phrase: it receives no transcript and emits only a visual instruction after stable compatibility. Stage 4's exact typed phrase is one-shot arming friction, not identity, consent, intent, or conversational authorization. The intended contribution is not a historically first speaker-following demo. It is an auditable research composition of selective prediction, hard-negative testing, data minimization, policy freezing, passive cueing, operator arming, and a narrow experimental motion governor.

## What was tested

| Stage | Experimental question | Frozen result |
|---|---|---|
| 2A — passive fusion matrix | Does visible-face geometry agree with the acoustic axis? | 15 accepted trials and 815 correlated numeric observations. Alignment improved availability but did not establish source ownership. |
| 2A — retrospective tournament | What coverage is lost when temporal consensus becomes stricter? | Development-selected 3-hit policy produced 0/37 hard-negative confirmations but only 2/31 matching confirmations on the retrospective evaluation repetition. |
| 3V — fresh horizontal off-axis holdout | Does the frozen shadow policy choose the correct left/right direction and a bounded passive yaw target? | 18 accepted trials from 21 attempts; all four gates passed; 12/12 positive trials proposed movement; 0/6 hard-negative trials contained a would-move row; maximum target error 2.647°. |
| 3V — post-hoc robustness replay | How uncertain are the trial fractions, and which components matter on the saved holdout? | Nominal 95% Wilson intervals: 75.8%–100% positive coverage and 0%–39.0% hard-negative false-proposal rate. One-hit audio/visual replay proposed in 2/6 negatives; vision-only in 6/6; audio-only front hypothesis in 4/6. Exploratory, not a second holdout. |
| 3P — association-gated visual cue | Does stable centred compatibility trigger one visual instruction while no-cue controls time out? | 9 accepted trials from 18 attempts; seven gates passed; 6 vertical transitions and 3 fail-closed controls; 0 robot, actuation, or cloud requests. |
| AV synchrony development pilot | Can local microphone energy and fixed-box mouth-region pixel change separate matched live speech from playback hard negatives? | **Instrument rejected.** Twelve laptop-only trials from 13 captures; 0/240 frozen settings met the selection rule. No robot connection or command. |
| AV synchrony V2 pilot | Can tracked, face-normalized lip aperture separate matching speech from colocated-playback hard negatives in one setup? | **Pilot candidate frozen; not confirmation.** Twelve canonical trials from 23 attempts passed every quality gate. The selected setting produced candidates for 4/4 development and 2/2 internal-validation positives, and 0/4 plus 0/2 hard negatives. Zero robot connections or commands. |
| M5 fused shadow contract | Does one deterministic interface fail closed across supported, pending, conflicting, stale, mismatched, unavailable, and unhealthy synthetic evidence? | **Software prototype only.** Ten deterministic cases pass with `SELECT`, `HOLD`, or `ABSTAIN`; zero motion/response authority or commands. No joint real input has been tested. |
| 4A V3 — supervised mechanical pilot | Does one bounded 3° head-only command execute and return inside tolerance? | **Failed.** One physical trial and two head-only commands; measured motion 1.350°, target error 2.079°, return error 1.678°. |
| 4A V4 — corrected mechanical path | Can the diagnosed V3 defects be corrected without retroactively changing its thresholds? | No V4 physical trial has run. A controlled three-start, zero-command series found a repeatable 2.529–2.752° mean start offset; all traces failed the unchanged 1° project gate. A later 193-frame observation found the retained target coherently `UNSET`, but did not validate motion or return. Custom centring remains rejected. |

These are small, correlated, single-site experiments: 42 accepted robot-side passive trials across Stages 2A, 3V, and 3P; one rejected and one candidate-nominating 12-trial laptop-only development instrument; and one failed physical trial. Observation-row denominators are telemetry summaries, not participant counts or independent samples. Zero events in six Stage 3V hard-negative trials or three Stage 3P controls do not establish a near-zero population error rate; see [`ATTEMPT_ACCOUNTING.md`](docs/ATTEMPT_ACCOUNTING.md).

The new trial-level replay makes that limitation numerical: 0/6 hard-negative trial proposals still has a nominal 95% Wilson upper bound of 39.0%. Its baselines and threshold sweeps were chosen after the data were known, so they diagnose fragility but do not upgrade the original claim.

## Central finding

Acoustic/visual alignment is useful **compatibility evidence**, but it is not proof that the visible person owns the sound:

- matching visible face + speech confirmed 62/71 tracked rows (87.3%);
- speech with no face confirmed 0/35 tracked rows;
- a silent visible face plus spatially separate phone speech still confirmed 13/63 tracked rows (20.6%);
- a visible silent face was present during all 13 compatibility confirmations in that hard-negative condition.

This falsified assumption is more important than the positive coverage number. It motivated stricter temporal consensus, explicit `ABSTAIN`, no-cue controls, and an independent mechanical readiness gate.

## What the repository demonstrates—and what it does not

| Supported by the public record | Not established |
|---|---|
| A local pipeline can represent abstention, passive cueing, and a separate one-shot mechanical gate. | An integrated candidate-to-command attention system. |
| Frozen numeric artifacts reproduce the reported passive results. | Generalization beyond one robot, room, and primary operator. |
| Hard negatives can reveal false associations hidden by positive demos. | A multi-person participant study or socially valid eye-contact behavior. |
| Passive policy success does not silently authorize hardware. | Certified functional safety or formal verification. |
| The failed motion result was preserved without relaxed thresholds. | Successful physical speaker following or autonomous actuation. |
| The M5 software contract deterministically fuses same-clock spatial and synchrony evidence with no side-effect authority. | Real phone-playback rejection, liveness, speaker identity, motion, or response. |

The strongest current artifacts are the **permission architecture, preserved hard-negative evidence, and failure-preservation process**. They support the primary objective but do not substitute for the absent integrated robot behaviour.

## Code and evidence map

The working repository contains 142 package modules (24,848 lines), 58 test modules, public verification/diagnostic scripts, and frozen numeric artifacts. Counts describe implementation volume, not research success. Versioned files preserve rejected and superseded protocol generations rather than presenting every generation as an active alternative.

| Path | Responsibility | Review note |
|---|---|---|
| [`reachy_doa/`](reachy_doa) | Read-only DoA client, angle handling, confidence windows, offline policies, manifests, replay, and source-validity analysis. | The network client exposes GET-only access to an allowlisted private IPv4 endpoint. |
| [`reachy_stage2a/`](reachy_stage2a) | Local face detection, camera lifecycle, audio/visual fusion, trial protocol, recording, and policy tournament. | Face geometry is an availability signal, not identity or active-speaker proof. |
| [`reachy_stage3a/`](reachy_stage3a) | Passive motion-shadow controller and evaluation. | It computes counterfactual targets and has no hardware authority. |
| [`reachy_stage3v/`](reachy_stage3v) | Fresh horizontal off-axis passive validation, the M5 fused shadow interface, and a command-free joint recorder/commissioning analysis. | The fused interface and instrument have software checks and zero side-effect authority; no joint real spatial/synchrony capture has passed commissioning yet. |
| [`reachy_stage3p/`](reachy_stage3p) | Passive vertical targeting history plus association-gated visual-cue logic and result freezes. | The cue gate reads no transcript and has no command capability; V1–V7 are an audit trail, not a minimal reusable package. |
| [`reachy_stage4/`](reachy_stage4) | Frozen V4 history plus a receive-only trace client, exact offline trajectory review, exact-v1.9.0 health gate, offline-only lifecycle rehearsal, and split target/return design. | The only new executor accepts mock adapters and explicitly denies hardware authority; V4's automatic return remains frozen history. |
| [`reachy_avsync/`](reachy_avsync) | Command-free numeric audio–mouth synchrony prototypes, frozen pilot designs, offline analysis, complete-attempt audit, and candidate freeze. | V1 remains rejected. V2 nominated one content-frozen single-setup pilot candidate; confirmation remains absent. |
| [`scripts/verify_results.py`](scripts/verify_results.py) | Standard-library verifier for public hashes and headline frozen claims. | This is the public evidence entry point. |
| [`scripts/regenerate_public_results.py`](scripts/regenerate_public_results.py) | Deterministically renders the public headline table from frozen JSON after evidence verification. | It regenerates the committed summary, not the original acquisition or every historical policy search. |
| [`scripts/build_paper_artifacts.py`](scripts/build_paper_artifacts.py) | Regenerates all four manuscript tables and both SVG figures from seven hash-bound sources. | It verifies reporting artifacts; it does not rerun acquisition. |
| [`scripts/verify_paper_artifacts.py`](scripts/verify_paper_artifacts.py) | Runs the complete offline evidence, protocol, reporting, and software-test suite and checks a deterministic log. | It deliberately excludes live media and hardware validation. |
| [`scripts/validate_target_schema_endpoints.py`](scripts/validate_target_schema_endpoints.py) | Negative/positive integration test of the real 1.9.0 state routes extracted from the official wheel. | Uses a stub backend and sends no robot or network request. |
| [`scripts/validate_target_schema_daemon.py`](scripts/validate_target_schema_daemon.py) | Negative/positive complete-daemon test with the official 1.9.0 mockup backend. | Enforces loopback-only sockets and disables media, mDNS, startup apps, and dataset downloads; it is not an on-robot test. |
| [`scripts/validate_successor_trajectory_v190.py`](scripts/validate_successor_trajectory_v190.py) | Byte-verifies the exact 1.9.0 wheel/install, cross-checks the continuous `GotoMove` law, runs exact IK, and reports configured-limit margins. | Offline geometric review only; zero transport or commands. |
| [`scripts/capture_successor_present_target_trace.py`](scripts/capture_successor_present_target_trace.py) | Bounded receive-only present/target trace, gated by authorization artifacts supplied outside this repository. | A valid 193-frame live trace observed coherent `UNSET` targets throughout, with zero client application messages or robot commands; no defined-target or movement claim follows. |
| [`scripts/build_successor_review_manifest.py`](scripts/build_successor_review_manifest.py) | Builds/checks hashes for the complete proposed successor review packet. | Content addressability does not make the proposal approved. |
| [`scripts/run_offline_fault_rehearsal.py`](scripts/run_offline_fault_rehearsal.py) | Replays four fixed failure classes through isolated local Python mock processes. | Validates mock mutual exclusion and restoration gating, not real daemon, serial-bus, torque, or shutdown behavior. |
| [`scripts/run_stage3v_robustness.py`](scripts/run_stage3v_robustness.py) | Replays trial-level uncertainty, ablations, threshold sensitivity, and finite risk/coverage operating points. | Post-hoc diagnostic analysis; trial denominators remain small. |
| [`scripts/freeze_av_synchrony_protocol.py`](scripts/freeze_av_synchrony_protocol.py) and [`scripts/run_av_synchrony_faults.py`](scripts/run_av_synchrony_faults.py) | Check the frozen future study design and deterministic synthetic fault artifact. | Neither script captures media, contacts Reachy, or validates real audiovisual association. |
| [`tools/avsync_pilot_recorder.html`](tools/avsync_pilot_recorder.html) and [`scripts/analyze_av_synchrony_pilot.py`](scripts/analyze_av_synchrony_pilot.py) | Collect three local numeric columns in a browser and search the frozen 240-candidate development grid. | The fixed mouth box is confounded by head/lighting changes; selected pilot settings are not confirmation results. |
| [`tools/avsync_pilot_recorder_v2.html`](tools/avsync_pilot_recorder_v2.html), [`scripts/analyze_av_synchrony_pilot_v2.py`](scripts/analyze_av_synchrony_pilot_v2.py), and [`scripts/freeze_av_synchrony_pilot_v2_candidate.py`](scripts/freeze_av_synchrony_pilot_v2_candidate.py) | Record only local numeric audio level and tracked face features, search 45 settings on development, evaluate internal validation, and bind a passing candidate to exact code/assets/input hashes. | The V2 pilot passed and is frozen locally, but does not validate speaker ownership or the 54-trial confirmation study. |
| [`tests/`](tests) | Self-contained component and protocol tests. | 329 software tests are not 329 robot trials and do not validate hardware. |
| [`evidence/`](evidence) | Derived CSV/JSON evidence, analyses, compliance records, and freeze manifests. | No raw audio, camera pixels, transcripts, or identity labels are included. |

### Current reference path versus preserved history

The version suffixes document how the protocol changed; they do not mean that every version is an active alternative. For review and reuse, follow this map:

| Status | Reference files | Meaning |
|---|---|---|
| Current passive evidence | [`reachy_stage3v/revised_policy_v3.py`](reachy_stage3v/revised_policy_v3.py), [`reachy_stage3v/confirmation_analysis_v3.py`](reachy_stage3v/confirmation_analysis_v3.py), and the Stage 3V manifests under [`evidence/manifests/`](evidence/manifests) | Frozen horizontal off-axis policy and its fresh held-out evaluation. |
| Current fused shadow interface | [`reachy_stage3v/fused_shadow.py`](reachy_stage3v/fused_shadow.py), [`scripts/run_fused_shadow_contract.py`](scripts/run_fused_shadow_contract.py), and [`docs/FUSED_SHADOW_CONTROLLER.md`](docs/FUSED_SHADOW_CONTROLLER.md) | Deterministic `SELECT`/`HOLD`/`ABSTAIN` software boundary; synthetic only, visible-speaker-only, and no motion/response authority. |
| Joint-input commissioning | [`tools/joint_shadow_recorder.html`](tools/joint_shadow_recorder.html), [`scripts/run_joint_shadow_instrument.py`](scripts/run_joint_shadow_instrument.py), [`reachy_stage3v/joint_analysis.py`](reachy_stage3v/joint_analysis.py), and [`docs/JOINT_SHADOW_INSTRUMENT.md`](docs/JOINT_SHADOW_INSTRUMENT.md) | Joins GET-only DoA with local face/lip/audio features and explicit timing diagnostics; numeric-only, command-free, and not yet commissioned with real input. |
| Attention/interaction shadow | [`reachy_stage3v/attention_hold.py`](reachy_stage3v/attention_hold.py) and [`reachy_stage3v/interaction_shadow.py`](reachy_stage3v/interaction_shadow.py) | Pure replay/simulation contracts for bounded hold and ordered response permission; synthetic only, with zero motion or audio commands. |
| Current cue-boundary evidence | [`reachy_stage3p/association_gated_cue.py`](reachy_stage3p/association_gated_cue.py), [`reachy_stage3p/cue_confirmation.py`](reachy_stage3p/cue_confirmation.py), [`reachy_stage3p/cue_confirmation_protocol.py`](reachy_stage3p/cue_confirmation_protocol.py), and the Stage 3P manifests | Passive visual-instruction experiment; no transcript or robot command path. |
| Frozen command-capable candidate | [`reachy_stage4/protocol.py`](reachy_stage4/protocol.py), [`reachy_stage4/runtime.py`](reachy_stage4/runtime.py), [`reachy_stage4/pilot.py`](reachy_stage4/pilot.py), and [`reachy_stage4/safety.py`](reachy_stage4/safety.py) | Prepared but unvalidated V4 path; blocked pending independent gate/target/maintenance review. The custom centring proposal was rejected for hardware execution. |
| Design-only future successor | [`successor_review.py`](reachy_stage4/successor_review.py), [`successor_trace.py`](reachy_stage4/successor_trace.py), [`trajectory_review.py`](reachy_stage4/trajectory_review.py), [`split_authorization.py`](reachy_stage4/split_authorization.py), and [`docs/BASELINE_RELATIVE_SUCCESSOR.md`](docs/BASELINE_RELATIVE_SUCCESSOR.md) | Separately versioned post-V4 proposal. Offline trajectory reconstruction is complete; live target tracing and the external authorization gates remain outside the evidence package. It authorizes zero commands. |
| Future scientific study | [`reachy_avsync/confirmation_protocol.py`](reachy_avsync/confirmation_protocol.py), [`docs/AV_SYNCHRONY_CONFIRMATION_PROTOCOL.md`](docs/AV_SYNCHRONY_CONFIRMATION_PROTOCOL.md), and [`docs/AV_SYNCHRONY_PILOT_V2_RESULT.md`](docs/AV_SYNCHRONY_PILOT_V2_RESULT.md) | Candidate-bound 54-trial confirmation design attacking spatially matched playback. V2 nominated and froze the instrument in one setup; rooms, consented voices, devices, and fixed playback marks must be privately bound before collection. No confirmation result exists. |
| Preserved development history | Earlier Stage 3/4 versioned modules and their freeze artifacts | Audit trail of rejected, superseded, or failed designs. Do not treat these as the recommended API. |

There is now one fused candidate-decision interface, but no production candidate-to-motion/attention/response entry point. The sensing, physical action, hold, and response paths remain separate until end-to-end integration is designed and tested.

### What one command now rebuilds—and what it does not

The public evidence was reorganized under `evidence/`, while several preserved acquisition and freeze modules retain their original laboratory `data/...` paths. Consequently:

- `python scripts/verify_results.py` verifies the public frozen claims;
- `python scripts/regenerate_public_results.py --check` verifies all listed evidence, reconstructs the headline result table from frozen machine-readable artifacts, and compares it byte-for-byte with [`docs/GENERATED_RESULTS.md`](docs/GENERATED_RESULTS.md);
- the unit tests exercise curated software components without a robot or private laboratory tree;
- the repository still does **not** provide one command that reruns every historical policy search from the public layout, reproduces deleted encrypted audit clips, or reproduces live hardware acquisition end to end.

The new report closes the narrower “can a reviewer reconstruct the displayed headline table?” gap. It does not close full experimental reproducibility.

## Reproduce what is currently reproducible

Verify 171 manifest-listed evidence files and the headline results using only the Python standard library:

```bash
python scripts/verify_results.py
```

Regenerate the public result table to standard output, check the committed copy, or deliberately refresh it:

```bash
python scripts/regenerate_public_results.py
python scripts/regenerate_public_results.py --check
python scripts/regenerate_public_results.py --write
```

Check the new offline robustness analysis, future study design, and synthetic synchrony faults:

```bash
python scripts/run_stage3v_robustness.py --check
python scripts/freeze_av_synchrony_protocol.py --check
python scripts/run_av_synchrony_faults.py --check
python scripts/freeze_av_synchrony_pilot_protocol.py --check
python scripts/run_av_synchrony_pilot_dry_run.py --check
python scripts/freeze_av_synchrony_pilot_v2_protocol.py --check
python scripts/run_av_synchrony_pilot_v2_dry_run.py --check
python scripts/freeze_av_synchrony_confirmation_protocol.py --check
python scripts/build_paper_artifacts.py --check
```

Or verify the complete paper package and its committed log in one command from the frozen environment described in [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md):

```bash
.venv/Scripts/python scripts/verify_paper_artifacts.py --check
```

To run V2 locally, install and verify its pinned browser assets once with `python scripts/fetch_av_synchrony_v2_assets.py --install`; the large generated files are ignored by Git.

CI runs the integrity, stale-artifact, protocol, and synthetic-fault checks before the software tests.

Install the curated package and run 329 self-contained software tests:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-test.lock
.venv/Scripts/python -m pip install --no-deps -e .
.venv/Scripts/python -m unittest discover -s tests -p "test_*.py"
```

Live camera acquisition is optional and isolated:

```bash
python -m pip install -e ".[live]"
```

No robot command should be sent merely because evidence verification or unit tests pass. Read [`SAFETY.md`](SAFETY.md) before any hardware work.

## What review would be most useful

The project is deliberately asking for criticism before stronger claims or further actuation. The highest-value questions are:

1. Is the abstention/coverage frontier framed and measured correctly at the **trial** level?
2. Which hard negatives would most strongly challenge the inference from spatial compatibility to speaker ownership?
3. Is the Stage 3P system-issued visual instruction a useful experimental transition, and what evidence would be required before calling any later mechanism human authorization?
4. Does the motion governor actually isolate perception from actuation, or are there hidden shared assumptions and failure paths?
5. What is required for a genuinely independent, multi-room evaluation when one operator performs the robot-side experiments?
6. Which parts are established engineering practice, which are a useful composition, and which—if any—constitute a research contribution?

See the full [`external review packet`](docs/EXTERNAL_REVIEW.md) and [`role-specific prompts`](docs/REVIEW_PROMPTS.md).

## Roadmap

1. Keep all external authorization and review outside this repository. No correspondence or response artifact is part of the research package.
2. Treat the revised patch's extracted-route and complete mock-daemon validation plus the offline lifecycle rehearsal as software evidence only. Review the fact that backend construction writes PID gains; do not describe the controller lifecycle as command-free.
3. Treat the completed bounded observation as the end of the current observation-only stage. It established a coherent `UNSET` target and healthy restoration, not a defined target, movement, or return.
4. Keep successor motion blocked. A later protocol would need movement-specific abort thresholds, clearance/load evidence, and separately reviewed target and return legs. Do not revive or relabel V4.
5. Keep the successful V2 pilot candidate fixed, but pause the 54-trial collection before Trial 1. The current five-column recorder cannot identify the frozen Stage 3V spatial comparator or independent heading-error endpoints.
6. Resume confirmation only after either adding and validating acoustic-direction capture and refreezing the execution contract, or explicitly narrowing the study to synchrony-only exploratory claims.
7. Prioritize the critical path in [`docs/MILESTONE_MATRIX.md`](docs/MILESTONE_MATRIX.md): joint-input shadow instrumentation, phone-playback rejection, bounded physical orientation, face-directed hold, gated response, and end-to-end validation. Manuscript polishing and repository release remain downstream supporting work.

Detailed dependencies and realistic effort ranges are in [`docs/EXTERNAL_REVIEW.md`](docs/EXTERNAL_REVIEW.md#realistic-roadmap-and-timeline).

## Privacy, safety, citation, and licence

The public datasets retain derived measurements and state only—no camera pixels, raw audio, transcripts, or identity labels. This is data minimization, not formal anonymity; see [`docs/DATA_CARD.md`](docs/DATA_CARD.md).

The Stage 4 path is an operator-supervised research instrument, not a certified safety system. Never bypass a failed readiness check or weaken a threshold after observing an outcome.

See [`CITATION.cff`](CITATION.cff) for citation metadata. Code, documentation, and included derived evidence are Apache-2.0 unless a file states otherwise. The bundled YuNet model retains its upstream terms in [`models/README.md`](models/README.md).
