# Audio–mouth synchrony falsification study

## Status and purpose

This is a **future passive study design**, frozen before collecting any data for it. It does not authorize robot motion. Its machine-readable design is [`av_synchrony_falsification_protocol_v1.json`](../evidence/manifests/av_synchrony_falsification_protocol_v1.json), fingerprint `c61ed6fa70029f5016c567bcb6c6952d6e8dc5f5e1742ad06a2aa731ae165572`.

Post-freeze status: the required [`V2 development pilot`](AV_SYNCHRONY_PILOT_V2_RESULT.md) nominated and content-froze an instrument candidate. No trial from the 54-trial confirmation design has been collected.

The prior study established that acoustic direction and face position can be geometrically compatible. It also falsified the stronger inference that compatibility proves the visible face owns the sound. This study asks a narrower next question:

> When acoustic direction and face position agree, can derived audio–mouth synchrony reduce false visible-speaker proposals without unacceptable loss of matching-trial coverage?

Even a positive result would support only a **candidate association**. Synchrony does not establish identity, consent, authorization, intent, or mechanical readiness.

## What is implemented now

[`reachy_avsync/synchrony.py`](../reachy_avsync/synchrony.py) is a command-free numeric prototype. It:

- derives an RMS speech-energy envelope from an already-loaded mono waveform and scale-normalized mouth motion from already-local lip landmarks, or accepts equivalent timestamped numeric arrays;
- rejects missing, nonfinite, stale, gapped, low-dynamic-range, and excessive-clock-drift inputs;
- searches a bounded lag window for positive normalized cross-correlation;
- abstains when two face tracks have similarly strong scores;
- requires the same face-track candidate across three windows before returning `SUPPORTED_CANDIDATE`;
- deliberately names every positive output `NOT_IDENTITY`.

The numeric defaults in [`SynchronySpec`](../reachy_avsync/synchrony.py) remain uncalibrated engineering defaults, not confirmation thresholds. The successful V2 pilot separately freezes its selected candidate—minimum correlation `0.25`, maximum absolute lag `120 ms`, and three-sample smoothing together with every other bound, exact code, local model/runtime assets, and input hashes. Confirmation must use that content-addressed candidate rather than silently changing the implementation defaults.

The deterministic synthetic suite covers aligned motion, silence, static mouth, unrelated motion, frame gaps, clock drift, equally synchronous faces, overlapping sources, and rapid face switching. All nine software cases pass in [`av_synchrony_synthetic_faults_v1.json`](../evidence/analysis/av_synchrony_synthetic_faults_v1.json). This proves branch behavior on constructed arrays only; it is not real audiovisual evidence.

## Confirmation design

The frozen design contains 54 trial units: six conditions at three headings in three acoustically different rooms or documented acoustic configurations.

| Condition | Role | Why it matters |
|---|---|---|
| Visible live continuous speech | matching positive | Basic coverage. |
| Visible live interrupted speech | matching positive | Tests natural pauses and latency. |
| Silent face + colocated playback | hard negative | Spatial evidence agrees although the visible person is not the source. |
| Silent mouthing + time-shifted colocated playback | hard negative | Attacks naive mouth-motion detection. |
| Silent face + opposite playback | hard negative | Retains a spatial-mismatch control. |
| Live speech + opposite playback | hard negative | Requires abstention under overlapping-source ambiguity. |

There are 18 matching-positive and 36 hard-negative trials. Within each room, the schedule is shuffled once by the predeclared seed rule. At least two consented recorded voices are used as stimuli; they are not counted as participants.

The required 12-trial V2 development pilot is complete and its data must never enter the confirmation result. Before opening confirmation, bind the already frozen candidate to the 54-trial acquisition implementation, allowed exclusions, exact randomized file list, and fresh output directory; rehearse the full attempt ledger offline without changing the candidate.

## Trial procedure

1. Keep the robot passive: no target, movement, torque, calibration, or motor-mode command.
2. Place the robot, visible operator, and fixed playback source on documented marks.
3. Follow the already-randomized condition card; do not improvise the label after capture.
4. Derive audio energy, mouth motion, face track, geometry, timing, and health fields locally.
5. Store only the declared numeric outputs and hashes publicly. Do not publish audio, pixels, transcripts, or identity embeddings.
6. Apply outcome-blind quality gates before policy replay. Retain and label every attempt, including exclusions.
7. Finish the fixed 54-trial schedule unless equipment safety or consent requires stopping. Do not stop early because the results look good or bad.

The design assumes any captured or recorded voice is used with consent. If temporary raw media is needed for instrumentation audit, its encryption, access, retention, and deletion procedure must be declared before collection.

## Frozen endpoints and decision rule

The experimental unit is the trial. Frames are correlated observations inside it.

Primary endpoints:

- matching-positive trial coverage;
- hard-negative trial false-proposal rate;
- paired hard-negative proposal difference versus the frozen Stage 3V spatial policy.

Secondary endpoints are first-proposal latency, observed abstention duration, wrong-sign proposals, maximum target-heading error, and abstention reasons. Report nominal 95% Wilson intervals over trials and the two-sided exact McNemar result for paired hard-negative outcomes. Also report every endpoint by room, condition, and heading.

The predeclared confirmation rule is:

- 0 of 36 synchrony-gated hard-negative trials may contain a proposal;
- at least 15 of 18 matching-positive trials must contain a proposal;
- zero wrong-sign proposals;
- maximum target-heading error no greater than 8°;
- strictly fewer hard-negative trial proposals than the frozen spatial comparator;
- no condition may be silently removed from the result.

Zero of 36 hard-negative events would still not prove zero population risk; its nominal 95% Wilson upper bound is about 9.6%. The room and voice sample also remains too small for broad generalization.

## Predeclared quality exclusions

An attempt may be excluded only when its capture is incomplete, a required numeric stream is missing/nonfinite, the newly frozen sample-gap or drift limit is exceeded, the face configuration is absent for the newly frozen minimum fraction, or the setup deviates from the randomized card. Exclusion must be decided without viewing policy outcomes. Every attempt and reason remains in the ledger.

## Falsification logic

The idea should be rejected or narrowed if any of the following occurs:

- spatially colocated playback repeatedly passes the synchrony gate;
- silent mouthing plus shifted playback repeatedly passes;
- overlap produces a confident single-face proposal instead of abstention;
- acceptable hard-negative performance is obtained only by destroying positive coverage;
- the result changes materially across rooms, recorded voices, or minor threshold changes;
- timestamp drift, face tracking, or signal quality cannot be measured reliably enough to enforce the declared gates.

## Reproduction

```bash
python scripts/freeze_av_synchrony_protocol.py --check
python scripts/run_av_synchrony_faults.py --check
python -m unittest tests.test_av_synchrony
```

These commands are offline. The first verifies the frozen design, the second regenerates constructed fault cases, and the third tests the numeric implementation. None collects experimental data or contacts Reachy.
