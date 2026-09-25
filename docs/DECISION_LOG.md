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

## Change rule

A new decision that changes the objective, success definition, safety boundary, privacy boundary, or critical path must name the decision it supersedes. Implementation choices that do not change those boundaries may be appended without rewriting history.
