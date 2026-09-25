# Project operating instructions

Before proposing strategy, starting a substantial task, changing claims, or publishing, read these canonical records in order:

1. `docs/PROJECT_CHARTER.md`
2. `docs/MILESTONE_MATRIX.md`
3. `docs/DECISION_LOG.md`
4. `docs/NOVELTY_CLAIMS_LEDGER.md`
5. `docs/STRATEGY_GATE.md`

The primary objective is a real Reachy Mini behaviour: when the visible person is silent and speech comes from a phone or another playback device, Reachy must not socially orient or respond; when the visible person speaks live, Reachy should turn toward them, maintain bounded face-directed attention, and respond. The repository has not achieved or validated that behaviour end to end.

Do not replace this objective with a paper, passive study, safety protocol, repository release, or intermediate component. Those may support the objective, but they are not substitutes for it. Any proposed objective change requires explicit user approval and a superseding entry in `docs/DECISION_LOG.md`.

Use these status words consistently:

- `WORKING`: demonstrated only in a development setting or partial path;
- `VALIDATED`: passed a frozen test within an explicitly stated scope;
- `PUBLISHABLE`: privacy, evidence, reproducibility, claim, and strategy gates all pass;
- `NOVEL`: supported by a current prior-art search and a precise differentiated claim.

Never infer one status from another. Software tests do not validate robot behaviour; passive proposals do not validate motion; a polished manuscript does not make the research complete; and absence of matching prior art does not prove novelty.

Before substantial work, complete the strategy gate in `docs/STRATEGY_GATE.md`. Prefer the highest-value task on the current critical path. Do not start confirmation collection while its instrumentation is known to miss frozen primary endpoints. Do not create or publish a submission-ready manuscript or paper PDF before the research-completion gate in `docs/PROJECT_CHARTER.md` is satisfied.

Keep external correspondence, replies, identities, approval records, raw audio, and raw camera media outside the repository. GitHub publication is a separate explicit gate after privacy, content, evidence, and strategy review. Never push merely because a local commit exists.
