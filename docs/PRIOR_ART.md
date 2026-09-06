# Prior art and positioning

This project is a composition and experimental argument, not a claim that speaker following, active-speaker detection, abstention, social gaze, or runtime gating is new. The purpose of this review is to locate the narrow contribution and prevent the repository from borrowing novelty from established fields.

## Reachy Mini behavioral baseline

Pollen Robotics publishes a [`sound_doa.py`](https://github.com/pollen-robotics/reachy_mini/blob/main/examples/sound_doa.py) example that reads the speech direction of arrival, transforms a head-relative point into world coordinates, and calls `look_at_world`. An open Reachy Mini issue, [“DoA-guided who-to-look-at”](https://github.com/pollen-robotics/reachy_mini/issues/1262), also frames direction-guided social attention as ecosystem work.

That official example is the primary platform baseline for the next benchmark. This repository starts at a different question: when should a plausible DoA target be withheld before it reaches a social or mechanical boundary?

## Robot audition

Robot audition already encompasses localization, tracking, source separation, noise reduction, recognition, moving sources, moving robots, and ego-noise handling. Nakadai et al.'s [HARK account of robot audition for dynamic environments](https://www.jp.honda-ri.com/api/upload/document/entry/20121018/Nakadai_2012_941_6250.pdf) is a concrete example of this much broader technical field.

This project uses only Reachy Mini's scalar endpoint DoA plus a speech flag. It does not perform multichannel source separation, source tracking, beamforming, speech recognition, or ego-noise suppression. Therefore the current work should not be presented as an advance in robot audition algorithms. Its relation to that literature is a downstream decision boundary over a much weaker signal.

## Audio-visual active-speaker detection

Active-speaker detection seeks to determine which visible person is speaking by combining synchronized audio and visual information. The [AVA-ActiveSpeaker dataset and model](https://research.google/pubs/ava-activespeaker-an-audio-visual-dataset-for-active-speaker-detection/) provide millions of labeled face frames across tens of hours and report gains from joint audio-visual and temporal modeling. [TalkNet](https://arxiv.org/abs/2107.06592) uses audio and visual temporal encoders, cross-attention, and longer-term speaking evidence. Work on [multi-person speech recognition and active-speaker selection](https://research.google/pubs/a-closer-look-at-audio-visual-multi-person-speech-recognition-and-active-speaker-selection/) further shows that selecting a speaker in multi-person scenes is a substantive research problem, not a by-product of geometric overlap.

The present system is not an active-speaker detector. It stores no synchronized media, lip motion, learned audio-visual embedding, transcript, diarization state, or identity. Its one-face/DoA geometry can only establish spatial compatibility. The Stage 2A phone-speech hard negative demonstrated exactly why compatibility cannot be called source ownership.

## Selective prediction and abstention

Rejecting uncertain predictions is established selective-classification practice. [SelectiveNet](https://proceedings.mlr.press/v97/geifman19a.html) explicitly studies the risk-coverage trade-off of an integrated reject option. This repository adopts the vocabulary and asymmetric-cost intuition, but it does not train a selective neural model or estimate a population risk-coverage curve.

The research opportunity is narrower: make abstention observable across a physical interaction pipeline, report the coverage it sacrifices, and preserve failures when the final mechanics gate refuses execution.

## Runtime assurance

Runtime assurance and Simplex-style architectures conventionally separate an advanced component from a trusted reversionary component, with a monitor and switch condition. NASA work on a [formal verification framework for runtime assurance](https://shemesh.larc.nasa.gov/fm/papers/NFM2024-draft.pdf) illustrates how much stronger that term can be: explicit system models, safety properties, trusted components, monitor timing, and proofs.

Stage 4 is only *influenced* by this pattern. Its expiring read-only preflight, one-shot direction lock, typed arm phrase, bounded command, and attempted return are experimental safeguards. There is no verified safe set, trusted independent controller, formal switching proof, fault-tolerance claim, or functional-safety certification. “Experimental motion governor” is more accurate than “runtime-assurance system.”

## Social gaze and conversation

Head orientation toward a face is not equivalent to eye contact, mutual gaze, joint attention, conversational grounding, or socially meaningful attention. Admoni and Scassellati's [review of social eye gaze in HRI](https://publications.ri.cmu.edu/social-eye-gaze-human-robot-interaction-review) separates human-, design-, and technology-centered questions. Andrist et al.'s [conversational gaze-aversion work](https://graphics.cs.wisc.edu/Papers/2014/ATGM14/) distinguishes face tracking, idle motion, and purposeful gaze behavior and evaluates human perceptions with participants.

This repository has not conducted an HRI participant study, measured perceived attention, modeled turn taking, or validated eye-contact behavior. Consequently, phrases such as “maintains eye contact” or “socially meaningful attention” describe a future research target, not a current result.

## Positioning matrix

| Area | Established capability | What this repository actually adds | What remains unproven |
|---|---|---|---|
| Reachy Mini DoA following | Read DoA and turn the head toward a sound target. | A frozen, inspectable refusal path before any intended command. | A fair end-to-end comparison on the same trials. |
| Robot audition | Localization, tracking, separation, recognition, and dynamic/ego-noise methods. | No new audition algorithm; only downstream use of a scalar endpoint. | Robustness to moving sources, reverberation, overlapping speech, or robot motion. |
| Active-speaker detection | Learned synchronized audio-visual inference of who is speaking. | A hard-negative demonstration that spatial compatibility is insufficient. | Speaker ownership, diarization, identity, or multi-person active-speaker accuracy. |
| Selective prediction | Formal reject options and risk-coverage analysis. | Embodied abstention states and an empirical coverage cost in a small robot pipeline. | A statistically powered selective-risk curve or calibrated uncertainty model. |
| Runtime assurance | Monitor/switch architectures with explicit safety arguments, sometimes formally verified. | One-shot supervised preflight and failure preservation. | Formal assurance, independent trusted fallback, or certified safety. |
| Social gaze | Rich gaze behavior evaluated for interaction goals and human perception. | A proposed permission boundary for future socially directed motion. | Eye contact, joint attention, turn taking, acceptance, or social benefit. |

## Defensible contribution statement

The most defensible contribution is an **auditable abstention-first research composition**:

- hard negatives treated as primary outcomes rather than demo edge cases;
- passive policies frozen before fresh collection;
- explicit separation of candidate compatibility, passive visual cueing, typed operator arming, and mechanical readiness;
- media-minimized public evidence with hashes and deterministic headline reconstruction;
- failed physical motion retained as a first-class result rather than repaired by post-outcome threshold relaxation.

That is a useful engineering and experimental package. It is not yet evidence of a new algorithm, general performance, social validity, or successful physical speaker following.

## Comparisons required next

On the same preregistered trial set, the next study should compare:

1. official-style DoA following;
2. speech-flag filtering only;
3. one-frame acoustic/visual compatibility;
4. the frozen temporal-abstention policy;
5. an oracle condition derived from the known stimulus source, for analysis only.

Report trial-level false movement proposals, coverage, correct-direction coverage, latency, target error, and abstention duration, with room- and voice-level holdouts. Without those baselines and independent conditions, the value of the added gates remains a credible design argument rather than a comparative robotics result.
