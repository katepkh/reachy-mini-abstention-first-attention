# Frozen V2 source-validity condition audit

**Audit date:** 2026-08-24  
**Model fingerprint:** `1bbb131ff91a2ccffa48489e968e7531c51bf5238df86f16d17a2ae820297890`  
**Evidence-manifest fingerprint:** `ee413a0a59bd0f53d6bd1841542076ec291fbc1de2acf41abd5a958d4827781a`

This is a post-evaluation audit of the already frozen metadata-only source-validity probe. No
threshold, feature, label, split or model parameter was changed after viewing the held-out results.
The audit uses only the existing `source_validity_evaluation_v1.csv` artifact.

## Held-out operating point

| Measure | Count | Estimate | Wilson 95% interval |
|---|---:|---:|---:|
| Decision coverage | 9 / 35 | 25.71% | 14.16–42.07% |
| Selective accuracy among decided trials | 9 / 9 | 100.00% | 70.09–100.00% |
| False-human acceptance among non-live trials | 0 / 7 | 0.00% | 0.00–35.43% |
| Live-human rejection | 0 / 28 | 0.00% | 0.00–12.06% |
| Live-human acceptance | 8 / 28 | 28.57% | 15.25–47.06% |
| Non-live rejection | 1 / 7 | 14.29% | 2.57–51.31% |

The intervals matter. Nine correct decisions do not establish general 100% accuracy, and zero
false-human accepts in only seven non-live trials does not establish a production safety rate.

## Condition-level decisions

`A` = `ABSTAIN_AMBIGUOUS`; `N` = `ABSTAIN_NO_EVIDENCE`; `L` = `LIVE_LIKELY`;
`R` = `NON_LIVE_LIKELY`.

| Held-out condition | Protocol truth | n | L | R | A | N | Median live-similarity | Median speech-positive samples |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Direction · front | live human | 2 | 2 | 0 | 0 | 0 | 0.725 | 11.0 |
| Direction · front-right | live human | 2 | 0 | 0 | 2 | 0 | 0.492 | 2.5 |
| Direction · right | live human | 2 | 0 | 0 | 2 | 0 | 0.506 | 2.0 |
| Direction · back-right | live human | 2 | 1 | 0 | 1 | 0 | 0.691 | 4.5 |
| Direction · back | live human | 2 | 0 | 0 | 2 | 0 | 0.590 | 6.0 |
| Direction · back-left | live human | 2 | 0 | 0 | 2 | 0 | 0.539 | 7.0 |
| Direction · left | live human | 2 | 0 | 0 | 2 | 0 | 0.436 | 2.0 |
| Direction · front-left | live human | 2 | 0 | 0 | 2 | 0 | 0.598 | 3.5 |
| Continuous · right end-fire | live human | 1 | 0 | 0 | 1 | 0 | 0.637 | 14.0 |
| Continuous · left end-fire | live human | 1 | 0 | 0 | 1 | 0 | 0.601 | 9.0 |
| Orientation swap · original right | live human | 1 | 0 | 0 | 1 | 0 | 0.459 | 7.0 |
| Orientation swap · original left | live human | 1 | 0 | 0 | 1 | 0 | 0.451 | 4.0 |
| Front/back · front only | live human | 1 | 0 | 0 | 1 | 0 | 0.485 | 5.0 |
| Front/back · back only | live human | 1 | 0 | 0 | 1 | 0 | 0.515 | 7.0 |
| Front/back · alternating | live human | 1 | 0 | 0 | 1 | 0 | 0.497 | 7.0 |
| Front/back · rapid switch | live human | 1 | 1 | 0 | 0 | 0 | 0.800 | 14.0 |
| Two speakers · alternating | live human | 1 | 1 | 0 | 0 | 0 | 0.768 | 15.0 |
| Two speakers · rapid switch | live human | 1 | 1 | 0 | 0 | 0 | 0.896 | 18.0 |
| Two speakers · overlap | live human | 1 | 1 | 0 | 0 | 0 | 0.787 | 21.0 |
| Two speakers · masking | live human | 1 | 1 | 0 | 0 | 0 | 0.744 | 29.0 |
| Very quiet baseline | non-live | 1 | 0 | 0 | 1 | 0 | 0.406 | 104.0 |
| Clap | non-live | 1 | 0 | 0 | 0 | 1 | 0.500 | 0.0 |
| Keys | non-live | 1 | 0 | 1 | 0 | 0 | 0.274 | 5.0 |
| Instrumental music | non-live | 1 | 0 | 0 | 1 | 0 | 0.473 | 5.0 |
| Television/podcast playback | non-live | 1 | 0 | 0 | 0 | 1 | 0.500 | 1.0 |
| Continuous tone/AI narration | non-live | 1 | 0 | 0 | 1 | 0 | 0.395 | 2.0 |
| Mechanical/vibration playback | non-live | 1 | 0 | 0 | 1 | 0 | 0.373 | 10.0 |

## What the audit establishes

1. **The probe is selectively correct because it usually refuses to decide.** It abstained on
   26/35 trials, including 20/28 controlled live-human trials and 6/7 non-live trials.
2. **The only confident non-live rejection was keys.** This is a condition-specific success, not a
   general non-live detector.
3. **The quiet baseline is an adversarial counterexample to sample-count intuition.** It contained
   104 speech-positive samples yet remained semantically ambiguous. `speech_detected` frequency alone
   is not evidence of a live human.
4. **All four held-out two-speaker conflict conditions appeared live-like.** The probe can recognise
   human-like temporal dynamics while remaining unable to establish one speaker, identity, or a safe
   physical attention target.
5. **Exact lateral and most oblique single-speaker directions were rejected by abstention.** Sparse
   VAD evidence and end-fire behaviour degrade not only localisation but downstream semantic inference.
6. **No evaluation errors were observed among decided trials, but the sample is too small for a safety
   claim.** The 95% interval for selective accuracy extends down to approximately 70%.

## Decision for the next stage

Do not tune another classifier on the same two endpoint fields or unlock the held-out set. The
metadata-only observability limit is now itself the result. The fastest high-value next experiment is
a separately authorised, passive multimodal confirmation layer:

- keep acoustic attention as a folded-axis hypothesis generator;
- obtain camera frames read-only and process them locally in volatile memory;
- store only timestamped face-presence/position/confidence metadata, never frames;
- confirm the visible front candidate when face and acoustic evidence agree;
- retain the back candidate or abstain when the camera cannot confirm it;
- make no movement request and keep the simulator in shadow mode;
- compare against the frozen V1/V2 baselines on a new, pre-registered split.

This directly tests whether one additional local signal resolves the two demonstrated limitations:
front/back ambiguity and non-human activation. It is a Stage 2 safety boundary and must not be added
without explicit camera/privacy authorisation and a fresh code audit.
