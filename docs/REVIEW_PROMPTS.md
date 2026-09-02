# External review prompts

These prompts are designed for human experts or capable technical-review systems. Replace bracketed context where needed. The repository is public at:

**https://github.com/katepkh/reachy-mini-abstention-first-attention**

For every review, ask the reviewer to distinguish:

- a bug from a scientific limitation;
- a missing test from a failed experiment;
- software verification from empirical validation;
- a known technique from a potentially useful composition;
- a strong claim from a well-scoped research-preview claim.

## Master multidisciplinary review prompt

```text
Act as an independent senior reviewer of an early-stage robotics research repository. Your role is adversarial but constructive: identify what is genuinely supported, what is overstated, what is missing, and what would most efficiently increase scientific and engineering credibility.

Repository:
https://github.com/katepkh/reachy-mini-abstention-first-attention

Start with:
- README.md
- docs/EXTERNAL_REVIEW.md
- docs/RESEARCH_NOTE.md
- docs/METHODS.md
- docs/RESULTS.md
- docs/FAILURE_LEDGER.md
- docs/LIMITATIONS.md
- docs/MAINTENANCE_TRIAGE.md
- docs/DATA_CARD.md
- docs/PRIOR_ART.md
- SAFETY.md

Then inspect representative code and tests rather than reviewing prose alone:
- reachy_doa/client.py
- reachy_doa/policies.py
- reachy_stage2a/fusion.py
- reachy_stage2a/tournament.py
- reachy_stage3a/controller.py
- reachy_stage3v/revised_policy_v3.py
- reachy_stage3p/association_gated_cue.py
- reachy_stage3p/cue_confirmation.py
- reachy_stage4/safety.py
- reachy_stage4/runtime.py
- reachy_stage4/pilot.py
- scripts/verify_results.py
- tests/
- evidence/manifests/

If you can execute code, run:
python scripts/verify_results.py
python -m unittest discover -s tests -p "test_*.py"

Research context:
- one Reachy Mini, one site, one primary operator;
- additional voices can be used as consented recordings;
- passive stages passed their narrow frozen gates;
- the only physical motion trial failed;
- no successful live policy-to-motor speaker following or eye-contact result is claimed;
- the intended contribution is an abstention-first permission architecture and auditable failure process, not a historically first DoA/vision system.

Review the project across these dimensions:
1. research-question clarity and importance;
2. novelty relative to DoA following, audiovisual active-speaker localization, selective prediction, HRI gaze/turn-taking, and runtime assurance;
3. experimental validity, including independence, controls, correlated observations, selection bias, policy-version history, and uncertainty;
4. software correctness and maintainability;
5. perception-to-actuation isolation and failure containment;
6. privacy and data-governance claims;
7. reproducibility from the public repository;
8. safety language and unsupported implications;
9. usefulness to robotics researchers and companies;
10. GitHub presentation and communication quality.

Do not accept the repository's descriptions as proof. Trace important claims to evidence, manifests, tests, or code. When possible, cite an exact file and line or a frozen artifact. State explicitly when you could not verify something.

Return:
A. a 200-word executive verdict;
B. the five strongest aspects;
C. the ten most important weaknesses, ranked by severity;
D. a claim audit table with columns: claim, evidence, verdict, missing evidence;
E. a code-risk table with columns: component, failure mode, current guard, remaining risk, recommended test;
F. a scientific-design critique;
G. a novelty/prior-art critique;
H. a GitHub/reproducibility critique;
I. the minimum next study that would materially change your confidence;
J. a prioritized 2-week, 1-month, and 3-month roadmap;
K. the wording you would use to describe this work publicly without exaggeration;
L. three questions you would ask the author before endorsing or sharing it.

Label each finding as CRITICAL, MAJOR, MODERATE, or MINOR. Separate confirmed defects from hypotheses that require investigation. Be direct; do not reward file quantity, test count, or careful wording unless the underlying evidence supports the claim.
```

## Robotics and HRI research prompt

