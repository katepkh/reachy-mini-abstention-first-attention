# Decision log

Canonical status: **ACTIVE**
Reconstructed: **2026-09-25**

This log records project-level decisions, not private correspondence. Dates identify the best repository/conversation reconstruction available; they are not a claim that every decision was made in one instant.

| ID | Date | Decision | Why | Supersedes or constrains |
|---|---|---|---|---|
| D001 | 2026-08 | The primary objective is a real robot that orients, maintains bounded face-directed attention, and responds to a live visible speaker while refusing silent-person plus phone-playback hard negatives. | This is the intended useful behaviour and the research problem exposed by early playback errors. | Governs every intermediate stage and the charter. |
| D002 | 2026-08 | Treat false social/physical activation as more costly than abstention. | A plausible but wrong orientation is more damaging to the project claim than a conservative refusal. | Requires explicit `ABSTAIN`/`HOLD` and hard negatives. |
| D003 | 2026-08-25 | Do not call acoustic/face geometric agreement speaker ownership. | A silent visible face plus spatially separate phone speech produced compatibility confirmations. | Supersedes early interpretations of spatial agreement as sufficient evidence. |
| D004 | 2026-08 to 2026-09 | Keep candidate inference, passive cueing, operator arming, and mechanical readiness separately inspectable until deliberately integrated. | This prevents passive evidence from silently authorizing hardware. | Constrains integration design; does not make separation the final objective. |
| D005 | 2026-09 | Preserve the failed 3° V3 physical trial and do not weaken its thresholds. | Changing a gate after observing failure would invalidate the result. | Blocks relabelling V3 and constrains any successor to a new frozen protocol. |
| D006 | 2026-09 | Reject custom centring on the borrowed robot under the reviewed evidence. | Calibration, target observability, collision/load, and failure-response evidence were insufficient. | Blocks command-capable centring; permits read-only diagnosis. |
| D007 | 2026-09 | Keep private outreach, replies, identities, and approval records outside Git and outside the research evidence. | Privacy and the user’s explicit publication preference. | External operational decisions may be satisfied without repository evidence. |
| D008 | 2026-09 | Pause the 54-trial confirmation before Trial 1. | The current recorder lacks acoustic-direction and policy inputs required to identify frozen spatial endpoints. | Supersedes the earlier plan to begin multi-room collection immediately. |
| D009 | 2026-09-25 | Restore end-to-end real-world behaviour as the critical path. | Laptop confirmation and manuscript work had begun displacing the unachieved robot objective. | Supersedes “paper/confirmation first” prioritization; it does not erase useful component evidence. |
| D010 | 2026-09-25 | Treat the manuscript as a working evidence synthesis, not submission-ready research completion. | The integrated controller, physical success, playback refusal, attention hold, response path, and held-out validation are absent. | Removes the premature paper-PDF/release framing. |
| D011 | 2026-09-25 | Require the five canonical records and a strategy gate before substantial work. | Conversational memory and polished artifacts were not reliable project-state controls. | Governs future planning, context recovery, experiments, claims, and publication. |
| D012 | 2026-09-25 | Keep GitHub publication as a separate explicit decision after local amendment and review. | A valid local commit can still be strategically wrong, private, overstated, or incomplete. | Blocks automatic publication of the current local commit. |
| D013 | 2026-09-25 | Scope the first integrated candidate gate to speakers already visible in the camera and treat audio–lip synchrony as condition-specific association evidence, not liveness. | Out-of-view acquisition requires a separate safe search policy, while synchronized video or deliberate lip-sync can defeat a synchrony-only interpretation. | Narrows D001's first implementation without changing its real-robot positive/negative objective; constrains M5–M6 claims and evaluation. |
| D014 | 2026-09-25 | Separate the working-system, research-validation, and optional publication gates. | A functioning robot interaction is the primary engineering goal; scientific validation is stronger evidence; a paper or repository release is not itself completion and need not precede the working system. | Clarifies D001, D009, D010, and D012 without deprioritizing eventual research evidence. |
| D015 | 2026-09-26 | Require a mouth-activity-plus-speech-activity baseline without synchrony and retain silent mouthing with unrelated playback as a mechanistic hard negative. | Silent-face phone playback alone could be rejected by detecting an inactive mouth and therefore cannot identify synchrony's incremental value. | Refines D008 and D013 without changing the primary real-world phone-playback negative. |
| D016 | 2026-09-26 | Select final study size from a predefined precision or power target only after joint-instrument commissioning and a no-motion pilot. | Arbitrary participant or trial totals do not control uncertainty, availability, clustering, or the positive-engagement operating point. | Blocks treating the existing 54-trial schedule or any suggested total as an evidence standard. |
| D017 | 2026-09-26 | Treat the passing joint capture as observability commissioning only and freeze a new 21-trial no-motion pilot before further collection. | The transferred V2 synchrony setting abstained on the commissioning positive and selected its best allowed lag at the boundary; one positive cannot justify threshold or lag changes. | Opens a predeclared development/internal-validation pilot, preserves the 54-trial pause, and prohibits tuning on commissioning or validation data. |
| D018 | 2026-09-26 | Require the joint-pilot analyzer and a content-addressed, ignored private setup seal before Trial 1. | Trial labels, thresholds, baselines, stimulus identity, device selection, and geometry must not drift during collection or be repaired after outcomes are visible. | Closes pilot collection until the analyzer manifest is current and the private binding seal verifies; retains zero motion/response authority. |
| D019 | 2026-09-30 | Invalidate joint-pilot v1 and replace it with a separately fingerprinted v2 protocol using a `0.06` minimum median normalized inter-eye scale and condition-specific browser quality reporting. | V1's `0.16` gate was incompatible with the sealed one-metre/approximately 60° camera geometry and had never been demonstrated in either pre-pilot commissioning capture. Geometry and the two pre-pilot scale distributions independently support `0.06`; v1 outcome attempts are excluded from threshold selection and all later analysis. | Supersedes only D017–D018's v1 protocol identity. Preserves their 21-trial design, development/validation boundary, private seal, no-retuning rule, and zero motion/response authority. V1 files and attempts remain preserved but cannot be reused. |
| D020 | 2026-09-30 | Reject v2 Trial-1 attempt 1 on its frozen acquisition gates, preserve it privately, and expose live face scale plus momentary face/DoA readiness before repeating the same trial. | Browser and offline checks agreed: single-face fraction was 23.9% and median normalized inter-eye scale was 0.0569, below the frozen 95% and 0.0600 gates; all speech, DoA, timing, spatial, privacy, and command checks passed. The operator otherwise had no live view of the gated scale. | Does not change D019's threshold, protocol conditions, analysis, or trial order. No v2 trial is accepted; Trial 1 must be repeated under a newly content-addressed and resealed execution build. |
| D021 | 2026-09-30 | Reject v2 Trial-1 attempt 2 on its frozen acquisition gates, preserve it privately, and block pilot capture until condition-aware face state plus five consecutive fresh valid DoA polls and the expected speech flag are present. | Attempt 2 fixed the visual failure (95.7% single-face coverage; median scale `0.0638`) but DoA was valid in only 47.8% of rows, p95 DoA age was 1782 ms, and speech was detected in 6.5%. The stream recovered after capture, identifying a transient preflight/readiness failure rather than evidence about the candidate. | Does not change D019's thresholds, conditions, analysis, or order. The new preflight enforces existing acquisition requirements before capture; zero v2 trials are accepted and Trial 1 remains next. |
| D022 | 2026-09-30 | Pause the laptop-camera v2 pilot before any accepted trial and require command-free commissioning of Reachy's actual camera before freezing a successor pilot. | The primary objective is robot behaviour, while v2 observes face/lip evidence through the laptop webcam. Completing 21 laptop-camera trials would leave an untested transfer to Reachy's camera geometry, transport, latency, and landmark quality. Zero v2 trials were accepted, so correcting the sensor boundary now avoids invalidating collected evidence later. | Supersedes D021's instruction to repeat v2 Trial 1, but does not relabel or delete either rejected attempt. V2 remains preserved development infrastructure. A successor protocol may be frozen only after the separately specified real-camera commissioning checks pass; motion and response remain unauthorized. |

