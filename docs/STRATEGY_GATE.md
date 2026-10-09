# Strategy gate

Canonical status: **ACTIVE**
Last reviewed: **2026-10-09**

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

1. **Integrate in shadow mode:** build one deterministic decision orchestrator over existing sensing/proposal components, with motion and response outputs stubbed. **Software contract complete; joint decision unvalidated.**
2. **Instrument the joint decision:** capture DoA/spatial geometry, face track, lip synchrony, capture age, buffering/processing delay, dropped samples, and availability on one browser clock without raw-media retention or robot commands; do not pair unrelated historical trials. **Real observability commissioning passed.**
3. **Close the real sensor boundary:** **Scoped observability PASS on the sixth 2026-10-01 capture**, with 16.99881 analyzed fps and 99.20% face/joint coverage. Five earlier failures remain preserved. Corrected frame age includes conversion but not upstream exposure/network/decode latency. Fine synchrony and selection remain unvalidated; laptop audio remains an external reference. Laptop-camera v2 stays paused with zero accepted trials.
4. **Attack the central hard negative:** the separately fingerprinted robot-camera no-motion pilot is now frozen, with live speech, silent-face phone playback, silent mouthing with unrelated playback, missing-face and spatial-conflict controls. Require its execution/private seal and microphone match before collection. Freeze development selection before opening validation; retain every failed attempt and activity-without-synchrony baselines.
5. **Repair the physical action path:** define one baseline-relative outward leg with numeric abort thresholds and no automatic return after failure; review before hardware use.
6. **Add bounded attention hold:** implement face-error, dwell, loss, update-rate, and oscillation limits before response generation.
7. **Gate a minimal response:** a response is permitted only after a live-speaker selection; abstention produces no conversational response.
8. **Integrate and validate:** freeze an end-to-end trial protocol only after every endpoint is measurable; compare with the required baselines.
9. **Then synthesize the paper:** update claims, figures, and manuscript after the evidence exists.

## Current gate assessments

2026-10-09 development checkpoint review: advance M14 by preserving the
implementation, tests and honest status of M5-M10 in the existing public
research repository under the explicit publication request. This is bounded
research infrastructure, not manuscript polishing or an end-to-end result.
It temporarily displaces offline report repair, then returns to the M5-M6
critical path. D007/D010/D012 and all hardware/recording gates remain in force.
Review the complete unpublished history and new files for private content,
preserve the sanitized public ancestor, exclude private run/approval records
and raw media, run offline evidence/software/generated-artifact checks, and
verify the remote commit after a normal fast-forward push. Stop for privacy
findings, failed verification, unexpected remote changes or missing authority;
never force-push or alter a frozen experiment to obtain publication. This supersedes the historical
blanket publication-defer row only for this reviewed development checkpoint,
not for future releases or research-completion claims. No robot is contacted.

Review outcome: the outgoing history remains descended from sanitized public
commit `2c6f50b`; the reviewed index contains no private run/approval files or raw
media. Personal filesystem paths were removed from explanatory documentation.
All 171 frozen evidence-source checks and the offline generated-artifact gates
pass. The Windows suite ran 1,977 tests (1,964 passed, 13 platform-dependent
skips); 24 JavaScript unit tests passed. Frozen CRLF evidence bytes are retained,
with diff whitespace review treating CR as a line terminator rather than
rewriting evidence. M14's development-publication gate passes; the upload still
requires normal fast-forward success and independent remote-head verification.
This review does not resolve the failed Linux report, prove the historical
Enter failure's cause, or authorize another robot/microphone run.

2026-10-08 no-audio Linux verification preparation: remove the M5-M6 input
observability blocker with one automatic, operator-run software check. Send only
source-pinned reader/statistics/capture-loop definitions and a synthetic harness
in memory; never deploy the complete command-capable helper. Exercise isolated
generated terminal input and generated integer samples through real Linux pipes
and an owned, bounded Python child. Stub hardware/guard checks explicitly.
No phone playback, timed operator input, sensor access, routing, robot API,
settings change, remote file installation or acquisition authority. Preserve
all old sources and close-outs. No higher-value task is displaced and
D026/D029/D030 remain unchanged. Complete local regression/source/transport
tests and prepare a one-use launcher; Linux results require operator execution
and review. Stop for source drift, unbounded resource use, failed cleanup or
scope expansion. Success can establish only synthetic Linux compatibility,
not microphone health, physical-keyboard behavior or historical causation.

