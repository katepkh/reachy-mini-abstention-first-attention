# Microphone signal-path diagnostic — approval proposal

## Latest status — no-audio Linux result unverified, 2026-10-09

The automatic generated-data Linux check was attempted once on 2026-10-08.
Its saved local status is `CONNECTION_OR_RESULT_UNVERIFIED` with SSH exit code
zero. The pinned remote harness returns zero only for its own success branch,
but the laptop rejected the output and did not retain the detailed result.
Consequently the detailed Linux/cleanup result cannot be independently checked
from that receipt. Do not relabel this attempt as a verified pass or rerun its
spent one-use launcher. Investigate report validation offline first; no new
microphone attempt follows from this publication.

The local preparation suite reported 158 tests, including three skipped tests
(155 passed). That is software evidence, not a hardware-health result. The
check used generated terminal input and integer samples with hardware checks
stubbed, no operator Play/Enter prompts, and no microphone, routing or movement
action. The original report, sources and run records remain preserved privately.
Inputs 2/3 still lack a completed playback comparison; historical input failures
remain unexplained. All sections below are dated provenance, not standing
execution authorization. Public source copies omit private approvals and latches.

## Current offline preparation — counts-only observation candidate, 2026-10-08

`tools/reachy_mic_health_observed_candidate.py` is a separate, **execution-blocked**
candidate. It preserves the old helper, every spent launcher and all run records.
There is no new live launcher, deployment, private acquisition capability or
robot connection. `--execute` and the guard reject before device/file setup
because `EXECUTION_RELEASED` is false. Default simulation is offline.

The unchanged `TerminalInputReader` parser is wrapped by
`ObservedTerminalInputReader`; the embedded, separately tested definitions in
`tools/reachy_input_observation.py` retain only bounded metadata:

- saturating counts of reads, bytes, LF, CR, other whitespace, other bytes and EOF;
- selector calls/returns/readiness, read calls/returns/errors, thread start/exit
  and published event counts, with first/latest relative times;
- sanitized error stage/errno, thread-alive/stop state and known reader faults;
- read-only terminal flags and whether foreground process groups match, without
  tty paths, process IDs, terminal writes or mode changes.

The reader returns bytes unchanged. No typed contents, passwords, raw media or
per-keystroke byte history are saved by this instrumentation. It starts only
inside the capture function, after the original start approval input. There
are at most four progress snapshots: reader start, after the Play prompt, before
reader close and after reader close. Counters saturate at one million with an
explicit saturation flag; snapshots contain no unbounded list. Times share the
capture origin and are observations, not physical keypress/kernel-arrival times.
Concurrent snapshots can precede publication of a counter update; the final
post-join snapshot is meaningful only with verified reader exit.

These records can show read bytes that produced no Enter, a read/selector call
that has not returned, or a reported reader fault. Healthy polling with zero
read bytes still does **not** prove that the operator did not press Enter, nor
distinguish every transport/buffering cause. Unsupported/error terminal metadata
is explicitly unavailable, not a healthy-state assertion. Diagnostic snapshot
unavailability does not override original input decisions or cleanup.

Source comparison verifies the old parser and every other pre-existing
function/class are unchanged; only the capture function's instrumentation
hooks are added. Input recognition, prompt text, 10-second confirmation,
sample counts, capture/guard/restoration limits and abort decisions are retained.
In particular, a lone CR is counted but is not silently converted to Enter.

Offline verification: 143 passed, two POSIX-only skips across the observation,
combined capture/input, exact-reader, prior keyboard and original input suites.
A separate unaccelerated generated-sample run completes 48,000 quiet and 160,000
playback frames, one accepted Enter and verified reader exit. Four snapshots
serialize to about 4.7 KB compactly in that fixture. Tests cover saturation,
content exclusion, read/selector faults and stalls, missing input, CR, normal
Enter, duplicate/text/EOF, cleanup, deadline behavior and release blocking.
See `evidence/analysis/mic_input_observation_synthetic_v1.json`.

This is instrumentation preparation, not a cause or fix for the historical
failure and not microphone-health evidence. Linux PTY/real capture-process
behavior remains unverified. Before considering a live acquisition release,
review a no-audio Linux synthetic check and its source bindings; no such
operator command or authorization is issued by this preparation.

## Current result and offline capture/input investigation — 2026-10-08

The one-shot exact-reader keyboard check is complete and spent. The saved
source-bound local report says `BOTH_ENTER_READERS_ACKNOWLEDGED`, exit zero.
The supplied console result shows one LF, zero CR, one recognized Enter event,
verified reader exit and unchanged canonical terminal flags with ICRNL enabled.
This rules out a persistent failure of that standalone keyboard path, not a
historical or capture-dependent failure. It does not establish keypress timing
in the earlier aborted run, and does not support asking the operator to hurry.

The local investigation now exercises the preserved `capture_pair`, `Stats`
and `TerminalInputReader` together in
`tests/test_mic_capture_input_integration.py`. A SHA-pinned AST allowlist loads
only those definitions, `Stop` and `capture_command`; no hardware, HTTP,
authorization or live execution code is loaded. Connected local sockets model
stdin and capture pipes, while a producer generates integer sample values.
Real reader/producer threads and selectors run concurrently. Capture launch,
guard status and device checks are explicit stubs; no actual capture child,
audio device, robot connection or Linux terminal is tested. This Windows host
has no installed WSL environment, and none was installed for this task.

Normal LF, CRLF and fragmented whitespace/newline input complete the synthetic
quiet/playback path. The reader also recognizes Enter during simulated blocking
status checks and main-thread CPU work. Text, duplicate Enter, EOF, capture
driver failure, capture EOF/stall and guard exit retain their abort behavior;
reader and fake-capture cleanup are checked. Most cases accelerate the harness
clock fivefold without changing the source, sample counts or limits. A separate
unaccelerated case also completed: 48,000 quiet frames, 160,000 playback frames,
one LF observed 2.703 seconds after the synthetic prompt, processed 16 ms later,
with reader exit verified. These are generated samples, not microphone evidence.

The combined suite reports 98 passed and one POSIX-only skip. Reproduce locally
with `.venv\Scripts\python.exe -B -m unittest tests.test_mic_capture_input_integration
tests.test_exact_reader_probe tests.test_reachy_keyboard_probe tests.test_mic_input_candidate`
(one command). The unaccelerated synthetic result is retained in
`evidence/analysis/mic_capture_input_synthetic_v1.json`, including the initial
harness-only prompt-wait failure and its correction; the live helper was not
changed.

The original abort is **not reproduced by ordinary concurrent sample
processing** in these tests. Deliberately absent input, lone CR and a deliberately
gated-off reader can all produce the same old empty-event timeout; only the
harness's extra observations distinguish them. The gated reader is an injected
fault, not a defect found in the helper. The old run does not record raw-read
counts, reader progress or terminal flags, so its cause remains undetermined.

At investigation close, the engineering recommendation was to review an instrumentation-only, unreleased
candidate with bounded counts-only reader progress, read/event timing and
read-only terminal/foreground state. Never store typed text or passwords or
change terminal modes. That investigation itself prepared no candidate; the
subsequent offline preparation is described above. Preserve the old helper/launcher hashes, deadlines and all run
records; no new microphone attempt or acquisition capability is issued.

## Preserved abort review and keyboard preparation — 2026-10-08

The `missing-pair-v3-05` connection replacement is spent. It passed deployment
checks, captured three seconds of quiet input-2/3 measurements and aborted with
`confirmation_deadline_no_observed_enter`; no playback measurement is present.
The reader's event log is empty and physical keypress timing is unknown. This
does not establish whether Enter was pressed or why it was not observed.
Routing restoration, capture and reader exit, baseline equality and all 17
after-checks are verified. The agreed remote inventory and the local after-review
contain only expected numeric/control files, without deletion. A separate final
receipt preserves all original pending/control records and the aborted result.
This is scoped ordinary-file close-out, not forensic erasure or robot-return
clearance. No health or pilot result follows.

Do not issue another microphone attempt to diagnose this input path. A local
synthetic byte test shows the exact reader recognizes LF and CRLF but ignores
a lone CR without emitting an event. That is a possible explanation, not proof
of the terminal bytes during the failed run. The earlier successful keyboard
probe used input()/readline(), not this independent raw-byte reader.

`scripts/check_reachy_exact_reader.py` prepares one keyboard-only check under
`reader-path-20261008-01`. It sends only the exact source-pinned Stop and
TerminalInputReader classes, plus `tools/reachy_exact_reader_probe.py`, in memory
over the same interactive SSH transport. First it reads one ordinary Enter with
input(); then the exact reader observes a second Enter. Each prompt allows two
minutes. A counts-only os.read wrapper passes bytes through unchanged and reports
CR/LF/other counts, relative read/event times and read-only terminal flags. It
does not save typed text, normalize input, change terminal modes, install a
robot file, open audio/USB, call a robot API or launch a capture process. There
is no phone playback or acquisition approval. A one-second observation settle
period belongs only to this keyboard harness; diagnostic timing is unchanged.

The launcher inherits all console streams so the SSH password stays there.
Detailed numeric observations are printed in that console, not captured into
local files. The fixed private local folder
`data/private/mic_keyboard_reader_check/reader-path-20261008-01` exclusively
records start/source/status metadata before SSH and remains spent after failure.
At preparation time, offline tests passed (89 passed, one POSIX skip), with live
keyboard evidence pending. The completed check is reviewed above. Real
capture-load behavior remains unverified. A pass cannot retrospectively prove
the failure's cause or authorize another microphone run. No automatic retry.

## Preserved preparation — one connection-timeout replacement, 2026-10-08

The original `missing-pair-v3-05` launcher is now spent: the operator console
shows a connection timeout before login, and the four local numeric records
stop at deployment. No diagnostic capture or routing occurred. Their scoped
local before/after metadata is reviewed with no unexpected files; preserve all
four originals. A later status read succeeds with motor mode disabled, but
does not replace a scoped remote file check. Remote close-out remains pending.

`scripts/run_reachy_mic_input_connect_replacement.py` prepares one separately
authorized and separately latched `connect-replacement-01` in the SAME agreed
local/remote session scopes listed below. It reuses the byte-identical helper
and source-pinned launcher. Before deployment, exact run/helper/capability
paths must be absent; permission errors, links or present entries stop it.
The remote absence receipt must be saved and validated before interactive
execution, alongside all 17 fresh machine checks. The nine earlier completed
run checks and the no-capture predecessor check remain intact. Original records
are never overwritten; new transport records use the replacement prefix.

Preparation issued no new capability, connected to nothing and opened no audio.
Default/help and `--inspect` work offline; inspection explicitly does not grant
execution. Tests: 256 passed, four POSIX skips on Windows. There is no new timing,
pair, prompt or restoration limit. A separate scoped approval plus live setup
confirmation is still required. After any attempted execution, review the
scoped numeric collection and close-out; no automatic retry or deletion.
Absence does not establish forensic erasure or a robot-return check.

## Preserved preparation — inputs 2/3 successor, 2026-10-08

`missing-pair-v3-04` and its login replacement remain spent. The first stopped
at authentication; the replacement stopped at fresh motor-mode preflight before
capture or routing. After the separately supervised stock sleep, the operator's
saved read-only after-report passes all 17 checks and matches the baseline
parameters, mixer and audio configuration. It reports the agreed robot run
directory absent. The checked local inventory contains only expected records.
The separate private final receipt closes this no-execution scope without
deletion or rewriting its original pending/failure records. Absence is not a
forensic-erasure claim or proof of no media outside the agreed scope.

`scripts/run_reachy_mic_input_next.py` and
`tools/reachy_mic_health_input_next.py` prepare **missing-pair-v3-05**, only
inputs 2 and 3. All helper function/class bodies remain unchanged; only the
fixed session and capability path differ from v3-04. There is no second pair,
inputs-0/1 repeat, timing relaxation or automatic retry. The launcher preserves
the nine completed remote predecessor checks, verifies the pinned no-capture
final receipt and unchanged local evidence, and requires the predecessor run
directory plus new helper/capability/run paths absent before deployment.
It rechecks predecessor absence before interactive execution as well.

Proposed metadata-only scopes (not a fabricated before-inventory):

- Laptop: `data/private/mic_closeout/missing-pair-v3-05`.
- Robot: `/home/pollen/reachy-mic-health-runs-v2/run-missing-pair-v3-05`.
- New helper: `/home/pollen/reachy_mic_health_input_v3_05.py`.
- New capability: `/home/pollen/reachy_mic_input_v3_05_authorization.json`.

Preparation has made no robot connection and issued **no acquisition/routing
capability**. Separate scoped approval, residual/restoration-risk acceptance,
fresh disabled-motor/consumer checks and live physical/phone-speaker confirmation
remain required. Capture/restoration limits and D026/D029/D030 are unchanged.
237 focused tests pass; four POSIX cases skip on Windows. This is software
verification, not microphone health, capture-load success or pilot readiness.
Default/help, `--inspect` and `--walkthrough` are offline. Do not run any spent
launcher. Stock sleep is already observed complete and is not part of this
preparation. Final robot-return checks remain separate.

## Preserved login-failure replacement — now spent, 2026-10-08

The first `missing-pair-v3-04` connection was rejected at SSH authentication.
The console and pinned local transport records agree: no remote deployment
or diagnostic execution started. The original launcher remains spent. Local
metadata review finds only its four expected numeric/control records, with
the before-inventory authorization unchanged. Those records are preserved;
this is not a remotely observed restoration or forensic-erasure claim.

`scripts/run_reachy_mic_input_login_replacement.py` provides one separately
latched replacement within the SAME agreed local/remote scope. Its private
source-bound review and authorization are outside the run directory. It
requires the original records and current local metadata to match exactly,
saves `login-replacement-01-started.json` exclusively before SSH, and refuses
deployment if the exact remote helper, authorization or run path is present
or unreadable. The remote absence receipt must be returned and validated
before interactive execution. Thus the remote failure check is still pending
now, but cannot be skipped before replacement acquisition. If anything is
unexpected, stop for review; do not delete, reset or infer cleanup from absence.

The helper is byte-identical; input indices, prompts, recording/restoration
limits, nine predecessor checks and fresh physical/client gates are unchanged.
Transport reports receive replacement-prefixed names; original pending/failure
records stay intact. Subsequent numeric collection is read-only and the final
scoped close-out still needs review, including after interruption. No robot
connection, microphone capture, routing write or deletion occurs during this
offline preparation. Tests: 86 focused cases, 85 passing and one POSIX skip on
Windows, covering the exact replacement transport and existing diagnostic.

## Preserved preparation — single remaining pair, 2026-10-08

The operator's fixed stock-sleep journal records one acknowledged request and
two disabled/no-move observations with daemon/media running. Exact physical
pose was not instrument-verified. The subsequent source-bound preparation
report passes all five synthetic Linux terminal checks, all 17 machine checks
and nine predecessor scope checks. No audio was opened or settings changed;
the unreleased candidate was copied to its distinct path. These observations
do not establish present readiness, consumer isolation, microphone health or
terminal behavior under capture load. Do not repeat those completed commands.

