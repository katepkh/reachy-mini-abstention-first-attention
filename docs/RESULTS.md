# Frozen results

Run `python scripts/verify_results.py` to check the public copy against its source manifests. Run `python scripts/regenerate_public_results.py --check` to reconstruct the headline table from the frozen machine-readable artifacts and compare it with [`GENERATED_RESULTS.md`](GENERATED_RESULTS.md).

These are frozen engineering results, not population-rate estimates. Rows within a trial are correlated telemetry. Across the principal passive protocols there are 42 accepted trials; Stage 4 adds one failed physical trial. See [`ATTEMPT_ACCOUNTING.md`](ATTEMPT_ACCOUNTING.md) for attempt flow and uncertainty context.

A later **post-hoc exploratory** replay reports Stage 3V trial-level Wilson intervals, ablations, leave-one-trial-out deletion, threshold sensitivity, latency, and finite risk/coverage operating points in [`stage3v_trial_robustness_v1.md`](../evidence/analysis/stage3v_trial_robustness_v1.md). It reproduces 12/12 positive and 0/6 hard-negative trial proposals for the frozen policy, but the nominal 95% intervals are 75.8%–100% and 0%–39.0%, respectively. This analysis does not convert the original result into a population estimate or a second holdout.

## Audio–mouth synchrony development pilot

- 12 scheduled laptop-only trials from 13 captures; one duplicate trial-03 capture is disclosed and retained as sensitivity evidence.
- 6 matching-positive and 6 hard-negative trials in the primary set.
- 240/240 frozen threshold settings were ineligible; no threshold was selected.
- At the most permissive frozen dynamic-range settings, every positive still fell below the minimum 0.35 correlation threshold.
- Replacing the duplicate trial-03 capture with the earlier attempt did not change the verdict.
- 0 robot connections and 0 actuation commands.

The fixed mouth-box frame-difference instrument is rejected. This result does not validate audiovisual association and the 54-trial confirmation study must not begin with this instrument. Full diagnostics and exact report hashes are in [`AV_SYNCHRONY_PILOT_RESULT.md`](AV_SYNCHRONY_PILOT_RESULT.md).

The replacement [`V2 face-landmark pilot`](AV_SYNCHRONY_PILOT_V2_RESULT.md) completed with 12 quality-passing canonical trials from 23 total attempts. Eight of 45 development settings were eligible; the deterministic tie-break selected correlation `0.25`, maximum absolute lag `120 ms`, and three-sample smoothing. It produced candidates for 4/4 development positives and 0/4 development hard negatives, then 2/2 internal-validation positives and 0/2 internal-validation hard negatives. The exact code, assets, inputs, and setting are locally content-frozen. The public counts can be reconstructed from [`av_synchrony_pilot_v2_public_summary_v1.json`](../evidence/analysis/av_synchrony_pilot_v2_public_summary_v1.json). This is a single-person, single-setup instrument pilot, not confirmation, identity, authorization, or robot evidence. The separate [`candidate-bound confirmation protocol`](AV_SYNCHRONY_CONFIRMATION_PROTOCOL.md) is frozen but has no collected trials.

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

## Stage 3V fresh horizontal off-axis holdout

- Protocol: `d2f1182dd1a4d2a3e6e2a6215277c94f07223abe36e619f6eedbaed15ed766d0`
- Policy: `34382c415d44cb595c1d03bb95f6fdbe4b4ea3a1b6372df012e79896473ec0d1`
- 18 accepted trials from 21 attempts; 3 rejected/noncompliant.
- 12/12 matching-positive trials with a passive move proposal.
- 0/6 accepted hard-negative trials contained a would-move row; 0 wrong-sign moves.
- Maximum target error: 2.647237°.
- Safety, direction, coverage, and accuracy gates: **PASS**.

## Stage 3P targeted cue boundary

- Protocol: `bb78a7a32c7b61f74e3b894c055e66f4515a361bdba7c9c0c232dcf79d92b158`
- Policy: `cc6fc9731d2149a2e273989e6e0dea4caacca5859aee45ccf16d82d1f53b6da1`
- 9 accepted trials from 18 attempts; 9 superseded attempts.
- 6/6 vertical transitions displayed the expected visual move instruction; 0/3 accepted controls displayed an unexpected instruction.
- The software did not recognize the spoken test phrase and received no transcript.
- 0 control adjustments, 0 robot requests, 0 actuation commands, 0 cloud requests.
- Seven cue, integrity, control, direction, bound, and coverage gates: **PASS**.

This validates a passive system-issued visual cue boundary only. It is not evidence of speaker authorization, consent, or an end-to-end command path.

## Stage 4A supervised motion pilot

- Protocol: `0f9b1e8d076cf3ce6a3d4ca138aa8f07a691fae98543e9ad02db545c021f52af`
- 1 physical `UP` trial; 2 head-only commands.
- 0 body-yaw, antenna, torque, or motor-mode commands.
- Measured motion from baseline: 1.349887°.
- Error to requested target: 2.079459°.
- Return-to-baseline error: 1.677847°.
- Mechanical gate: **FAIL**.
- Thresholds weakened after outcome: **false**.

The passive results do not override this failure or authorize another command.
