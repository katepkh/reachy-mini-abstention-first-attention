# Milestone matrix

Canonical status: **ACTIVE**
Last reviewed: **2026-10-09**

Allowed milestone states are `ABSENT`, `PROTOTYPE`, `PASS`, `FAIL`, and `BLOCKED`. `PASS` always applies only to the scope stated in that row; it does not imply end-to-end validation.

| ID | Required capability | State | Evidence and boundary | Exact next experiment or deliverable |
|---|---|---|---|---|
| M0 | Privacy-minimized evidence repository | PASS | Public evidence is numeric/media-free and integrity checked. This says nothing about robot behaviour. | Re-run the privacy scan immediately before any GitHub write. |
| M1 | Read local speech/DoA state | PASS | `reachy_doa/` and recorded trials support passive local DoA/speech acquisition in the studied setup. It is not speaker identity. | Exercise the same input through the future integrated shadow controller and record freshness/dropout behaviour. |
| M2 | Detect and geometrically track one visible face | PASS | Stage 2A/3V records support ephemeral one-face geometry within limited single-operator conditions. | Bind the detector output to an integrated attention-state interface and define loss/reacquisition behaviour. |
| M3 | Passive spatial compatibility with abstention | PASS | Stage 3V passed its 18-trial frozen horizontal holdout; Stage 2A also showed 13/63 false compatibility rows for a silent face plus separate phone speech. Compatibility is not source ownership. | Use phone-playback trials as mandatory hard negatives for the integrated decision layer. |
| M4 | Distinguish live visible speech from playback | PROTOTYPE | The earlier laptop-only candidate passed a small development/internal-validation pilot. No robot-camera discrimination result exists; earlier laptop attempts remain excluded. The separately frozen robot-camera pilot retains an external laptop microphone. | Collect the successor pilot under its new execution/private seal; compare activity-without-synchrony and hard-negative baselines. Do not infer liveness or fully robot-native audio. |
| M5 | One fused visible-speaker decision interface | PROTOTYPE | `fused_shadow.py` has zero authority. The sixth Reachy-camera commissioning capture passes unchanged observability gates: 16.99881 analyzed fps, 99.20% face/joint coverage, 100% valid DoA, p95 local frame age 159.45 ms. Five preceding failures remain failed. This is observability, not selection or fine-synchrony validation. See `ROBOT_CAMERA_COMMISSIONING.md`. | Resolve the audio/direction blocker: the two-pair attempt failed before capture. The corrected reader succeeded on both second transfers (64 then 0). Scoped close-out is reconciled with no deletion; the new-path unreleased candidate passed all 17 preflight checks. Successor `two-pair-v3-01` captured only Pair A quiet, then aborted at the playback-confirmation deadline. Routes and baseline restored, capture exited, 17 after-checks passed and both scoped close-outs finalized without deletion. No playback comparison exists. `two-pair-v3-02` then aborted before either pair at its preparation prompt, with no capture or routing writes; both scoped close-outs and 17 after-checks are verified. `two-pair-v3-03` captured only Pair 1 quiet, then aborted at the playback-confirmation deadline. Capture exit, restored routes, baseline equality and 17 after-checks are verified; both scoped close-outs are finalized without deletion. No playback comparison exists. `two-pair-v3-04` completed Pair 1 quiet and playback, then aborted before Pair 2 preparation was confirmed. Its incomplete result and first-pair measurements are preserved; capture exit, route restoration, baseline equality, 17 after-checks and both scoped close-outs are verified without deletion. `two-pair-v3-05` subsequently retained Pair 1 quiet plus 5.936 seconds of partial playback, then aborted with `unexpected_operator_input`. Its saved recovery/baseline and 17 after-checks pass; remote scoped files are expected, and local close-out is now finalized from the saved report and checked local inventory without deletion. Offline analysis retains v3-04's complete first pair and v3-05's partial evidence for inputs 0/1 without relabelling either run. Both paths vary without recorded clipping; approximately 2-3 dB playback-minus-quiet changes are descriptive, not calibrated SNR or a health pass. Inputs 2/3 remain unmeasured. Do not repeat inputs 0/1 by default. The subsequent `missing-pair-v3-01` attempt failed before capture or Play because the single-pair USB adapter still indexed an absent second pair. Its original failure is preserved; saved after-checks match baseline and scoped inventories contain only expected files. The operator-run reconciliation and local final review are complete: baseline equality was checked twice, all 17 after-checks pass, and both agreed scopes contain only expected numeric files, without deletion. A separate execution-blocked candidate fixes the adapter and single-pair guard completion, with direct fake-USB adapter regression tests; no hardware-health or new acquisition approval follows. Reconciliation changed only that failed run's numeric close-out; the original pending records and failure evidence are preserved. The corrected candidate itself remains undeployed and execution-blocked. The corrected `missing-pair-v3-02` attempt subsequently captured quiet only for inputs 2/3 and aborted at playback confirmation. Its failure remains preserved; capture exit, restored routes, baseline equality, 17 after-checks and both scoped close-outs are verified without deletion. Inputs 2/3 still lack playback measurements. The distinct `missing-pair-v3-03` attempt also stopped at playback confirmation with quiet-only input-2/3 data. Recovery, baseline equality, all 17 after-checks and both scoped close-outs are verified, with no deletion. Its result remains aborted; no key-arrival timestamps establish the cause. An offline queued-input/deadline ordering weakness is reproduced, not proven as the cause of that run. The keyboard-only SSH probe subsequently acknowledged both Enter presses with exit status zero and no audio/settings/device changes or remote installation. This does not establish the historical capture failure's cause. A separate execution-blocked input candidate now observes terminal input independently, preserves queued on-time observations through main-loop delay and records bounded numeric timing/failure diagnostics. Offline tests exercise real local reader-thread I/O plus simulated capture/guard faults; Linux PTY/capture-load behavior remains unverified. All measurement, confirmation and restoration limits and earlier measurements are preserved. No new live launcher, deployment or acquisition capability is issued. Do not reuse spent launchers. Resume the unchanged robot-camera pilot only after readiness and geometry are demonstrated; freeze development selection before internal validation. |
| M6 | Reject silent-person plus phone playback end to end | BLOCKED | Zero robot-camera pilot trials accepted; no playback discrimination or robot action is validated. Laptop v1/v2 material cannot substitute for the new sensor path. | Evaluate the new no-motion pilot's live/phone/mouthing/control conditions. Physical integration remains subject to M7–M9. |
| M7 | Safe bounded physical orientation | FAIL | The only supervised 3° V3 trial failed target and return tolerances. Later V4 work remained blocked; a read-only successor trace observed `UNSET` targets and did not validate motion. | Define and independently review one baseline-relative, one-leg motion protocol with numeric abort limits before any new command. |
| M8 | Face-directed attention hold | PROTOTYPE | `attention_hold.py` now defines replay-only image-region, dwell, freshness, loss, bounded-correction, and oscillation behavior with zero command authority. Its engineering defaults pass synthetic tests but have consumed no real track and are not physically validated. | Replay the contract on real joint observations, revise only as commissioning work, then freeze before any physical hold test. |
| M9 | Audible response attributable to accepted live speech | ABSENT | The shadow state machine proposes one deterministic acknowledgement only after attention is held, but it emits zero audio commands. No end-to-end output, STT/dialogue/TTS path, or response evidence exists. | After M5–M8 pass their gates, implement one local response adapter behind the explicit permission boundary and verify abstention produces no output. |
| M10 | Single end-to-end controller | PROTOTYPE | `interaction_shadow.py` orders selection, reported orientation, bounded hold, and deterministic acknowledgement in a fault-latched state machine with all side effects stubbed. It has not consumed joint real evidence or driven a robot/audio output. | Feed commissioned M5/M8 replay evidence through the state machine, add a guarded M7 adapter only after M7 passes, and keep M9 output stubbed until separately tested. |
| M11 | End-to-end held-out validation and baselines | BLOCKED | No valid integrated result exists. The frozen 54-trial confirmation is paused because its recorder lacks acoustic direction and required Stage 3V inputs. | Build M10 and verify endpoint identifiability before freezing a new final protocol with DoA-only, visual-only, activity-without-synchrony, synchrony-only, non-abstaining, abstaining, and strongest-feasible learned audiovisual baselines. |
| M12 | Research manuscript | PROTOTYPE | A working evidence manuscript exists, but it describes incomplete component studies and is not a completion or submission-readiness claim. | Update only when a milestone changes or a claim audit requires it; do not prioritize presentation over M5–M10. |
| M13 | Defensible differentiated research claim | BLOCKED | The broad behaviour and its individual techniques have substantial prior art. A narrower playback-resistant, privacy-minimal, abstention-first composition remains a hypothesis, not a proven novelty claim. | Complete M10–M11, rerun the prior-art search, and compare against the baselines in `NOVELTY_CLAIMS_LEDGER.md`. |
| M14 | Publication gate for the reviewed development checkpoint | PASS | The 2026-10-09 development-only update has an explicit publication decision and passed strategy, outgoing-history privacy/content, frozen-evidence, generated-artifact and offline software reviews. It preserves the sanitized public ancestor and excludes private run/approval records and raw media. This is not research-completion or submission readiness. | Complete the normal fast-forward upload and verify GitHub's head. Review future changes separately; return to the unresolved M5-M6 reporting/sensor blocker. |

