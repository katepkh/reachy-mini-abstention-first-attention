# Movement as a permission decision

## Abstract

This research preview investigates selective speaker grounding for Reachy Mini under a deliberately asymmetric loss: a false movement is treated as more costly than abstention. A local acoustic direction-of-arrival endpoint is fused with ephemeral face geometry, temporal consensus, an explicit human cue, and a final mechanical-readiness gate. The system retains derived numeric state rather than raw audio or camera frames. A 15-trial matrix exposed a central failure mode: acoustic/visual alignment improves availability but does not establish source ownership. Frozen passive policies were then evaluated in a fresh 18-trial vertical holdout and a 9-trial cue-boundary experiment. Both passive stages passed their predefined gates. The first supervised physical 3° pilot failed its unchanged mechanical tolerance and was frozen as a negative result. The work therefore supports an auditable permission architecture—not autonomous speaker-following—and identifies independent multi-room, multi-speaker validation as the next scientific requirement.

## Research question

How can a social robot combine weak acoustic and visual signals so that it moves only after evidence, human authorization, and mechanical readiness have each passed independently inspectable gates?

The key shift is from continuous target estimation to selective action:

\[
\text{observation} \rightarrow \{\text{target},\;\text{abstain}\}
\]

and then, separately:

\[
\text{target} + \text{cue} + \text{readiness} \rightarrow \{\text{bounded command},\;\text{block}\}.
\]

## Design

1. **Acoustic observation:** query local DoA and speech state through an exact GET-only client with explicit stale/invalid handling.
2. **Visual availability:** detect a face locally and discard pixels after extracting non-identifying geometry.
3. **Association:** require spatial and temporal agreement; disagreement, multiple faces, stale evidence, or insufficient hits produce abstention.
4. **Shadow target:** calculate the motion that would have been requested, but send no robot command.
5. **Authorization cue:** require a frozen human cue after stable association; no-cue controls must time out fail-closed.
6. **Mechanical gate:** preflight the daemon, start pose, command envelope, and one-shot authorization before any physical command.

## Results

The Stage 2A matrix showed both utility and non-identifiability. Matching speech/face geometry confirmed 62/71 tracked rows, while no-face speech confirmed 0/35. Yet spatially separate phone speech confirmed 13/63 tracked rows in the presence of a silent visible face. The system could therefore infer *compatibility*, not source ownership.

A retrospective development/evaluation tournament quantified the safety/coverage frontier. The development-selected 3-hit consensus policy produced 0/37 hard-negative confirmations but only 2/31 matching confirmations on the evaluation repetition. Because the complete matrix had already been inspected before the split was formalized, this is comparative internal evidence, not a pristine blind estimate.

The next two policies were frozen before fresh collection. Stage 3V accepted 18 of 21 attempts and passed hard-negative safety, direction, per-heading coverage, and target-accuracy gates. All 12 positive trials produced a passive proposal, hard-negative would-move rows were zero, and maximum target error was 2.647°. Stage 3P accepted 9 of 18 attempts and passed seven cue-boundary gates across six transitions and three controls; it made zero robot, actuation, or cloud requests.

The physical pilot did not pass. Its one commanded trial issued two head-only commands and no body, antenna, torque, or motor-mode commands. Robust reconstruction measured 1.350° motion against a requested 3°, 2.079° target error, and 1.678° return error. The outcome remained failed.

## Interpretation

The strongest evidence here is not raw accuracy. It is the sequence of falsifiable permissions and the preservation of failure:

- hard negatives are first-class experimental conditions;
- `ABSTAIN` is a valid output, not a missing prediction;
- passive success cannot silently authorize motion;
- protocol fingerprints prevent post-outcome edits from masquerading as preregistered choices;
- a failed mechanical trial remains failed even after its instrumentation defects are understood.

This approach is relevant to any embodied system in which an uncertain perception estimate could trigger a socially or physically consequential action.

## Status

The current evidence supports a reproducible single-site research preview. It does **not** support claims of identity recognition, intent detection, generalization, autonomous safety, or successful physical speaker-following.

