# Discord introduction

I have been testing an abstention-first attention stack on Reachy Mini. The interesting part is not another “robot turns toward sound” demo; it is the permission boundary between noisy evidence and motion.

The pipeline separates local DoA, ephemeral face geometry, temporal consensus, an explicit operator cue, and a final mechanical readiness gate. I kept hard negatives in the protocol and froze results before changing policy versions.

Three results I would value expert scrutiny on:

- Acoustic/visual matching gave useful coverage (62/71 tracked matching rows), but a silent visible face plus spatially separate phone speech still produced 13/63 confirmations. Geometry is not source ownership.
- A fresh passive vertical holdout passed all four gates: 18 accepted trials, 12/12 positive trials with bounded shadow proposals, zero hard-negative would-move rows, and 2.647° maximum target error.
- The first supervised 3° physical pilot failed: only 1.350° measured motion, 2.079° target error, and 1.678° return error. I froze the failure and root-cause analysis instead of relaxing thresholds.

The repo includes code, numeric evidence without raw audio/video, SHA-256 freezes, rejected/superseded attempts, limitations, and a one-command verifier:

`python scripts/verify_results.py`

I would especially appreciate critique of (1) the abstention/coverage frontier, (2) whether the cue gate is the right human authorization primitive, and (3) the design of an independent multi-speaker, multi-room evaluation before any further actuation.

GitHub: **https://github.com/katepkh/reachy-mini-abstention-first-attention**