2026-10-08 counts-only instrumentation preparation: advance the M5-M6 input
blocker with a separate execution-blocked candidate, not another robot attempt.
Add bounded raw-read class counters, selector/reader progress, event timing and
read-only terminal/foreground metadata so a future reviewed result can separate
no observed bytes from unrecognized input or stalled observation. Retain no
typed contents, passwords or raw media. Preserve recognition, confirmation,
capture and restoration behavior and every old source/run. No higher-value
task is displaced; D026/D029/D030 remain unchanged. Complete source-diff,
privacy and synthetic fault/integration tests offline. Stop for behavioral
drift, unbounded logging, raw-content retention or a need for device access.
No deployment, acquisition capability, new live launcher or hardware claim.

Offline completion: a distinct execution-blocked candidate embeds the bounded
counts-only observer and wraps the unchanged input parser. Four fixed snapshots
record read/selector/thread progress and read-only terminal/foreground metadata;
typed contents and passwords are not recorded. Capture instrumentation hooks
leave original parsing, prompts, timing, sample counts and abort/cleanup logic
unchanged. 143 tests pass, two POSIX-only tests skip; one unaccelerated synthetic
run also completes. Old helper/launcher and original run receipts are preserved.
No deployment or acquisition authorization is issued. Historical causation and
Linux real-capture behavior remain unknown; review no-audio Linux verification
before considering live release. This does not advance any milestone to PASS.

2026-10-08 offline capture/input investigation: advance the M5-M6 blocker
after the exact-reader keyboard-only check acknowledged both input paths.
Inspect and reproduce the preserved diagnostic's full input/capture interaction
with synthetic input and fake capture only. Produce regression evidence and a
bounded diagnosis, not a live-helper repair or acquisition release. No
higher-value task is displaced; D026/D029/D030 and all timing, restoration,
privacy and physical-action gates remain unchanged. Preserve old sources and
run records. Stop at source drift, a need for robot/audio access, or an
unreproduced hypothesis; do not infer historical causation from a simulation.

Offline completion: 98 focused tests pass, one POSIX-only test skips. The
preserved capture loop and exact reader run together against generated samples,
real local threads/selectors and explicit capture/status stubs. Normal input,
blocking status and CPU work do not reproduce the failed robot attempt. One
unaccelerated case also completes the unchanged 48,000/160,000-frame counts.
Missing input, CR-only input and a deliberately unavailable reader all produce
the old empty-event failure, illustrating missing diagnostic observability,
not establishing the historical cause. No WSL installation, robot connection,
audio access, live-helper repair or acquisition release occurred. Recommend
bounded counts-only instrumentation review before any further live attempt.

2026-10-08 exact-reader keyboard investigation: advance the M5-M6 input
blocker without another microphone attempt. The replacement captured quiet
only and recorded no observed Enter event. Restoration, capture/reader exit,
baseline equality, all 17 after-checks and scoped close-out are verified;
all original records and the aborted result remain preserved. A local byte
test shows the unchanged reader ignores a lone CR, but this is not evidence
of the bytes or physical keypress timing during the robot attempt. Prepare one
keyboard-only probe with the exact source-pinned reader class, unchanged-byte
read counters and read-only terminal flags. Preserve the input()-to-reader
handoff and console transport; allow two minutes per prompt. No microphone,
USB, robot API, routing, process launch or file installation on the robot.
Keep numeric metadata only; no key contents or passwords. No higher-value work
is displaced; D026/D029/D030 and all acquisition limits remain unchanged.
Stop for source drift, unsupported terminal, errors or uncertain reader exit.
Success would establish only this keyboard path without capture load, not
historical causation, microphone health or permission for another diagnostic.

Offline completion: the keyboard-only payload extracts the byte-identical
reader class from the preserved helper, uses the same SSH console options and
adds counts-only instrumentation without translating bytes. Tests distinguish
LF/CRLF recognition, ignored CR, no bytes, text, duplicates, EOF, reader faults,
terminal drift, source drift and spent local attempts. 89 tests pass, one POSIX
case skips. No robot connection, probe run, microphone release or settings
change occurred during preparation. Numeric results remain on the operator
console; only status/source metadata is saved locally, without passwords/text.

2026-10-08 connection-timeout replacement preparation: support the M5-M6
inputs-2/3 blocker without repeating inputs 0/1 or changing the measurement.
The operator console shows the `missing-pair-v3-05` connection timed out before
login; its four local numeric records stop at deployment. A subsequent status
read succeeds with motor mode disabled, but is not a scoped file after-check.
Review local metadata and preserve all original records; keep remote close-out
pending until exact helper/capability/run-path absence is checked. Prepare one
separately latched, separately authorized replacement using the identical helper
and existing predecessor/readiness/live-confirmation gates. No higher-value work
is displaced; D026/D029/D030 and M7 remain unchanged. Stop on changed evidence,
unexpected or inaccessible paths, failed tests or missing new scoped approval.
Local preparation connects to nothing and grants no capture, routing, motion,
deletion, pilot or publication authority. No hardware-health claim follows.

