# Stage 2A offline counterfactual policy tournament v1

Frozen evidence fingerprint: `f3832e8a2637ffbf478d91434c1cf69a42a4bb9123dc5da95fefca820463f959`

> This is a retrospective internal comparison, not a pristine blind holdout. The complete matrix had already been inspected before the split was formalised.

## Fixed split and selection

- Development: repetitions 1–2 (10 trials).
- Evaluation: repetition 3 (5 trials).
- Winner selected on development only using the frozen lexicographic safety rule in the manifest.
- Development-selected policy: **3-hit safety consensus**.

## Development comparison

| Policy | Matching confirmations / tracked | Matching tracked coverage | Hard-negative confirmations / tracked | Hard-negative tracked false rate | Boundary confirmations |
|---|---:|---:|---:|---:|---:|
| Recorded Stage 2A | 38 / 40 | 95.00% | 21 / 74 | 28.38% | 2 |
| Current speech only | 12 / 40 | 30.00% | 9 / 74 | 12.16% | 2 |
| Short hold 250 ms + disagreement reset | 15 / 40 | 37.50% | 11 / 74 | 14.86% | 2 |
| 2-hit consensus + reset | 6 / 40 | 15.00% | 2 / 74 | 2.70% | 0 |
| 3-hit safety consensus | 3 / 40 | 7.50% | 1 / 74 | 1.35% | 0 |

## Retrospectively frozen evaluation

| Policy | Matching confirmations / tracked | Matching tracked coverage | Hard-negative confirmations / tracked | Hard-negative tracked false rate | Silent / no-face / mismatch false confirms | Boundary confirmations |
|---|---:|---:|---:|---:|---:|---:|
| Recorded Stage 2A | 24 / 31 | 77.42% | 5 / 37 | 13.51% | 2 / 0 / 3 | 0 |
| Current speech only | 11 / 31 | 35.48% | 0 / 37 | 0.00% | 0 / 0 / 0 | 0 |
| Short hold 250 ms + disagreement reset | 9 / 31 | 29.03% | 0 / 37 | 0.00% | 0 / 0 / 0 | 0 |
| 2-hit consensus + reset | 4 / 31 | 12.90% | 0 / 37 | 0.00% | 0 / 0 / 0 | 0 |
| 3-hit safety consensus | 2 / 31 | 6.45% | 0 / 37 | 0.00% | 0 / 0 / 0 | 0 |

## Result

The development-selected policy was **3-hit safety consensus**. On the retrospective evaluation repetition it confirmed 0 hard-negative rows at 2/31 tracked matching rows (6.45%). The recorded policy confirmed 5 hard-negative rows at 24/31 tracked matching rows (77.42%).

The evaluation repetition also shows why this is a frontier rather than a deployment winner: the current-speech-only rule had zero hard-negative confirmations and higher matching coverage than the stricter consensus variants on that small retrospective split, while it was less safe on development. More independent repetitions are required to estimate that trade-off.

This result measures a counterfactual decision rule on one robot, room and operator. It does not validate autonomous actuation, source identity or generalisation.
