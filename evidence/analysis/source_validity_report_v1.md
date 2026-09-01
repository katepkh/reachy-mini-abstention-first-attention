# Reachy Mini metadata-only source-validity experiment v1

This offline experiment uses only saved DoA, `speech_detected`, timing and validity metadata. It stores no audio, images, video or transcripts and makes no robot or cloud request.

## Guardrail

The model was fitted only on 61 development trials. Its frozen model fingerprint is `1bbb131ff91a2ccffa48489e968e7531c51bf5238df86f16d17a2ae820297890`. Evaluation consists of held-out repetitions of known controlled conditions; it does not establish generalization to novel sounds, rooms or operators.

## Development leave-one-condition-group-out cross-validation

- Coverage: 19.672%
- Selective accuracy: 100.0%
- False-human acceptance: 0.0%
- Live-human rejection: 0.0%
- Live-human abstention: 76.596%

## Locked held-out evaluation

- Trials: 35 (28 live-human, 7 non-live)
- Coverage: 25.714%
- Selective accuracy: 100.0%
- False-human acceptance: 0.0%
- Live-human rejection: 0.0%
- Live-human abstention: 71.429%
- Non-live rejection: 14.286%
- Non-live abstention: 85.714%

## Interpretation

`LIVE_LIKELY` means only that endpoint dynamics resemble this laboratory's controlled live-human development trials. It is not proof of a person, identity or intent. High overlap or abstention is evidence that the metadata endpoint alone is not sufficiently observable for source semantics.

The frozen post-evaluation condition breakdown and uncertainty intervals are recorded in
[`source_validity_condition_audit_v1.md`](source_validity_condition_audit_v1.md). It documents that
keys were the only confidently rejected non-live condition, while all four held-out two-speaker
conflict conditions appeared live-like and the quiet baseline remained ambiguous despite 104
speech-positive samples.