### D023 — 2026-10-01: repair processing before further camera collection

Retain both failed Reachy-camera commissioning attempts and the unchanged v1
numeric thresholds/fingerprint. About 30 received frames/s became only 9.4/9.8
distinct analyzed frames/s; synchronous browser inference plus an additional
30-ms wait is a measured implementation bottleneck. Move inference to a bounded
GPU-preferred worker, declare CPU fallback, add five-second performance
preflight and numeric failure diagnostics, and record a separate execution-build
fingerprint. Preserve zero robot command authority. The second capture's zero-
face gaps are observed but their visual cause is unknown; do not fill them or
relax detector settings. This implements D022's repair branch, does not change
the objective or acceptance thresholds, and keeps pilot collection blocked.

### D024 — 2026-10-01: remove DoA/frame server contention without changing gates

Retain both post-worker commissioning failures alongside the first two. The
no-hat capture has 100% face and joint-spatial coverage but only 13.99916 analyzed
fps. The preceding capture has 66.53% coverage and 14.99745 fps; neither passes.
All eight slow fetches in the no-hat capture overlap a pending DoA request, and
a synthetic test reproduces the single-threaded server's blocking behaviour.
Replace that serialization with two reusable HTTP workers, four bounded pending
slots, single-flight uncached DoA reads, serialized receiver lifecycle, and
numeric queue/worker/pipeline diagnostics. Do not restore unbounded per-request
thread creation or change landmark settings or any frozen threshold. This
continues D022–D023's M5 repair branch, establishes no live throughput pass, and
keeps the pilot and all robot motion/response unauthorized.