## Current critical path

Latest M5 evidence review (2026-10-09): the 2026-10-08 automatic no-audio
Linux check returned SSH exit zero, but the local validator rejected its report
and retained only `CONNECTION_OR_RESULT_UNVERIFIED` plus source/status metadata.
Detailed Linux and cleanup success remain unverified; preserve the spent run
and investigate the reporting path offline. The preceding local suite reported
155 passed and three skipped tests. No new capture, routing, motion, pilot
collection or hardware-health pass follows. The earlier preparation-only
statements below are historical, not instructions to repeat the check.

Latest M5 preparation update (2026-10-08): a separate execution-blocked
counts-only observation candidate is prepared offline. It adds fixed-size
read/selector/thread progress, byte-class/event counts and read-only terminal
metadata, preserving the old parser, acquisition limits, abort rules and all
old helpers/run records. 143 tests pass with two POSIX-only skips; an
unaccelerated generated-sample run also completes. There is no live launcher,
deployment, new acquisition capability or hardware access. The historical
failure remains unexplained; verify Linux behavior without audio before any
live release. No milestone state is promoted.

Earlier M5 investigation update (2026-10-08): the exact-reader keyboard check
acknowledged both Enter paths; one normal LF and unchanged terminal flags are
reported. The preserved reader and capture loop now also pass a combined local
synthetic-sample exercise, including blocked status checks, CPU work and one
unaccelerated full-count case. This does not reproduce the actual robot abort
or establish its cause. The old empty-event log cannot distinguish missing
bytes from unavailable observation. No microphone access, robot connection,
live-helper edit or new acquisition capability occurs during investigation.
Review bounded input-path instrumentation offline before another live attempt;
real Linux/capture-child behavior and inputs-2/3 playback remain unverified.
No milestone state is promoted.