Offline completion: one source-bound connection-timeout replacement is prepared
without a new capability. The original four files and helper remain unchanged;
the private review records local metadata and explicitly pending remote absence.
256 tests pass with four POSIX skips, including missing-approval/spent-session,
preflight rejection and exact remote-path guards. No timing limit is changed.

2026-10-08 post-preflight successor preparation: advance M5-M6 by finalizing
the reviewed no-capture `missing-pair-v3-04` close-out and preparing one new
inputs-2/3-only identity. The operator's saved after-report passes all 17 checks,
matches baseline audio settings, reports the old remote run directory absent
and matches the expected local metadata. Preserve both failed attempts and the
original pending record; a separate final receipt must describe no capture,
not fabricate a completed remote diagnostic. Preserve the completed stock-sleep
result without repeating it. Use the unchanged input, capture and restoration
code, nine completed remote predecessor checks, plus an explicit fresh absence
check for this pre-capture predecessor. No higher-value task is displaced;
D026/D029/D030 and M7 remain unchanged. Stop for source/inventory drift,
uncertain close-out, failed offline tests or absent fresh scoped permission.
Preparation grants no acquisition/routing authority, makes no robot connection
and establishes no microphone-health, pilot or end-to-end result.

Offline completion: the no-execution final receipt is saved separately and
all original failure files remain byte-identical. The new `missing-pair-v3-05`
helper changes only its fixed session/capability identity; every function and
class body is preserved. The launcher retains the nine completed remote scope
checks and additionally validates the pre-capture predecessor receipt/evidence
and fresh remote absence. 237 focused tests pass with four POSIX skips. The
private preparation record records proposed scopes only; no execution approval
or before-inventory is issued. Final stock-sleep observations are preserved;
no further sleep, motion, recording, routing or deletion occurred here.

2026-10-08 stock-sleep login replacement: the second sleep attempt's console
shows SSH authentication denial before remote execution; its unchanged journal
contains only the local pending event. A subsequent login-only check succeeded,
but does not establish why the preceding authentication failed. Prepare one
separately authorized, separately latched replacement using the byte-identical
D031 remote routine. Bind the original failure journal and private evidence
review; preserve every earlier launcher, authorization and journal. This removes
the M5-M6 readiness blocker without displacing higher-value work or changing
motion, privacy or research gates. Fresh live confirmation and machine checks
still precede at most one sleep request. Stop on drift, existing replacement
journal, failed checks or uncertain outcome; no automatic retry or recording.
The microphone attempt's scoped close-out remains pending and is not cleared
by sleep success. No robot connection occurs during this offline preparation.

2026-10-08 second stock-sleep preparation: remove the M5-M6 readiness blocker
using the unchanged D031 routine under a new one-use session. The microphone
login replacement reached read-only preflight: 16/17 checks passed, but disabled
motor mode was not verified, so no diagnostic capture or routing occurred.
A subsequent operator status read explicitly reports enabled motors. Preserve
the completed first sleep journal and both stopped microphone attempts; the
reason motor mode changed is unknown. Prepare only supervised stock sleep and
status verification, not another microphone attempt. No higher-value task is
displaced; no M7 or microphone-health claim follows. Stop for source/approval
drift, failed fresh checks, an existing journal or an uncertain outcome. No
automatic retry, wake, backend toggle, deletion or recording is authorized;
the microphone attempt's final scoped close-out remains pending.

2026-10-08 reviewed login-failure replacement: advance M5-M6 without changing
the diagnostic. The operator console reports authentication denial, and the
source-bound local records stop at deployment with no execution. Preserve
all four original records and the spent launcher. Review local metadata;
require explicit remote absence of this session's helper, capability and run
directory before a separately latched replacement can deploy. Reuse the same
byte-identical helper, nine predecessor checks, agreed inventory scopes and
fresh live setup/readiness gates. No higher-value task is displaced and no
threshold or D026/D029/D030 boundary changes. Stop for changed failure evidence,
an existing replacement latch, any unexpected remote path or interrupted
outcome; no automatic retry, deletion or remote action during preparation.

