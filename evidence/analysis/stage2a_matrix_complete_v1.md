# Stage 2A passive camera-confirmation matrix — complete result

Date: 2026-08-25

## Scope and safety boundary

- Fifteen accepted trials: five controlled conditions with three repetitions each.
- Latest saved capture for each numbered step is treated as the accepted matrix capture; earlier attempts remain preserved as diagnostics.
- Passive local processing only: no pixels, audio, transcript, identity data, cloud inference or actuation was retained or used.
- Total accepted evidence: 815 numeric observations; 801 valid DoA responses (98.28%).

## Condition matrix

| Condition | Rows | Valid | Speech + | No face | One face | Multi-face | Tracking axis | Confirmed | Confirmed / tracking |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Visible silent face | 165 | 97.6% | 7.9% | 0.0% | 100.0% | 0.0% | 7.9% | 13 (7.9%) | 100.0% |
| Speech, no visible face | 103 | 98.1% | 30.1% | 100.0% | 0.0% | 0.0% | 34.0% | 0 | 0.0% |
| Matching visible face + speech | 201 | 100.0% | 24.9% | 8.5% | 88.6% | 3.0% | 35.3% | 62 (30.8%) | 87.3% |
| Silent face + phone speech at right | 179 | 98.3% | 31.3% | 0.0% | 88.3% | 11.7% | 35.2% | 13 (7.3%) | 20.6% |
| Partial edge face + speech | 167 | 97.0% | 39.5% | 27.5% | 9.0% | 63.5% | 64.1% | 2 (1.2%) | 1.9% |

Across the complete matrix, median/P95/max DoA latency was 51.3/517.7/1099.8 ms.

## Main findings

1. **The visual-availability gate works.** Speech with no visible face produced 35 tracked acoustic rows and zero physical confirmations.
2. **Matching geometry provides useful coverage.** Matching face/speech produced 62 confirmations over 71 tracked rows (87.3%).
3. **Geometry is not source ownership.** The visible-silent condition confirmed all 13 false acoustic tracking episodes. The spatially mismatched phone condition falsely confirmed 13/63 tracked rows (20.6%).
4. **Rolling evidence is a safety trade-off.** In matching speech it supplied continuity for 39/62 confirmations, but in the mismatched condition it contributed 9/13 false confirmations.
5. **Visual boundary behaviour is not graceful.** A partial edge face generated 106/167 multiple-face rows and 46/167 no-face rows, despite one operator. Fusion safely abstained on 105/107 tracked rows, but availability collapsed.
6. **Transport is usually valid but bursty.** Aggregate DoA validity was 98.28%, while condition-level P95 latency and individual timeouts show that a realtime policy must explicitly handle stale/missing observations.

## Engineering conclusion

The passive camera layer materially improves observability and prevents target selection when no face is visible. It is not safe as a speaker-confirmation mechanism: acoustic reflections or endpoint variation can align a spatially separate sound with a visible face, and retained evidence can prolong the error. The current fusion state should therefore remain shadow-only.

The highest-value next step is an entirely offline counterfactual policy evaluation over the frozen matrix. Candidate hardening rules should include: immediate track invalidation after sustained acoustic/visual disagreement; shorter evidence memory; concurrent-speech requirements for initial confirmation; multi-frame face/axis association; and strict missing/multiple/stale-face lockout. Development and evaluation trials must be separated before tuning so improvements are measured rather than fitted to the same evidence.

Status: **MATRIX COMPLETE — USEFUL PASSIVE OBSERVABILITY DEMONSTRATED; SOURCE-OWNERSHIP AND VISUAL-BOUNDARY LIMITATIONS PRECLUDE ACTUATION.**