Earlier M5 input update (2026-10-08): `missing-pair-v3-05`'s reviewed connection
replacement captured quiet only, then reported no observed Enter event.
Playback for inputs 2/3 is still missing. Restoration, capture/reader exit,
baseline equality, all 17 after-checks and both scoped close-out reviews pass,
with no deletion and all original records preserved. Stop microphone retries;
the prepared one-shot keyboard-only probe now uses the exact raw-byte reader
after input(), with unchanged-byte CR/LF counters and read-only terminal flags.
89 offline tests pass with one POSIX skip. A lone-CR observation gap is reproduced
synthetically, not established as the live failure's cause. No hardware access
or robot connection occurred during this preparation, and no new acquisition
capability is issued. All pilot and physical-behavior milestones are unchanged.

Earlier M5 transport preparation (2026-10-08): the approved `missing-pair-v3-05`
attempt timed out before SSH login, with no diagnostic capture or routing.
Its four original records remain intact. Local metadata review is complete;
the exact remote-path after-check remains pending. A subsequent status read
succeeds with motors disabled but does not clear that file check. One separately
latched connection-timeout replacement is prepared using the unchanged helper,
with exact remote absence, all predecessor checks and fresh readiness required
before execution. 256 tests pass with four POSIX skips. No new execution
capability is issued by this preparation; no recording, sleep or connection
occurred during it. Inputs 2/3 playback and pilot readiness remain unproven.

Current M5 preparation update (2026-10-08): `missing-pair-v3-04` stopped at
authentication; its reviewed login replacement then stopped at motor-mode
preflight, both before diagnostic capture/routing. A separately supervised
stock sleep is observed complete. The subsequent read-only report passes all
17 checks, matches baseline audio settings and reports the old robot run
directory absent. Local scoped after-review is complete without deletion;
the separate final receipt preserves the original pending/failure records.
`missing-pair-v3-05` is prepared for inputs 2/3 only, with unchanged input,
capture and recovery code, nine completed predecessor scope checks and an
additional pinned no-capture predecessor review/fresh absence check. Offline
tests pass (237 passed, four POSIX skips); no new acquisition capability is
issued. No robot connection, sensor access or settings changes occurred during
preparation. Capture-load behavior, microphone health and fresh physical/client
readiness remain unverified. The unchanged pilot has zero accepted trials;
no milestone state is promoted. After specific scoped approval and fresh live
checks, complete only inputs 2/3, then restoration/scoped close-out and pilot
readiness. Do not repeat inputs 0/1, spent attempts or stock sleep by default.

`M5 joint-input instrument → M6 phone-playback rejection → M7 bounded orientation → M8 attention hold → M9 gated response → M10 integration → M11 held-out validation → M13 claim review`

The 54-trial confirmation study and further manuscript polishing are not the current critical path. The confirmation design may later supply part of M11 after its inputs and estimands are repaired, but collecting the present design would consume time without identifying all frozen primary endpoints.
