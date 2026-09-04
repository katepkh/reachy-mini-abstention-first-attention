# Reachy Mini Abstention-First Attention

[![Evidence and tests](https://github.com/katepkh/reachy-mini-abstention-first-attention/actions/workflows/ci.yml/badge.svg)](https://github.com/katepkh/reachy-mini-abstention-first-attention/actions/workflows/ci.yml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](pyproject.toml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)

**When should a social robot refuse to look?**

This research preview studies selective attention proposals for Reachy Mini under an asymmetric cost: a false social or physical movement is treated as more costly than abstention. Local direction of arrival (DoA), ephemeral face geometry, temporal agreement, a passive visual cue, operator arming, and mechanical readiness are treated as different boundaries. Missing, stale, ambiguous, or conflicting evidence produces `ABSTAIN` or `HOLD`, not a guessed target.

## Current physical-motion protocol blocker

**Physical validation is suspended.** The first supervised 3° motion trial failed its unchanged mechanical gate. The corrected V4 path then failed read-only preflight because the daemon reported the head outside the unchanged 1° neutral gate.

- **Impact:** 0 of 4 V4 directions have been accepted; no V4 motion command has been sent.
- **Decision:** do not retroactively weaken or bypass the 1° neutral preflight gate. Diagnose the measured start pose and review whether a future protocol needs a different preregistered readiness criterion; 1° is a conservative project choice, not a vendor tolerance.
- **Diagnostic finding:** an initial pair of uncontrolled command-free observations found 4.159–4.221° and 1.333–1.459° from identity. A subsequent controlled three-power-cycle series measured means of 2.529°, 2.752°, and 2.746° (between-start range 0.223°); every complete trace remained outside 1°. All three captures reported motor control `enabled` before and after sampling, zero control-loop errors, and no daemon/backend error. Daemon 1.9.0 source confirms that identity is the intended final wake pose, while the controlled joint states show a repeatable residual dominated by Stewart 5 (−4.071° mean from rounded identity IK) and Stewart 6 (+3.078°). This establishes a repeatable non-identity start state for this unit under the narrow protocol, not its cause. Matrix REST, Euler REST, and the matrix state stream agreed within sampling drift. Desktop app v0.9.34 streams a matrix pose but its controller-sync hook reads object fields and substitutes zeros, so the widget's `0.000` values are a presentation defect rather than measured-pose evidence; see the [`read-only neutral-frame diagnostic`](docs/NEUTRAL_FRAME_DIAGNOSTIC.md), [`controlled startup characterization`](docs/STARTUP_CHARACTERIZATION.md), [`post-wake reference audit`](docs/POST_WAKE_REFERENCE_AUDIT.md), and [`maintenance triage`](docs/MAINTENANCE_TRIAGE.md).
- **Review verdict:** reject the custom centring proposal for hardware execution. Motor scan/configuration does not establish geometric calibration; daemon 1.9.0 drops requested target-state fields from its REST response; default analytical IK has no collision check; and the proposed bounds, path monitoring, and failure response are unvalidated. A four-field schema repair now applies cleanly to the released source and passes negative-control/positive-control tests through both extracted routes and complete isolated daemon application processes. The daemon-process result used the official 1.9.0 mockup backend, loopback-only socket enforcement, no media, no mDNS, and zero robot connections or commands. The patch remains uninstalled on the robot and does not establish the cause. The counterfactual planner and schema tests authorize zero commands; see the [`source-backed centring review`](docs/CENTERING_REVIEW.md) and [`target-state observability analysis`](docs/TARGET_STATE_OBSERVABILITY.md).
- **Successor work:** a receive-only simultaneous present/target recorder now fails closed when target fields are absent. An offline validator reproduced the exact 1.9.0 `GotoMove` law and analytical IK for all four proposed 3° outward and nominal return paths; the smallest configured-limit margin was 42.706°, but this is not collision, load, tracking, or safety validation. Exact source review then found that Wireless startup may modify system surfaces, daemon startup offers no public reflash opt-out, controller construction may conditionally reboot a faulty motor, and graceful close does not itself disable torque. A separate lifecycle patch and non-executing loopback-only invocation plan now address the avoidable startup side effects. Four local mock-process fault scenarios pass duplicate-start and restoration-interlock checks, but do not prove real torque or serial-bus behavior. Failure no longer maps blindly to “power down”: it enters a conditional, design-only matrix with no automatic return. The owner confirmed the limited temporary-daemon, restore-and-verify request; the exact exchange is preserved in a hash-verified private record. No approval for a 3° target/return protocol is inferred. Independent human review remains pending. No successor command has been sent; see the [`trace status`](docs/RECEIVE_ONLY_SUCCESSOR_TRACE.md), [`temporary-daemon lifecycle review`](docs/TEMPORARY_DAEMON_LIFECYCLE.md), [`offline failure rehearsal`](docs/OFFLINE_FAILURE_REHEARSAL.md), [`trajectory review`](docs/SUCCESSOR_TRAJECTORY_REVIEW.md), and [`split authorization design`](docs/SPLIT_TARGET_RETURN_PROTOCOL.md).
- **Forecast:** unknown. There is no defensible completion date until the reference-frame mismatch is understood.

Passive validation passed only for the frozen single-site conditions below. It does not validate physical motion or erase the failed Stage 4 result.

> **Integration boundary:** Stage 3V validates horizontal passive proposals; Stage 3P validates a system-issued visual `MOVE` cue and has no command path; Stage 4 separately validates typed operator arming and mechanical readiness. These stages have **not** been connected and validated end to end.

![System architecture](figures/architecture.png)

## Start here

| If you want to... | Read... |
|---|---|
| Review the whole project critically | [`docs/EXTERNAL_REVIEW.md`](docs/EXTERNAL_REVIEW.md) |
| Reuse a rigorous review prompt | [`docs/REVIEW_PROMPTS.md`](docs/REVIEW_PROMPTS.md) |
| Read the compact paper-style account | [`docs/RESEARCH_NOTE.md`](docs/RESEARCH_NOTE.md) |
| Audit methods and frozen results | [`docs/METHODS.md`](docs/METHODS.md) and [`docs/RESULTS.md`](docs/RESULTS.md) |
| Check novelty and adjacent fields | [`docs/PRIOR_ART.md`](docs/PRIOR_ART.md) |
| Check trial units, uncertainty, and superseded attempts | [`docs/ATTEMPT_ACCOUNTING.md`](docs/ATTEMPT_ACCOUNTING.md) |
| Rebuild the public result table | [`docs/GENERATED_RESULTS.md`](docs/GENERATED_RESULTS.md) and [`scripts/regenerate_public_results.py`](scripts/regenerate_public_results.py) |
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
| Request owner scope or independent review | [`docs/OWNER_SCOPE_REQUEST.md`](docs/OWNER_SCOPE_REQUEST.md) and [`docs/INDEPENDENT_PROTOCOL_REVIEW.md`](docs/INDEPENDENT_PROTOCOL_REVIEW.md) |
| Audit restoration of the borrowed robot | [`docs/RETURN_TO_BORROWED_CONDITION.md`](docs/RETURN_TO_BORROWED_CONDITION.md) |
| Verify the exact successor review packet | [`docs/SUCCESSOR_REVIEW_MANIFEST.json`](docs/SUCCESSOR_REVIEW_MANIFEST.json) and [`scripts/build_successor_review_manifest.py`](scripts/build_successor_review_manifest.py) |
| Read the hardware verdict on custom centring | [`docs/CENTERING_REVIEW.md`](docs/CENTERING_REVIEW.md) |
| Audit the rejected counterfactual centring proposal | [`docs/CENTERING_PROTOCOL_DRAFT.md`](docs/CENTERING_PROTOCOL_DRAFT.md) |
| Check claim boundaries and data contents | [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) and [`docs/DATA_CARD.md`](docs/DATA_CARD.md) |
| Introduce the work to an expert group | [`DISCORD_MESSAGE.md`](DISCORD_MESSAGE.md) |

## The research question

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
| 3P — association-gated visual cue | Does stable centred compatibility trigger one visual instruction while no-cue controls time out? | 9 accepted trials from 18 attempts; seven gates passed; 6 vertical transitions and 3 fail-closed controls; 0 robot, actuation, or cloud requests. |
| 4A V3 — supervised mechanical pilot | Does one bounded 3° head-only command execute and return inside tolerance? | **Failed.** One physical trial and two head-only commands; measured motion 1.350°, target error 2.079°, return error 1.678°. |
| 4A V4 — corrected mechanical path | Can the diagnosed V3 defects be corrected without retroactively changing its thresholds? | Protocol code is prepared, but no V4 physical trial has run. A controlled three-start, zero-command series found a repeatable 2.529–2.752° mean start offset; all traces failed the unchanged 1° project gate. Custom centring is rejected pending cause/gate review and better target-state observability. |

These are small, correlated, single-site experiments: 42 accepted passive trials across Stages 2A, 3V, and 3P, followed by one failed physical trial. Observation-row denominators are telemetry summaries, not participant counts or independent samples. Zero events in six Stage 3V hard-negative trials or three Stage 3P controls do not establish a near-zero population error rate; see [`ATTEMPT_ACCOUNTING.md`](docs/ATTEMPT_ACCOUNTING.md).

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

The strongest current artifact is the **permission architecture and failure-preservation process**. The empirical study is still a research preview.

## Code and evidence map

The repository contains 124 package modules (21,121 lines), 45 test modules, nine public verification/diagnostic scripts, and the frozen numeric artifacts. Forty package files retain explicit version tags because rejected and superseded protocol generations were preserved.

| Path | Responsibility | Review note |
|---|---|---|
| [`reachy_doa/`](reachy_doa) | Read-only DoA client, angle handling, confidence windows, offline policies, manifests, replay, and source-validity analysis. | The network client exposes GET-only access to an allowlisted private IPv4 endpoint. |
| [`reachy_stage2a/`](reachy_stage2a) | Local face detection, camera lifecycle, audio/visual fusion, trial protocol, recording, and policy tournament. | Face geometry is an availability signal, not identity or active-speaker proof. |
| [`reachy_stage3a/`](reachy_stage3a) | Passive motion-shadow controller and evaluation. | It computes counterfactual targets and has no hardware authority. |
| [`reachy_stage3v/`](reachy_stage3v) | Fresh horizontal off-axis passive validation, audit/compliance checks, sampling, and frozen V3 policy. | Versioned modules expose the development trail but make navigation harder. |
| [`reachy_stage3p/`](reachy_stage3p) | Passive vertical targeting history plus association-gated visual-cue logic and result freezes. | The cue gate reads no transcript and has no command capability; V1–V7 are an audit trail, not a minimal reusable package. |
| [`reachy_stage4/`](reachy_stage4) | Frozen V4 preflight/actuation history plus a receive-only successor trace, exact offline trajectory review, external-record checks, and split target/return design. | V4's automatic return remains frozen history. The successor pieces authorize zero commands and are not an executor. |
| [`scripts/verify_results.py`](scripts/verify_results.py) | Standard-library verifier for public hashes and headline frozen claims. | This is the public evidence entry point. |
| [`scripts/regenerate_public_results.py`](scripts/regenerate_public_results.py) | Deterministically renders the public headline table from frozen JSON after evidence verification. | It regenerates the committed summary, not the original acquisition or every historical policy search. |
| [`scripts/validate_target_schema_endpoints.py`](scripts/validate_target_schema_endpoints.py) | Negative/positive integration test of the real 1.9.0 state routes extracted from the official wheel. | Uses a stub backend and sends no robot or network request. |
| [`scripts/validate_target_schema_daemon.py`](scripts/validate_target_schema_daemon.py) | Negative/positive complete-daemon test with the official 1.9.0 mockup backend. | Enforces loopback-only sockets and disables media, mDNS, startup apps, and dataset downloads; it is not an on-robot test. |
| [`scripts/validate_successor_trajectory_v190.py`](scripts/validate_successor_trajectory_v190.py) | Byte-verifies the exact 1.9.0 wheel/install, cross-checks the continuous `GotoMove` law, runs exact IK, and reports configured-limit margins. | Offline geometric review only; zero transport or commands. |
| [`scripts/capture_successor_present_target_trace.py`](scripts/capture_successor_present_target_trace.py) | Bounded receive-only present/target trace, gated by a byte-verified owner-scope artifact. | Not yet run; released 1.9.0 lacks the required serialized target fields. |
| [`scripts/build_successor_review_manifest.py`](scripts/build_successor_review_manifest.py) | Builds/checks hashes for the complete proposed successor review packet. | Content addressability does not make the proposal approved. |
| [`scripts/run_offline_fault_rehearsal.py`](scripts/run_offline_fault_rehearsal.py) | Replays four fixed failure classes through isolated local Python mock processes. | Validates mock mutual exclusion and restoration gating, not real daemon, serial-bus, torque, or shutdown behavior. |
| [`tests/`](tests) | Self-contained component and protocol tests. | 227 software tests are not 227 robot trials and do not validate hardware. |
| [`evidence/`](evidence) | Derived CSV/JSON evidence, analyses, compliance records, and freeze manifests. | No raw audio, camera pixels, transcripts, or identity labels are included. |

### Current reference path versus preserved history

The version suffixes document how the protocol changed; they do not mean that every version is an active alternative. For review and reuse, follow this map:

| Status | Reference files | Meaning |
|---|---|---|
| Current passive evidence | [`reachy_stage3v/revised_policy_v3.py`](reachy_stage3v/revised_policy_v3.py), [`reachy_stage3v/confirmation_analysis_v3.py`](reachy_stage3v/confirmation_analysis_v3.py), and the Stage 3V manifests under [`evidence/manifests/`](evidence/manifests) | Frozen horizontal off-axis policy and its fresh held-out evaluation. |
| Current cue-boundary evidence | [`reachy_stage3p/association_gated_cue.py`](reachy_stage3p/association_gated_cue.py), [`reachy_stage3p/cue_confirmation.py`](reachy_stage3p/cue_confirmation.py), [`reachy_stage3p/cue_confirmation_protocol.py`](reachy_stage3p/cue_confirmation_protocol.py), and the Stage 3P manifests | Passive visual-instruction experiment; no transcript or robot command path. |
| Frozen command-capable candidate | [`reachy_stage4/protocol.py`](reachy_stage4/protocol.py), [`reachy_stage4/runtime.py`](reachy_stage4/runtime.py), [`reachy_stage4/pilot.py`](reachy_stage4/pilot.py), and [`reachy_stage4/safety.py`](reachy_stage4/safety.py) | Prepared but unvalidated V4 path; blocked pending independent gate/target/maintenance review. The custom centring proposal was rejected for hardware execution. |
| Design-only future successor | [`successor_review.py`](reachy_stage4/successor_review.py), [`successor_trace.py`](reachy_stage4/successor_trace.py), [`trajectory_review.py`](reachy_stage4/trajectory_review.py), [`split_authorization.py`](reachy_stage4/split_authorization.py), and [`docs/BASELINE_RELATIVE_SUCCESSOR.md`](docs/BASELINE_RELATIVE_SUCCESSOR.md) | Separately versioned post-V4 proposal. Offline trajectory reconstruction is complete; limited owner scope for the temporary observational daemon is privately recorded, but live target tracing and independent approval are absent. It authorizes zero commands. |
| Preserved development history | Earlier Stage 3/4 versioned modules and their freeze artifacts | Audit trail of rejected, superseded, or failed designs. Do not treat these as the recommended API. |

There is currently no single production entry point: the three reference paths above remain deliberately separate until end-to-end integration is designed and tested.

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

CI runs both integrity verification and the stale-report check before the software tests.

Install the curated package and run 213 self-contained software tests:

```bash
python -m venv .venv
python -m pip install -e ".[test]"
python -m unittest discover -s tests -p "test_*.py"
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

1. Obtain an independent human robotics verdict using the [`complete review packet`](docs/INDEPENDENT_PROTOCOL_REVIEW.md), including the [`temporary-daemon lifecycle`](docs/TEMPORARY_DAEMON_LIFECYCLE.md) and [`return-to-borrowed-condition protocol`](docs/RETURN_TO_BORROWED_CONDITION.md). Limited owner permission for that temporary observational-daemon step is already preserved in a hash-verified private record; motion permission is not.
2. If—and only if—the resulting exact packet is approved, apply both reviewed patches in an isolated checkout and collect one bounded receive-only present/target trace using the loopback-only lifecycle plan. Do not combine that capture with motion; motor control must remain disabled.
3. Use the measured target state to finish the successor thresholds and separately review target and return. The exact nominal 1.9.0 trajectory/configured-limit calculation is complete, but collision, load, tracking, timing, and actual-return evidence remain absent.
4. Only after those dependencies pass, freeze a new successor protocol and consider one separately authorized direction. Do not revive or relabel V4.
5. Preregister a multi-room recorded-voice benchmark with room- and voice-level holdouts and compare official-style DoA following against the abstention policies.
6. Recruit additional consenting people before claiming live multi-speaker behavior or socially meaningful eye contact.

Detailed dependencies and realistic effort ranges are in [`docs/EXTERNAL_REVIEW.md`](docs/EXTERNAL_REVIEW.md#realistic-roadmap-and-timeline).

## Privacy, safety, citation, and licence

The public datasets retain derived measurements and state only—no camera pixels, raw audio, transcripts, or identity labels. This is data minimization, not formal anonymity; see [`docs/DATA_CARD.md`](docs/DATA_CARD.md).

The Stage 4 path is an operator-supervised research instrument, not a certified safety system. Never bypass a failed readiness check or weaken a threshold after observing an outcome.

See [`CITATION.cff`](CITATION.cff) for citation metadata. Code, documentation, and included derived evidence are Apache-2.0 unless a file states otherwise. The bundled YuNet model retains its upstream terms in [`models/README.md`](models/README.md).