`scripts/run_reachy_mic_input.py` and `tools/reachy_mic_health_input_run.py`
prepare the new session `missing-pair-v3-04`: inputs 2/3 only, preserving the
usable earlier inputs-0/1 measurements and every prior result. All function
and class bodies match the input candidate exactly; only the build/session
identity, candidate provenance and private-authorization release constant
change. At preparation time no matching private capability was issued and no
diagnostic run or robot connection occurred. The subsequent attempted launch
stopped at login, as recorded above. The original candidate stays
execution-blocked. Default/help, `--inspect` and `--walkthrough` are offline.

The proposed metadata-only scopes are project-relative
`data/private/mic_closeout/missing-pair-v3-04` and robot-side
`/home/pollen/reachy-mic-health-runs-v2/run-missing-pair-v3-04`.
A private PREPARED_NOT_AUTHORIZED record is outside the run registry; it is
not a before-inventory, acquisition approval or fabricated completed close-out.
After separate scope approval, the launcher requires the exact private
capability, checks the pinned preparation and all nine prior receipts, latches
the local attempt before SSH, deploys only new helper/authorization paths and
checks fresh preflight. The live start confirms physical/client/speaker setup.
Success, abort or disconnect spends the attempt; numeric collection and scoped
close-out review remain mandatory. No automatic retry, deletion or pilot release.

There is one quiet/playback measurement and no second-pair preparation. Keep
the existing phone clip paused at its beginning, 50%, front mark, one metre,
microphone height; verify built-in speaker output and disconnect headphones
before the live run. The start confirmation begins quiet automatically.
At the live PLAY + ENTER cue, tap phone Play then press PowerShell Enter once
within the existing ten-second limit. Keep playing until PAUSE; do not press
additional Enter keys or switch away for screenshots. No new timed input or
changed capture/watchdog/restoration limit is introduced. Raw audio is not
intentionally saved/exported, but OS residual copies remain possible.

Offline verification: 146 focused tests, 143 passing and three Windows-skipped
POSIX cases. These exercise the exact prepared helper's capture/input reader,
single-pair USB adapter and restoration, nine predecessor inventories, report
identity, missing approval, spent-session/transport failures and scoped export.
The prior robot-side synthetic PTY pass does not replace capture-load testing.

## Preserved stock-sleep preparation — 2026-10-08 (now completed)

A new read-only status reports physical v1.9.0 with media available and enabled
motor mode; the microphone diagnostic remains blocked. A separately identified
stock-sleep launcher, `scripts/request_reachy_stock_sleep_current.py`, binds the
unchanged reviewed D031 source to one new fixed private journal and matching
private authorization. It retains the original live operator confirmation and
fresh status/app/slot/movement checks, sends no command if already disabled,
and preserves every earlier journal. It offers no retry or microphone mode.
The resulting journal has now been reviewed as described above; it is not
permission to repeat the command. This stock sleep result does not validate
experimental motion, camera geometry or microphone health.

## Completed automatic terminal/readiness preparation (no acquisition)

The completed operator command was `scripts/prepare_reachy_mic_input.py
--prepare-once`; it is not the next action to repeat. It required the phone
paused and Reachy apps/pages closed. Only the
SSH password may be requested; there is no Play cue or timed Enter exercise.
It performs one bounded connection and stops with a private report. It does
not start the microphone diagnostic or automatically retry after interruption.

Before connecting, it verifies the pinned source and all nine previous scoped
close-outs from the saved numeric records and current local metadata. On Reachy,
it rechecks those exact inventories and close-out records, then exercises the
candidate's independent reader on isolated synthetic Linux pseudo-terminals:
one Enter, split whitespace/Enter, duplicate Enter, text classification and EOF.
Reader exit and unchanged terminal modes must pass. It never writes to the
operator's terminal or retains typed content. This is terminal compatibility,
not a test of real keyboard latency or behavior under microphone-capture load.

If those checks pass, it copies only the execution-blocked candidate to the new
`/home/pollen/reachy_mic_health_input_candidate.py` path, preserving old helpers.
An identical copy can be verified; a different existing file is not overwritten.
It then collects the existing 17 read-only machine checks. The candidate remains
`EXECUTION_RELEASED=False`; no approval, routing, motion, OS-setting change,
audio capture or deletion is included. No new microphone run is created.

Started/final reports are saved beneath the ignored
`data/private/mic_input_preflight/<unique-check>/` directory. Review the exact
source identities, terminal results, all 17 checks and any failed stage before
preparing the new one-shot inputs-2/3 acquisition. A saved readiness report is
not future live readiness or consumer-isolation confirmation. Preserve every
failed report; a timeout does not prove whether the candidate copy completed.

The unchanged robot-camera pilot's offline status/seal also verifies, with zero
accepted trials and the original spatial-conflict trial still first. This is
not live readiness. After the missing pair and its restoration/scoped close-out
review, demonstrate speech/direction and geometry readiness before returning
to that no-motion pilot. Do not repeat inputs 0/1 by default, change the frozen
pilot, infer microphone health from preparation, or enable motion/response.

Offline verification on 2026-10-03: the full Python suite completed 1,668 tests,
with 1,659 passing and nine skipped, no failures. This includes preparation
report/transport failures and generated remote-program ordering with fake
devices. At that point actual Linux execution was pending; it subsequently
passed in the 2026-10-08 preparation report above. Windows still skips the
POSIX unit test. Project-alignment and whitespace checks pass.

## Preserved offline input-handling correction (not released)

The keyboard-only check completed on 2026-10-03: both Enter presses were
acknowledged, with SSH exit status zero. The saved local report identifies the
reviewed probe and confirms no audio, settings change or remote installation.
This establishes the two observed acknowledgements, not the old failure's
cause or behavior under microphone-capture load. Do not repeat that probe by
default or reuse any spent microphone launcher.

`tools/reachy_mic_health_input_candidate.py` is a separate, execution-blocked
candidate. The preparation-only launcher above can copy/check it, but no
acquisition capability has been issued and no live result is yet available.
Its single dedicated input reader timestamps recognized input atomically with
event publication, independently of the capture loop. The loop checks queued
observations and their synchronized snapshot time before classifying
confirmation expiry. An Enter observed within the existing ten seconds can
therefore survive later main-loop processing; input first observed at/after
the deadline is rejected, never backdated. This does not establish when a
physical key was pressed or when PowerShell displayed the cue.

Numeric diagnostics distinguish no observed Enter, observation after the
deadline, early/extra input, reader failure and unverified reader exit. They
retain bounded event kinds/publication-observation/processing times, prompt-write
start/finish times and reader-exit status, not key contents. Prompt-write
completion is not proof of local display. Thread/transport scheduling can
still delay observation; that uncertainty is explicit.

No additional operator action or prompt is added. Inputs 2/3 only, all phase
sample counts, the ten-second confirmation limit, capture/stall limits,
40-second routing watchdog and five-second restoration limit are unchanged.
Capture limits are rechecked after blocking status/selector work; queued input
cannot extend them. Reader cleanup is bounded, and its failure cannot skip
capture shutdown or the parent's existing route-restoration path. Original
helpers, approvals, results and scoped close-out receipts remain unchanged.

Tests cover deterministic delayed-loop input, queue-snapshot/expiry races,
deadline boundaries, early and duplicate input, fragmented PCM, hard limits,
reader errors/overflow/exit and
parent restoration. Real local socket-pair selectors exercise the independent
reader thread; these are not SSH or terminal-device tests. A canonical-PTY test
is included but skipped on Windows. Linux PTY/capture-load behavior remains
unverified; this candidate is not a microphone-health result or permission to
record. Review that boundary and a separately prepared, newly approved one-shot
scope before any live use. Existing inputs-0/1 measurements remain retained.

Focused offline verification on 2026-10-03: 49 tests, 48 passing and the one
POSIX-PTY case skipped on Windows. The original spent helper and keyboard probe
still match their reviewed SHA-256 values. Tests compare every other helper
function/class against the preserved source: only the capture loop changes,
and only the independent terminal reader is added. Execution and guard entry
points reject this candidate before hardware or session-file access.
Candidate SHA-256:
`a97f34778dda3f3f042d7a1f8493eedcc7de023953fd8bf5e46895f33dc0edff`.
The final full Python regression completed 1,645 tests: 1,637 passed, eight
skipped, no failures. Project-alignment and whitespace checks also pass. These
are software checks only; no new physical milestone or acquisition permission
follows.

## Completed keyboard-only transport check

`missing-pair-v3-03` also stopped at `operator_deadline`, with three seconds of
quiet data and no playback measurement. The result remains aborted. Its saved
report verifies capture exit, route restoration, baseline equality and all 17
after-checks. Both scoped ordinary-file checks are finalized privately with
no unexpected files or deletion. No new microphone session is prepared.

The capture loop tests expiry before polling queued input. An offline synthetic
case reproduces a queued Enter at 9.99 seconds followed by a loop resumption at
10.01 seconds and an abort without reading it. This establishes an ordering
weakness, NOT the historical cause: the run contains no key-arrival or local
prompt-display timestamps. Earlier tests injected selector events and did not
validate the actual PowerShell/SSH/PTY input path.

`scripts/check_reachy_keyboard.py --check-once` sends the pinned
`tools/reachy_keyboard_probe.py` source in memory through the same interactive
SSH options and inherited stdin/stdout/stderr. It uses the same remote Python
runtime, first `input()`, then selector plus `stdin.readline()`. It asks for
Enter at **STEP 1/2**, acknowledges it, then asks at **STEP 2/2**. Each prompt
allows 120 seconds. The phone stays paused; there is no playback or timed
Play/Enter action. No microphone, robot API, USB, routing, motion, settings
write, remote installation or automatic retry exists in this probe.

The probe's candidate reader polls before classifying expiry, records numeric
readiness-observation/read-completion times and explicitly labels input first
observed beyond the deadline as ambiguous. It does not infer physical keypress
time or accept late/unknown input as timely. The old acquisition code and all
its limits remain unchanged. The longer keyboard-only wait grants no recording
permission and must not silently become an acquisition deadline change.

Only local started/exit/status metadata is saved under the Git-ignored
`data/private/mic_keyboard_check/<unique-check>/` folder. Each explicit command
uses a distinct folder, preserving earlier checks. Detailed numeric timing is
printed to the inherited terminal, not automatically captured; passwords and
key contents are not stored. Review the final console output and local report
before any further action. A failed check does not start a microphone retry.
Passing this probe demonstrates only those two acknowledgements, not the full
timing behavior under capture load or the cause of the old failure.

Offline verification: 18 probe/launcher tests, including real selector/text I/O
on a local socket pair and deterministic deadline-boundary cases. The socket
test is not a Linux PTY or SSH validation. The subsequent operator-run
terminal/SSH check acknowledged both input methods; no robot connection was
made during offline preparation or input correction.

## Preserved single-pair replacement: missing-pair-v3-03 (now spent)

The corrected `missing-pair-v3-02` attempt captured only quiet for inputs 2/3,
then stopped at playback confirmation with `operator_deadline`. Preserve its
`ABORTED_REVIEW_REQUIRED` result. Capture exit, restored routes, baseline
parameters/mixer/asoundrc and all 17 saved after-checks pass. Both agreed
ordinary-file scopes are now `CHECKED_NO_UNEXPECTED_FILES`; local review and
after-inventory are recorded privately, without another robot connection or
deletion. This is not a playback-response, microphone-health or robot-return
pass. The old launcher remains spent.

`scripts/run_reachy_mic_missing_pair_speaker.py` and
`tools/reachy_mic_health_missing_pair_speaker.py` prepare one new inputs-2/3-only
attempt under `missing-pair-v3-03`. All eight predecessor receipts and scoped
inventories are checked. The agreed new scopes are local
`data/private/mic_closeout/missing-pair-v3-03` and remote
`/home/pollen/reachy-mic-health-runs-v2/run-missing-pair-v3-03`.
The helper and private capability use distinct new paths. Existing capture,
routing, readback, watchdog, restoration and timing code is unchanged.

Before launching, disconnect headphones, briefly play the existing clip to
verify it is audible from the phone's built-in speaker, then rewind and pause
at 50%. Keep the same front mark, one-metre distance and microphone height.
The existing live start acknowledgement also confirms this speaker check;
there is no new timed prompt, extra Enter, or second pair. Only at the live
**PLAY + ENTER NOW** cue: tap phone Play, then Enter once within ten seconds.
Keep playing until **PAUSE**, then pause and wait for final report collection.
Do not reuse a spent command. Fresh physical/consumer setup and machine checks
remain required. No hardware access occurs during preparation.

Verification: 88 focused offline tests pass for this exact helper, including
the real adapter through fake USB, all eight predecessor checks, and AST
comparison confirming that the execution body changes only printed setup
instructions. Software checks are not a live microphone pass.

## Preserved preparation: missing-pair-v3-02 (now spent)

That prepared attempt measured only inputs 2 and 3. Earlier inputs 0/1
measurements remain retained; no second pair or between-pair prompt exists.
`tools/reachy_mic_health_missing_pair_run.py` takes the adapter and one-pair IPC
repair from the offline fixed candidate without changing capture, routing,
readback, watchdog, restoration, privacy or timing behavior. Only its session
identity and private-authorization release differ. The fixed candidate itself
remains execution-blocked; all spent helpers and original results are preserved.

`scripts/run_reachy_mic_missing_pair_corrected.py` requires a separately bound
private capability for one attempt, verifies all seven predecessor receipts,
their local metadata, the exact reconciled remote record and fresh preflight,
then requires the operator's live start/setup acknowledgement. The new remote
helper and authorization have distinct `missing_pair_v3_02` paths. Agreed
metadata-only inventory scopes are the new remote
`/home/pollen/reachy-mic-health-runs-v2/run-missing-pair-v3-02` directory and local
`data/private/mic_closeout/missing-pair-v3-02` directory. A durable pending record
precedes SSH/acquisition; success or abort is followed by scoped numeric export
and review. No automatic retry, deletion, motor/OS change or pilot release.

At the live start confirmation the phone must be paused at the beginning of the
same existing clip, at 50%, front mark, one metre away and microphone height;
Reachy is resting head-down, clients closed, operator beside it, mechanism
clear. Confirmation starts the quiet phase automatically. Remain in PowerShell.
At **PLAY + ENTER NOW**, tap phone Play then press Enter once within ten seconds.
That is a confirmation deadline, not an instruction to stop playback after ten
seconds. After **ENTER RECEIVED**, leave both controls alone until **PAUSE**.
Pause the phone then wait for numeric report collection. There is no Pair 2.
On a stop/disconnect, pause the phone, retain output and do not rerun or reboot.

