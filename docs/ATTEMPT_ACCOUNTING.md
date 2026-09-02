# Trial units, uncertainty, and attempt accounting

This note prevents observation rows, accepted trials, attempts, and software tests from being conflated.

## Units at a glance

| Stage | Accepted trials | Recorded attempts represented publicly | Primary unit | Status |
|---|---:|---:|---|---|
| 2A passive matrix | 15 | The public release contains the 15 selected accepted captures; it does not claim a complete attempt denominator. | Trial; rows are repeated telemetry within a trial. | Exploratory; the later development/evaluation split was retrospective. |
| 3V horizontal off-axis holdout | 18 | 21 | Trial; 12 matching positives and 6 hard negatives. | Fresh passive protocol; policy frozen before collection. |
| 3P vertical visual-cue boundary | 9 | 18 | Trial; 6 cue transitions and 3 fail-closed controls. | Fresh passive protocol; no transcript, robot request, or actuation path. |
| 4A V3 physical pilot | 0 accepted | 1 commanded trial | Physical trial. | Mechanical gate failed and remains failed. |

The 42 accepted passive trials are not independent replications of a population: they share one robot, site, room context, and primary operator. The 213 passing tests are software tests, not empirical trials.

## Stage 3V attempt flow

The accepted-file list in [`evidence/stage3v_v3/progress.json`](../evidence/stage3v_v3/progress.json) identifies 18 accepted trials. Three additional attempts are retained:

| Frozen step | Condition | Superseded attempts | Public disposition |
|---:|---|---:|---|
| 17 | face −20° / phone +20°, repetition 2 | 1 | `NONCOMPLIANT`; both position and speech/playback attestations are false. |
| 18 | face +20° / phone −20°, repetition 2 | 2 | `NONCOMPLIANT`; both position and speech/playback attestations are false. |

This produces 18 accepted trials from 21 attempts. The three exclusions are all in hard-negative conditions, which is relevant when interpreting safety performance even though the frozen criteria retain them and prohibit treating them as accepted trials.

## Stage 3P attempt flow

The accepted-file list in [`evidence/stage3p_cue_v1/progress.json`](../evidence/stage3p_cue_v1/progress.json) identifies nine accepted trials. Nine earlier attempts are retained:

| Frozen step | Condition | Superseded attempts | Public disposition |
|---:|---|---:|---|
| 1 | centre to down 10°, repetition 1 | 1 | `NONCOMPLIANT`; expected visual cue was not observed. |
| 5 | centre to down 10°, repetition 3 | 1 | `NONCOMPLIANT`; expected visual cue was not observed. |
| 7 | silent centred-face control | 6 | Five are `NONCOMPLIANT`; one has metadata but no compliance sidecar. All observed the expected no-cue timeout. |
| 9 | speaking, visible, up 10°, not centred | 1 | `NONCOMPLIANT`; observed the expected no-cue timeout. |

This produces nine accepted trials from 18 attempts. Eight superseded attempts have generic noncompliance records and one lacks a compliance sidecar. The public records do not preserve a sufficiently specific reason to reconstruct every retry. That is an audit limitation: no more detailed explanation should be inferred after the fact.

## How to read zero-event results

The frozen gates are deterministic pass/fail checks for these protocols. They are not population-rate estimates.

- Stage 3V observed a passive proposal in 12/12 matching-positive trials and no would-move row in 0/6 accepted hard-negative trials.
- Stage 3P observed the required visual cue in 6/6 accepted transitions and no unexpected cue in 0/3 accepted controls.

For scale only, if these were independent Bernoulli trials, exact one-sided 95% bounds would be approximately:

| Observation | One-sided 95% bound |
|---|---:|
| 12/12 positive trials produced a proposal | true proposal probability greater than 77.9% |
| 0/6 hard-negative trials contained a would-move row | true event probability less than 39.3% |
| 0/3 controls emitted an unexpected cue | true event probability less than 63.2% |

The shared operator, robot, and room violate the external-independence assumption, so these values are explanatory bounds rather than generalization claims. The next study should use room- and recording-speaker-level holdouts, publish trial-level outcomes, and separate development from evaluation before data are observed.

## Reporting rules

Public summaries should:

1. lead with trial and attempt counts;
2. label row fractions as correlated telemetry summaries;
3. report accepted and superseded attempts together;
4. distinguish a frozen protocol gate from a population error-rate claim;
5. avoid calling 13/63 Stage 2A compatibility confirmations a general false-positive rate;
6. keep recorded-voice robustness separate from live participant, speaker-ownership, and HRI claims.