```text
Review this repository as a senior robotics/HRI researcher:
https://github.com/katepkh/reachy-mini-abstention-first-attention

Focus on whether "movement as a permission decision" is a useful research framing and whether the current experiments say anything meaningful about social attention.

Specifically assess:
- whether DoA plus face geometry measures source compatibility, active-speaker status, or neither;
- whether the hard negatives are sufficient and ecologically valid;
- whether Stage 3P's system-issued visual instruction is a useful experimental transition or a confound;
- whether Stage 4's typed arm should be treated only as operator confirmation rather than identity, consent, or conversational authorization;
- the gap between head orientation, gaze, eye contact, turn-taking, and socially meaningful attention;
- how one primary operator and recorded voices limit inference;
- which additional live-participant conditions are indispensable;
- what outcome measures an HRI study should include beyond angular error;
- whether abstention should be evaluated for social acceptability, latency, legibility, and user trust;
- how to avoid optimizing only for refusal while making the robot unusable.

Compare the project with established audiovisual active-speaker localization, robot gaze control, turn-taking, and selective prediction. Do not assume novelty. Identify the closest prior work and explain whether the contribution is a new method, a new evaluation, a safety-oriented composition, or primarily an engineering case study.

Return a publication-readiness verdict for: workshop demo, workshop paper, HRI late-breaking report, full conference paper, and open-source engineering note. For each, list the missing evidence and a realistic study design.
```

## Experimental-design and statistics prompt

```text
Audit the experimental validity of:
https://github.com/katepkh/reachy-mini-abstention-first-attention

Read docs/METHODS.md, docs/RESULTS.md, docs/LIMITATIONS.md, evidence/analysis/, and the relevant manifests. Treat observation rows within a trial as repeated correlated measurements, not independent samples.

Answer:
1. What is the true experimental unit at each stage?
2. Which denominators in the README are descriptive telemetry counts rather than independent samples?
3. Does the retrospective development/evaluation split support any out-of-sample claim?
4. Could trial acceptance, supersession, detector-quality gates, or policy-version selection bias the reported rates?
5. Are the Stage 3V horizontal off-axis and Stage 3P vertical cue protocols genuinely frozen-before-collection evaluations? What evidence verifies that?
6. What confidence intervals or hierarchical models are appropriate at trial, room, voice, and operator levels?
7. What baselines and ablations are missing?
8. How should risk-coverage curves be computed when the cost of false movement is asymmetric?
9. What sample size and randomization plan would support a multi-room recorded-voice benchmark?
10. Which claims remain non-identifiable even with more repetitions of the present protocol?

Propose a preregistered next protocol that one robot-side operator can run using multiple consented recorded voices in at least three rooms. Include hypotheses, experimental units, factors, randomization, exclusions, frozen thresholds, baselines, primary/secondary outcomes, uncertainty analysis, and stopping rules. Clearly state which live-HRI claims cannot be tested with recordings.
```

## Robotics safety and runtime-assurance prompt

```text
Review the command boundary in:
https://github.com/katepkh/reachy-mini-abstention-first-attention

Prioritize:
- SAFETY.md
- reachy_stage4/config.py
- reachy_stage4/safety.py
- reachy_stage4/runtime.py
- reachy_stage4/protocol.py
- reachy_stage4/pilot.py
- reachy_stage4/result_freeze_v3.py
- tests/test_stage4a_protocol_transport.py
- tests/test_stage4a_supervised_motion.py
- evidence/manifests/stage4a_supervised_motion_pilot_v3.json
- evidence/manifests/stage4a_supervised_motion_pilot_v3_diagnostic_freeze.json

Threat-model the boundary from passive target to physical command. Examine:
- stale or inconsistent telemetry;
- diagnosed desktop matrix/object synchronization defect; a controlled three-start series with mean residuals of 2.529°, 2.752°, and 2.746°, enabled motors, and zero reported loop errors; daemon 1.9.0's dropped target-state response fields; the project's non-vendor 1° gate; and the rejected custom centring proposal;
- TOCTOU between preflight and execution;
- replay or reuse of a one-shot armed session;
- process crash after target motion but before return;
- network loss, partial command completion, daemon restart, and motor fault;
- incorrect frame transforms or non-rigid poses;
- concurrency and duplicate execution;
- unsafe exception handling;
- mismatch between official SDK semantics and the custom transport;
- operator-observation reliability;
- whether "runtime assurance" is an appropriate term without a verified backup controller or formal invariant.

Return:
1. a control/data-flow diagram;
2. a failure-mode and effects analysis;
3. confirmed safeguards versus assumed safeguards;
4. missing tests, including property, fuzz, fault-injection, and hardware-in-the-loop tests;
5. a verdict on whether any additional physical pilot is justified;
6. whether the frozen 1° V4 identity gate is defensible, and what a separately
   versioned baseline-relative successor would need if it is not;
7. exact preconditions that must be met before any actuation;
8. language corrections needed to avoid implying certified safety or diagnosed
   hardware failure.

Do not recommend bypassing or retroactively relaxing the neutral-pose gate
merely to collect a passing V4 result. You may recommend a separately versioned,
preregistered successor criterion if you can justify its absolute mechanical
envelope and baseline-relative measurement.
```