Preparation opens no robot connection or audio. Software tests, earlier
preflight and a private capability are not a hardware-health or readiness claim;
fresh machine and live setup checks remain mandatory for the actual attempt.
Verification: 87 focused corrected-session tests pass, including the actual
USB adapter path and all seven predecessor checks. The full offline suite runs
1,490 tests with seven skips and no failures; this is not a live microphone pass.

## Current result and offline adapter repair (2026-10-03)

`missing-pair-v3-01` failed before capture or the live Play cue. The one-pair
adaptation left `USBBoard.write` indexing `PAIRS[1]`, which does not exist.
The pinned source and offline reproduction establish an `IndexError` before
any diagnostic USB OUT transfer, including attempted restoration writes.
The guard conservatively reported `RESTORATION_UNVERIFIED`; preserve that
original result. This was a software defect, not an operator-timing failure.

The saved after-report matches both baseline routes, every checked parameter,
mixer and `.asoundrc`; 16 checks pass and only this run's pending close-out
blocks the remaining check. Scoped metadata shows expected numeric/control
files only. Local review is recorded privately in
`data/private/mic_closeout/missing-pair-v3-01/closeout-review-v1.json`.
The subsequent operator-run reconciliation succeeded at 07:26 UTC. The exact
old helper/source identities match, two fresh baseline snapshots agree, and all
17 after-checks pass with no pending robot run reported. Only the run's numeric
`closeout.json` changed; the failure result and guard journal remain unchanged.
Both agreed scopes are now **CHECKED_NO_UNEXPECTED_FILES**, with a separate
private `closeout-final-v1.json` preserving the original pending records.
No files were deleted. This does not prove absence of media outside the scope,
erasure from swap, a hardware-health pass or readiness for another acquisition.

`tools/reachy_mic_health_missing_pair_fixed.py` is a separate **unreleased
offline candidate**, not a new session approval. It derives allowed writes
from the configured pairs and ends the guard after that many restored pairs.
`--execute` and `--guard` refuse before account, file or hardware access.
The old helper and launcher hashes are unchanged. Direct tests exercise the
real USB adapter methods through a synthetic USB transport, including the
original exception, exact 2/3-only routing, partial writes, restoration errors,
external drift, watchdog, readbacks and one-pair IPC completion. Capture and
restoration limits are unchanged. These are software checks, not a hardware
health pass; inputs 2 and 3 still have no diagnostic measurements.

The separately prepared `scripts/reconcile_reachy_mic_missing_pair.py` exposes
one operator-run `--reconcile-once` action. It pins the saved report and old
helper, checks the same exact five remote records and file metadata, requires
two fresh equal baseline snapshots and no observed diagnostic process/lock
owner, then updates **only that run's numeric `closeout.json`**. It preserves
the old failure result and guard journal, installs nothing, opens no audio,
changes no routing/motors/settings and deletes nothing. It performs the final
read-only preflight without excluding any pending run. No automatic retry;
its saved report requires review after success or interruption. That review is
now complete for this one attempt; preserve its spent record and do not rerun.
This is not whole-system consumer isolation or the final robot-return check.

Completed operator flow: apps closed, phone paused, one reconciliation command
and SSH password, then the saved report reviewed locally.
There is **no Play cue, no timed Enter and no recording** in this command.
No robot connection or metadata update was performed during offline preparation.
During reconciliation, only the authorized numeric close-out metadata changed;
there was no audio capture, routing write, helper installation or deletion.
The corrected candidate remains undeployed and execution-blocked. Inputs 2/3
remain unmeasured; earlier inputs 0/1 evidence remains preserved. No new test,
pilot, motion, publication or final robot-return authorization follows.
Offline verification: the full suite ran 1,403 tests with seven skips and no
failures, including 17 new adapter/reconciliation tests. Project alignment and
whitespace checks pass. The private review is Git-ignored; no publication occurred.

## Preserved history

Updated: 2026-10-03. **Historical V1 helper copied and hash-verified on Reachy;
its read-only preflight stopped at the swap check. No V1 diagnostic acquisition
or routing write ran. The v2 read-only follow-up has been reviewed. The temporary swap/core
protection design below is retired under D029; it was never implemented or
applied. Preparation now uses the application-level retention scope and
per-run close-out below. V2 is now implemented and offline-tested locally under
D030 and deployed with a matching hash. The fresh post-restart preflight
passes all 17 machine checks, including explicit disabled motor mode. V1 and
the v2 robot helper remain unchanged. The one authorized attempt subsequently
failed during guard startup, before a pair or capture began (`guard_EOF`). Its
numeric failure records and original pending close-out are preserved. The separate
read-only probe observed USB retry status 64 on both routing-register reads,
which v2 incorrectly treats as fatal. The corrected reader subsequently
succeeded on both second transfers. Scoped close-out is now reconciled locally
and on Reachy with no deletion. The unreleased v3 candidate is installed at its
new path and all 17 preflight checks passed; do not repeat acquisition.**

Preserved preceding result: `two-pair-v3-04` completed Pair 1 quiet and playback, then
aborted before Pair 2 at `preparation_not_confirmed`. The first-pair measurements
are preserved; this is not a completed two-pair diagnostic. Capture exit,
restored routes and all 17 after-checks are verified with baseline settings
unchanged. Both scoped ordinary-file close-outs are finalized from the saved
report and local after-inventory, without unexpected files or deletion. This
is not a microphone-health conclusion or proof of whole-device audio absence.

Earlier result: the separately approved `two-pair-v3-05` ran and aborted with
`unexpected_operator_input` during Pair 1 playback. It retained three seconds
of quiet and 5.936 seconds of partial playback for inputs 0 and 1; no Pair 2
was started. The precise keystrokes are not retained, so do not attribute the
failure to the operator's pace or infer a deliberate extra Enter. Saved guard
and after-check records verify capture exit, restored routes, baseline equality
and 17 passing checks. Its remote scoped inventory contains only expected
numeric/control files. Local close-out is now finalized from that saved report
and the checked local before/after inventory, with no deletion. The original
pending record is preserved inside its separate private review receipt. This
does not establish present robot state or the final robot-return check.

Offline review of v3-04 and v3-05 retains the completed first pair rather than
requesting another full repeat. Both inputs have varying, non-identical samples
and no recorded full-scale clipping. Their playback-minus-quiet levels are
respectively +2.64/+2.23 dB in v3-04 and +2.39/+2.66 dB in partial v3-05. These
are descriptive changes, not calibrated SNR or a health pass. Per-second levels
vary substantially and the quiet baselines differ; do not pool sessions or
claim controlled replication. The private derived analysis is
`data/private/mic_analysis/first-pair-review-v1.json`; original results and
helpers remain unchanged, and neither aborted run is relabelled complete.

Inputs 2 and 3 remain unmeasured. If the all-four-path question is continued,
the minimum useful new acquisition is that missing pair only. The analysis
itself prepared/authorized no run; the subsequent scoped preparation below is
separate. Existing evidence supports
continued offline work but does not identify the DoA problem, certify physical
capsules, or reopen the pilot. Do not reuse any spent launcher.

This proposal advances M5–M6 and the charter's live-speaker/playback distinction
by checking the individual microphone signal paths behind the unexplained DoA
readings. It produces a bounded diagnostic helper, not calibration, a hardware
health certificate, or pilot evidence. It displaces no higher-value task. Stop
if safe stream access, explicit approval, numeric-only retention, or verified
restoration cannot be established.

Preparation does not authorize device writes or new audio acquisition. D026's
pilot remains paused at zero accepted trials; D027–D028's completed diagnostics
remain separate and excluded from fitting/validation. No frozen file, seal,
threshold, trial accounting, firmware, or installed robot software is changed.

## Missing inputs 2 and 3 only — prepared one-pair successor

`missing-pair-v3-01` narrows the acquisition to the unmeasured paths. It does
not rerun inputs 0/1, combine sessions into a completed old run, or retune any
threshold. This advances M5-M6 by filling a specific coverage gap, not by
certifying microphones or explaining DoA. Stop on inconsistent prior evidence,
changed readiness or an interruption. No higher-value work is displaced.

- Helper: `tools/reachy_mic_health_missing_pair.py`, SHA-256
  `2e18a7c7b706590ce726c00c3e6e2c87523d0b75ddc2eb069eeb139b6615303a`.
- Launcher: `scripts/run_reachy_mic_missing_pair.py`, SHA-256
  `d4ea2df205f3e62668f78a905171451984af6b1226304f822c1f50881ae6b428`.
- New robot helper: `/home/pollen/reachy_mic_health_missing_pair_v3_01.py`.
- Robot inventory: `/home/pollen/reachy-mic-health-runs-v2/run-missing-pair-v3-01`.
- Laptop inventory: `data/private/mic_closeout/missing-pair-v3-01/`.
- All six preceding close-outs are pinned and checked locally and again on
  deployment. V3-05's final receipt hash is
  `d28a0cd6d44de0d9f3fa7bcfa83b8dc56ac7598f5218143c3374c1dc6582ee25`.

The only allowed pair is L `[3,2]`, R `[3,3]`; the guard rejects a second pair
or repeat. The numeric labels remain actual input indices `[2,3]`, even though
the local pair ordinal is zero. The capture command, 2-second flush, 3-second
quiet phase, 10-second Play/Enter confirmation window, 2-second settling,
10-second playback phase, stall checks, 40-second routing watchdog and
5-second restoration budget are unchanged. The between-pair preparation
prompt is absent. This is not an unlimited-wait or relaxed-deadline build.

Live authority still requires the exact private scoped capability and terminal
acknowledgement. Its setup fields require confirmation **at the live start**;
offline preparation does not assert that current physical/client conditions
have already been observed. The terminal explicitly asks for the resting head,
closed clients, operator presence and clear mechanism space before confirmation.
Approval details stay private. No robot connection was made during preparation.

### Operator sequence for this successor

1. Leave Reachy resting with head down, on its stable surface. Close Reachy
   apps and browser/media clients; do not stop the daemon or send movement.
2. Put the same existing phone clip at its beginning, paused, at 50% volume.
   Keep the original front mark, one-metre distance and microphone height.
   Do not make a new recording or change volume/position for a better result.
3. Use the new launcher only. Its `--walkthrough` is offline and optional;
   `--run-once` deploys the new helper, checks fresh readiness and opens the
   live confirmation. Enter SSH passwords only in the console when requested.
4. At `LIVE START CONFIRMATION`, check the setup, enter the exact displayed
   scope once and press Enter once. This begins quiet acquisition automatically
   after checks. Leave the phone paused and do not send an extra Enter.
5. At the live `PLAY + ENTER NOW` cue, tap phone Play, then immediately press
   Enter **once** in PowerShell, within the stated ten seconds. Do not wait for
   the clip to finish. `ENTER RECEIVED` confirms acceptance.
6. Leave playback running and do not press Enter again until `PAUSE THE PHONE
   NOW`. Pause the phone then. There is no second pair or preparation prompt.
7. Stay in PowerShell for restoration and numeric report collection. SSH may
   request the password again. Send the final report path or screenshot only
   after it finishes. `COMPLETE_RESTORED` is still subject to close-out review.
8. On abort, timeout or disconnect, pause the phone, retain the output, and do
   not rerun, reset, reboot or reopen robot clients as a recovery attempt.

Verification: 76 focused synthetic tests passed, including actual input labels,
one-pair write limits, timeout/extra-input cleanup, six-predecessor checks and
transport failure handling. Full offline suite: 1,386 tests, seven skipped.
These are software checks, not a live acquisition or microphone-health result.

## Completed lifecycle preparation — separate stock sleep and recovery

`scripts/request_reachy_stock_sleep.py --sleep-once` is a separate operator
launcher, not part of this microphone helper. Default invocation only shows
help. It sends source through verified SSH to Python stdin without installing
a robot file. It requires interactive confirmation of closed clients, operator
presence, clear head/antenna/drop space and accessible physical power control.

The vendor routine can pass through its initial pose, lower the head and move
antennas, play the sleep sound, disable tracking/wobbling and release torque.
It leaves the audio service running. No automatic wake, return, torque setter,
service/OS change, capture or routing write is provided. Keep the marked base
fixed; changed head/microphone height needs review before any later diagnostic
or pilot. This is not experimental-motion validation or pose restoration.

The launcher checks daemon/mode/error/media state, current app, managed-app
slot, API moves and timestamped state responses. Already-disabled mode sends
no command. At most one sleep POST is followed by up to 20 seconds of status
observation, with two-second individual network timeouts (not hard real-time
guarantees). Completion requires two disabled/no-API-move observations with
the daemon/media available. API response timestamps do not prove hardware
sample freshness or achieved pose; direct SDK clients bypass managed-app
tracking, so operator isolation remains required.

The private exclusive local journal is
`data/private/stock_sleep/standard-sleep-once-v1.jsonl`. It blocks reruns even
after failure or missing output; do not delete it to try again. Ctrl+C or
closing the terminal does **not** cancel a movement accepted by Reachy. On
unexpected contact, harsh noise or uncontrolled movement, remain clear and
use physical power only if safely reachable without entering the moving
mechanism/drop area; do not restart or improvise recovery. Send the journal
for review. The launcher never starts the microphone diagnostic.

This supports M5–M6 readiness and displaces no higher-value task. It establishes
no M7 result, acoustic diagnosis or collection permission and stops for unknown
or failed state. Its initial verification used synthetic tests only.

The first operator invocation subsequently failed during SSH connection, before
remote execution; its original private pending log is preserved. The supplied
console evidence, not absence of remote events alone, supports this distinction.
A separate private review binds the exact original-log hash and unchanged
remote-source hash. After that review, `--retry-reviewed-connect-timeout`
permits one replacement attempt with fresh interactive operator confirmation,
the same machine checks and a different exclusive local journal. Missing,
changed or incompatible review evidence blocks it; an existing replacement
log also blocks it. There is no log deletion, reset, automatic retry or third
attempt option. Fourteen synthetic launcher tests pass. The replacement's
private journal subsequently reports one acknowledged sleep request and two
disabled/no-move observations with daemon/media running. The operator reported
the head went down. Closing the desktop app alone had not produced sleep;
do not assume app closure implies disabled motors.

Later SSH/API availability was intermittent; the subsequent preflight lost its
connection and returned no report. A separately supervised ordinary power
cycle restored access at the same address. This does not identify the original
cause or validate Wi-Fi, the microphone, or restoration of a diagnostic route.
No microphone route write or acquisition had yet occurred. The new preflight
report at 2026-10-02T10:01:36Z passes 17/17 machine checks with disabled motors,
the expected running media daemon, no active managed app, baseline routes and
no preceding run close-out. Consumer isolation and the physical setup remain
operator-reviewed, not proved by machine preflight.

## Attempted operator step — stopped before capture; do not repeat

The authorized attempt on 2026-10-02 stopped immediately after scope
confirmation, before the first pair prompt. The saved result has no pair
results and reports `guard_EOF`; `guard.json` was never created. The parent
discarded the child's stderr, so the underlying startup exception was not
retained. This is an error-reporting defect, not evidence identifying a USB,
microphone, network or hardware fault.