### D025 — 2026-10-01: move conversion off reception and correct local frame age

Retain the fifth failed commissioning capture: 14.84108 analyzed fps with 100%
face, DoA and joint-spatial coverage, failing only the rate gate. Long HTTP waits
were absent, but consecutive bridge frames still had a roughly 305-ms gap.
Pixel conversion ran on the receiving event loop and was excluded from frame
age; a synthetic delay reproduced that blind spot without establishing live
causation. Move conversion into the existing single-flight worker, reject late
results after terminal state, and carry pre-conversion receipt and stage timing
with each frame. Record the corrected age origin in a separate v3 execution
build/v2 timing definition; do not rewrite old captures or change thresholds.
This continues D022–D024's M5 repair path. Software tests cannot open the pilot
or authorize motion/response; live improvement must still pass the frozen gates.

### D026 — 2026-10-01: accept scoped commissioning and freeze robot-camera pilot

The sixth Reachy-camera capture passes the unchanged v1 observability checks:
16.99881 analyzed fps, 99.20% one-face/joint coverage, 100% valid DoA, and
159.45 ms p95 local frame age on the verified conversion-timing build. Preserve
all five failed captures; exclude all six from fitting and validation. This
satisfies D022–D025's commissioning prerequisite only, not M5 selection or any
whole-system goal.

Freeze a separately fingerprinted robot-camera no-motion pilot with seven
conditions, fourteen development trials and seven locked internal-validation
trials. Keep the earlier candidate grid and acquisition gates, add the original
robot timing/rate gates, and derive lip timing from distinct frame receipt
estimates rather than repeated display samples. Fix the timing convention,
bounded retry rule and boundary-lag stop rule before collection. The laptop
microphone remains an explicitly external sensor. Require a new private seal
and matching microphone, preserve every attempted pair, and freeze development
selection before opening validation. No laptop-camera attempt can be reused.

This replaces D025's pending-live-check next action, not the objective or any
historical failure. Pilot collection is conditional on the tested execution and
private binding gates. Movement, attention hold, response and publication remain
separately unauthorized. See `ROBOT_CAMERA_PILOT.md`.

