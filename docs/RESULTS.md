# Frozen results

Run `python scripts/verify_results.py` to check the public copy against its source manifests.

## Stage 2A matrix

- 15 accepted trials; 815 rows; 801 valid DoA responses (98.28%).
- Matching face + speech: 62 confirmations / 71 tracking rows (87.3%).
- Speech, no face: 0 / 35.
- Silent face + spatially separate phone speech: 13 / 63 (20.6%).
- Partial edge face: 2 / 107 tracking rows; detector availability degraded into 106 multi-face and 46 no-face observations.

## Stage 2A retrospective tournament

Evidence fingerprint: `f3832e8a2637ffbf478d91434c1cf69a42a4bb9123dc5da95fefca820463f959`

Development selected **3-hit safety consensus**. On the evaluation repetition:

| Policy | Matching / tracked | Hard-negative / tracked |
|---|---:|---:|
| Recorded Stage 2A | 24/31 | 5/37 |
| Current speech only | 11/31 | 0/37 |
| 2-hit consensus + reset | 4/31 | 0/37 |
| 3-hit safety consensus | 2/31 | 0/37 |

This is a safety/coverage frontier, not evidence that the strictest policy is universally optimal.

## Stage 3V fresh passive holdout

- Protocol: `d2f1182dd1a4d2a3e6e2a6215277c94f07223abe36e619f6eedbaed15ed766d0`
- Policy: `34382c415d44cb595c1d03bb95f6fdbe4b4ea3a1b6372df012e79896473ec0d1`
- 18 accepted trials from 21 attempts; 3 rejected/noncompliant.
- 12 positive trials with a move proposal.
- 0 hard-negative would-move rows; 0 wrong-sign moves.
- Maximum target error: 2.647237°.
- Safety, direction, coverage, and accuracy gates: **PASS**.

## Stage 3P targeted cue boundary

- Protocol: `bb78a7a32c7b61f74e3b894c055e66f4515a361bdba7c9c0c232dcf79d92b158`
- Policy: `cc6fc9731d2149a2e273989e6e0dea4caacca5859aee45ccf16d82d1f53b6da1`
- 9 accepted trials from 18 attempts; 9 superseded attempts.
- 6 transitions and 3 fail-closed controls.
- 0 authorized control adjustments, 0 robot requests, 0 actuation commands, 0 cloud requests.
- Seven cue, integrity, control, direction, bound, and coverage gates: **PASS**.

## Stage 4A supervised motion pilot

- Protocol: `0f9b1e8d076cf3ce6a3d4ca138aa8f07a691fae98543e9ad02db545c021f52af`
- 1 physical trial; 2 head-only commands.
- 0 body-yaw, antenna, torque, or motor-mode commands.
- Measured motion from baseline: 1.349887°.
- Error to requested target: 2.079459°.
- Return-to-baseline error: 1.677847°.
- Mechanical gate: **FAIL**.
- Thresholds weakened after outcome: **false**.

The passive results do not override this failure or authorize another command.

