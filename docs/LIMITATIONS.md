# Limitations and claim boundaries

## Supported claims

- The included local pipeline can represent abstention and enforce staged passive gates.
- The frozen single-site datasets reproduce the reported safety/coverage observations.
- The fresh Stage 3V and targeted Stage 3P passive protocols passed their predefined gates.
- The Stage 4 physical pilot failed its mechanical gate and its failure record was preserved.

## Unsupported claims

- **No historical priority:** this repository does not claim to be the first system combining DoA, vision, selective prediction, passive cueing, operator arming, or runtime motion gating.
- **No speaker identity:** face geometry and DoA do not identify a person or prove source ownership.
- **No intent inference:** speaking, looking, or issuing the test phrase does not establish intent outside the frozen operator protocol.
- **No phrase recognition:** Stage 3P uses speech activity but receives no transcript and does not know which words were spoken.
- **No end-to-end validation:** the passive candidate, visual operator instruction, and Stage 4 command boundary were tested separately and have not been validated as one integrated path.
- **No generalization:** one robot, room, microphone geometry, operator, and narrow set of controlled recordings are insufficient.
- **No participant study:** recorded voices are stimuli, not a multi-person user study.
- **No autonomous safety:** software guards are not certified functional safety.
- **No successful physical validation:** one failed mechanical trial is neither success nor a performance estimate.
- **No formal privacy proof:** removing raw media reduces exposure, but timestamps, headings, filenames, and experimental metadata may still reveal context.
- **No formal verification:** hashes demonstrate file integrity, not correctness of every implementation or assumption.

## Evaluation risks

- Stage 2A's evaluation repetition was frozen only after the full matrix had been inspected.
- Repeated measurements within a trial are correlated; row counts are not independent sample counts.
- Trial acceptance and protocol compliance involved the same research process that developed the system.
- Face detection performance may change with illumination, appearance, distance, and model version.
- DoA behavior is room- and acoustics-dependent, especially under reflection and playback.
- Stage 3P's visual `MOVE` instruction is a passive experimental transition, not human authorization. Stage 4's typed arm is local operator confirmation, not identity, consent, or conversational permission.
- Stage 3P accepted 9 of 18 attempts; its public records do not preserve a specific reason for every superseded attempt.

## Next evidence needed

An independent protocol should preregister hypotheses and thresholds, use new rooms and positions, include multiple live speakers with consent, randomize playback and hard negatives, report trial-level uncertainty, and keep all policy development separate from the final test set. Physical work should resume only after the neutral-coordinate disagreement is resolved by read-only diagnosis and a newly frozen protocol.