2026-10-08 remaining-pair preparation: advance the M5-M6 signal-path blocker
with one new inputs-2/3-only session using the independently observed input
candidate. The reviewed operator preparation passed all five synthetic Linux
terminal checks, all 17 machine checks and nine predecessor scope checks;
that does not validate input handling under capture load or microphone health.
Preserve all old helpers, results, scopes and limits. Prepare a separately
identified helper/launcher and proposed private inventory scope, without
issuing acquisition authorization, connecting or recording. No higher-value
work is displaced; D026/D029/D030 remain unchanged. Stop for source/report
drift, unresolved close-out, failed tests or any need for broader permission.
Fresh scoped approval and live setup/machine checks still precede acquisition.

Offline completion: `run_reachy_mic_input.py` prepares `missing-pair-v3-04`
with a new fixed helper, source-bound prerequisite and ninth close-out receipt.
All helper function/class bodies remain identical to the tested candidate;
143 focused tests pass and three POSIX cases skip on Windows. No capability
has been issued and no new diagnostic run, robot connection or recording has
occurred during preparation. Earlier Linux-preparation-pending statements are
historical: the reviewed operator report now passes synthetic terminal and
machine checks, not microphone acquisition or physical keyboard timing.

2026-10-08 stock-sleep preparation: advance the M5-M6 microphone readiness
blocker using the unchanged D031 stock-sleep routine under a distinct fixed
session and private one-attempt authorization. Preserve the old source and
spent journals. Fresh physical-daemon/media/error, motor-mode, state, app-slot
and movement checks remain mandatory; no command if already disabled. This
is a supervised stock lifecycle action, not an M7 experiment or microphone
release. No higher-value work is displaced. Stop on source/approval drift,
an existing new journal, unknown state or interrupted outcome; no automatic
retry, recovery motion, backend toggle, update, capture or routing writes.
Return the resulting journal for review before the prepared no-audio check.

2026-10-03 staged return to pilot: advance M5-M6 by preparing a new inputs-2/3
attempt from the tested input candidate, with automated no-audio Linux-PTY
verification and read-only readiness before any acquisition. Reuse inputs-0/1
evidence and preserve every old helper/receipt. Prepare collection/review tools
and assess the unchanged pilot's offline bindings, but do not start the pilot
or motion from software tests or blanket permission. Live setup, fresh status,
source-bound preparation results and one-shot scope must be satisfied first.
No higher-value task is displaced; D026/D029/D030 and all limits remain intact.
Stop at missing evidence, changed inventories, failed terminal/readiness checks
or unconfirmed physical conditions. Exact-path deletion and robot-return checks
remain separate; approval details stay private.

Offline preparation is implemented as `prepare_reachy_mic_input.py`: pinned
source, all nine predecessor checks, isolated synthetic terminal self-check,
new-path unreleased helper copy and the existing read-only machine checks.
It stops with a private report, never proceeds to acquisition and has no
automatic retry. Linux evidence is still pending operator execution. The
unchanged pilot's saved binding verifies with zero accepted trials; this is
not current physical readiness. The next live microphone scope remains inputs
2/3 only and requires review of preparation plus current setup, followed by
result/restoration and scoped ordinary-file close-out before pilot readiness.

2026-10-03 offline input correction: the keyboard-only probe acknowledged both
input APIs; this does not establish the old capture failure's cause. Advance
M5-M6 with a separate execution-blocked candidate that observes terminal input
independently, records bounded numeric receipt/processing timing, and checks
queued on-time events before classifying expiry. Keep capture, guard, routing,
restoration and confirmation limits unchanged. Test late/early/duplicate input,
reader faults, cleanup and stalled-loop cases without hardware. Preserve all
old helpers, reports and permissions. No higher-value task displaced; no pilot
or new acquisition release. Stop for unverified reader exit, timing ambiguity,
source drift or a need to change a frozen limit. D026/D029/D030 stand.

Offline completion: the separate candidate now uses an independently observed,
timestamped input queue with an atomic expiry snapshot. Its 49 focused tests
complete with 48 passes and one Windows-inapplicable POSIX-PTY skip, including
queued-input races, reader failures, capture cleanup and parent restoration.
Original helper/probe hashes and all non-capture function/class bodies remain
unchanged. No live launcher, permission or deployment was issued. Linux
PTY/capture-load behavior and the historical failure's cause remain unverified.

2026-10-03 keyboard-path investigation: advances M5-M6 by isolating terminal
confirmation from microphone acquisition. Prepare one bounded keyboard-only
SSH probe using the existing interactive stdin path, with two clearly labelled
Enter prompts and numeric outcome metadata. Install nothing remotely; open no
audio, robot API, USB, route, motor or settings interface. Preserve every spent
helper and run. Test deadline ordering and timing diagnostics offline; boundary
reproduction is not proof of the historical failure's cause. No higher-value
task is displaced; D026/D029/D030 remain unchanged. Stop for unexpected state,
input-path failure or scope expansion. No new recording capability is issued.

