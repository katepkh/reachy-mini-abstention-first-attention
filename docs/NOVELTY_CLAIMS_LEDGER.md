# Novelty and claims ledger

Canonical status: **ACTIVE**
Last reviewed: **2026-09-25**

This ledger separates an interesting system goal from a defensible research claim. “No exact implementation was found” is not evidence that an idea is historically first.

| Proposed claim | Closest established work | What may be different here | Evidence still required | Permissible wording now |
|---|---|---|---|---|
| Reachy turns toward sound | Official Reachy Mini DoA-following examples and extensive robot audition work | Nothing yet at the behaviour level. | None would make the broad behaviour novel. | “Uses Reachy’s local DoA as one input.” |
| A robot tracks a speaking person with audiovisual cues | Active-speaker detection, audiovisual speaker tracking, NAO/robot speaker-orientation studies | A Reachy-specific implementation may be new as an artifact, but the concept is established. | Direct same-condition comparison and a precise implementation contribution. | “Researches a Reachy Mini implementation”; never “first audiovisual speaker tracker.” |
| Robot holds eye contact and responds | Social gaze, face tracking, turn-taking, dialogue systems, and conversational HRI | A bounded, playback-gated composition on Reachy may be useful. | Operational gaze metric, participant-facing validation if claiming eye contact/social effect, and an integrated response study. | “Future bounded face-directed attention target.” |
| Abstention before robot motion | Selective prediction/reject options and runtime-assurance/safety-gating architectures | The particular inspectable composition and evidence trail may be a useful engineering contribution. | Integrated risk/coverage results and comparison to non-abstaining alternatives. | “Applies an abstention-first permission architecture”; not a novel theory of abstention. |
| Prevent playback-induced false social orientation | Active-speaker detection already addresses audiovisual ownership; playback attacks and liveness detection are adjacent | A privacy-minimal, edge-only gate using weak Reachy-accessible signals, explicit refusal, and physical-action consequences is the strongest candidate differentiation. | Held-out phone/playback conditions, actual robot outputs, baseline comparison, uncertainty, and failure analysis. | “Targets playback-induced false orientation”; novelty remains unestablished. |
| Privacy-minimal numeric sensing | Privacy-preserving edge inference and media-minimizing HRI are established themes | The exact no-raw-media Reachy pipeline plus auditable trial artifacts may be practically distinctive. | Clear data-flow audit and comparison with a stronger audiovisual baseline, including performance/privacy trade-off. | “Stores derived numeric state rather than raw media.” |
| Staged failure-preserving robot research | Preregistration, negative-result preservation, safety cases, and reproducible robotics are established | The concrete Reachy case study combines frozen gates, failed motion preservation, and restoration controls. | External replication or evidence that the process improves error discovery versus a simpler workflow. | “Provides an auditable case study”; not “a new safety framework.” |
| Complete system is groundbreaking | Broad behaviour and components all have prior art. | Only the precise composition, constraints, and empirical outcome could support a narrower contribution. | Complete M5–M11, then rerun a systematic current search and obtain critical review. | **Not currently permissible.** |

## Current best research hypothesis

The strongest plausible contribution is:

> A privacy-minimal, edge-only, abstention-first multimodal gate can reduce playback-induced false social orientation on Reachy Mini while preserving useful live-speaker engagement, and can expose the perceptual, human-interaction, and mechanical permission boundaries separately.

This is a **hypothesis**, not a result. It becomes a result only after end-to-end robot validation and appropriate baselines. Even then, words such as “first,” “novel,” or “groundbreaking” require a refreshed prior-art search and evidence that the differentiated elements—not merely the implementation platform—drive the result.

## Required baselines for a defensible claim

- official-style DoA-following behaviour;
- acoustic-only selection;
- visual-only face selection;
- synchrony-only selection;
- fused non-abstaining selection; and
- the proposed fused abstaining controller.

Report trial-level coverage, hard-negative activation, wrong-target/motion outcomes, response errors, uncertainty, and the privacy/latency cost of each baseline.

See [`PRIOR_ART.md`](PRIOR_ART.md) for the source-backed literature boundary. Refresh that review immediately before any paper submission or novelty statement.
