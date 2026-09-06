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

### Post-hoc Stage 3V robustness replay

After the V3 confirmation result was known, the accepted trial list was replayed with nominal 95% Wilson intervals, leave-one-trial-out deletion, one-parameter sensitivity, a 25-point geometry/hit operating grid, and four named diagnostic ablations. The experimental unit is the accepted trial. The analysis reports latency and abstention duration from each trial's first timestamp and does not count telemetry rows as independent samples.

The original V3 policy remains the only held-out policy in this dataset. The robustness plan, ablations, and operating points are post-hoc and therefore descriptive. In particular, they do not provide a calibrated population risk–coverage curve or causal component effects. The deterministic implementation and report are [`reachy_stage3v/robustness.py`](../reachy_stage3v/robustness.py) and [`stage3v_trial_robustness_v1.md`](../evidence/analysis/stage3v_trial_robustness_v1.md).

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

## Future audio–mouth synchrony study

The next passive falsification design began in [`AV_SYNCHRONY_FALSIFICATION_PROTOCOL.md`](AV_SYNCHRONY_FALSIFICATION_PROTOCOL.md). It has no collected confirmation data. The numeric prototype accepts already-derived local signals, and its nine passing synthetic cases verify only declared fail-closed software branches. The first 12-trial [`laptop-only development pilot`](AV_SYNCHRONY_PILOT_GUIDE.md) was run and rejected: 0/240 fixed-box settings met its selection rule. The separately versioned [`V2 pilot`](AV_SYNCHRONY_PILOT_V2_RESULT.md) recorded local microphone dBFS plus face-tracked lip aperture normalized by outer-eye distance, applied uniform objective quality gates, searched 45 settings using only repetitions one and two, and evaluated the accepted repetition-three files with the development-selected setting. Twelve canonical trials from 23 attempts passed both rules; the exact candidate, code, model, runtime, protocol, and input hashes are locally frozen. The candidate-bound [`54-trial confirmation protocol`](AV_SYNCHRONY_CONFIRMATION_PROTOCOL.md) now fixes room slots, balanced voice assignment, playback geometry, unchanged V2 quality gates, exclusions, and analysis. Exact private room/device/voice bindings remain required before collection. This remains development and design evidence, not confirmation.
