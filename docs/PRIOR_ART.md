# Prior art and positioning

This project is a composition and experimental argument, not a claim that its individual ingredients are new.

## Reachy Mini baseline

Pollen Robotics publishes a [`sound_doa.py`](https://github.com/pollen-robotics/reachy_mini/blob/main/examples/sound_doa.py) example that reads speech DoA, transforms it into world coordinates, and commands the head to look toward the source. An open Reachy Mini issue, [“DoA-guided who-to-look-at”](https://github.com/pollen-robotics/reachy_mini/issues/1262), directly frames direction-guided social attention as relevant ecosystem work.

This official example is the primary behavioral baseline for future comparisons. This repository starts after basic DoA following: it studies when weak local evidence should be withheld from a movement boundary.

## Selective prediction

Abstaining rather than forcing a prediction is established selective-classification practice. [SelectiveNet](https://proceedings.mlr.press/v97/geifman19a.html) is a useful modern reference for the coverage/risk framing. Here, the asymmetric cost is embodied: lower coverage may be preferable to a false social or physical movement.

## Runtime assurance

The Stage 4 design is influenced by the broader runtime-assurance idea, but it is not an independent verified safety controller. Preflight reads state without commanding, the local session expires, direction is locked, execution is one-shot, and return is attempted automatically. These mechanisms are experimental software safeguards, not a certified Simplex, formally verified safe set, or functional-safety implementation.

## Multimodal speaker localization

Audio-visual speaker localization and active-speaker detection are mature research areas, commonly using synchronized media and learned representations. The [AVA-ActiveSpeaker dataset and baseline](https://research.google/pubs/ava-activespeaker-an-audio-visual-dataset-for-active-speaker-detection/) illustrate the scale and diversity of that separate problem. This project does not compete with active-speaker recognition: it takes a deliberately restrictive route using local scalar DoA, ephemeral face boxes, no identity embedding, no retained media, explicit abstention, passive visual cueing, and separately tested operator arming. Its possible contribution is the auditable safety/coverage trade-off under these information constraints.

## Distinctive research angle

The most defensible novelty is the package of practices:

- hard negatives treated as primary outcomes;
- passive policy freezes before fresh collection;
- explicit separation of compatibility, passive visual cueing, operator arming, and mechanical readiness;
- media-minimized public evidence;
- failed physical motion retained as a first-class result.

Independent replication is needed before stronger novelty or generality claims.

The next benchmark should compare official-style DoA following, speech-only filtering, one-frame acoustic/visual compatibility, and temporal abstention on the same trial set. Without those baselines, the benefit of the added gates remains descriptive rather than comparative.
