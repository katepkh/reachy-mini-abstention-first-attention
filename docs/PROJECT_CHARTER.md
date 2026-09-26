# Project charter

Canonical status: **ACTIVE**
Last reconstructed: **2026-09-25**

This charter is the authoritative objective and completion boundary for the project. Intermediate protocols, studies, documents, and repositories support this charter; they do not supersede it.

## Primary real-world behaviour

Build and validate one privacy-minimal Reachy Mini interaction path with two visibly different outcomes:

1. **Live-speaker positive:** when a person already visible within the camera field of view speaks live, Reachy identifies that person as the current attention candidate, turns its head toward them within a bounded motion envelope, keeps the face within a predefined attention region for a predefined hold interval, and produces an appropriate audible response.
2. **Playback hard negative:** when the visible person is silent and speech comes from a phone or another playback device, Reachy does not treat the visible person as the live speaker, does not initiate socially directed head motion, and does not respond as though the person spoke.

“Eye contact” is a motivating user-facing phrase, not yet an empirical claim. Until an HRI study validates mutual gaze, the measurable engineering target is **bounded face-directed attention**: the selected face remains within a preregistered image region for a preregistered duration, without oscillation or repeated reacquisition commands.

The first working version is explicitly **visible-speaker-only**. Speech outside
the camera field of view must abstain; autonomous search or acquisition motion
is deferred until it has its own bounded safety and evaluation contract.

## Definition of success

The **working-system goal** is achieved when one documented, runnable
controller demonstrates both primary outcomes on the physical robot: the
bounded positive interaction and refusal of the phone-playback hard negative.
That demonstration must retain failures and must not bypass the safety or
privacy constraints below.

The stronger **research-validation goal** is achieved only when all of the
following are additionally true:

- positive and negative decisions are evaluated at the **trial** level, not inferred from correlated telemetry rows;
- a frozen end-to-end protocol contains live speech, silent-visible-person plus phone playback, silence, speech with no usable face, sensor-loss, and conflicting-cue conditions;
- the evaluation contains a visible-mouth-motion plus unrelated-playback condition and a speech-activity-plus-mouth-activity baseline without synchrony, so any incremental synchrony claim is identifiable;
- acceptance thresholds, exclusions, abort rules, and baselines are fixed before outcome collection;
- the physical robot completes the bounded positive behaviour within the frozen motion and recovery envelope;
- playback hard negatives produce no socially directed motion and no conversational response under the frozen rule;
- failures, exclusions, retries, and aborted trials are retained and reported;
- the result is reproduced in held-out conditions sufficient for the exact claim being made; and
- privacy and borrowed-robot restoration gates pass.

Exact quantitative acceptance thresholds for the final study must be frozen only after the integrated instrument exists and its measurements are shown to be identifiable. Existing small-stage thresholds must not be silently reused as end-to-end thresholds.

## Positive and negative scenarios

| Scenario | Required system behaviour |
|---|---|
| Visible person speaks live | Select only if live-speaker evidence and health gates pass; orient once; maintain bounded face-directed attention; respond once. |
| Visible person is silent; phone plays speech | `ABSTAIN` or `HOLD`; no socially directed movement; no response attributed to the person. |
| Visible person mouths silently while unrelated phone speech plays | `ABSTAIN` or `HOLD`; this isolates whether temporal association adds value beyond detecting mouth and speech activity separately. |
| Speech but no usable visible face | `ABSTAIN` or a separately defined non-social behaviour; never invent a face target. |
| Visible silent face | `HOLD`; presence alone is not evidence of speaking. |
| Conflicting acoustic and visual evidence | `ABSTAIN`; do not choose the most convenient cue. |
| Stale/missing sensor or daemon state | Fail closed; no new motion or automatic retry. |
| Failure after a target command | Latch the fault; no automatic return; require fresh state and deliberate recovery authorization. |

## Non-goals for the current project

- speaker identity recognition, face recognition, diarization, or biometric authentication;
- general multi-party conversation competence;
- out-of-field-of-view speaker search in the first working version;
- general liveness or anti-spoofing detection: audio–lip synchrony is only candidate-association evidence under explicitly tested playback conditions;
- certified functional safety or a formal runtime-assurance proof;
- a claim of human mutual gaze, social benefit, trust, or acceptance without a participant study;
- a new direction-of-arrival, speech-recognition, language-model, or text-to-speech algorithm;
- weakening a frozen gate to make a failed physical result pass;
- persistent modification of the borrowed robot beyond separately reviewed and reversible development needs; or
- treating a manuscript, PDF, GitHub release, or software-test count as completion of the real-world behaviour.

## Safety and privacy constraints

- Exactly one process may own the motor connection.
- Readiness, state freshness, error state, motor mode, and physical clearance must be checked before motion.
- Motion remains blocked after stale state, unexpected movement, abnormal noise, contact, communication loss, or a motor/daemon error.
- Return is a separate movement decision and is never automatic after failure.
- The physical power control and clear Stewart-platform drop area must be accessible during powered work.
- No threshold is weakened after seeing an outcome.
- Store derived numeric evidence by default; exclude raw audio, raw camera media, transcripts, identities, and external correspondence from the public repository.
- In the present laptop instruments, camera frames and microphone samples are consumed transiently in the local browser/runtime to derive numeric audio level, face geometry, and lip-aperture features; the recorder saves and uploads none of the raw samples. A future robot-integrated instrument must document separately which raw samples remain transient on Reachy, which derived fields cross to the laptop, what is retained, and when temporary state is deleted.
- Restore and verify the borrowed robot’s documented stock state after temporary development work.

## Research-completion gate

The project may be described as an **integrated working prototype** only after one controller demonstrates both primary scenarios on the physical robot. It may be described as **validated** only after the frozen end-to-end study passes. A decision to submit or publish is separate and optional; if taken, the work may be described as **publishable** only after evidence, reproducibility, privacy, limitations, prior-art, and claim reviews pass. It may be described as **novel** only to the extent permitted by `NOVELTY_CLAIMS_LEDGER.md`.

The current project passes none of those four whole-system gates. Several components have narrower validated results; those remain valuable and are recorded in `MILESTONE_MATRIX.md`.
