# Movement as a permission decision

> This compact research note summarizes component evidence. [`MANUSCRIPT.md`](MANUSCRIPT.md) is a working evidence synthesis, not a submission-ready or end-to-end completion claim. The authoritative objective is [`PROJECT_CHARTER.md`](PROJECT_CHARTER.md).

## Abstract

This research preview investigates selective attention proposals for Reachy Mini under a deliberately asymmetric loss: a false movement is treated as more costly than abstention. A local acoustic direction-of-arrival endpoint is fused with ephemeral face geometry and temporal consensus; passive visual cueing and a separate operator-armed mechanical boundary are tested in later stages. The system retains derived numeric state rather than raw audio or camera frames. A 15-trial matrix exposed a central failure mode: acoustic/visual alignment improves availability but does not establish source ownership. A frozen policy was then evaluated in a fresh 18-trial horizontal off-axis holdout, followed by a 9-trial passive vertical cue-boundary experiment. Both passive stages passed their predefined gates. The first supervised physical 3° pilot failed its unchanged mechanical tolerance and was frozen as a negative result. The work therefore supports an auditable staged research architecture—not autonomous speaker-following—and identifies independent multi-room, multi-speaker validation and end-to-end integration as future requirements.

## Research question

How can a social robot keep weak acoustic/visual compatibility, operator arming, and mechanical readiness as separately inspectable boundaries before any movement is permitted?

The key shift is from continuous target estimation to selective action:

\[
\text{observation} \rightarrow \{\text{target},\;\text{abstain}\}
\]

and then, separately:

\[
\text{stable compatibility} \rightarrow \{\text{visual instruction},\;\text{timeout}\},
\]

and, in a separate unintegrated physical pilot:

\[
\text{typed arm} + \text{readiness} \rightarrow \{\text{bounded command},\;\text{block}\}.
\]

## Design

1. **Acoustic observation:** query local DoA and speech state through an exact GET-only client with explicit stale/invalid handling.
2. **Visual availability:** detect a face locally and discard pixels after extracting non-identifying geometry.
3. **Association:** require spatial and temporal agreement; disagreement, multiple faces, stale evidence, or insufficient hits produce abstention.
4. **Shadow target:** calculate the motion that would have been requested, but send no robot command.
5. **Passive operator cue:** display a frozen visual instruction after stable centred compatibility; controls must time out fail-closed. The system receives no transcript and does not match phrase content.
6. **Mechanical gate:** separately preflight the daemon, start pose, command envelope, exact typed arm, and one-shot session before a physical command.

## Results

The Stage 2A matrix showed both utility and non-identifiability. Matching speech/face geometry confirmed 62/71 tracked rows, while no-face speech confirmed 0/35. Yet spatially separate phone speech confirmed 13/63 tracked rows in the presence of a silent visible face. The system could therefore infer *compatibility*, not source ownership.

A retrospective development/evaluation tournament quantified the safety/coverage frontier. The development-selected 3-hit consensus policy produced 0/37 hard-negative confirmations but only 2/31 matching confirmations on the evaluation repetition. Because the complete matrix had already been inspected before the split was formalized, this is comparative internal evidence, not a pristine blind estimate.

The next two protocols were frozen before fresh collection. Stage 3V accepted 18 of 21 attempts and passed horizontal hard-negative safety, yaw direction, per-heading coverage, and target-accuracy gates. All 12 positive trials produced a passive proposal, none of the six accepted hard-negative trials contained a would-move row, and maximum target error was 2.647°. Stage 3P accepted 9 of 18 attempts and passed seven passive visual-cue gates across six vertical transitions and three controls; it made zero robot, actuation, or cloud requests.

The first laptop-only audio–mouth synchrony instrument was rejected when 0/240 fixed-box settings met its rule. A separately frozen V2 face-landmark pilot retained all 23 attempts, accepted 12 quality-passing trials, selected 1 of 8 eligible settings from a 45-setting development grid, and passed its four-trial internal validation. That candidate is content-frozen but remains single-person, single-setup development evidence rather than confirmation or speaker-ownership evidence. A candidate-bound 54-trial confirmation schedule is now frozen; data collection cannot begin until three rooms, two consented voice recordings, capture/playback devices, and fixed placement marks are privately bound.

The physical pilot did not pass. Its one commanded trial issued two head-only commands and no body, antenna, torque, or motor-mode commands. Robust reconstruction measured 1.350° motion against a requested 3°, 2.079° target error, and 1.678° return error. The outcome remained failed.

## Interpretation

The strongest evidence here is not raw accuracy. It is the sequence of falsifiable permissions and the preservation of failure:

- hard negatives are first-class experimental conditions;
- `ABSTAIN` is a valid output, not a missing prediction;
- passive success cannot silently authorize motion;
- protocol fingerprints prevent post-outcome edits from masquerading as preregistered choices;
- a failed mechanical trial remains failed even after its instrumentation defects are understood.

This approach is relevant to any embodied system in which an uncertain perception estimate could trigger a socially or physically consequential action.

The passive candidate, visual cue, and physical command boundary remain separately tested components. No end-to-end speaker-to-motion system has been validated. A controlled three-start, command-free series found repeatable 2.529–2.752° mean post-wake offsets, all outside the unchanged 1° project gate, with enabled motors and zero reported loop errors. A source-backed review rejected a custom corrective-centring proposal pending independent review of gate validity, observable present-versus-target state, and open maintenance hypotheses; the gate failure is not presented as proof of hardware fault.

A successor adds a receive-only simultaneous present/target trace client, exact offline daemon 1.9.0 trajectory and analytical-IK reconstruction, separate target/return authorization states, an exact-version health gate, and a mock-only lifecycle executor. The offline path matched official `GotoMove` at 201 ideal samples per leg and stayed at least 42.706° inside the supplied configured joint bounds. This is not collision, load, tracking, cable, timing, or physical-safety validation. After two contained fail-closed rehearsals exposed a patch-staging error and a client deadline-handling error, a bounded live observation retained 193 frames over 10 seconds. Every frame reported the coherent target state `UNSET`; the trace client sent zero application messages and zero robot commands. The temporary process released its resources and stock v1.9.0 was restored healthy with motors disabled. This closes the receive-only trace gate, but no defined target, target transition, motion result, or hardware executor exists. External authorization and review are outside this repository; no correspondence is retained as research evidence.

## Status

The current evidence supports a reproducible single-site research preview. It does **not** support claims of identity recognition, intent detection, generalization, autonomous safety, or successful physical speaker-following.
