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
- **No hardware successor executor:** the baseline-relative successor remains a post-V4 review artifact. A valid bounded recorder run observed only coherent `UNSET` targets and therefore did not validate defined-target tracking. The lifecycle executor accepts mocks only, ships no hardware adapter, and explicitly denies hardware authority. The split target/return state machine remains non-executable on Reachy.
- **No physical-safety result from offline IK:** the exact 1.9.0 path stayed at least 42.706° inside the supplied configured joint bounds on the ideal grid, but analytical collision checking is absent and load, current, cables, enclosure clearance, tracking, scheduling, and the actual measured return path were not validated.
- **No hardware-recovery result from mock failures:** four offline fault scenarios validate only local process and lease logic. They do not prove serial-bus release, torque removal, safe shutdown, or safe restart on Reachy.
- **External authorization is not research evidence:** this repository contains no correspondence, replies, or external authorization records. It therefore makes no claim that temporary-daemon or physical-motion work is authorized.
- **No confirmed audio–mouth synchrony instrument:** V1's real 12-trial pilot rejected its fixed mouth box at 0/240 eligible settings. V2's tracked, face-normalized single-person pilot nominated and froze one candidate after passing its development and small internal-validation rules, but confirmation across new rooms, voices, and harder conditions has not occurred. Synchrony remains candidate-association evidence rather than identity or authorization.

## Evaluation risks

The manuscript's generated [`threats-to-validity table`](paper/generated/TABLE_3_THREATS_TO_VALIDITY.md) gives a compact consequence-and-treatment ledger. In particular, the V2 public record does not identify the exact microphone, camera, or browser version used during acquisition; confirmation must bind those devices before collection rather than infer them afterward.

- Stage 2A's evaluation repetition was frozen only after the full matrix had been inspected.
- Repeated measurements within a trial are correlated; row counts are not independent sample counts.
- Trial acceptance and protocol compliance involved the same research process that developed the system.
- Face detection performance may change with illumination, appearance, distance, and model version.
- DoA behavior is room- and acoustics-dependent, especially under reflection and playback.
- Stage 3P's visual `MOVE` instruction is a passive experimental transition, not human authorization. Stage 4's typed arm is local operator confirmation, not identity, consent, or conversational permission.
- Stage 3P accepted 9 of 18 attempts; its public records do not preserve a specific reason for every superseded attempt.

## Next evidence needed

The new [`audio–mouth synchrony design`](AV_SYNCHRONY_FALSIFICATION_PROTOCOL.md) preregisters the next failure-focused study structure. The [`V2 development pilot`](AV_SYNCHRONY_PILOT_V2_RESULT.md) passed and its candidate is locally content-frozen. Confirmation must use new rooms, randomized conditions, consented voice stimuli, trial-level uncertainty, complete attempt accounting, and no retuning from pilot or confirmation outcomes. Multiple live speakers are still required before any live multi-speaker or socially meaningful eye-contact claim.

Separately, the controller/daemon display discrepancy has been diagnosed, and a controlled three-start series found repeatable 2.529–2.752° mean post-wake offsets with enabled motors and zero reported loop errors. Daemon 1.9.0 still does not expose requested target fields through its released `FullState` response. A bounded patched observation retained 193 valid simultaneous present/target frames over 10 seconds, all with coherent `UNSET` targets, and restored stock healthy with motors disabled. It also established that backend construction writes PID gains, so the controller lifecycle is not read-only even though the trace client sent no application messages or robot commands. Because the frozen 1° gate is project-selected rather than a vendor tolerance, motion should resume only after a newly frozen movement-specific protocol addresses the still-unobserved defined-target transition, abort thresholds, clearance/load evidence, and split return; failing that gate alone is not proof of hardware failure. The current custom centring proposal is [rejected for hardware execution](CENTERING_REVIEW.md); see the [maintenance triage](MAINTENANCE_TRIAGE.md), [offline trajectory result](SUCCESSOR_TRAJECTORY_REVIEW.md), and [split return design](SPLIT_TARGET_RETURN_PROTOCOL.md).