### D027 — 2026-10-01: isolate playback preflight diagnostics from the frozen pilot

The operator reports phone playback at the unchanged sealed setup while the
pilot screenshot shows `speech=false` and a direction warning. This does not
establish a persistent detector failure or physical misplacement. The pilot
start gate cannot capture that state, and its direction warning also evaluates
no-speech readings. At the operator's request, add a separately identified
ten-second receive-only diagnostic that records missing speech, unexpected
direction and unavailable DoA without using those observations as start gates.
Keep camera/model/face/processing and matching-microphone readiness, explicit
operator playback confirmation, numeric-only output and zero command authority.

Do not edit D026's frozen source files, thresholds, manifests, seal or attempt
accounting. Diagnostic downloads use a distinct non-pilot schema and cannot be
imported as pilot evidence. They are excluded from fitting and validation. Stop
after one diagnostic pair for review; do not raise volume, move marks, relabel a
detector miss as a successful hard negative, or weaken a gate to obtain a pass.
This supports M5–M6 debugging and does not supersede D026's collection boundary.
See `ROBOT_CAMERA_DIAGNOSTIC.md`.

### D028 — 2026-10-01: separate three-position direction check

The playback diagnostic records speech-active direction readings about 25°
from a near-centred face, below the frozen 40° conflict gate. A read-only audit
finds that the conversion agrees with Pollen's v1.9 convention; the inherited
metadata incorrectly names its sign as robot-right-positive, while both numeric
paths use robot-left-positive. The pilot warning also evaluates non-speech
angles and cannot establish physical misplacement. Neither issue justifies
changing the observed direction or weakening the gate.

At the operator's request, prepare one separate front / 60° robot-left / 60°
robot-right diagnostic sequence, ten seconds at each position, same iPhone,
recording and sealed 50% volume. Keep Reachy, its head, laptop and existing marks
fixed; add temporary marks at the existing right mark's horizontal distance.
For this diagnostic, keep the phone speaker at head/microphone height across
all three marks. Record that distance and explicit operator confirmation, not claimed
instrument-measured ground truth. Correct the coordinate description only in
the new diagnostic's metadata; preserve the inherited contract as provenance.

This extends D027's one-pair stop rule only for this new three-position check.
Keep its separate schema, source fingerprints, numeric-only data, no command
authority and exclusion from all pilot fitting/validation. Preserve raw angles;
interpret direction only during fresh speech-active readings. Do not fit an
offset, certify calibration, retune, change volume, or move positions to obtain
a pass. Stop after the sequence or an interrupted capture for review. No frozen
pilot file, seal, threshold or attempt accounting changes. Zero accepted pilot
trials remain zero. Browser-local numeric recovery copies and a start journal
prevent accidental untracked repeats; no raw media is retained.

### D029 — 2026-10-02: scoped retention and repeatable diagnostic close-out

Prepare the microphone signal-path diagnostic under an explicit application-
level retention boundary: no intentional raw-media file recording or export;
retain derived numeric evidence. Ordinary-file inspection and deletion cannot
identify or selectively erase audio fragments in OS swap, filesystem remnants
or backups. Do not promise forensic erasure or all-lifetime RAM-only handling.
Private approvals and run records remain outside Git.

This supersedes the temporary swap/core-toggle proposal in
`MICROPHONE_HEALTH_DIAGNOSTIC.md`, not D026's frozen pilot or the charter's
real-robot objective. The reviewed v2 metadata identifies a swap-bound setup
service with a zram-reset stop action, conflicting with the proposed no-reset
restoration scope. Leave OS settings untouched; do not implement that proposal.
The deployed helper remains unchanged and blocked. Any implementation change,
fresh motor/consumer check and acquisition/routing approval remain separate.

