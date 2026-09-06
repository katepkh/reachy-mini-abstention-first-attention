# Stage 3V exploratory trial-level robustness

> **Status:** post-hoc exploratory replay. The frozen V3 result was held out, but this analysis plan was written after those results were known. It does not authorize motion.

## The honest headline

The frozen policy proposed a target in **12/12** matching trials and **0/6** hard-negative trials. At the trial level, the nominal 95% Wilson intervals are **75.8%–100.0%** for positive coverage and **0.0%–39.0%** for the hard-negative false-proposal rate.

The intervals—not the perfect sample fractions—are the useful caution. Six negative trials are compatible with a substantially larger underlying false-proposal rate. All frames inside one trial are correlated and are not treated as independent evidence.

## Diagnostic ablations

| Replay policy | Positive trial coverage | Hard-negative trial proposals | Selective risk among proposed trials | Median first proposal | Max target error |
|---|---:|---:|---:|---:|---:|
| `full_frozen_v3` | 12/12 (100.0%) | 0/6 (0.0%) | 0.0% | 3030 ms | 2.647° |
| `single_frame_audio_visual` | 12/12 (100.0%) | 2/6 (33.3%) | 14.3% | 2236 ms | 2.628° |
| `audio_visual_without_speech_gate` | 12/12 (100.0%) | 0/6 (0.0%) | 0.0% | 3027 ms | 2.647° |
| `visual_only_temporal` | 12/12 (100.0%) | 6/6 (100.0%) | 33.3% | 309 ms | 2.388° |
| `audio_only_front_hypothesis` | 12/12 (100.0%) | 4/6 (66.7%) | 25.0% | 2287 ms | 37.040° |

Definitions:

- `full_frozen_v3`: the published V3 policy, unchanged.
- `single_frame_audio_visual`: the same policy with one hit instead of three; this isolates temporal consensus.
- `audio_visual_without_speech_gate`: the same policy with every row counterfactually marked speech-positive; this isolates the VAD latch.
- `visual_only_temporal`: calibrated face direction plus three-hit temporal consensus; no acoustic evidence.
- `audio_only_front_hypothesis`: the front acoustic hypothesis plus speech latch and three-hit consensus; it encodes a front-hemisphere assumption.

These baselines were defined after data collection, are not matched for information or complexity, and cannot establish causal component importance.

## Threshold sensitivity

The machine-readable JSON and CSV files replay one parameter at a time around the frozen point and a 25-point grid over geometry tolerance (6°–14°) and required hits (1–5). These are finite operating points on this dataset, not a calibrated population risk–coverage curve.

- One required hit retained 12/12 positive coverage but produced proposals in 2/6 hard negatives. Four hits reduced coverage to 10/12; five reduced it to 0/12.
- Tightening the geometry envelope from the frozen 10° to 6° reduced positive coverage to 10/12; 8°–14° retained 12/12 and 0/6 at the other frozen settings.
- Removing the speech latch reduced positive coverage to 3/12; 400 ms produced 11/12, and 800–1600 ms produced 12/12 on this sample.
- Tested face-offset, consensus-window, heading-tolerance, and disagreement-lockout alternatives did not change trial-level proposal counts at the other frozen settings. That flatness may reflect coarse outcomes and limited conditions, not genuine invariance.

Leave-one-trial-out deletion is also reported. It measures arithmetic fragility of this small dataset; because it reuses the same site and session, it is not evidence of external generalization.

## Reproduce

```bash
python scripts/run_stage3v_robustness.py --check
```

The accepted source bundle is content-addressed as `bb44c7f4309e995f34177ba21824c9dedef95dabe34cbaf01d4029ddad4944ee`. Exact per-file hashes are in the JSON.

## Claim boundary

- Rows within a trial are correlated; intervals use trial counts only.
- The original frozen V3 policy was held out, but all analyses in this file were chosen after seeing its results.
- Ablations are diagnostic counterfactual replays, not randomized comparisons or causal evidence.
- The audio-only front-hypothesis baseline encodes a front-hemisphere choice and is not a general DoA resolver.
- Risk/coverage points are finite policy operating points on one small single-site dataset, not a calibrated population curve.
- No result authorizes a robot command or establishes speaker identity, ownership, consent, or mechanical safety.
