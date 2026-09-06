# V2 face-landmark synchrony pilot result

## Outcome

The predeclared V2 development and internal-validation rules both passed in one single-person, single-setup laptop pilot. This nominates and freezes an instrument candidate; it is **not** confirmation evidence and does not validate identity, authorization, multiple speakers, social attention, or robot behavior.

- Protocol fingerprint: `afb6794ec5a94a6d6739142dd69e873c1aec2f6df307a8bf4b9b4cf6612e8754`.
- Twelve canonical ten-second trials passed every objective quality gate.
- The complete ledger contains 23 attempts: 12 canonical and 11 quality-failed attempts.
- Six recorder-commissioning attempts failed `INSUFFICIENT_SAMPLES`; five later attempts failed the unchanged `LIP_DYNAMIC_RANGE_TOO_LOW` gate.
- All failed attempts were retained. No individual value was edited and no failed attempt entered threshold selection or validation scoring.
- The analysis made 0 robot connections and sent 0 actuation commands.

## Development selection and internal validation

Eight of the 45 predeclared development settings were eligible. The deterministic tie-break selected:

- minimum correlation `0.25`;
- maximum absolute lag `120 ms`;
- moving average `3` samples;
- all other synchrony and quality values exactly as recorded in the candidate freeze.

On repetitions one and two, the selected setting produced candidates for 4/4 matching-positive trials and 0/4 hard-negative trials. It was then applied once to the accepted repetition-three files: 2/2 matching-positive trials produced candidates and 0/2 hard-negative trials did. All twelve accepted files passed their fixed quality gates.

The two quality-failed acquisition attempts preceding accepted validation trial 12 are disclosed in the complete ledger. Both failed the predeclared mouth-motion quality gate before candidate scoring; the accepted validation file was scored once. This preserves the declared quality-repeat rule but still adds acquisition dependence that must be considered when interpreting such a small internal validation.

## Integrity and privacy

The raw numeric CSVs and their full audit remain under the Git-ignored `data/private/` tree. They contain derived audio level and face-landmark measurements, so they are not placed in the public evidence tree by default.

- Canonical source-bundle SHA-256: `e389ff1e2643533ced7ca8e8a2cc54df7099808cc14a15d878fae7c3fc2dabe5`.
- Private analysis JSON SHA-256: `3443076a8e98609b4642996555d2e554b8d4ca7d2b4cd268897f7f8f55b002e4`.
- Complete 23-attempt audit JSON SHA-256: `f853fad82e1e6e363006edde80271ceca6c84402996e35fb47fd9735da969eac`.
- Candidate-freeze fingerprint: `586882b1a72b6eff64baebc98556e988a047d2290f4f484178a0aeb07db52e46`.
- Candidate-freeze JSON SHA-256: `b113d15f0384cb9e9cd3dd6b9a5a928978c1d221dba919fa6552b1b27f919590`.

The candidate freeze binds the selected setting to the protocol, twelve canonical input hashes, analysis code, recorder, pinned model, and installed MediaPipe runtime assets.

## Interpretation and next boundary

The tracked, face-normalized instrument succeeded where the V1 fixed mouth box failed, but this is a small development result using one operator and one setup. The next evidence must come from a separately opened confirmation protocol with new acoustic configurations, randomized hard negatives, multiple consented recorded voices, complete attempt accounting, and no retuning of this candidate. Reachy is not needed for the next protocol-design and offline-rehearsal work and should remain powered off.
