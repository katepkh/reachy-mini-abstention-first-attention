# Discord introduction

I have been testing an abstention-first attention stack on Reachy Mini. The interesting part is not another “robot turns toward sound” demo; it is the permission boundary between noisy evidence and motion.

The work currently consists of separately tested boundaries: local DoA plus ephemeral face geometry can produce a passive candidate or abstain; stable centred compatibility can display a visual instruction to the operator; and a separate physical pilot requires typed operator arming plus mechanical readiness. These pieces are not yet validated end to end. I kept hard negatives and superseded attempts in the record and froze policies before the fresh evaluations.

Three results I would value expert scrutiny on:

- Acoustic/visual matching gave useful coverage (62/71 correlated tracked rows), but a silent visible face plus spatially separate phone speech still produced 13/63 compatibility confirmations. Geometry is not source ownership, and these rows are not independent trials.
- A fresh passive horizontal off-axis holdout passed its four frozen gates: 18 accepted trials from 21 attempts, 12/12 matching-positive trials with bounded shadow proposals, 0/6 accepted hard-negative trials containing a would-move row, and 2.647° maximum target error. This is a small single-site result, not a population error rate.
- A separate passive vertical experiment displayed the expected visual instruction in 6/6 accepted transitions and no instruction in 0/3 accepted controls. It received no transcript and did not recognize the spoken test phrase.
- The first supervised 3° physical pilot failed: only 1.350° measured motion, 2.079° target error, and 1.678° return error. I froze the failure and root-cause analysis instead of relaxing thresholds.

The repo includes code, numeric evidence without raw audio/video, SHA-256 freezes, rejected/superseded attempts, limitations, and a one-command verifier:

`python scripts/verify_results.py`

I would especially appreciate critique of (1) the abstention/coverage frontier and trial-level analysis, (2) the separation between passive cueing, operator arming, and mechanical readiness, and (3) the strongest baselines and hard negatives for a preregistered multi-room recorded-voice evaluation.

GitHub: **https://github.com/katepkh/reachy-mini-abstention-first-attention**