The collected after-state matches all 17 baseline parameter values and the
mixer digest, including both original `[8, 0]` routes. Disabled motors and a
running physical media daemon were independently observed. The stable scoped
inventory contains only the four expected numeric/control files and no
unexpected entries. This supports a pre-capture startup failure; it does not
manufacture a missing guard/restoration record or establish microphone health.
Both local and robot close-out remain `PENDING` for review. The original
one-attempt latch is spent and remains in place.

### Completed step — read-only startup probe

`scripts/read_reachy_mic_startup.py --collect` sends
`tools/reachy_mic_startup_probe.py` to Python stdin through host-verified SSH;
it installs no robot file. Default invocation shows help without connecting.
It binds the single failed-run review locally, verifies the unchanged helper
hash remotely, and inspects that exact failed run. A separate private local
one-shot record and report live under `data/private/mic_startup_probe/`; the
old failure records, helper and close-out are never rewritten.

The probe reports named stages: verified identity, failed-run records,
read-only platform checks, baseline parameters/mixer, lock metadata/visible
owners, USB dependencies/backend, matching-device enumeration, and at most
one 500-ms vendor-IN read for each original routing register. Device reads are
skipped if the platform, baseline or lock observations are unavailable or
changed. It repeats read-only state/baseline/inventory observations afterward.
It neither acquires a lock nor opens PCM, starts the guard, writes a route,
sets a resource limit, changes a service, deletes a file or starts a retry.
Ignoring this one pending run during platform inspection reproduces startup
checks for diagnosis only; it does not clear any acquisition gate.

Each stage is flushed before and after its action. Structured failures retain
exception class, missing dependency name, numeric errno/backend code, or USB
response length/status, without arbitrary tracebacks, environments or error
bodies. Partial stdout is preserved after SSH timeout/nonzero exit. Interrupted
or missing output remains unknown. Ordinary SSH/OS logging may occur; this is
not a forensic no-disk-write claim. Software budgets are not hard real-time
guarantees.

This fixes visibility in the new diagnostic path, not retroactively in the
pinned acquisition helper. The original exception cannot be recovered from
discarded output. A transient fault may not recur; lock acquisition, journal
writes, core-limit changes and guard IPC are deliberately not exercised. Even
a clean probe is not acquisition approval or completion of failed-run close-out.
Review its report before choosing a narrowly supported helper correction.

Offline verification: 26 startup-probe/launcher tests pass, including fixed
USB-IN requests, busy/short/error responses without retry, dependency errors,
baseline/owner blockers, partial timeout reports and the one-shot latch. The
full Python suite runs 573 tests: 572 pass and the existing Windows symlink
test is skipped. Alignment/whitespace checks pass and private probe output is
Git-ignored. The helper and failed review hashes are unchanged. These checks
did not identify the original startup cause; the subsequently collected live
probe is reviewed below.

### Observed retry status and local correction — 2026-10-02

The completed read-only probe found the expected device/backend and received
three-byte replies with status `64` for both output-register reads. Pollen's
pinned v1.9.0 source names this `SERVICER_COMMAND_RETRY` and retries a read;
the custom v2 adapter instead raises immediately on every nonzero status.
An offline replay of status 64 through v2 reproduces a startup failure before
the initial guard journal, without any routing write. This establishes a
protocol-handling bug and strongly explains the original `guard_EOF`; its
discarded exception is not recovered proof of that exact historical cause.
No microphone-health or DoA conclusion follows.

The probe's before/after configuration equals the failed-run baseline, motors
remain disabled, and its scoped inventory is unchanged. The existing lock
file has no visible owners in that observation; this is not complete process
isolation. Preserve the original helper, four numeric/control files, probe
report and both spent latches. Failed-run close-out remains pending; no file
has been deleted and no new capture is approved.

The separately named `tools/reachy_mic_health_v3.py` is a LOCAL CANDIDATE, not
a deployed replacement. Its default remains simulation and its command-line
execution/guard modes are explicitly unreleased. It retains the same run
registry and pending-close-out gate, so a new filename cannot bypass v2's
outstanding run. Its differences are:

- Retry only correctly sized status-64 vendor-IN reads, with ten attempts
  maximum, 10-ms inter-attempt waits and one 500-ms total budget per logical
  read. Time already spent is subtracted from each transfer timeout. Outer
  pair/restoration deadlines can only shorten this allowance; no zero
  (unlimited) USB timeout is issued and late success is rejected.
- Transfer exceptions, unknown statuses, short/oversized replies and exhausted
  budgets stop without retry. The write adapter is unchanged and writes are
  never automatically retried. Existing 40-second pair and 5-second restoration
  budgets remain; these remain software, not hard-real-time guarantees.
- Guard startup/session failures travel as structured IPC with stage, fixed
  reason, status/attempt history and numeric error codes. The parent preserves
  these in result metadata even without a guard journal. Bounded exception
  context preserves an earlier failure if cleanup also fails. No arbitrary
  stderr, traceback, environment or audio data is exported.

`scripts/check_reachy_mic_retry.py --collect` prepares one new read-only
verification, not a second audio attempt. It binds the completed private
status-64 report and sends only the preserved read-only probe plus the exact
candidate reader/error definitions through SSH stdin. The candidate's writer,
guard and acquisition code are not transmitted or evaluated on Reachy. No
helper is installed. Both register reads use the bounded policy above, with
fresh baseline/platform/lock checks and after-state/inventory observations.
The generated source, candidate and reader hashes are retained privately.
Output goes to `data/private/mic_retry_check/`, with a separate one-shot latch
and partial-timeout reporting. No general reset/retry switch exists. The narrow
reviewed connect-timeout replacement below preserves all old records.

Review that result before any deployment or acquisition release. Success would
verify only this read protocol in the observed state, not restoration under
fault, shared audio capture, microphone health, pilot readiness or close-out.
Stop for mismatch/unavailable state; no thresholds, services, firmware, OS
settings or frozen pilot files change. This supports M5–M6's startup blocker
and displaces no higher-value task. The first transport attempt timed out
before login; the corrected reader has not run on Reachy yet.

Candidate verification: 110 focused tests ran (109 passed; one existing
Windows symlink test skipped), including the legacy synthetic contracts run
against the candidate and a generated-bundle adapter check. The full suite
ran 683 tests: 681 passed and two instances of that Windows symlink test were
skipped. Alignment/whitespace checks pass; private retry-check output is
Git-ignored. Original v2 helper and probe hashes are unchanged. No robot
connection, installation, capture, cleanup deletion or GitHub write was made
while preparing/testing this correction. Live read success remains unverified.

#### Reviewed pre-login connection failure and one replacement

The first verification's terminal reports an SSH connect timeout before the
password prompt. Its saved report has exit code 255, zero events and zero
invalid lines. That terminal evidence, not exit 255 or empty output alone,
establishes that this particular attempt did not start the reader. A later
operator TCP-port check returned true; this establishes reachability at that
moment, not authentication, daemon readiness or a cause of the earlier failure.

`--retry-reviewed-connect-timeout` permits one separately logged read-only
replacement. It requires the exact reviewed original start/report hashes,
the same prior evidence and run directory, and byte-identical transported
source. It saves to `two-pair-v2-01-connect-replacement-01` under the existing
private retry-check root. Its exclusive start record is written before SSH;
success, another connect failure, interruption or timeout all consume that
replacement. Neither original record is rewritten or removed, and ordinary
`--collect` still refuses the spent original attempt. There is no further
automatic retry, connection-configuration change or release of acquisition.
All platform/disabled-motor checks, after-checks and pending close-out remain.

Offline replacement verification: 117 focused tests ran, 116 passed and one
existing Windows symlink test was skipped. The actual local original-record
bindings and unchanged source hash also passed a no-connection check. This
preparation did not connect to Reachy; the operator must return the replacement
report for review before any subsequent live action.

### Preserved launcher contract

`scripts/run_reachy_mic_diagnostic.py --run-once` is a local, interactive
launcher for the unchanged, hash-pinned v2 helper. Default invocation is help
without a connection. It requires the separate ignored private authorization
and reviewed preflight binding. It creates an exclusive local `PENDING`
close-out record before SSH, refuses a repeated attempt or an unexpected local
entry, verifies the robot helper hash and an empty robot run root, then starts
that helper through an interactive SSH terminal. It does not install a helper,
change its source, or add robot-side services. The robot helper repeats its
fresh machine checks and requires its existing typed scope acknowledgment.

The console directs both pairs: keep the phone paused for each quiet phase;
only when prompted, restart the fixed recording at 50% and press Enter within
ten seconds. Do not press Enter early. The unchanged helper restores/checks
baseline routing between pairs and after completion or abort, with no motion,
firmware, gain, filter, OS or service-setting change. Hardware/connection loss
can still defeat restoration; a timeout is not permission to reboot or retry.

After SSH returns, a separate read-only connection collects the one run's known
numeric/control JSON files and immediate-child file metadata into the private
local session folder. It may ask for the SSH password again. Unexpected names,
links, invalid/oversized records, missing records or changing inventories are
not silently treated as clean; unexpected files are not opened or deleted.
The collection also repeats read-only machine checks. The local record stays
`PENDING` until the outcome, restoration, process-exit evidence and both scoped
inventories are reviewed. No report is a microphone-health pass automatically.

On local interruption or transport timeout, the durable local record remains
pending; the existing independent robot guard retains its recovery role.
`--collect-only` can retrieve read-only evidence after review of the failure;
it cannot launch acquisition, reset the one-run latch or change routing. No
automatic retry exists, including for failure before capture. Preserve all
records. This advances M5–M6's signal-path diagnosis, not the frozen pilot or M7.

## Completed operator step — v2 deployment and read-only preflight

The reviewed launcher creates `/home/pollen/reachy_mic_health_v2.py` exclusively
or reuses an identical file; it never overwrites the existing v1 helper or an
unexpected v2 file. It verifies the pinned source hash and runs only preflight.
The report gathers independent machine blockers together, discloses active
swap without changing it, and saves a private JSON on the laptop under
`data/private/mic_preflight/`. Machine-check success is not execution approval.

For provenance, the completed command in local PowerShell was
(do not repeat it as an automatic follow-on):

```powershell
$reachyProject = (Resolve-Path ".").Path # Run from your local project root.
& "$reachyProject\.venv\Scripts\python.exe" -B "$reachyProject\scripts\copy_reachy_mic_preflight.py" --deploy-preflight
```

Enter the SSH password only at its console prompt. Send the printed report
path or JSON for review. Do not run `--execute`, toggle motors, stop services,
change swap or repeat the old readiness survey as an automatic follow-on.
The earlier snapshot had enabled motors; the fresh post-restart report passes
that check. This launcher reports blockers but does not attempt to fix them.
No media acquisition or routing write
is part of this step. Copying the helper is the only proposed robot file write.

### Corrected reader observed; close-out review and candidate preflight prepared

The reviewed replacement completed on 2026-10-02. Both direct output-register
reads returned status 64 followed by 0, succeeding on their second transfer:
12.380 ms for left and 10.774 ms for right, both returning the original `[8, 0]`.
All probe stages were available; before/after settings matched the failed-run
baseline and its four-file inventory was unchanged. This demonstrates the
bounded retry reader in that observed state, not microphone health, fault
restoration or acquisition readiness. The full candidate remains unreleased.

The private, append-only `closeout-review-v1.json` now records the reviewed
ordinary-file evidence and local metadata inventory. No unexpected entries
were found in the agreed scopes; no deletion is needed there. Original failure,
approval, pending close-out, startup probe and both transport-attempt records
are preserved. The missing guard journal is not fabricated; the original result
remains `RESTORATION_UNVERIFIED`. Matching settings are observed-state evidence,
not a successful test of recovery under failure. Robot return still requires
its final scoped check; there is no forensic-erasure claim.

`scripts/prepare_reachy_mic_v3.py` is prepared and tested locally. Default is
help; `--review-local` only reads known numeric evidence and scoped metadata.
The separately requested `--reconcile-preflight` is one operator SSH action:

1. Revalidate the exact reviewed records/inventory, private run scope, installed
   v2 helper identity, baseline settings twice, and absence of matching
   diagnostic processes or visible lock owners. Do not kill processes or
   create/acquire/remove the diagnostic lock. Other pending runs still block.
2. Only if those checks match, atomically update this run's `closeout.json`
   using the existing close-out function, then read it back and compare the
   remaining files' metadata. The immutable original local export preserves
   the complete prior pending record; `result.json` is never rewritten. This
   is reviewed reconciliation of a pre-capture abort, not an automatic retry
   or a change to what the failed diagnostic demonstrated.
3. Copy the same reviewed candidate to the new exact path
   `/home/pollen/reachy_mic_health_v3_candidate.py`; reuse only identical bytes
   if present, and refuse a conflicting destination. Preserve v1 and v2.
4. Run only that candidate's read-only preflight, without ignoring any pending
   run. Keep `EXECUTION_RELEASED = False`; no guard, capture, routing, motion,
   firmware, service, OS changes or deletion are part of this command.

The local start/report live under `data/private/mic_v3_preflight/`; a durable
exclusive start record prevents repeats, including after connect failure.
Structured partial output is retained on timeout. Interruption may leave the
remote bookkeeping completed but unconfirmed locally: review the report, do
not rerun or infer rollback. Local final close-out remains pending report
review until the live result is checked. Process/lock observations do not prove
complete isolation from arbitrary clients; keep apps closed and phone paused.

Offline tests exercise blocked writes on baseline/record/process changes,
unchanged failure files, generated-bootstrap execution with fake resources,
preflight-only dispatch, default no-connection behavior, and preservation of
partial results and the one-shot latch. This preparation advances the M5 audio
blocker without replacing the live-speaker/playback objective or changing the
frozen pilot. No robot connection, remote record change or deployment was made
while preparing it. Review the live report before considering any new two-pair
run; acquisition, consumer isolation and physical setup need separate approval.

### Observed reconciliation and candidate preflight — 2026-10-02

The single prepared command completed successfully. Its report retains the
original pending close-out, the updated record, and metadata before/after the
update. Only `closeout.json` changed in the run folder; the three other files,
including the failed result, are unchanged. Fresh baseline checks matched and
no matching diagnostic process or visible lock owner was observed. The robot
record is now `CHECKED_NO_UNEXPECTED_FILES`, with capture exit and baseline
state verified. No files were deleted. This resolves this pre-capture abort's
ordinary-file close-out, not the original failed experiment or fault-recovery
validation, and does not certify erasure outside the agreed scopes.

The exact candidate was created at the separate v3-candidate path and all 17
read-only preflight checks passed, including no unresolved robot run, disabled
motors, and unchanged parameters/mixer/configuration. Its execution release
remains false. No audio capture, routing, movement or OS changes occurred.
The local report/source/review identities were checked and the private local
close-out is finalized with `closeout-final-v1.json`, preserving its original
pending record and referencing the untouched raw report. Earlier `PENDING`
fields in immutable reports describe their historical state, not an unresolved
final review. All one-shot records remain spent.