## Software engineering and reproducibility prompt

```text
Review this repository as a staff robotics software engineer and reproducibility maintainer:
https://github.com/katepkh/reachy-mini-abstention-first-attention

Inspect package structure, pyproject.toml, CI, scripts/verify_results.py, representative modules from every stage, all tests, and the public evidence layout.

Evaluate:
- whether package boundaries reflect runtime authority;
- whether the GET-only and command-capable paths are actually isolated;
- path handling and the mismatch between original data/... paths and public evidence/... paths;
- versioned-module proliferation and how to preserve audit history without making the active implementation ambiguous;
- dependency locking and platform assumptions;
- API/CLI discoverability;
- test quality, untested branches, and missing coverage/type/lint/security checks;
- atomic file writes, concurrency, serialization, integrity checks, and replay resistance;
- deterministic regeneration of tables, figures, and result claims;
- hardware-free simulation and fake-adapter quality;
- documentation accuracy relative to code.

Return:
A. confirmed bugs or inconsistencies with exact file references;
B. architecture and maintainability risks;
C. a proposed target repository layout;
D. a migration plan that preserves frozen evidence and historical protocols;
E. a minimal public CLI design;
F. a CI matrix and quality gates;
G. the smallest pull requests that would most improve external reproducibility.

Do not propose deleting failed or superseded evidence. Distinguish archival code from the active supported path.
```

## Novelty and prior-art prompt

```text
Conduct a skeptical prior-art review of the research framing in:
https://github.com/katepkh/reachy-mini-abstention-first-attention

Use primary literature and official project sources. Cover at least:
- Reachy Mini DoA-driven look behavior;
- audiovisual active-speaker detection and localization;
- robot audition and sound-source tracking;
- selective prediction/reject options and risk-coverage evaluation;
- runtime assurance/Simplex-style control separation;
- HRI gaze, joint attention, turn-taking, and attention legibility;
- human authorization and consent for embodied systems, kept distinct from passive visual instructions and typed operator arming;
- privacy-preserving or data-minimized multimodal perception.

For each cluster, identify the closest work, summarize the overlap, and state what remains distinct here. Classify the repository's contribution as one or more of:
- novel algorithm;
- novel architecture;
- novel experimental finding;
- novel benchmark/protocol;
- system integration;
- safety case/failure case study;
- open-source reproducibility artifact;
- not yet distinct.

Do not infer priority from the repository title or narrative. Flag missing citations and terminology that established communities would challenge. End with the narrowest novelty statement you believe could survive expert peer review.
```

## Red-team prompt

