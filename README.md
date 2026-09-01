# Reachy Mini Abstention-First Attention

[![Evidence and tests](https://github.com/katepkh/reachy-mini-abstention-first-attention/actions/workflows/ci.yml/badge.svg)](https://github.com/katepkh/reachy-mini-abstention-first-attention/actions/workflows/ci.yml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](pyproject.toml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)

**When should a social robot refuse to look?**

This research preview studies selective attention proposals for Reachy Mini under an asymmetric cost: a false social or physical movement is treated as more costly than abstention. Local direction of arrival (DoA), ephemeral face geometry, temporal agreement, a passive visual cue, operator arming, and mechanical readiness are treated as different boundaries. Missing, stale, ambiguous, or conflicting evidence produces `ABSTAIN` or `HOLD`, not a guessed target.

## Current hardware blocker

**Physical validation is suspended.** The first supervised 3° motion trial failed its unchanged mechanical gate. The corrected V4 path then failed read-only preflight because Reachy Mini Control displayed a zeroed head while the daemon reported the head approximately 2.35–4.43° from its neutral reference across restarts.

- **Impact:** 0 of 4 V4 directions have been accepted; no V4 motion command has been sent.
- **Decision:** do not weaken or bypass the 1° neutral preflight gate. Diagnose the coordinate disagreement using read-only observations first.
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
| 4A V4 — corrected mechanical path | Can the diagnosed V3 defects be corrected without weakening thresholds? | Protocol code is prepared, but no V4 physical trial has run. Read-only preflight remains blocked by neutral-coordinate disagreement. |

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

The repository contains 110 package modules (18,827 lines), 28 test modules (2,059 lines), two public verification/reporting scripts, and the frozen numeric artifacts. Forty package files retain explicit version suffixes because rejected and superseded protocol generations were preserved.

| Path | Responsibility | Review note |
|---|---|---|
| [`reachy_doa/`](reachy_doa) | Read-only DoA client, angle handling, confidence windows, offline policies, manifests, replay, and source-validity analysis. | The network client exposes GET-only access to an allowlisted private IPv4 endpoint. |
| [`reachy_stage2a/`](reachy_stage2a) | Local face detection, camera lifecycle, audio/visual fusion, trial protocol, recording, and policy tournament. | Face geometry is an availability signal, not identity or active-speaker proof. |
| [`reachy_stage3a/`](reachy_stage3a) | Passive motion-shadow controller and evaluation. | It computes counterfactual targets and has no hardware authority. |
| [`reachy_stage3v/`](reachy_stage3v) | Fresh horizontal off-axis passive validation, audit/compliance checks, sampling, and frozen V3 policy. | Versioned modules expose the development trail but make navigation harder. |
| [`reachy_stage3p/`](reachy_stage3p) | Passive vertical targeting history plus association-gated visual-cue logic and result freezes. | The cue gate reads no transcript and has no command capability; V1–V7 are an audit trail, not a minimal reusable package. |
| [`reachy_stage4/`](reachy_stage4) | Expiring read-only preflight, one-shot arming, relative bounded pose, robust SO(3) measurement, automatic return, and immutable result handling. | Command-capable code is experimental. V4 is unvalidated and must not bypass a failed preflight. |
| [`scripts/verify_results.py`](scripts/verify_results.py) | Standard-library verifier for public hashes and headline frozen claims. | This is the public evidence entry point. |
| [`scripts/regenerate_public_results.py`](scripts/regenerate_public_results.py) | Deterministically renders the public headline table from frozen JSON after evidence verification. | It regenerates the committed summary, not the original acquisition or every historical policy search. |
| [`tests/`](tests) | Self-contained component and protocol tests. | 142 software tests are not 142 robot trials and do not validate hardware. |
| [`evidence/`](evidence) | Derived CSV/JSON evidence, analyses, compliance records, and freeze manifests. | No raw audio, camera pixels, transcripts, or identity labels are included. |

### Current reference path versus preserved history

The version suffixes document how the protocol changed; they do not mean that every version is an active alternative. For review and reuse, follow this map:

| Status | Reference files | Meaning |
|---|---|---|
| Current passive evidence | [`reachy_stage3v/revised_policy_v3.py`](reachy_stage3v/revised_policy_v3.py), [`reachy_stage3v/confirmation_analysis_v3.py`](reachy_stage3v/confirmation_analysis_v3.py), and the Stage 3V manifests under [`evidence/manifests/`](evidence/manifests) | Frozen horizontal off-axis policy and its fresh held-out evaluation. |
| Current cue-boundary evidence | [`reachy_stage3p/association_gated_cue.py`](reachy_stage3p/association_gated_cue.py), [`reachy_stage3p/cue_confirmation.py`](reachy_stage3p/cue_confirmation.py), [`reachy_stage3p/cue_confirmation_protocol.py`](reachy_stage3p/cue_confirmation_protocol.py), and the Stage 3P manifests | Passive visual-instruction experiment; no transcript or robot command path. |
| Current mechanical candidate | [`reachy_stage4/protocol.py`](reachy_stage4/protocol.py), [`reachy_stage4/runtime.py`](reachy_stage4/runtime.py), [`reachy_stage4/pilot.py`](reachy_stage4/pilot.py), and [`reachy_stage4/safety.py`](reachy_stage4/safety.py) | Prepared but unvalidated V4 path; blocked by read-only neutral-coordinate disagreement. |
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

Install the curated package and run 142 self-contained software tests:

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

1. Obtain adversarial external review of the claims, threat model, experiment design, and code boundary.
2. Make the historical policy searches replayable from the public layout and add coverage/static-analysis reporting; the headline-table regeneration is now complete.
3. Resolve the daemon/controller neutral-coordinate disagreement using read-only diagnosis.
4. Freeze and run the already-bounded V4 four-direction mechanical pilot only after preflight passes consistently.
5. Preregister a multi-room recorded-voice benchmark with room- and voice-level holdouts and compare official-style DoA following against the abstention policies.
6. Recruit additional consenting people before claiming live multi-speaker behavior or socially meaningful eye contact.

Detailed dependencies and realistic effort ranges are in [`docs/EXTERNAL_REVIEW.md`](docs/EXTERNAL_REVIEW.md#realistic-roadmap-and-timeline).

## Privacy, safety, citation, and licence

The public datasets retain derived measurements and state only—no camera pixels, raw audio, transcripts, or identity labels. This is data minimization, not formal anonymity; see [`docs/DATA_CARD.md`](docs/DATA_CARD.md).

The Stage 4 path is an operator-supervised research instrument, not a certified safety system. Never bypass a failed readiness check or weaken a threshold after observing an outcome.

See [`CITATION.cff`](CITATION.cff) for citation metadata. Code, documentation, and included derived evidence are Apache-2.0 unless a file states otherwise. The bundled YuNet model retains its upstream terms in [`models/README.md`](models/README.md).
