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
- **No successful physical validation:** one failed mechanical trial is neither success nor a performance estimate; a pure centring planner is a rejected counterfactual, not a repair or hardware result.
- **No formal privacy proof:** removing raw media reduces exposure, but timestamps, headings, filenames, and experimental metadata may still reveal context.
- **No formal verification:** hashes demonstrate file integrity, not correctness of every implementation or assumption.
- **No executable successor:** the baseline-relative successor is a post-V4, design-only review artifact. Its receive-only recorder has not been run, and the split target/return state machine has no executor. Candidate bounds and complete-record state authorize zero robot connections or commands.
- **No physical-safety result from offline IK:** the exact 1.9.0 path stayed at least 42.706° inside the supplied configured joint bounds on the ideal grid, but analytical collision checking is absent and load, current, cables, enclosure clearance, tracking, scheduling, and the actual measured return path were not validated.
- **No hardware-recovery result from mock failures:** four offline fault scenarios validate only local process and lease logic. They do not prove serial-bus release, torque removal, safe shutdown, or safe restart on Reachy.
- **Only limited owner scope is recorded:** the owner accepted the temporary minimally patched daemon plus restore/verify request in a private hash-verified record. The 3° target/return legs were not requested, and no independent human robotics verdict has been recorded.

## Evaluation risks

- Stage 2A's evaluation repetition was frozen only after the full matrix had been inspected.
- Repeated measurements within a trial are correlated; row counts are not independent sample counts.
- Trial acceptance and protocol compliance involved the same research process that developed the system.
- Face detection performance may change with illumination, appearance, distance, and model version.
- DoA behavior is room- and acoustics-dependent, especially under reflection and playback.
- Stage 3P's visual `MOVE` instruction is a passive experimental transition, not human authorization. Stage 4's typed arm is local operator confirmation, not identity, consent, or conversational permission.
- Stage 3P accepted 9 of 18 attempts; its public records do not preserve a specific reason for every superseded attempt.

## Next evidence needed

An independent protocol should preregister hypotheses and thresholds, use new rooms and positions, include multiple live speakers with consent, randomize playback and hard negatives, report trial-level uncertainty, and keep all policy development separate from the final test set. The controller/daemon display discrepancy has been diagnosed, and a controlled three-start series found repeatable 2.529–2.752° mean post-wake offsets with enabled motors and zero reported loop errors. Daemon 1.9.0 still does not expose requested target fields through its released `FullState` response. Limited owner permission for the temporary observational daemon and restoration is privately recorded, but the receive-only successor instrument remains blocked pending independent human review. Because the frozen 1° gate is project-selected rather than a vendor tolerance, physical work should resume only after that review, a successful present/target trace, explicit owner permission for motion, and a newly frozen protocol; failing that gate alone is not proof of hardware failure. The current custom centring proposal is [rejected for hardware execution](CENTERING_REVIEW.md); see the [maintenance triage](MAINTENANCE_TRIAGE.md), [offline trajectory result](SUCCESSOR_TRAJECTORY_REVIEW.md), and [split return design](SPLIT_TARGET_RETURN_PROTOCOL.md).
