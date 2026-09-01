# Methods

## Experimental unit and environment

Experiments used one Reachy Mini, one room, and one primary operator. Other human voices were introduced as controlled recordings; they were not additional human participants. Distances, headings, and eye-line marks were physically measured for the frozen protocols.

## Data minimization

Runtime camera frames were used only to derive face count, detector confidence, and position. The main datasets store no pixels. The DoA interface supplied numeric direction, speech/validity state, and timing; the public evidence contains no waveform or transcript. A narrow later protocol used encrypted, temporary audit clips for operator review, then recorded deletion; those sidecars and keys are excluded from this repository.

## Stage 2A: five-condition passive matrix

Fifteen accepted trials covered five conditions with three repetitions each:

1. visible silent face;
2. speech with no visible face;
3. matching visible face and speech;
4. silent visible face with phone speech from the right;
5. partial edge face with speech.

The latest accepted capture for each immutable step was selected. The matrix produced 815 observations, of which 801 had valid DoA responses. No robot command was available in this stage.

## Counterfactual tournament

Five policies were replayed over frozen numeric rows. Repetitions 1–2 formed development; repetition 3 formed evaluation. Selection used development only: prefer zero hard-negative confirmed rows, then maximize matching-positive coverage and trial coverage; otherwise minimize hard-negative confirmation before maximizing coverage.

Important caveat: the complete matrix had already been inspected before this split was formalized. The evaluation repetition is retrospectively frozen and is not called a blind holdout.

## Stage 3V: fresh passive horizontal off-axis validation

The chosen shadow policy was frozen before new data collection. Eighteen accepted trials covered horizontal yaw headings at ±10° and ±20° plus six hard negatives. Three additional hard-negative attempts were retained as noncompliant evidence. Gates required:

- zero hard-negative would-move rows;
- correct turn sign;
- proposals in all required repetitions per heading;
- target error within the frozen tolerance.

All outputs were counterfactual shadow targets; this stage had no actuation authority.

## Stage 3P: association-gated visual-cue boundary

Nine accepted trials comprised six associated centre-to-vertical transitions and three no-cue controls. The protocol required three stable centred compatibility rows before the software displayed a `MOVE UP` or `MOVE DOWN` instruction to the operator. Controls tested silence, speaking without a face, and speaking while visible but not centred. The correct control outcome was a fail-closed timeout with no visual move instruction.

The repeated test phrase supplied speech energy only. Stage 3P stored no transcript, did not recognize or match phrase content, emitted no robot request, and had no actuation capability. It tests passive cue timing and fail-closed behavior, not human identity, intent, consent, or command authorization.

All accepted trials had a compliance review. Nine superseded attempts were preserved. Eight have generic `NONCOMPLIANT` sidecars and one has no compliance sidecar, so the public record cannot reconstruct a specific reason for every retry. Audit clips were deleted after review and are not public evidence. See [`ATTEMPT_ACCOUNTING.md`](ATTEMPT_ACCOUNTING.md).

## Stage 4A: supervised one-shot pilot

The pilot limited authority to a displayed direction, a 3° head-only target, and automatic return. Each preflight was read-only and expiring; execution required the exact typed arming string and consumed a one-shot local session. This is an operator arming mechanism, not identity, consent, intent, or conversational authorization. Body yaw, antenna, torque, and motor-mode commands were excluded.

Acceptance tolerances were frozen before execution. One physical trial ran and failed. A diagnostic reconstruction identified early target sampling, absent return settling, fragile rotation-angle computation on slightly non-orthonormal matrices, and an absolute-neutral target that did not guarantee a 3° increment from the captured baseline. The failed result was not retried under the same protocol.

## Integrity controls

- protocol and policy fingerprints;
- SHA-256 file manifests;
- accepted, rejected, and superseded attempts retained;
- frozen results are immutable;
- threshold changes after an outcome are forbidden;
- passive stages contain no command path;
- physical authority is narrow, expiring, and one-shot.

Threshold freezing does not establish that a value was calibrated. [`THRESHOLD_PROVENANCE.md`](THRESHOLD_PROVENANCE.md) separates development-selected values from protocol-fixed, project-fixed, and hardware-bound choices and records the missing sensitivity work.

The passive candidate, Stage 3P visual cue, and Stage 4 command boundary have not yet been connected and validated as one end-to-end system.