Next is separate preparation and approval for a newly identified two-pair
attempt, with fresh setup/consumer checks; do not reuse the original launcher
or rerun reconciliation. Full guard/capture/restoration operation is not yet
demonstrated on the corrected build. The frozen pilot remains paused with zero
accepted robot-camera trials, and robot return still needs its final scoped
check. This records M5 component progress only; no whole-system claim changes.

### Prepared successor `two-pair-v3-01` — private one-shot approval required

`tools/reachy_mic_health_v3_run.py` is a separately named, session-bound copy
of the reviewed candidate. The candidate and all prior helpers/records remain
unchanged. The corrected USB reader, two-field writer, guard/recovery logic,
capture phases, deadlines, numeric summaries and ordinary-file checks are
unchanged. The successor adds a matching private authorization check in both
parent and guard, structured authorization-stage errors, and exclusive creation
of the fixed run directory below. Default execution is still synthetic only;
preflight remains read-only and cannot approve acquisition.

The prepared helper SHA-256 is
`cb86a5ee1e067d4da2fc093fcfe6e07045e7781a7a177da72ba721af7004c5b3`.
The original candidate remains unreleased at its existing path. The successor
had not yet been copied to Reachy at the preparation stage. Preparation itself
created no local or remote approval. No live start or result was then observed.
No connection, audio, routing, motion,
deletion, OS setting change or publication occurred during preparation.

`scripts/run_reachy_mic_v3.py` defaults to help; `--inspect` checks only local
numeric provenance and reports preparation, not approval. Future `--run-once`
requires fresh explicit approval, with the ignored authorization bound to the
launcher, both transport dependencies, successor helper, reviewed candidate
preflight, completed old close-out receipt and exact scopes. There is no CLI
approval generator or retry/reset switch. The approved workflow would:

1. Recheck local close-out and original evidence, inventory the new private
   local session, and durably mark it `PENDING` before the first SSH connection.
2. Verify no pending robot run, unchanged old run metadata/close-out, and no
   existing new session directory. Copy only the new successor helper, with
   exclusive creation or identical-byte reuse, never overwrite another helper.
3. Run fresh read-only preflight. Only a passing result may install the exact
   separately approved session capability. A failed check stops the workflow
   before guard/capture, preserving the report and spent local latch.
4. Open one interactive SSH session. The parent repeats live machine checks
   and requires the existing typed scope acknowledgment; it exclusively creates
   this session's robot directory before any route write or capture. The guard
   independently verifies the matching authorization and exact session path.
5. Follow the same two-pair phone prompts, restoring/checking between pairs and
   after completion/abort. Once the session returns, collect only this run's
   known numeric JSON and immediate-child metadata over a read-only connection.
   The local close-out remains pending until review of both scopes and recovery.

The three SSH stages may each request the password in the operator's console.
The launcher never receives or stores it. Transport timeout/interruption is
not cancellation or restoration proof; preserve all state and review before
using read-only `--collect-only`. That mode cannot retry capture or clear a
latch. A missing remote directory is reported as missing, not clean. An
unexpected file is inventoried without opening or deleting it. The original
failed launcher, replacement probes and reconciliation command remain spent.

Exact proposed paths:

- New helper: `/home/pollen/reachy_mic_health_two_pair_v3_01.py`.
- Private session capability: `/home/pollen/reachy_mic_two_pair_v3_01_authorization.json`.
- Robot run/file-check scope: `/home/pollen/reachy-mic-health-runs-v2/run-two-pair-v3-01/`.
- Laptop run/file-check scope: `data/private/mic_closeout/two-pair-v3-01/`.

No new motion or sleep operation is included. Before approval, the operator
must freshly confirm the resting/stable head, clear mechanism/drop area and
accessible physical power control, closed robot apps/browser/media clients,
and no other audio consumers. Leave the daemon running; machine checks must
observe disabled motors. Use the same fixed recording at 50%, phone initially
paused at the front one-metre mark at the current microphone height. Accept
only two ordered routing pairs and transient local audio with numeric output;
ordinary-file close-out is mandatory, OS residuals remain possible and recovery
can fail after hardware/power loss. No pilot, firmware/gain/service change,
camera, motion, automatic wake/return, deletion or publication is included.

Offline verification runs the inherited synthetic acquisition/recovery/close-out
contracts against the new helper, checks source-level equivalence of all
unchanged measurement/control definitions, and tests the added session gates,
generated transports, failed deployment/preflight, timeout, scope drift and
numeric-only collection. These establish software behavior, not live shared
capture compatibility, microphone health or fault-recovery validation.

Verification for this preparation: 112 focused tests ran (111 passed; one
Windows symlink check skipped). The full suite ran 818 tests (815 passed;
three instances of the existing Windows symlink check skipped). Project
alignment and whitespace checks pass. The offline provenance check verifies
the prior final close-out/candidate report and both helper identities; it
reports no authorization and the new local run directory is absent. The future
private run/approval path is Git-ignored. These checks do not open the live gate.

Before operator handoff, an offline Windows check identified that the nested
approval used backslashes for a robot path while Linux would require slashes.
The successor now serializes that remote scope explicitly as POSIX; a regression
test compares Windows and POSIX path representations. Only this serialization
and its build binding changed; the capture/routing/recovery implementation and
preserved candidate are unchanged. Private authorization must bind the corrected
hash above. This correction was made before any successor approval or deployment.
The corrected build passes 113 focused tests (112 passed, one Windows symlink
skip) and the full 819-test suite (816 passed, three instances of that skip).
Operator handoff records belong only in the ignored private session folder;
their existence is not evidence that deployment, acquisition or close-out ran.

### Observed first-pair quiet capture and operator timeout — 2026-10-02

The successor deployment and fresh preflight completed. Its guard preserved
the baseline, reserved only Pair A, and verified the temporary `[3, 0]` / `[3, 1]`
routes before capture. Three quiet blocks, each 16,000 frames per channel, were
summarized. No playback phase or Pair B measurement was completed. The helper
stopped after the ten-second playback-confirmation window (`operator_deadline`),
with `ABORTED_REVIEW_REQUIRED`; this is not a microphone-health failure or a
completed diagnostic comparison. The result is not relabelled or discarded.

The guard reports `ROUTES_RESTORED`, `dirty=false`, and terminal completion;
the capture exit is verified. The separately collected read-only after-check
passes all 17 checks, and both original routes, all other parameters, the mixer
and ALSA configuration match the preserved baseline. This observes recovery
after this operator timeout, not a guarantee for hardware/power loss.

The robot before-inventory was empty; its stable after-inventory contains only
the five expected numeric/control JSON files, with no missing/invalid records
or unexpected entries. Its close-out is `CHECKED_NO_UNEXPECTED_FILES`. The
local review also verified the before/export inventories, original artifact
hashes and after-inventory, and finalized the private local close-out with a
separate receipt preserving its initial pending marker. Nothing was deleted.
This concerns only the two agreed run scopes, not global audio absence, swap,
filesystem/backup erasure, whole-robot readiness or the final return check.

The one-shot session remains spent. Next is separately requested preparation
of an unambiguous PAUSE / PLAY-existing-clip workflow and a newly identified,
approved attempt if still needed. Do not reuse this approval, reset a latch,
weaken a timeout or resume the frozen pilot. No successor is prepared or
authorized by this result review; accepted pilot trials remain zero.

### Clear-phone-cue successor `two-pair-v3-02` — 2026-10-03

This is a new offline-prepared attempt, not a retry of a spent launcher or a
change to the measurement protocol. The helper is
`tools/reachy_mic_health_v3_play.py`, SHA-256
`240a7bf400bab72bffd28c8db0def8decfcd37f35a0b62d115477d937606b7d8`;
the launcher is `scripts/run_reachy_mic_v3_play.py`. The old v3-01 source
and all earlier helpers/launchers are preserved byte-for-byte.

The exact proposed paths are:

- robot helper: `/home/pollen/reachy_mic_health_two_pair_v3_02.py`;
- robot private capability: `/home/pollen/reachy_mic_two_pair_v3_02_authorization.json`;
- robot metadata scope: `/home/pollen/reachy-mic-health-runs-v2/run-two-pair-v3-02`;
- local private scope: `data/private/mic_closeout/two-pair-v3-02/`.

There is no new private authorization or run record from preparation. A fresh
approval must bind this helper, launcher, dependencies, both finalized
predecessor receipts, the exact scopes, consumer isolation and physical setup.
The launcher verifies both prior local inventories; deployment also compares
both prior robot inventories and close-out records, then requires fresh
preflight before the interactive helper. Missing records or changes stop it.
No previous approval, directory or one-shot marker is reused or cleared.

The local `--walkthrough` mode is offline and performs no file writes. An
approved `--run-once` also presents the same instructions and waits for `READY`
**before** creating its pending record or making its first SSH connection.
This reading/preparation step has no time limit and cannot substitute for the
separate private authorization or the helper's existing acknowledgement.

For each pair the phone workflow is:

1. **PAUSE:** same existing clip paused at the start, unchanged 50% volume,
   front mark, one metre, microphone height. Press Enter once when ready.
2. **WAIT:** remain silent with phone paused; do not press Enter.
3. **PLAY THE EXISTING CLIP NOW:** tap Play on the phone, then press Enter once
   in the terminal within the unchanged ten-second confirmation window.
4. **WAIT:** keep the clip playing, without further Enter presses or pausing,
   until the helper verifies pair restoration and prints **PAUSE THE PHONE NOW**.
5. Pause playback. For Pair 2, return the same clip to its start while paused
   and follow the next cue. Stop after Pair 2 or any interruption; do not rerun.

The phone plays an existing stimulus; the operator does **not** make a new
recording. The diagnostic itself still consumes transient robot microphone
samples. Two-second flushing, three-second quiet, ten-second operator deadline,
two-second settling, ten-second playback, capture/guard deadlines, two-field
routing allowlist, restoration, process exit and close-out are unchanged.
Only session identity and console prompts differ in the standalone helper.
No automatic retry, new sound cue, firmware/gain/OS/motion change, raw-media
file/export, pilot release or erasure guarantee is added. A final scoped check
before returning the robot remains required independently of these closed runs.

Offline verification covers prompt order on synthetic PCM, unchanged frame
counts/deadlines, early Enter and missed-play aborts, helper AST equivalence
after removing console text and session identity, predecessor provenance,
both local/robot metadata checks, absent-approval refusal, exclusive session
records, Windows/POSIX scope equality and inherited capture/guard/close-out
contracts. These are software checks, not evidence of microphone health or
permission to acquire. The focused suite ran 121 checks (120 passed, one
Windows symlink skip); the full suite ran 940 (936 passed, four Windows symlink
skips). Offline provenance inspection passed with no new authorization present.
The next action is fresh scoped operator approval,
not a new experiment launched by this preparation step.

### V3-02 first-pair preparation abort and close-out — 2026-10-03

The local lowercase `ready` entry stopped before a start record or SSH. A later
invocation accepted the walkthrough confirmation, deployed the exact helper,
passed 17/17 checks, and reached the robot-side start acknowledgement. It then
stopped at the separate first-pair preparation prompt after about 30 seconds,
with `ABORTED_REVIEW_REQUIRED` / `preparation_not_confirmed`.

The result has no pair entries. The guard reserved zero pairs, remained clean,
finished terminally and reports `NOT_CHANGED`. There was no diagnostic capture
or routing write. The after-check passes 17/17 with both routes, all sentinel
parameters, mixer and ALSA configuration equal to baseline. The stable robot
inventory has exactly the five expected numeric/control files, no missing or
invalid records, no unexpected entries and a completed ordinary-file close-out.

The local final receipt preserves the initial pending marker and hashes of the
original evidence, mirrors that robot close-out, and records an after-inventory
of the local numeric records. Both agreed scopes are checked; no files were
deleted or old start markers reset. Later repeat commands were blocked locally
because the session was spent. They do not constitute further diagnostic runs.
No whole-device audio-absence, forensic-erasure or robot-return claim follows.

### Single-start successor `two-pair-v3-03` — prepared offline

New helper: `tools/reachy_mic_health_v3_start.py`, SHA-256
`a7b5771d39ba40356b4eff60ff7bfe4434b5b48da374f4b89eb3c5935435096d`.
New launcher: `scripts/run_reachy_mic_v3_start.py`. Old sources and approvals
remain bound to their old sessions and cannot authorize this one.

Proposed exact paths:

- helper `/home/pollen/reachy_mic_health_two_pair_v3_03.py`;
- private capability `/home/pollen/reachy_mic_two_pair_v3_03_authorization.json`;
- robot inventory `/home/pollen/reachy-mic-health-runs-v2/run-two-pair-v3-03`;
- local inventory `data/private/mic_closeout/two-pair-v3-03/`.

The launcher checks approval and spent state before displaying its overview.
The overview is informational, takes no READY input, and contains no example
live PLAY cue. The robot-side full acknowledgement is now explicitly labelled
as the **start of Pair 1**, with the existing phone clip paused at its beginning
at 50%. After that acknowledgement and fresh state checks, Pair 1 begins without
a separate Enter prompt. It still refuses missing/wrong private approval or
acknowledgement and baseline/state drift before any route write or capture.

This consolidates two adjacent first-pair readiness confirmations into one
clearly announced start action; it does not increase an active measurement
deadline. Pair 2 still requires a separate paused-at-start confirmation within
30 seconds, only after Pair 1 restoration. The quiet/flush/settle/playback
lengths, ten-second playback confirmation, capture/guard/restoration limits,
pair count, routing allowlist, sentinel checks, process cleanup and numeric-only
retention are unchanged. The remote execution's existing overall time limit
also remains unchanged. No automatic retry, movement or output sound is added.

All three previous close-outs are pinned and checked locally and during
deployment. The new scope needs a fresh private approval, fresh preflight and
current operator setup/consumer confirmation. No new authorization or start
record is written by offline preparation. The pilot remains at zero accepted
trials; this is operator-workflow repair, not evidence of improved microphones.

Offline verification: the focused suite ran 120 checks (119 passed, one
Windows symlink skip); the full suite ran 1,060 (1,055 passed, five Windows
symlink skips). Tests exercise the single start, explicit pre-start disclosure,
wrong-acknowledgement refusal, unchanged active measurement and restoration
logic, fresh drift refusal before Pair 1, separate Pair-2 preparation, spent
session refusal before overview/SSH, all three predecessor inventories, and
the inherited authorization/capture/guard/close-out contracts. Offline inspection
passes with no v3-03 authorization or run directory present. Source hashes and
earlier records remain preserved; project alignment and whitespace checks pass.

### V3-03 playback-confirmation timeout and close-out — 2026-10-03

The approved single-start attempt passed preflight, reserved Pair 1 and
collected three quiet blocks (48,000 frames per channel). It then stopped with
`ABORTED_REVIEW_REQUIRED` / `operator_deadline`. There is no playback summary
and no second-pair entry; do not interpret this as microphone failure or a
successful comparison. The subsequent operator account is consistent with a
missed terminal confirmation, but the record establishes only that the helper
did not accept Enter within the deadline.

