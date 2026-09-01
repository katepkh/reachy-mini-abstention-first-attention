# Reachy Mini Abstention-First Attention

**Privacy-minimal selective speaker grounding and runtime-gated head motion.**

> Research preview: passive validation is complete for the frozen conditions below. Physical motion is **not** validated; the first supervised motion pilot failed its unchanged mechanical acceptance gate.

![System architecture](figures/architecture.png)

Most demos ask: *can a robot turn toward a voice?* This project asks the harder question: **when is the evidence strong enough that the robot should be allowed to move at all?**

The implementation treats direction of arrival (DoA), visible-face geometry, temporal agreement, an explicit operator cue, and mechanical readiness as separate permissions. Ambiguous evidence produces `ABSTAIN`, not a guessed target. The result is a staged, hash-frozen path from passive sensing to tightly bounded motion.

## What is demonstrated

| Stage | Question | Frozen result |
|---|---|---|
| 2A — passive fusion matrix | Does a visible face spatially agree with the acoustic axis? | 15 accepted trials, 815 numeric observations; useful coverage, but geometry alone did not establish source ownership. |
| 2A — counterfactual tournament | What does stricter temporal consensus trade away? | Development-selected 3-hit policy: 0/37 hard-negative confirmations and 2/31 matching confirmations on the retrospective evaluation split. |
| 3V — fresh vertical holdout | Does the frozen shadow policy choose the right direction and bounded target? | 18 accepted trials; all four passive gates passed; 12/12 positive trials proposed a move; 0 hard-negative would-move rows; max target error 2.647°. |
| 3P — association-gated cue | Does movement remain blocked until an explicit cue, including no-cue controls? | 9 accepted trials; seven gates passed; 6 transitions and 3 fail-closed controls; 0 robot, actuation, or cloud requests. |
| 4A — supervised mechanical pilot | Does one bounded 3° head-only command execute and return within tolerance? | **Failed.** One physical trial, two head-only commands; measured motion 1.350°, target error 2.079°, return error 1.678°. |

The failure is part of the contribution, not an omitted outlier. Its record was frozen, the thresholds were not weakened, and the protocol defects were documented before a corrected version was attempted.

## Central finding

Acoustic/visual alignment is useful **availability evidence**, but it is not proof that the visible person owns the sound. In the Stage 2A matrix:

- Matching visible face + speech confirmed 62/71 tracked rows (87.3%).
- Speech with no face confirmed 0/35 tracked rows.
- A visible silent face plus spatially separate phone speech still confirmed 13/63 tracked rows (20.6%).
- A visible silent face confirmed every one of 13 false acoustic tracking episodes.

That failure mode motivated an abstention-first policy, hard-negative controls, explicit cue gating, and a separate mechanical readiness gate.

## Reproduce the published claims

The verification script uses only the Python standard library. It checks frozen state, raw-file hashes, and the headline claims:

```bash
python scripts/verify_results.py
```

Install the analysis package and run the curated unit tests:

```bash
python -m venv .venv
python -m pip install -e ".[test]"
python -m unittest discover -s tests -p "test_*.py"
```

Live camera acquisition is optional and isolated:

```bash
python -m pip install -e ".[live]"
```

No live command should be sent to a robot merely because the passive tests pass. Read [SAFETY.md](SAFETY.md) before any hardware work.

## Repository map

- [`docs/RESEARCH_NOTE.md`](docs/RESEARCH_NOTE.md) — compact paper-style account.
- [`docs/METHODS.md`](docs/METHODS.md) — staged protocol and evaluation design.
- [`docs/RESULTS.md`](docs/RESULTS.md) — frozen results and fingerprints.
- [`docs/FAILURE_LEDGER.md`](docs/FAILURE_LEDGER.md) — what failed and what changed afterward.
- [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) — boundaries on every claim.
- [`docs/DATA_CARD.md`](docs/DATA_CARD.md) — what the public evidence does and does not contain.
- [`docs/PRIOR_ART.md`](docs/PRIOR_ART.md) — relationship to Reachy and adjacent work.
- [`evidence/`](evidence) — numeric CSV/JSON evidence and immutable result manifests.
- [`reachy_doa/`](reachy_doa), [`reachy_stage2a/`](reachy_stage2a), [`reachy_stage3a/`](reachy_stage3a), [`reachy_stage3v/`](reachy_stage3v), [`reachy_stage3p/`](reachy_stage3p), [`reachy_stage4/`](reachy_stage4) — staged implementation.
- [`DISCORD_MESSAGE.md`](DISCORD_MESSAGE.md) — concise expert-group introduction.
- [`PUBLISHING.md`](PUBLISHING.md) — final GitHub and Discord release steps.

## Privacy and evidence policy

The published numeric datasets contain derived measurements and state only—no camera pixels, raw audio, transcripts, or identity labels. Temporary encrypted audit clips used for protocol compliance review are deliberately excluded. This is data minimization, not a claim of formal anonymity; see the data card for residual metadata risks.

## Scientific status

This is a single-robot, single-room, primarily single-operator study. Recorded voices were controlled stimuli, not additional study participants. Stage 2A's development/evaluation split was formalized after the matrix had already been inspected, so it is explicitly described as retrospective. The passive results do not establish generalization, identity, intent, or safe autonomous actuation.

The defensible contribution is the **permission architecture and auditable failure process**, not a claim that speaker-following robotics is solved or historically first.

## Citation and licence

See [`CITATION.cff`](CITATION.cff). Code, documentation, and the included derived evidence are released under Apache-2.0 unless a file states otherwise. The bundled YuNet model retains its upstream terms and attribution in [`models/README.md`](models/README.md).
