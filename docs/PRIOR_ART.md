# Prior art and positioning

This project is a composition and experimental argument, not a claim that its individual ingredients are new.

## Reachy Mini baseline

Pollen Robotics publishes a [`sound_doa.py`](https://github.com/pollen-robotics/reachy_mini/blob/main/examples/sound_doa.py) example that demonstrates access to sound direction. An open Reachy Mini issue, [“DoA-guided who-to-look-at”](https://github.com/pollen-robotics/reachy_mini/issues/1262), directly frames direction-guided social attention as relevant ecosystem work.

This repository starts after basic DoA access: it studies when weak local evidence should be allowed to cross a movement boundary.

## Selective prediction

Abstaining rather than forcing a prediction is established selective-classification practice. [SelectiveNet](https://proceedings.mlr.press/v97/geifman19a.html) is a useful modern reference for the coverage/risk framing. Here, the asymmetric cost is embodied: lower coverage may be preferable to a false social or physical movement.

## Runtime assurance

Separating an experimental controller from an independent safety or readiness guard follows the broader runtime-assurance idea. The Stage 4 boundary is intentionally narrow: preflight reads state without commanding, authority expires, direction is locked, execution is one-shot, and return is automatic. These mechanisms are experimental safeguards, not a certified Simplex or functional-safety implementation.

## Multimodal speaker localization

Audio-visual speaker localization and active-speaker detection are mature research areas, commonly using synchronized media and learned representations. This project takes a deliberately more restrictive route: local scalar DoA, ephemeral face boxes, no identity embedding, no retained media, explicit abstention, and operator-gated movement. The contribution is the auditable safety/coverage trade-off under these information constraints.

## Distinctive research angle

The most defensible novelty is the package of practices:

- hard negatives treated as primary outcomes;
- passive policy freezes before fresh collection;
- explicit separation of compatibility, authorization, and mechanical readiness;
- media-minimized public evidence;
- failed physical motion retained as a first-class result.

Independent replication is needed before stronger novelty or generality claims.