The guard is terminal and clean with `ROUTES_RESTORED`; capture exit is verified.
All 17 after-checks pass, and the routes, sentinel parameters, mixer and ALSA
configuration match baseline. The saved stable robot inventory contains only
the five expected numeric/control files, with no missing or invalid records.
Its scoped close-out is `CHECKED_NO_UNEXPECTED_FILES`. The private local final
receipt preserves the original pending marker and source hashes, mirrors the
robot check, and records a verified local after-inventory. No files were deleted,
no robot connection was made for this review, and the original failed result
and one-shot state remain intact. Robot return still requires its final check.

### Explicit confirmation successor `two-pair-v3-04` — prepared offline

Helper: `tools/reachy_mic_health_v3_confirm.py`, SHA-256
`315e2a0e38fc17d66ca8bab1043bbafa6640ec5caf60b7cbc7ebad2f67e05c5d`.
Launcher: `scripts/run_reachy_mic_v3_confirm.py`.

Proposed exact paths:

- helper `/home/pollen/reachy_mic_health_two_pair_v3_04.py`;
- private capability `/home/pollen/reachy_mic_two_pair_v3_04_authorization.json`;
- robot inventory `/home/pollen/reachy-mic-health-runs-v2/run-two-pair-v3-04`;
- local inventory `data/private/mic_closeout/two-pair-v3-04/`.

The helper differs from v3-03 only in session identity and displayed instructions.
At the live PLAY cue, it displays two separate actions: tap Play on the phone,
then immediately press Enter once in PowerShell, both within ten seconds.
`ENTER RECEIVED` appears only after that input is accepted. Phone playback alone
is not confirmation; the operator must not wait for the clip to finish.
The offline overview does not display a live PLAY cue or request input.

The single start acknowledgement, separate Pair-2 preparation, two-pair limit,
capture phases, all deadlines, routing allowlist, restoration, numeric retention
and process/file checks are unchanged. No automatic retry or motion is added.
The launcher binds all four closed predecessors locally and rechecks their
exact robot inventories before installing a new session capability. Offline
preparation writes no new authorization or start marker. Fresh scoped execution
approval and current physical/consumer setup remain required; the live launcher
must still pass fresh machine checks. Earlier approval is not transferred.

Focused offline verification: 124 tests, 123 passed and one Windows symlink
skip. This includes AST equivalence apart from identity/prints, live cue order,
confirmation acknowledgement, timeout without Enter despite incoming synthetic
PCM, capture cleanup, and local/remote predecessor drift refusal. These tests
do not establish live microphone health or reopen the frozen pilot.

Full offline verification: 1,184 tests, 1,178 passed and six Windows symlink
skips. Project alignment and whitespace checks pass. Offline inspection verifies
all four prior receipts and reports no v3-04 authorization. No new run directory,
robot connection, deployment, capture, route write, motion or deletion occurred
during this preparation. The source identities of earlier attempts remain intact.

### V3-04 first pair completed; second-pair preparation abort — 2026-10-03

Pair 1 completed three seconds of quiet and ten seconds of playback: 48,000
and 160,000 frames per channel respectively, with all thirteen blocks preserved.
The input acknowledgement was accepted. Original routes and sentinel settings
were restored before the separate Pair-2 preparation prompt. That preparation
was not confirmed; Pair 2 was never reserved or captured. The overall result
remains `ABORTED_REVIEW_REQUIRED` / `preparation_not_confirmed`, not a pass.
The operator reports not seeing the between-pairs prompt.

The final guard is terminal and clean, capture exit is verified, and all 17
after-checks pass with parameters, mixer and ALSA configuration equal to baseline.
The stable remote inventory contains only the five expected numeric/control
files with no missing or invalid records. The private local final receipt
preserves the original pending marker and source hashes, mirrors the scoped
robot check and records a verified local after-inventory. Both scoped close-outs
are `CHECKED_NO_UNEXPECTED_FILES`. Nothing was deleted, no robot connection was
made for finalization, and no old start marker was reset. This preserves useful
first-pair measurements without filling in the absent second pair or asserting
microphone health. The final check before robot return remains separate.

### Prominent Pair-2 successor `two-pair-v3-05` — prepared offline

Helper: `tools/reachy_mic_health_v3_ready.py`, SHA-256
`95a37ca4aac2a4c76c5e24cb311d35ded2aaacf33fc1577c95ccffe7248f95cf`.
Launcher: `scripts/run_reachy_mic_v3_ready.py`.

Proposed exact paths:

- helper `/home/pollen/reachy_mic_health_two_pair_v3_05.py`;
- private capability `/home/pollen/reachy_mic_two_pair_v3_05_authorization.json`;
- robot inventory `/home/pollen/reachy-mic-health-runs-v2/run-two-pair-v3-05`;
- local inventory `data/private/mic_closeout/two-pair-v3-05/`.

The helper changes only session identity and displayed instructions. Pair-2
preparation is now a separated multi-line banner, each line at most 78 characters:
pause and rewind the phone, then press Enter once in PowerShell while the phone
remains paused, within the unchanged 30 seconds. It states that this Enter starts
the second quiet phase and that playback must wait for the later live PLAY cue.
The overview and pre-start disclosure tell the operator to stay in PowerShell
until the final report and send screenshots afterward. No alert sound, repeated
prompt, new input action, timer reset or automated retry is added.

Pair-1 acknowledgement, both capture routines, the ten-second playback input
deadline, routing allowlist, guard/restoration checks and retention are unchanged.
The launcher pins and rechecks all five closed predecessor scopes before a new
capability can be installed. Earlier approvals cannot authorize this session.
Offline preparation creates neither authorization nor a run record; fresh scoped
approval, current manual setup/consumer review and live machine checks remain
required. The frozen pilot still has zero accepted trials.

Focused offline verification: 126 tests, 125 passed and one Windows symlink
skip. Checks cover prompt-only AST changes, readable banner content, unchanged
preparation/capture functions, readiness after restoration, refusal on missing
input or baseline drift, and all five local/remote predecessor checks.

The full offline suite ran 1,310 tests: 1,303 passed, seven Windows symlink skips.
Project alignment and whitespace checks pass. Offline inspection verifies all
five prior receipts and no new authorization/run directory. No robot connection,
deployment, acquisition, routing write, motion, deletion or publication occurred
during preparation; old helper identities and numeric evidence remain preserved.

## Current retention scope and mandatory per-run close-out

D029 governs current preparation. Keep raw diagnostic audio out of saved files
and exports; preserve derived numeric results and recovery evidence. Leave
swap, systemd units and the daemon's resource limits unchanged. A later scoped
file check can find ordinary saved files in the agreed locations; it cannot
certify that no audio exists elsewhere, identify audio inside swap, or prove
forensic erasure after deletion. Do not wipe swap or unrelated robot data.

Use this checklist for **every authorized microphone diagnostic**, including
failed or interrupted runs. Do not rely on conversational memory:

1. **Before acquisition:** create a unique private close-out record under the
   Git-ignored `data/private/mic_closeout/`. Record the run ID, UTC start time,
   execution-build identity and exact agreed robot/laptop inventory locations.
   Inventory file metadata only (path, type, size, timestamps and access errors),
   including unexpected extensions; do not open, hash, play or upload audio.
   Do not follow symlinks/reparse points outside the agreed scope or silently
   expand to whole disks/home directories. Preserve pre-existing files.
2. **On success or any abort:** stop acquisition through the approved diagnostic
   recovery path, verify diagnostic children have exited, and record route/
   sentinel restoration separately. Compare the same scoped file metadata
   with the baseline. Missing access or a disconnected robot is `PENDING`, not
   a clean result; resume the check when authorized access returns.
3. **If unexpected media is found:** record exact paths privately and establish
   which files belong to this run. Timestamps alone do not prove ownership.
   Obtain approval for those specific files before removal. Never delete the
   phone's fixed stimulus, unrelated recordings, active lock files or numeric
   recovery/failure evidence as part of audio cleanup. Do not use broad globs
   or recursive deletion against a general directory.
4. **Verify and record:** repeat the scoped check after approved cleanup. Record
   what was removed, whether it remains recoverable (or that this is unknown),
   and whether any unexpected files remain. Use `CHECKED_NO_UNEXPECTED_FILES`,
   `CLEANED_AND_RECHECKED`, or `PENDING` with a reason. These describe ordinary
   file visibility in the stated scope, not secure erasure or robot readiness.
5. **Before the next diagnostic and before robot return:** review all run
   records, resolve outstanding close-out, and make the final scoped check.
   A known run with no record is unresolved, not evidence that nothing was
   saved. Unaffected offline analysis and preparation may continue.

Each private record must include the before/after inventory references, run
outcome (including abort), restoration status, unexpected-file review, any
exact-path cleanup approval/action, final check time/scope/result, and pending
reason/next action. Keep approval details outside Git; do not fabricate a run
or a clean baseline when no acquisition has occurred.

V2 now implements the robot-side pending record, bounded before/after inventory
and unresolved-close-out gate. Its exact remote scope is one new directory
under `/home/pollen/reachy-mic-health-runs-v2/`, not other robot folders. It
reports unexpected filenames, non-regular entries or leftover atomic-update
files for review; it does not inspect their contents or certify that every
expected JSON file is media-free by content inspection. No cleanup deletion
command is exposed. Missing/inaccessible/corrupt records block a subsequent
diagnostic. A killed process leaves its pre-existing pending record for review.
The operator workflow still requires the local private run record/mirror and
specific scope approval before acquisition; no live run command is issued here.
A daily reminder in the working chat is a
backup: it checks available local records for newly outstanding cleanup, not
the robot itself, and performs no recording or deletion. No extra routine
robot/OS hardening is required by this checklist. Later research stages need
their own explicit retention scope; no universal no-swap rule is introduced.

## What the preceding audit establishes

- The observed USB device exposes two capture and two playback channels at
  16 kHz, S16_LE. Both streams were running in the supplied status snapshot.
- The capture mixer controls were enabled at 100% / 0 dB. Speaker playback's
  62% is a different control.
- Installed `audio_doa.py` and `audio_control_utils.py` hashes match the audited
  v1.9.0 reference files. This verifies those two files, not the entire runtime.
- The filtered current-boot kernel log returned no matching entries. This
  neither excludes unlogged faults nor establishes historical stream health.
- Earlier numeric configuration reads reported firmware 2.1.2 and both output
  routes `[8, 0]`. These are historical observations, never restoration values
  to assume without fresh reads.
- The operator's subsequent screenshots show the actual shared capture alias
  `reachymini_audio_src`: `dsnoop`, IPC key 4242, `hw:0,0`, stereo, 16000 Hz,
  period 1024 and buffer 4096 frames. The buffer represents 256 ms at this rate;
  it is not an end-to-end latency measurement.
- The reported owner of both hardware PCM nodes is the existing Reachy daemon:
  `python -u -m reachy_mini.daemon.app.main --wireless-version
  --no-wake-up-on-start`. Leave it running. The startup flag does not prove the
  current motor state, and ownership does not enumerate remote media consumers.
- Subsequent read-only operator output identifies the active swap as
  `/dev/zram0`, with priority 100 and zero used at that observation. Its backing
  device is `/dev/loop0`, backed by `/var/swap` on the ext4 root filesystem at
  `/dev/mmcblk0p2`. The observed core-dump pattern is `core`. This is persistent
  backing storage, not proof that any particular audio reached storage. Neither
  current memory headroom nor the daemon's core-size limit was established by
  that screenshot alone; the later v2 report below supplies a newer snapshot.

These findings do not identify the cause of the direction errors. Two USB
channels are not four independent microphone observations, and the four
`AEC_SPENERGY_VALUES` entries describe beams, not physical microphones.

## Proposed temporary change

The vendor's output selector supports individual amplified microphone signals
before beamforming, with the existing system delay. Use category **3** so this
check does not confuse quiet pre-amplification quantization with a dead sensor.
The current microphone gain would remain unchanged. This tests the delivered
signal path, not an isolated microphone capsule.

| Stage | `AUDIO_MGR_OP_L` | `AUDIO_MGR_OP_R` |
|---|---|---|
| Baseline | Freshly read and preserved | Freshly read and preserved |
| Pair A | `[3, 0]` — microphone 0 | `[3, 1]` — microphone 1 |
| Between pairs | Exact baseline value | Exact baseline value |
| Pair B | `[3, 2]` — microphone 2 | `[3, 3]` — microphone 3 |
| Finish or abort | Exact baseline value | Exact baseline value |

Only these two parameter names may be written. The source-index interpretation
is documented by the vendor but must still be checked for this installed
firmware; it is not physically verified by the earlier configuration reads.
Readback must confirm both assignments before any samples are labelled.

No firmware update is proposed. Do not use `SAVE_CONFIGURATION`,
`CLEAR_CONFIGURATION`, USB reset, gain/filter changes, mixer setters, service
restart, app start, motor APIs, a robot speaker output, or a camera. In
particular, this is **not command-free**: the two routing fields are device
writes requiring separate approval. They affect every consumer of the USB
capture output while active, not merely the diagnostic.

## Gate 1 — configuration observed; fresh execution preflight still required

The actual alias and hardware owner above were inspected read-only by the
operator. They support preparing a shared-capture helper, not declaring capture
compatibility proven. The helper requires this exact configuration (ignoring
comments/whitespace), card 0 USB identity `38fb:1001`, the two audited source
hashes, and the reviewed daemon command line. If a file/tool is missing or
access is denied, stop without installing tools, using `sudo`, killing
processes, or editing `.asoundrc`. `fuser` inspection is not proof that all
shared-memory clients or remote consumers have been enumerated.

Before execution, also establish that no robot application, browser/WebRTC
consumer, recorder, conversational service, or monitoring client could save,
transmit, respond to, or actuate on the temporarily rerouted audio. Check daemon
status, current app, session clients and local process ownership. Unknown
consumers block execution. Any required disconnection must be presented in the
approval scope; do not stop the daemon to obtain access. No new motor lifecycle
transition is part of this procedure.

Under D030, fresh status must show the physical media daemon `running`, motor
control mode explicitly `disabled`, media available, no active application,
and no daemon/backend error. Daemon `stopped` is not a substitute for a verified
motor mode and would also remove the needed media service. `backend.ready` is
not used as a motor-mode signal. The reviewed readiness report does not pass:
it reports mode `enabled`. If the required state is absent or
unknown, block this procedure; do not issue a stop/disable command as an implied
part of audio preparation. Recheck before each pair and abort on state drift.

Require a verified, unmodified stereo path to this exact USB card at 16 kHz
and S16_LE, with no downmix, channel duplication, codec, AGC, or resampling.
Do not use the default device, laptop microphone, or WebRTC audio as a fallback.
The observed 4096-frame ALSA buffer fits within the proposed two-second flush,
but upstream timing remains unmeasured. `arecord --fatal-errors` stops on an
xrun instead of recovering silently; the helper also stops on stderr, early
EOF or a two-second read stall. Unreported upstream losses remain a limitation.
An unavailable or busy source is a stop, not permission
to change audio services. Do not invoke the SDK's `.asoundrc` writer or volume
control constructors to perform preflight.