2026-10-03 speaker-confirmed replacement: `missing-pair-v3-02` is aborted
quiet-only evidence, not a playback or health result. Saved restoration,
baseline equality, capture exit, all 17 after-checks and both scoped inventories
are reviewed; local finalization preserves the original pending record and
failure, without deletion or robot connection. Prepare `missing-pair-v3-03`
for inputs 2/3 only with all eight predecessor checks. Add audible phone-speaker
confirmation to the existing live start, not another timed action. All capture
and restoration limits stay unchanged; no inputs-0/1 repeat or pilot release.
This advances M5-M6 with no higher-value task displaced; D026/D029/D030 stand.
Stop for evidence drift or uncertain live setup. Private one-attempt permission
is separate from the scope of this offline evidence review.

2026-10-03 corrected missing-pair successor: prepare `missing-pair-v3-02` for
inputs 2/3 only, advancing the M5–M6 signal-path blocker without repeating
inputs 0/1. Use the tested adapter repair, preserve all seven closed predecessor
records and old source hashes, and retain the existing capture/guard/restoration
limits. Produce one private-authorization-gated launcher, not a health result
or standing execution approval. No higher-value task is displaced. Stop for
changed records, failed tests, missing scoped approval or uncertain live setup.
No robot connection or acquisition is part of this offline preparation.

2026-10-03 reconciliation review: finish the authorized M5–M6 close-out from
the saved source-bound report and local metadata only. Preserve the failed
diagnostic and original pending records in the final receipt; no new robot
connection, recording, deletion or execution release. No higher-value work is
displaced. Stop for mismatched identities, incomplete checks or unexpected files.

2026-10-03 adapter repair: advances M5–M6 by fixing and directly testing the
one-pair USB adapter offline and reviewing the failed run's numeric close-out.
No higher-value task is displaced. Preserve D026/D029/D030, all spent helpers
and failure records, and every capture/recovery limit. Produce an unreleased
candidate, not acquisition approval or a hardware-health result. Stop for
inconsistent evidence or any unapproved live action. The robot's pending
close-out required fresh metadata-only reconciliation, now observed successful
in the operator's source-bound report and mirrored locally. No gate was cleared
from inference alone; all 17 fresh after-checks passed.

