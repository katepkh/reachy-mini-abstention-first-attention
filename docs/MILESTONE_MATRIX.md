# Milestone matrix

Canonical status: **ACTIVE**
Last reviewed: **2026-09-25**

Allowed milestone states are `ABSENT`, `PROTOTYPE`, `PASS`, `FAIL`, and `BLOCKED`. `PASS` always applies only to the scope stated in that row; it does not imply end-to-end validation.

| ID | Required capability | State | Evidence and boundary | Exact next experiment or deliverable |
|---|---|---|---|---|
| M0 | Privacy-minimized evidence repository | PASS | Public evidence is numeric/media-free and integrity checked. This says nothing about robot behaviour. | Re-run the privacy scan immediately before any GitHub write. |
| M1 | Read local speech/DoA state | PASS | `reachy_doa/` and recorded trials support passive local DoA/speech acquisition in the studied setup. It is not speaker identity. | Exercise the same input through the future integrated shadow controller and record freshness/dropout behaviour. |
| M2 | Detect and geometrically track one visible face | PASS | Stage 2A/3V records support ephemeral one-face geometry within limited single-operator conditions. | Bind the detector output to an integrated attention-state interface and define loss/reacquisition behaviour. |
| M3 | Passive spatial compatibility with abstention | PASS | Stage 3V passed its 18-trial frozen horizontal holdout; Stage 2A also showed 13/63 false compatibility rows for a silent face plus separate phone speech. Compatibility is not source ownership. | Use phone-playback trials as mandatory hard negatives for the integrated decision layer. |
| M4 | Distinguish live visible speech from playback | PROTOTYPE | The V2 lip-aperture synchrony candidate passed a 12-trial single-setup development/internal-validation pilot. No independent confirmation exists. | First integrate and validate acoustic direction plus synchrony in a no-motion instrument; do not run the currently unidentifiable 54-trial protocol. |
| M5 | One fused live-speaker decision interface | ABSENT | Existing spatial, synchrony, cue, and operator-arm paths are separate. There is no single production entry point. | Implement a deterministic shadow-only orchestrator emitting `SELECT`, `ABSTAIN`, or `HOLD` with reason codes from recorded/replayed inputs. |
| M6 | Reject silent-person plus phone playback end to end | ABSENT | Hard negatives exposed the problem, but no integrated controller has passed it. | Replay all compatible saved hard negatives through M5, then run a small preregistered live shadow test with no robot commands. |
| M7 | Safe bounded physical orientation | FAIL | The only supervised 3° V3 trial failed target and return tolerances. Later V4 work remained blocked; a read-only successor trace observed `UNSET` targets and did not validate motion. | Define and independently review one baseline-relative, one-leg motion protocol with numeric abort limits before any new command. |
| M8 | Face-directed attention hold | ABSENT | No integrated face-centering/hold controller or hold metric has been physically validated. | In simulation/replay first, define image-region error, dwell, update rate, command-rate limit, loss timeout, and oscillation limit. |
| M9 | Audible response attributable to accepted live speech | ABSENT | The repository intentionally stores no transcript and implements no end-to-end STT/dialogue/TTS response path. | Specify the minimal response path and its privacy boundary; integrate it only after M5 can gate response permission. |
| M10 | Single end-to-end controller | ABSENT | The README explicitly records that proposal, cue, and command boundaries are unintegrated. | Connect M5, guarded M7, M8, and M9 behind one explicit state machine; initially run with motion and response outputs stubbed. |
| M11 | End-to-end held-out validation and baselines | BLOCKED | No valid integrated instrument exists. The frozen 54-trial confirmation is paused because the recorder lacks acoustic direction and required Stage 3V inputs. | Build M10 and verify endpoint identifiability before freezing a new final protocol and official-style DoA, acoustic-only, visual-only, synchrony-only, and non-abstaining baselines. |
| M12 | Research manuscript | PROTOTYPE | A working evidence manuscript exists, but it describes incomplete component studies and is not a completion or submission-readiness claim. | Update only when a milestone changes or a claim audit requires it; do not prioritize presentation over M5–M10. |
| M13 | Defensible differentiated research claim | BLOCKED | The broad behaviour and its individual techniques have substantial prior art. A narrower playback-resistant, privacy-minimal, abstention-first composition remains a hypothesis, not a proven novelty claim. | Complete M10–M11, rerun the prior-art search, and compare against the baselines in `NOVELTY_CLAIMS_LEDGER.md`. |
| M14 | GitHub publication of current local work | BLOCKED | Local history is ahead of GitHub; publication was deliberately paused after strategy drift was identified. | Pass the strategy, privacy, content, generated-artifact, and diff reviews; then obtain an explicit publish decision. |

## Current critical path

`M5 fused shadow decision → M6 phone-playback rejection → M7 bounded orientation → M8 attention hold → M9 gated response → M10 integration → M11 held-out validation → M13 claim review`

The 54-trial confirmation study and further manuscript polishing are not the current critical path. The confirmation design may later supply part of M11 after its inputs and estimands are repaired, but collecting the present design would consume time without identifying all frozen primary endpoints.