Make ordinary-file close-out part of every authorized microphone diagnostic,
including aborted runs: a private run record, an agreed scoped before/after
metadata inventory, review of unexpected diagnostic-created audio, exact-path
cleanup approval, and an absence recheck. Preserve numeric recovery/failure
evidence and unrelated files. Resolve outstanding close-out before another
such diagnostic and perform a final scoped check before robot return. A daily
chat reminder supplements this operating rule; it is not automatic cleanup or
a software-enforced execution gate. Offline research can continue. Future
stages specify their own retention scope rather than inheriting a no-swap rule.

### D030 — 2026-10-02: implement the bounded v2 microphone diagnostic contract

Implement D029 locally as `reachy-mic-health-v2`. Disclose active swap and OS
residuals instead of disabling swap or treating it as an automatic rejection.
Retain numeric-only application output, the existing daemon core-limit check,
own-process dump suppression during execution, the two-field routing allowlist,
pair limits and restoration checks. Preflight collects independent failures
together and never authorizes execution, even when its machine checks pass.

Correct the v1 API mismatch (`mockup` to `mockup_sim_enabled`) and the conflation
of daemon lifecycle with motor mode. The reviewed v1.9 schema exposes these
separately; stopping the daemon also tears down its media path. The diagnostic
requires a running physical media daemon with explicit motor mode `disabled`,
no daemon/backend error and no current app. It rejects enabled, gravity-
compensation, missing or malformed mode. This supersedes the microphone
proposal's ambiguous stopped-backend wording, not the prohibition on motion.
It authorizes no disable/stop command or assumption of physical clearance.

Persist a pending close-out record before capture/routing in a private v2 run
directory, inventory immediate-child metadata without following links, check
after normal/aborted completion, and block another diagnostic when prior
close-out is unresolved. No file is automatically deleted. A crash before
close-out leaves the record pending. The scope is this run directory, not a
whole-device media search or forensic erasure. Mirror the numeric run record
privately on the laptop as part of operator execution preparation/review.

Deploy only to a new v2 helper path; preserve the existing v1 copy. Next live
action is copy plus read-only preflight, not acquisition. Consumer isolation,
fresh motor/physical setup review and specific two-pair routing/acquisition
approval remain required. D026's pilot files, thresholds, seal and attempt
accounting are unchanged; no motion, response or publication is authorized.

### D031 — 2026-10-02: separate, one-shot stock sleep transition

V2 deployment/hash verification and read-only preflight completed: 16/17 checks
passed; disabled motor mode was not verified. No microphone acquisition or
routing change occurred. Prepare one separate operator-supervised invocation
of the vendor's stock sleep routine and read-only status verification.

This routine can pass through its initial pose, lower the head, move antennas,
play its sleep sound, disable tracking/wobbling and release torque. It leaves
the media daemon running. There is no automatic wake or preceding-pose restore.
Keep operator confirmations private. Require clear head/antenna/drop space,
closed clients, an attentive operator and accessible physical power control.

The one-shot launcher checks fresh physical-daemon responses, error/media and
motor state, current app, managed-app slot and API moves before at most one
stock-sleep POST. Already-disabled mode sends no command. An exclusive private
local journal prevents accidental reruns; timeout/disconnect means uncertain
outcome, not cancellation. No retry, custom target, direct torque setter,
service/OS change, microphone capture or routing write is included. Observe
disabled/no-API-move state twice with daemon/media available afterward, without
claiming exact sleep-pose verification or microphone readiness. API timestamp
freshness is not hardware-sample freshness; managed-app checks cannot enumerate
all direct SDK clients. Operator isolation and supervision remain necessary.

This narrowly extends D030's preparation boundary for this separately reviewed
stock lifecycle step only. D005–D006, M7's failed experimental motion path and
the frozen pilot remain unchanged. Stop for uncertainty; no further action
without fresh review. Do not silently reuse changed head geometry in the pilot.

## Change rule

A new decision that changes the objective, success definition, safety boundary, privacy boundary, or critical path must name the decision it supersedes. Implementation choices that do not change those boundaries may be appended without rewriting history.