2026-10-02 update: D027–D028's diagnostic collections are complete, not standing
permission to repeat. Their unresolved audio/direction question leads to the
D029–D030 microphone-helper preparation. V2 deployment/preflight completed with
16/17 checks passing initially. D031's separately supervised stock sleep was
observed completed; after intermittent connectivity and ordinary restart,
fresh preflight passes all 17 machine checks, including disabled motors. A
one-attempt operator launcher with private pending/mirrored close-out was
used for the separately approved D030 attempt. It failed at guard startup
before capture (`guard_EOF`); suppressed child stderr leaves its cause unknown.
Original routes/parameters matched afterward, but close-out initially remained pending.
The completed read-only probe observed vendor retry status 64 on both direct
USB reads; v2 incorrectly treats it as fatal. A separate local candidate adds
bounded status-64 read handling and structured errors. After the first
transport timed out before login, its separately logged replacement succeeded:
both reads returned 64 then 0, with baseline and inventory unchanged. The local
close-out review and remote reconciliation are complete, with no unexpected
files in the agreed scopes and no deletion. The failed result is preserved;
only its separate close-out record was reconciled. The exact unreleased
candidate is installed at its new path and all 17 preflight checks passed.
The local final review mirrors that result without reopening any one-shot
record. The separately identified `two-pair-v3-01` successor and launcher are
now prepared offline with a private approval gate and independent one-shot
scope. It subsequently collected the first pair's quiet phase, then aborted
at the playback-confirmation deadline. No playback phase or second pair was
measured. Guard restoration and capture exit are verified; all 17 after-checks
pass with baseline settings unchanged. Both scoped close-outs are finalized
with no unexpected files or deletion. Preserve the incomplete result and spent
session. The separate `two-pair-v3-02` successor then passed preflight but
aborted at first-pair preparation without capture or routing changes. Its
17-check after-report and unchanged baseline are verified; both scoped file
checks are finalized with no deletion. The separately approved `two-pair-v3-03`
used the single start acknowledgement, captured only Pair 1 quiet and stopped
at the ten-second playback-confirmation deadline. Routes, capture exit and all
17 after-checks are verified; its scoped close-out is finalized locally from the
saved numeric report and checked local inventory, with no deletion or robot
connection. The separately approved `two-pair-v3-04` completed Pair 1 quiet and
playback, then aborted before Pair 2 when preparation was not confirmed. Its
first-pair data and incomplete overall result remain preserved. Capture exit,
route restoration, baseline equality and 17 after-checks are verified; both
scoped close-outs are finalized with no deletion. The separately approved
`two-pair-v3-05` then captured Pair 1 quiet and 5.936 seconds of partial playback
before `unexpected_operator_input`. Neither attempt measured inputs 2 and 3.
Its saved records verify recovery, unchanged baseline and 17 after-checks;
remote scoped files are expected. Local close-out has now been finalized from
the saved numeric report and checked local inventory, with no deletion; the
original pending record and all failure data remain preserved.
The offline review retains v3-04's complete first pair and v3-05's labelled
partial evidence. Inputs 0 and 1 are varying, non-identical and unclipped in
the measured phases, with approximately 2-3 dB descriptive level increases;
this is not calibrated SNR, an all-microphone health pass or a DoA diagnosis.
Do not repeat the measured pair by default. If all-four-path coverage remains
necessary, separately review only missing inputs 2 and 3. The subsequent
`missing-pair-v3-01` preparation now restricts the guard to that single pair
and removes the between-pair prompt. Measurement, timeout and restoration
limits remain unchanged. It requires a private scoped capability, fresh
machine checks and explicit physical/client confirmation in the live terminal.
No robot connection or acquisition occurred during preparation. The authorized
attempt subsequently failed before capture/Play: the USB adapter still indexed
an absent second pair. The saved after-check matches baseline; only the run's
pending close-out blocks preflight. The old failure remains preserved. A new
execution-blocked candidate repairs the adapter cardinality and single-pair
guard completion, with direct fake-USB adapter regression tests. The operator's
exact-run metadata reconciliation succeeded: baseline equality was checked
twice, all 17 after-checks passed, and only the numeric close-out record changed.
Local final review verifies the source bindings and scoped inventories; both
close-outs are complete without deletion, with original failure records kept.
The corrected candidate remains undeployed and execution-blocked. The separately
prepared `missing-pair-v3-02` session takes that same repair into a one-attempt
private-authorization-gated helper and launcher; all seven predecessor
close-outs and the reconciled record are checked. No acquisition occurs during
preparation, and no standing recording permission or robot-health result follows.
Approval details remain outside Git. Stop for changed or
unavailable state; there is no automatic retry or gate relaxation.
Preserve all frozen pilot files; accepted trials remain
zero. The historical proceed rows below do not reopen completed diagnostics.