```text
Try to falsify the strongest interpretation of this repository:
https://github.com/katepkh/reachy-mini-abstention-first-attention

Assume the authors may be unintentionally overfitting one room, one robot, one operator, and one set of measurement conventions. Find the simplest alternative explanations for every positive result.

Attack:
- source ownership inferred from geometry;
- temporal consensus under correlated samples;
- hard-negative completeness;
- face-detector state and boundary artifacts;
- DoA reflection and playback behavior;
- policy freezing and version selection;
- accepted/rejected trial handling;
- cue timing and experimenter effects;
- hash integrity as a substitute for correctness;
- software tests as a substitute for empirical validation;
- mechanical pose reconstruction;
- claims suggested by the architecture figure that are not supported by data.

Design ten adversarial tests ranked by expected information gain and safety. At least five must be passive. For every test, specify the failure hypothesis, variables, control, outcome, and what result would force the project to revise its central claim.

Conclude with a binary recommendation: SHARE NOW AS A RESEARCH PREVIEW, SHARE ONLY AFTER SPECIFIC FIXES, or DO NOT SHARE YET. Explain the decision without politeness padding.
```

## Robotics-company/startup review prompt

```text
Review this project as a robotics startup CTO evaluating a research/engineering candidate:
https://github.com/katepkh/reachy-mini-abstention-first-attention

Do not judge it as a finished product. Assess what the work demonstrates about the author's engineering judgment, experimental discipline, safety thinking, debugging ability, and communication.

Identify:
- signals of strong judgment;
- signals of overengineering or premature formalism;
- places where the implementation is fragile or too coupled to one machine;
- whether failure preservation and claim discipline are credible;
- what you would ask in a technical interview;
- what work would demonstrate production readiness;
- whether the repository is useful to your team today;
- whether the central framing has product value or mainly research value.

Return a hiring-signal assessment, an adoption assessment, the three strongest portfolio points, the three biggest credibility risks, and a 90-day project direction that would be impressive without exaggeration.
```

## GitHub and communication prompt

```text
Review only the public presentation and reviewer experience of:
https://github.com/katepkh/reachy-mini-abstention-first-attention

Assume the audience is an experienced robotics engineer with 5–10 minutes initially and 30–60 minutes if interested.

Assess:
- whether the first screen states the question, result, failure, and boundary;
- whether badges and figures add useful evidence or cosmetic maturity;
- whether the start-here path is obvious;
- whether result denominators could mislead;
- whether code entry points are discoverable;
- whether the repository is too large or historically noisy;
- whether the strongest negative result is easy to find;
- whether the reviewer can reproduce public claims quickly;
- whether the requested feedback is specific enough to receive serious responses;
- whether the Discord/LinkedIn framing would impress experts or trigger skepticism.

Return exact recommended edits in priority order. Rewrite the 100-word elevator pitch, the repository description, and a concise expert-group post. Keep every sentence within the currently supported claims.
```

## Short second-opinion prompt

Use this when the reviewer has limited time:

```text
Please give an unfiltered 15-minute technical review of this early-stage robotics research repository:
https://github.com/katepkh/reachy-mini-abstention-first-attention

Read README.md, docs/RESULTS.md, docs/FAILURE_LEDGER.md, and docs/LIMITATIONS.md. Then inspect at least one perception file, one cue-gating file, one motion-safety file, and scripts/verify_results.py.

Tell me:
1. what is genuinely interesting;
2. what is already known practice;
3. the strongest supported result;
4. the most damaging limitation;
5. any misleading wording;
6. the first code or evidence problem you found;
7. the single next experiment with highest information value;
8. whether you would share this with robotics colleagues, and under what framing.

Be specific and cite files. Do not equate 213 software tests with empirical validation.
```

## Suggested reviewer cover note

```text
I am sharing an early research preview, not a finished speaker-following system. The work asks when uncertain multimodal evidence should be prevented from crossing into robot motion. A hard negative showed that face/DoA alignment does not establish source ownership; two later passive protocols passed narrow frozen gates; the first physical 3° pilot failed and remains preserved as failed.

I would value a skeptical review of the scientific framing, experimental independence, code boundary, and whether the public evidence supports the README. The repository includes an external-review packet and role-specific prompts, but please challenge their assumptions rather than accepting them.

Repository: https://github.com/katepkh/reachy-mini-abstention-first-attention
Review packet: https://github.com/katepkh/reachy-mini-abstention-first-attention/blob/main/docs/EXTERNAL_REVIEW.md
```