## Gate 2 — implementation and approval requirements

The standalone source is `tools/reachy_mic_health.py`; its test file is
`tests/test_mic_health.py`. It imports hardware libraries only in the explicit
robot guard mode. Its default mode uses a fake device and synthetic samples.
It constructs no Reachy SDK object and exposes no generic parameter writer.
Preparation is not permission to deploy it or use `--execute`.

The implementation must:

1. Record and persist a small private recovery manifest **before** any write:
   baseline routes, device/firmware identity, source configuration hash, and
   numeric sentinel settings (microphone/reference gain, selected channels,
   system delay, AEC/AGC/noise-processing settings and mixer state). Missing or
   unexpected baseline data blocks the run. Approvals stay outside Git.
2. Enforce a two-field write allowlist and validate values, device identity,
   baseline and expected current route before each transition. Stop for
   unexpected changes by another client; never silently take over its state.
3. Treat the two writes as non-atomic. Any error, timeout or mismatched readback
   after the first write requires attempting restoration and verification of
   **both** baseline routes. An unreadable route or a foreign value is not
   overwritten blindly: mark restoration unverified and stop. Never proceed
   with one old and one new channel.
4. Use bounded low-level control calls and a separately tested restoration
   supervisor, not a laptop-only `finally` block. The stock helper has a
   100,000-ms transfer timeout and retries; it cannot be assumed to meet this
   proposal's deadlines. Do not patch that installed helper in place.
5. Enforce at most 40 seconds of acquisition/waiting per pair and then initiate
   restoration. Bound control operations to 500 ms per call and the complete
   route-restoration attempt to a nominal 5-second budget, including route
   readbacks. Do not start another operation after its budget expires. These
   are software timeouts, not hard real-time guarantees. Separate read-only
   sentinel checks follow restoration; their parameter-read budget is 10
   seconds, plus bounded platform/mixer checks. Supervision must
   survive an SSH disconnect or main-helper failure and prohibit later writes
   by an expired measurement worker. No overlapping diagnostic instances.
6. Restore after Pair A before any operator pause or Pair B. Restore after
   Pair B or any abort. Require two successful baseline readbacks and matching
   sentinel checks before reporting `RESTORED`. `RESTORATION_UNVERIFIED` keeps
   all experiments blocked; there is no automatic restart, reset, retry of the
   measurement, or claim that power cycling restores the exact prior state.
7. Use fake audio/control adapters for offline tests covering a zero channel,
   stuck nonzero samples, clipping, ordinary speech-like signals, duplicate
   channels, partial writes, short reads, buffer discontinuity, Ctrl+C,
   disconnect, main-worker death, supervisor failure, wrong device, unauthorized
   parameter, baseline drift and failed restoration. No hardware in these tests.

These remain requirements, **not hardware guarantees**. The offline tests
exercise fake device writes, a real subprocess pipe's EOF, fake PCM phase
transitions and failures. Real Linux session loss, USB timing, shared-capture
compatibility and physical restoration have not been demonstrated.
Hardware loss, power loss or failure of both processes can prevent restoration;
that residual risk must be disclosed and accepted before execution. Never
describe unsaved routing as guaranteed reversible merely because no flash-save
command is sent. Do not erase recovery evidence on failure.

## Retired temporary protection design — historical, do not execute

**D029 supersedes this design.** The v2 report identifies a swap-bound service
whose stop action resets zram, conflicting with the design's no-reset scope.
The proposed swap/core changes, supervisor and lifecycle below are retained
only as decision history. They are not the current implementation plan or
operator instructions. The independent read-only report remains useful; its
completed v2 review is recorded below. No swap/core toggle is authorized.

### Objective and limit

This preparation advances M5–M6 by defining a bounded way to investigate the
blocked microphone path. It produces a reviewed design, not permission to
change the robot, a demonstrated privacy guarantee, or a microphone result.
It displaces no higher-value experiment: acquisition is already blocked. Stop
design expansion if it requires persistent OS changes, a daemon restart, or
an unbounded security-hardening project.

The project-wide baseline is numeric research artifacts with no intentional
raw-media recording/export. That is distinct from the stronger statement that
no raw byte can ever reach OS-managed storage. Do not silently substitute one
claim for the other. At this historical design stage the v1 helper was unchanged
and refused enabled swap. D030 now implements the replacement local v2 contract;
the robot's existing v1 copy is still unchanged.

The proposed session can suppress new swap/core-file writes during its verified
window. It cannot prove forensic erasure, exclude previous persistence, or
prove all shared daemon/driver copies have disappeared before normal settings
return. Restoring swap or dump capability may expose still-resident copies
later. This residual issue needs an explicit scope decision before execution;
do not label the proposal an absolute, all-lifetime RAM-only solution.

### Non-interference requirements

- No edits to `/etc/fstab`, swap configuration, `.asoundrc`, service units,
  boot configuration, installed SDK/daemon code, firmware, or calibration.
- No deletion, recreation, formatting, zeroing or detaching of `/var/swap`,
  `/dev/loop0` or `/dev/zram0`; no reset of zram and no `swapoff --all`.
- No global `core_pattern` change, package installation, daemon restart,
  permanent root access, robot-side background service or recurring automation.
- No CPU, address-space or memory-allocation limit imposed on the daemon.
  Preserve its core-dump **hard** limit; lowering it can make ordinary-user
  restoration impossible. Change only a verified process's soft core limit
  if it is not already zero and that change is separately approved. [S2]
- No microphone gain, volume, camera processing, pilot threshold or scientific
  condition changes. The two routing fields remain a separate approved scope.
- This wrapper is not imported by the camera recorder, pilot, controller or
  future response adapter. Its stop state concerns this diagnostic and any
  actual unresolved shared-device fault, not unrelated offline research work.

### One consolidated read-only readiness report

Before proposing exact executable settings changes, collect one report, rather
than making the operator discover each remaining check through a new failed
launch. Continue read-only checks after a failure and report all results; do
not open audio or bypass the execution gate.

Record fresh memory totals/availability, swap use/device/priority, the zram/
loop/backing-file relationship, swap-manager configuration relevant to automatic
reactivation, and the core-dump pattern. Identify the daemon by command line,
UID, PID and process start time (not the historical PID alone). Read its soft
and hard core limits, relevant child/consumer processes, current app, motor
state and errors. Check the exact restoration tools and narrowly scoped
privileges without modifying sudoers or changing a resource.

Freeze the numeric memory margin from this report and the helper's bounded
memory requirement before a live run. Budget for existing used swap plus the
helper and a reserve for the daemon/OS; a historic zero-use reading is not
sufficient. If the margin is inadequate, do not disable swap, evict memory,
kill applications automatically or silently reduce the margin. Swap removal
can fail through insufficient memory and removes a memory-pressure fallback.
[S1] No claim of zero slowdown or zero OOM risk is justified by this design.

#### Prepared one-command report (not a protected run)

`tools/reachy_mic_readiness.py` implements this metadata survey independently
of the unchanged microphone helper. `scripts/read_reachy_mic_readiness.py`
sends its source to the reviewed Python interpreter's stdin through SSH with
host-key checking enabled and bytecode writing disabled. It does not install
a second robot file, change resource limits, acquire media, read swap contents,
open PCM/USB devices, construct the SDK, or alter any robot setting. Normal SSH
and OS audit logging may still occur; this is not a forensic no-disk-write claim.

Run this in **local Windows PowerShell**, not at the robot's `pollen@…` prompt:

```powershell
$reachyProject = (Resolve-Path ".").Path # Run from your local project root.
& "$reachyProject\.venv\Scripts\python.exe" -B "$reachyProject\scripts\read_reachy_mic_readiness.py" --collect
```

Enter the password only at OpenSSH's console prompt. Characters are invisible.
After login, allow roughly a minute for the report. The launcher prints the
exact JSON path under the Git-ignored `data/private/mic_readiness/` directory.
Attach that JSON for review; do not run the microphone helper afterward.
Without `--collect`, the launcher only prints help and makes no connection.

The report includes memory and swap snapshots before/after, the observed zram
and loop topology, core pattern, fresh daemon PID/start ticks/UID/limits,
visible hardware owners/direct children, the two allowlisted daemon/app GETs,
swap-related systemd unit metadata, filtered known swap configuration fields,
and tool paths. It does not export process environments, arbitrary command
arguments, full application records or journal logs. Missing files, permissions,
timeouts and other failures are retained as unavailable fields while later
checks continue. A 60-second cooperative collection budget and per-command/API
timeouts bound ordinary checks; they are not a hard real-time OS guarantee.

Narrow privilege probes use `sudo -n -k -l -- <candidate>` **only to list
policy**, never to execute the candidate. They neither prompt for a sudo
password nor refresh cached credentials. A positive listing is not a promise
of password-free future restoration; a negative one may reflect authentication
requirements rather than absent permission. Proposed swap activation flags
still require review against the actual manager configuration. [S5]

Every report explicitly says `execution_authorized: false`. This collector
cannot establish complete consumer isolation, freeze a memory margin, resolve
the privacy-scope choice, or validate an unbuilt protection supervisor. Missing
manager settings and scripts must be identified during review, not inferred
from priority alone. It adds no checks to the frozen pilot or later controller.
Offline fixtures cover continuation after failures, process identity drift,
soft/hard limit parsing, metadata filtering, command/HTTP restrictions,
list-only privilege probes and local transport/output handling. These tests do
not establish live robot readiness.

#### First live report and v2 correction — 2026-10-02

The private v1 report completed without acquisition or configuration writes.
It observed about 3.14 GiB available RAM, zero reported active swap use at both
snapshots, and a zero soft core limit in the existing daemon and its observed
direct child. No daemon core-limit change is indicated by that snapshot; future
execution still requires fresh state. Disk-backed zram and an active writeback
timer remained present. The daemon API reported `running`, no top-level error,
and no current app. The report did **not** retain motor control mode, so neither
motion nor a disabled motor mode can be inferred from that daemon state.

The seven unavailable entries were four absent alternative configuration files,
one failed unit inventory and two failed template-unit inspections. They were
not seven robot faults. The three unreported non-comment lines in
`/etc/rpi/swap.conf` cannot be called three active settings: the upstream default
has three section headings that v1 also discarded. The actual corrected read,
not that upstream example, must determine local content. [S7]

The v2 correction advances M5–M6 by resolving these diagnostic reporting gaps,
not by authorizing the blocked experiment. It displaces no higher-value task,
preserves all pilot files/gates and the deployed microphone helper, and stops
before any acquisition or system-setting change. Changes are limited to:

- `reachy-mic-readiness-v2` identity and fresh, uniquely named private output;
  the original v1 JSON remains unchanged.
- Source-filtered swap/zram/loop unit inventories; no runtime query of bare
  `@.service` templates. Query observed instances, including loop setup, and
  retain dependency, stop-command and timer metadata. Read command text as
  metadata only; never execute it or stop any unit.
- Correct `mockup_sim_enabled` field and selected `backend_status` fields:
  readiness, motor control mode and error presence. Missing/malformed fields
  remain unknown. Daemon `running` and motor mode remain distinct observations.
- Known Raspberry Pi configuration section headings/settings and bounded
  reads of relevant main/drop-in directories, including generated zram config.
  No sourcing, edits or presumed effective precedence. Optional absence is
  separate from permission/query errors; truncation/unknown content is explicit.
- Standard system-directory fallback for tool lookup, not tool installation.
  Privilege queries remain list-only; skip needless daemon-limit policy queries
  when its observed soft core limit is already zero.
- Fixed error reason codes for oversized/failed metadata commands, without
  exporting arbitrary stderr, secrets or API error bodies.

The original microphone helper also checks the incorrect `mockup` field; it
was deliberately **not** changed or redeployed in that reporting-only
step. D030 now corrects the local v2 schema/motor-state checks before any later execution,
separately from the actual motor-mode/consumer/privacy requirements. A readiness
report cannot bypass those requirements; daemon `running` alone is not an
accepted execution state.

Verification: 34 read-only collector/launcher tests and 51 unchanged microphone
helper tests pass (85 total), using fixtures only. These include the upstream
status shape, running-daemon/disabled-motor distinction, optional absence versus
denied access, source-filtered inventories, instance/template handling, relevant
drop-ins, sbin lookup, error codes, zero-limit no-op behavior and no mutating
commands. These tests establish no live readiness pass, microphone result or
protection-supervisor validation. The subsequent v2 report has now been
collected and reviewed; do not repeat it merely because the historical
preparation instructions describe collection.

#### Reviewed v2 result and scope decision — 2026-10-02

The private v2 report has zero unavailable checks; fifteen optional paths are
absent, not failed. It observes about 3.15 GiB available RAM, zero active swap
use at its snapshots, disk-backed zram, and zero soft core limits in the
collector, daemon and observed direct child. These are point-in-time metadata,
not evidence of no previous or future media persistence.

The live unit metadata includes `BindsTo=dev-zram0.swap` on the zram setup
service and an `ExecStop` invoking `zram-generator --reset-device zram0`.
Stopping swap cannot be assumed independent of that teardown. This conflicts
with the proposed no-reset restoration scope, so D029 retires the temporary
swap/core plan without running it. Do not stop units or reset/detach storage.

The daemon reports `running` and motor mode `enabled`; complete isolation of
other media consumers is not established. The report explicitly does not
authorize execution. The selected preparation boundary is application-level
numeric artifacts with disclosed OS residuals and mandatory ordinary-file
close-out, not absolute RAM-only handling. The original helper's no-swap gate
and schema check are unchanged; any successor needs reviewed implementation
and fresh separate acquisition/routing approval. D030's local implementation
subsequently replaces these checks for v2; the robot's v1 file remains intact.

### Historical proposed change and restoration scope — superseded by D029

| Surface | Temporary action, only after separate approval | Restoration and evidence |
|---|---|---|
| Exact active swap device `/dev/zram0` | Deactivate this device only, after checking headroom; confirm no active swap before capture | Reactivate the same unchanged device with its freshly recorded priority and relevant activation options; verify the original backing relationship and active state |
| Existing audio daemon | If required, set only its soft core-size limit to zero after preserving both limits and process identity | Restore the exact soft value only to the same process; leave the hard limit unchanged; never restart or target a reused PID |
| New diagnostic/guard/capture processes | Zero their own core allowance before consuming audio | These limits end with these processes; verify all diagnostic children exit |
| Audio output routing | Only the separately approved two-field, two-pair diagnostic | Existing per-pair restoration/readback plus sentinel verification; no added routing authority |
| Global/persistent configuration | No change | Relevant baseline hashes and service configuration must still match |

