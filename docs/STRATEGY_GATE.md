# Strategy gate

Canonical status: **ACTIVE**
Last reviewed: **2026-09-25**

Complete this gate before beginning a substantial experiment, feature, document, release, or multi-hour analysis. A task that fails the gate is deferred unless the user explicitly changes the project objective.

## Required questions

1. **Primary criterion:** Which success criterion in `PROJECT_CHARTER.md` does this advance?
2. **Critical path:** Which milestone in `MILESTONE_MATRIX.md` does it move, and what state transition is expected?
3. **Work type:** Is it evidence, implementation infrastructure, safety infrastructure, or presentation?
4. **Displacement:** What higher-value task could this displace?
5. **Consistency:** Does it contradict or supersede an entry in `DECISION_LOG.md`?
6. **Claim boundary:** What could be said after success, and what would still be unproven under `NOVELTY_CLAIMS_LEDGER.md`?
7. **Safety/privacy:** Can it affect the robot, expose private data, or publish externally? Which separate gate applies?
8. **Stop rule:** What result makes us stop, redesign, or abandon the task?

## Decision rule

Proceed only if the task advances a named primary criterion or removes a named critical-path blocker, has a measurable completion condition, does not silently broaden claims, and is not lower-value presentation work displacing absent end-to-end capability.

## Current approved strategic sequence

1. **Integrate in shadow mode:** build one deterministic decision orchestrator over existing sensing/proposal components, with motion and response outputs stubbed.
2. **Attack the central hard negative:** replay saved phone-speech cases, then run a small frozen no-motion live-versus-phone shadow study.
3. **Repair the physical action path:** define one baseline-relative outward leg with numeric abort thresholds and no automatic return after failure; review before hardware use.
4. **Add bounded attention hold:** implement face-error, dwell, loss, update-rate, and oscillation limits before response generation.
5. **Gate a minimal response:** a response is permitted only after a live-speaker selection; abstention produces no conversational response.
6. **Integrate and validate:** freeze an end-to-end trial protocol only after every endpoint is measurable; compare with the required baselines.
7. **Then synthesize the paper:** update claims, figures, and manuscript after the evidence exists.

## Current gate assessments

| Candidate task | Gate result | Reason |
|---|---|---|
| Start the existing 54-trial confirmation collection | **DEFER** | It cannot identify all frozen primary endpoints and is not the shortest path to an integrated controller. |
| Further polish or export the manuscript as a paper PDF | **DEFER** | Presentation would displace M5–M10 and risk implying completion. |
| Build the shadow-only fused decision orchestrator | **PROCEED** | Directly advances M5 and enables the central phone-playback test without robot motion. |
| Send a new physical motion command | **DEFER** | M7 remains failed/blocked until a new frozen one-leg protocol and abort thresholds pass review. |
| Publish the current local commit | **DEFER** | Content is being amended; publication requires a fresh privacy, evidence, diff, and strategy review plus an explicit decision. |

## Alignment statement template

Before work, record a short statement in the task notes or final report:

> This work advances milestone **[ID]** and the charter criterion **[criterion]**. It produces **[artifact/evidence]**. It does not establish **[remaining boundary]**. It displaces **[task or none]** and will stop if **[condition]**.

## Context-recovery protocol

After a context compaction, handoff, long pause, or strategic challenge:

1. reread the five canonical records;
2. inspect `git status`, the last five commits, and the current diff from `origin/main`;
3. identify the first non-`PASS` milestone on the critical path;
4. state the alignment sentence before acting; and
5. do not rely on a previous summary if it conflicts with these versioned records.