| Candidate task | Gate result | Reason |
|---|---|---|
| Close missing-pair-v3-02 and prepare a speaker-confirmed replacement | **PROCEED OFFLINE; ONE NEW INPUTS-2/3 SESSION ONLY** | Advances M5-M6 without repeating inputs 0/1. Preserve the aborted quiet-only result and user-reported stimulus-output issue privately; verify saved restoration and both scoped inventories before a new identity. Fold phone-speaker confirmation into the existing start acknowledgement, with no new timed action or changed acquisition/recovery limits. D026/D029/D030 unchanged; no higher-value work displaced. Stop for inconsistent evidence or live setup uncertainty. No robot connection during preparation, pilot reopening or health claim. |
| Prepare corrected missing-pair-v3-02 session | **ONE-ATTEMPT SOFTWARE PREPARED; FRESH LIVE GATES REQUIRED** | Inputs 2/3 only; preserve earlier measurements and every old helper. Direct adapter and guard/transport tests cover the repaired build. Require matching private capability, all seven scoped predecessor checks, fresh preflight and live setup confirmation. No sensor/robot access during preparation, no automatic retry or changed acquisition limits. |
| Repair missing-pair adapter and review its pre-capture failure | **OFFLINE REPAIR TESTED; SCOPED CLOSE-OUT COMPLETE** | Exact-run reconciliation verified baseline equality twice, all 17 after-checks and expected numeric files. The original failed helper/result and pending records remain preserved; no deletion. Corrected candidate remains undeployed and execution-blocked; no acquisition, hardware-health or robot-return release. |
| Close out v3-05 and prepare only missing microphone inputs 2/3 | **SCOPED CLOSE-OUT COMPLETE; ONE-PAIR SOFTWARE PREPARED** | Advances M5-M6 without repeating inputs 0/1. Preserve all results, old helpers and spent sessions. Limit the new guard to one pair, retain existing acquisition/recovery deadlines and all six predecessor checks, and require live setup confirmation. Private approval is separate from software preparation. Stop for changed/unknown state; no pilot, motion, calibration, hardware-health or publication claim. |
| Analyze and retain v3-04/v3-05 rather than repeat the full diagnostic | **OFFLINE REVIEW COMPLETE; FIRST-PAIR EVIDENCE RETAINED** | Advances the M5-M6 audio blocker with verified numeric summaries and explicit coverage limits. V3-04 provides one complete quiet/playback pair for inputs 0/1; v3-05 adds partial evidence for the same inputs. Inputs 2/3 remain unknown. No threshold changes, merged trials, new helper, robot connection or acquisition. Preserves D026/D029/D030 and all original records; no higher-value work displaced. Stop for inconsistent evidence. Local v3-05 close-out and final robot-return check remain outstanding; no pilot or hardware-health pass follows. |
| Close out v3-04 and prepare a prominent Pair-2 prompt in v3-05 | **PROCEED OFFLINE; NO NEW ACQUISITION APPROVAL** | Supports the M5–M6 audio blocker by preserving the completed first-pair measurements and the second-pair preparation abort, verifying recovery and scoped inventories, and making the existing readiness action prominent in a new session. Display text only; no extra sound, repeated prompt, capture, routing, preparation-time or recovery-limit change. D026/D029/D030 unchanged, no higher-value task displaced. Stop for inconsistent records, changed old identities or any unapproved live action. |
| Explicit-confirmation session `two-pair-v3-04` result review | **FIRST PAIR COMPLETE; OVERALL ABORTED; SCOPED CLOSE-OUT COMPLETE** | Quiet and playback captured for Pair 1 only. Pair 2 preparation was not confirmed; no second pair reserved. Both routes restored, capture exited, baseline equality and 17 after-checks verified. Expected numeric files only in both scopes; no deletion or robot-return claim. No complete four-microphone comparison, calibration, pilot or motion authorization follows. |
| Close out v3-03 and prepare a separate v3-04 attempt | **PROCEED OFFLINE; NO NEW ACQUISITION APPROVAL** | Advances the M5–M6 microphone blocker by reviewing the saved quiet-only timeout, restoration, process exit and scoped inventories, then preparing clearer phone-Play/PowerShell-Enter cues under a new identity. Preserve all old results and one-shot records, measurement/recovery limits and D026/D029/D030 boundaries. No higher-value work displaced, no microphone-health or pilot result claimed. Stop for inconsistent evidence, changed old artifacts or unapproved acquisition. |
| Single-start session `two-pair-v3-03` result review | **ABORTED; RESTORED; SCOPED CLOSE-OUT COMPLETE** | Pair 1 quiet only, followed by playback-confirmation timeout. Capture exit, restored routes, baseline equality and 17 after-checks verified; expected scoped numeric files only, no deletion. Preserve the failed result and spent identity. No playback comparison, microphone-health, pilot or robot-return conclusion. |
| Close out v3-02 and prepare a single-start v3-03 successor | **PROCEED OFFLINE; NO NEW ACQUISITION APPROVAL** | Removes the M5–M6 operator-start obstacle while preserving the aborted result, old helper hashes and one-shot records. Verify the saved numeric no-capture/no-route-change evidence and scoped before/after metadata, then prepare an explicitly announced single start acknowledgement instead of READY plus a separate Pair-1 prompt. Fresh state checks, Pair-2 preparation, active capture/playback/guard/restoration deadlines and D026/D029/D030 boundaries remain unchanged. No higher-value task displaced; no hardware result claimed. Stop for inconsistent close-out, missing evidence or changed measurement/recovery behavior. |
| Clear phone cues for `two-pair-v3-02` | **ABORTED BEFORE CAPTURE; SCOPED CLOSE-OUT COMPLETE** | First-pair preparation was not confirmed. Zero pairs reserved, no diagnostic capture or route write; unchanged baseline and 17 after-checks verified. Both scopes contain only expected numeric files; no deletion. Preserve this spent session and original result; it is not microphone-health evidence. |
| Corrected session `two-pair-v3-01` result review | **ABORTED; RESTORED; SCOPED CLOSE-OUT COMPLETE** | First-pair quiet capture only; playback confirmation timed out. Guard/capture exit and unchanged baseline verified; no unexpected scoped files or deletion. Preserves the failed result and advances the M5–M6 blocker without claiming microphone health or playback response. D029–D030 unchanged, no higher-value work displaced. New preparation/approval required before another attempt; no pilot, motion or publication release. |
| Correct microphone-helper USB retry handling | **READER OBSERVED; CLOSE-OUT/PREFLIGHT COMPLETE** | Both corrected reads succeeded on the second transfer. Close-out is reconciled with no unexpected scoped files or deletion; the new-path unreleased candidate passed all 17 preflight checks. Preserve the failed result and all spent latches. A newly identified acquisition needs separate preparation/approval; no automatic capture, routing/motion, release or pilot reopening. |
| One stock sleep transition and read-only verification | **SCOPED D031 STEP OBSERVED COMPLETE** | One acknowledged stock sleep followed by disabled/no-move observations with daemon/media running. No M7 pass, exact-pose verification or consumer-isolation claim follows; the old one-shot launcher is not to be repeated. |
| Start the existing 54-trial confirmation collection | **DEFER** | It cannot identify all frozen primary endpoints and is not the shortest path to an integrated controller. |
| Further polish or export the manuscript as a paper PDF | **DEFER** | Presentation would displace M5–M10 and risk implying completion. |
| Build the shadow-only fused decision orchestrator | **COMPLETE AS SOFTWARE PROTOTYPE** | M5 has a deterministic synthetic contract with no motion or response authority; one real capture commissioned its inputs but did not validate its decisions. |
| Build the same-clock, command-free joint numeric instrument | **COMMISSIONED FOR PILOT USE** | One real 200-row capture passed the frozen timing and availability checks with 100% joint spatial rows and zero commands. The transferred synchrony threshold abstained, so commissioning cannot be relabelled as selection accuracy. |
| Run the laptop-camera v2 no-motion pilot | **PAUSE; DO NOT COLLECT** | Zero v2 trials are accepted. Its laptop webcam leaves the primary Reachy-camera transfer untested, so finishing the schedule would not establish the intended robot sensor path. Existing attempts remain preserved and excluded. |
| Commission the command-free Reachy-camera instrument | **SCOPED OBSERVABILITY PASS** | Sixth capture passed unchanged gates; five failures retained. No selection, fine-synchrony or action claim follows. |
| Run robot-camera no-motion pilot v1 | **PROCEED ONLY THROUGH COLLECTION GATE** | New design/execution fingerprints, private setup seal, microphone match, scheduled first-quality-pass acceptance and locked validation. Zero accepted trials. |
| Diagnose phone-playback preflight separately | **PROCEED; NOT PILOT EVIDENCE** | D027: record the detector/direction state that prevents capture, without editing frozen pilot files, thresholds, seals or attempts. One numeric-only, receive-only diagnostic pair for review; no claim of a detector cause or playback rejection. |
| Check direction at three known phone marks | **PROCEED; DIAGNOSTIC ONLY** | D028: one fixed front/left/right sequence, same stimulus and 50% volume, no fitted correction. Preserve frozen pilot and historical files. Stop after three captures or an interruption; interpret no software test as physical calibration. |
| Choose a final sample size | **DEFER** | Choose from a predefined precision or power target only after commissioning and a no-motion pilot estimate availability, latency, clustering, and effect size. |
| Prepare the next motion test offline | **PROCEED IN PARALLEL** | Protocol, target construction, simulation, abort thresholds, and review may advance; no new physical command is permitted until M7's separate opening gate passes. |
| Send a new experimental physical motion command | **DEFER** | M7 remains failed/blocked until a new frozen one-leg protocol and abort thresholds pass review. D031's single stock lifecycle step is separate and grants no experimental motion authority. |
| Publish the current local commit | **DEFER** | Content is being amended; publication requires a fresh privacy, evidence, diff, and strategy review plus an explicit decision. |

## Alignment statement template

Current pilot assessment (2026-10-01): advances **M5–M6** and the live-speaker/
playback distinction by recording the scoped commissioning pass and freezing
the robot-camera no-motion pilot. Produces protocol, recorder, offline analysis,
private binding and failure-preserving attempt gates, not a discrimination or
robot-behaviour result. It displaces no higher-value task, preserves D022–D026,
and opens no sensors or robot connection during implementation/tests. Stop for
binding/acquisition failure, two failed attempts, no qualifying development
setting, boundary-lag timing failure or failed one-shot validation. Do not relax
gates, resume the laptop pilot, enable motion/response or publish externally.

Before work, record a short statement in the task notes or final report:

> This work advances milestone **[ID]** and the charter criterion **[criterion]**. It produces **[artifact/evidence]**. It does not establish **[remaining boundary]**. It displaces **[task or none]** and will stop if **[condition]**.

## Context-recovery protocol

After a context compaction, handoff, long pause, or strategic challenge:

1. reread the five canonical records;
2. inspect `git status`, the last five commits, and the current diff from `origin/main`;
3. identify the first non-`PASS` milestone on the critical path;
4. state the alignment sentence before acting; and
5. do not rely on a previous summary if it conflicts with these versioned records.