Do not treat enabling `/var/swap` directly as restoration: the active swap
device observed here is `/dev/zram0`. Do not use broad enable-all operations or
flags that reformat/discard storage. Exact relevant swap activation options
must be established, not inferred from priority alone. Device data placement,
counters, timestamps and logs will not be bit-identical after runtime use.

### Historical session lifecycle and recovery — superseded by D029

1. Complete operator setup and the consolidated report before protection begins.
   Preserve a private numeric baseline/recovery record before the first write.
2. Start a tested robot-local supervisor with only the narrowly approved
   restoration capabilities. It must outlive the SSH terminal and measurement
   process. An ordinary laptop-side `finally` block is insufficient.
3. Confirm the same stopped motor backend and absence of other media consumers.
   Apply/verify per-process dump protection and then the exact swap change.
   Open no diagnostic audio until every required check passes. Failed partial
   setup triggers restoration, never a capture attempt.
4. Admit only the prescribed two pairs. Propose a **five-minute outer lease**
   covering setup after the first change, pauses, capture and start of cleanup;
   retain the tighter 40-second per-pair and existing route-restoration budgets.
   This is a software abort deadline, not a promise that kernel calls or
   recovery finish by five minutes. No automatic lease extension or retry.
5. Monitor memory headroom, identity/state, swap reactivation and supervisor
   health. An abnormality, Ctrl+C, terminal loss or expired lease stops the
   diagnostic. The measurement worker must be unable to continue routing after
   expiry. Do not kill or restart the existing daemon.
6. Stop only diagnostic-owned capture processes, await the route guard's
   restoration attempt, retain numeric fault results, then restore the saved
   process limits and swap state. Attempt independent restoration steps even
   when another step fails; do not leave swap disabled merely to preserve an
   unachievable absolute privacy claim. Recovery must report any weakened
   protection, not hide it. Residual-buffer limits above still apply.
7. Compare the after-state with the baseline: same device/priority/backing,
   same live daemon identity and limits, unchanged configuration, no remaining
   diagnostic children or outstanding temporary runtime setting, and verified
   audio routes/sentinels. Read-only status should show no new error. This is
   configuration restoration, not proof of camera/ASR/motion performance.

If the daemon exits or is replaced, do not restore a limit to a reused PID and
do not restart it. If restoration fails, preserve the exact discrepancy and
seek targeted recovery approval; do not reset/reboot or keep experimenting on
unknown robot state. Unaffected code, analysis and planning can continue.
Power loss, kernel stalls and failure of the supervisor can defeat restoration;
no plan can promise they will never cause a delay.

### Avoiding a permanent research detour

This procedure expires with the microphone diagnostic. Once restoration is
verified, it leaves no policy that disables normal camera/audio processing,
ASR, later bounded movement, attention hold or response. Those stages still
need their own already-existing validation and safety approvals; this proposal
neither adds a universal no-swap requirement nor grants those capabilities.

Implementation should provide one start/check/restore workflow and one report,
not a sequence of manual global-setting commands. Require offline failure
rehearsal of partial setup, memory pressure, timeout, disconnect, PID reuse and
failed restoration before any protected run. The existing 447 tests did not
test this new supervisor; do not cite them as protection validation.

Do not turn one rejected preflight into repeated live attempts or a requirement
to harden all of Reachy's OS. If this bounded approach needs service changes,
cannot preserve adequate memory headroom, or cannot meet the chosen privacy
scope, return with one explicit decision: approve a narrower application-level
retention claim with disclosed OS residuals, or assess a separately scoped
isolated sensing path. Neither alternative is silently authorized here. A
process-local memory lock alone does not protect all other readers/copies.
[S4] No experiment or protection modification has been executed for this plan.

### Historical approval and implementation boundary — superseded by D029

The former next deliverable was a readiness report and a concrete supervisor
design/test result; D029 retires that supervisor proposal. This plan authorizes no swap operation,
daemon resource-limit change, audio rerouting or acquisition. Live approval
must name those exact temporary changes, the privacy scope/residuals, recovery
behavior and the two-pair limit. No new gate may be silently propagated into
the frozen pilot or later research protocols.

## Proposed operator sequence after both gates pass

One sequence only, with two pairs; no outcome-driven repeats.

- Keep Reachy and its head fixed. For this diagnostic only, place the single
  iPhone at the **front** phone mark, one metre from the head and at microphone
  height, speaker aimed toward Reachy. This is not the 60-degree conflict mark.
  Preserve all original marks. No second phone or video recording is needed.
- Use the same fixed recording and 50% volume. Remain silent; no face visibility
  requirement or camera input is needed for this signal-path check.
- For Pair A, verify the routes and drain/discard at least two seconds of fresh
  input (and more than the verified pipeline buffering). Measure three seconds
  of quiet. The console then gives a visual prompt: restart the recording from
  its beginning and confirm within ten seconds. Discard two seconds after that
  confirmation, then measure ten seconds of playback. There is no audible cue
  from Reachy. Restore both routes and verify them before pausing the phone.
- Repeat the same prescribed sequence once for Pair B, then restore and verify.
  Any unexpected noise, motion, device loss, overrun, missing samples, failed
  write/readback or missed deadline aborts the entire sequence for review.

The measured periods total 26 seconds; settling and operator preparation add
time. The 40-second per-pair deadline includes waiting, not just measurement.
The recording segment is restarted consistently, but manual timing and the two
different acquisitions prevent sample-aligned comparisons across all four mics.

## Numeric-only data and interpretation

Audio is consumed transiently **on Reachy** in bounded in-memory buffers, not
sent to the laptop, played back, transcribed or written as a waveform. Only
per-second and whole-phase summaries leave the helper. No debug sample dumps,
raw-media hashes or camera samples. The implementation must account for crash
dumps and swap when stating the retention scope. V2 records active swap as an
OS-residual limitation, not a reason to disable it. It still refuses a piped
core-dump collector or a nonzero core-dump allowance in the existing daemon.
During execution it sets a zero core-dump limit only for its own process and
children; read-only preflight does not set limits. It does not alter the
daemon's limits or system configuration. A
failed privacy preflight needs review, not permission to turn off system
features. Closing external consumers remains an operator requirement; the
helper cannot prove it automatically.

For each actual microphone index and phase, retain sample counts, elapsed time,
read errors/discontinuities, normalized DC mean, DC-removed RMS, peak magnitude,
digital-zero and full-scale sample fractions, and longest unchanged-sample run.
For signed 16-bit input normalize by 32768. Report RMS in dBFS; zero RMS is an
explicit zero/silence flag with a null logarithm, not an invented finite floor.
Retain within-pair exact-equality fraction and correlation (undefined for zero
variance), not samples. Count clipping at both signed rails. Preserve partial
numeric results and all routing/restoration outcomes when an abort occurs.

Report playback-minus-quiet RMS levels as descriptive changes, **not calibrated
SNR**. There is no absolute dBFS pass threshold or threshold fitted to these
observations. Report signal response, conspicuous pair imbalance, clipping,
stuck output or inconclusive acquisition for review; none alone establishes a
defective capsule. Correlated channels are expected under common speech, so high
correlation alone is not proof of duplication. Do not compare pair delays as
four-channel time-of-arrival evidence or fit a new DoA offset/sign correction.

Even a response on all four paths does not validate DoA, audio–lip synchrony,
playback rejection, motion or restoration of the robot's entire borrowed state.
The result remains a separate diagnostic, never a pilot trial or permission to
resume collection. If valid samples cannot be obtained without broader changes,
stop and seek a new decision rather than expanding the procedure.

## Prepared artifact, staged approval and cleanup

Proposed v2 deployment is one new file, `/home/pollen/reachy_mic_health_v2.py`,
using `/venvs/mini_daemon/bin/python -I -B`. Preserve the deployed v1 file.
Before copying, inspect the destination;
never overwrite an existing file without review. Compare SHA-256 before/after
transfer. No package installation or installed-source edit is proposed.

The first requested approval is **deployment plus `--preflight` only**. This
mode reads status/configuration and prints numeric/control metadata. It does
not open a capture, change routes, create recovery files or authorize execution.
The current helper source SHA-256 is
`01b14cb7ac76c67c81bba12a11509dafc97c8eac8b28ceada0982cf1a8bc0e7d`.
Recompute and review it if the helper changes.
The historical deployed v1 hash remains
`cec964cabc30060b8f497d491fdc3037635321cb0fc063b6b71957493b8d28bc`.

Only after reviewing that output and establishing consumer isolation may a
separate approval cover `--execute`: two ordered microphone pairs, the exact
two-field temporary routing above, transient local capture, and restoration.
Execution additionally requires the operator to type the displayed scope
confirmation in an interactive terminal. There is no automatic follow-on
capture after `--preflight` and no hardware activity in the default mode.

An approved execution would create a private random directory
`/home/pollen/reachy-mic-health-runs-v2/run-<random>/` containing `baseline.json`,
`approval.json`, `guard.json`, `result.json` and `closeout.json`, plus transient
`.new` files for atomic updates. The root/run directories are private; links,
unexpected ownership and shared permissions are rejected on the robot.
These contain settings, approval scope, numeric statistics and fault outcomes,
not audio. A mode-0600 `/tmp/reachy-mic-health.lock` prevents overlapping guards;
the guard deliberately does not unlink its lock while active. Preserve all
numeric recovery files on failure, copy them privately for review, and verify
both routes plus sentinels before any cleanup. Remove only the exact reviewed
helper, run directory and inactive lock after separate cleanup confirmation;
no broad home-directory or `/tmp` deletion. Do not erase recovery evidence or
reset the robot. Numeric records survive an ordinary terminal disconnect;
this is not a power-loss durability or secure-erasure guarantee.

Historical v1 offline check: 51 helper tests passed, including silent/stuck/clipped/duplicate
signals, fragmented PCM, complete and interrupted phases, driver error/EOF,
stalls, operator timeout, simulated robot/guard loss, partial writes, write
timeouts, drift preservation, journal errors and failed restoration. Tests use
no robot, camera, microphone or network connection. Passing them establishes
software behavior only; the signal-path cause and live restoration remain
unknown.

The historical full Python suite passed 447 tests before the readiness/v2 additions.
The project-alignment check passes and the pilot attempt directory remains
empty. No test count changes a physical milestone or authorizes collection.

### V2 local verification — 2026-10-02

The full Python suite completed 513 tests: 512 passed and one Windows symlink-
creation test was skipped because this host did not permit creating the test
link. Six additional launcher self-tests passed, including the pinned source
hash, exclusive/new destination behavior and read-only report contract.
The v2-specific tests cover explicit motor modes and missing status fields,
active-swap disclosure without changes, aggregate failures, no preflight
execution authority, per-run pending/after records, interrupted runs, unexpected
files, stale temporary files, bounded inventories, previous pending runs and
capture-process-group shutdown failures. No sensor, USB device or robot was
opened for these tests; Linux process/permission behavior remains to be checked
in the separately approved live scope.

Alignment and whitespace checks pass. The frozen pilot execution/private seal
still verifies, with zero accepted trials and Trial 1 / attempt 1 unchanged.
Its local `ready` status concerns the saved binding, not fresh acoustic health
or permission to resume collection. V2 was subsequently deployed and its
read-only preflight reviewed: the first report passed 16/17 checks with motor
mode unverified; the later post-restart report passes all 17. No acquisition
or routing followed that preflight before the separately authorized attempt.
That attempt later failed at guard startup before acquisition, as recorded
above; the one-attempt local launcher is not permission to try again.

## Sources and verification boundary

- [Vendor output selection and beam telemetry](https://github.com/respeaker/reSpeaker_XVF3800_USB_4MIC_ARRAY/blob/master/host_control/README.md#output-selection): selector categories/indexes; no independent-microphone interpretation of beam energy.
- [Pollen media controls](https://huggingface.co/docs/reachy_mini/platforms/reachy_mini/media_advanced_controls): four-microphone array with a stereo USB output; current six-channel firmware option is not proposed here.
- [Pollen v1.9.0 control implementation](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/media/audio_control_utils.py): read decoding, transfer timeout and non-transactional bulk apply behavior.
- [Pollen v1.9.0 ALSA template](https://github.com/pollen-robotics/reachy_mini/blob/v1.9.0/src/reachy_mini/media/audio_utils.py): shared input alias; the observed robot configuration above takes precedence over template buffer defaults. Do not execute its configuration-writing function.
- [ALSA shared capture](https://www.alsa-project.org/alsa-doc/alsa-lib/pcm_plugins.html#pcm_plugins_dsnoop): multiple readers do not imply isolation from global input routing.
- [Process-owner inspection and permission limits](https://manpages.debian.org/bookworm/psmisc/fuser.1.en.html): `-v` displays information; restricted visibility can leave other users' processes unreported.
- [ALSA capture command](https://manpages.debian.org/bookworm/alsa-utils/arecord.1.en.html): stdout capture, explicit format and fatal-error behavior.
- [Linux core-dump behavior](https://man7.org/linux/man-pages/man5/core.5.html): piped core collectors can ignore the core-size limit.

[S1] [Linux swap activation/removal](https://man7.org/linux/man-pages/man8/swapoff.8.html): specific-device operations, priority, memory-related failures and potentially destructive flags.

[S2] [Process resource limits](https://man7.org/linux/man-pages/man2/getrlimit.2.html): soft versus hard limits, core size, and process-specific changes.

[S3] [Linux zram writeback](https://docs.kernel.org/admin-guide/blockdev/zram.html): compressed RAM can have backing storage; zram reset is not a harmless inspection. Merely pausing writeback leaves a later-persistence question. The historical v1 no-active-swap gate is replaced by v2's explicitly disclosed application-level scope, not by an OS setting change.

[S4] [Memory locking](https://man7.org/linux/man-pages/man2/mlock.2.html): locking applies to specified mappings/process memory and has resource/capability limits; it is not proof that another consumer's copies are protected.

[S5] [Sudo policy listing](https://man7.org/linux/man-pages/man8/sudo.8.html): `-l` with a candidate lists permission without executing it; `-n` prevents prompting and `-k` with a listing ignores cached credentials without refreshing them.

[S6] [Process identity fields](https://man7.org/linux/man-pages/man5/proc_pid_stat.5.html) and [systemd read-only inspection](https://man7.org/linux/man-pages/man1/systemctl.1.html): process start ticks are recorded alongside PID and boot ID; `show`/unit listings inspect state without starting or stopping units.

[S7] [Raspberry Pi default swap configuration](https://github.com/raspberrypi/rpi-swap/blob/main/etc/rpi/swap.conf) and [configuration fields and drop-ins](https://github.com/raspberrypi/rpi-swap/blob/main/man/man5/swap.conf.5): section-aware parsing and relevant override locations. These upstream references do not establish the robot's installed configuration or authorize configuration changes.

The operator's subsequent output confirms helper deployment and a matching
hash, followed by a read-only preflight stop at swap. The protection plan used
local documentation/source review and supplied read-only observations only.
No diagnostic audio capture, routing write, swap change or daemon-limit change
has been executed. The pilot remains blocked at zero accepted trials.
