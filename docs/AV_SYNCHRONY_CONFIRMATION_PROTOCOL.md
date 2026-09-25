# Frozen AV-synchrony confirmation protocol

## Status

The 54-trial acquisition and analysis design is frozen before confirmation data collection. Machine-readable source: [`av_synchrony_confirmation_protocol_v1.json`](../evidence/manifests/av_synchrony_confirmation_protocol_v1.json), fingerprint `1e7f727d5fbf34bfd1be9464787151849b10e880eb8fcde758dce465f49b2bf8`, file SHA-256 `596dc8de7d8be4d984921a02c40640fcd257df508a84b2063acd7531a8507116`.

**Collection is paused before Trial 1.** The current recorder cannot identify several frozen primary endpoints because it records no acoustic direction or Stage 3V policy inputs. Partial private Room A preparation may be retained for future use, but it is not confirmation data. Collection may open only after acoustic-direction capture is validated and the execution contract is refrozen, or after the study is explicitly narrowed and refrozen as a synchrony-only exploratory study.

The separately content-addressed execution contract binds the dedicated 54-trial recorder, pinned local model/runtime, full-trial scoring path, requested acoustic-only, visual-only, and non-abstaining baselines, and the analysis implementation before any confirmation preview or capture. It leaves every V2 candidate threshold unchanged.

This successor preserves the earlier falsification design while closing its execution gaps. It binds the successful V2 candidate, retains every V2 quality threshold, assigns two voice stimuli evenly, defines playback placement when the visible person is centred, and specifies what must be privately bound before collection.

## Fixed design

- 54 ten-second trials;
- three distinct enclosed physical rooms not used for the V2 pilot;
- visible-person headings at −20°, 0°, and +20°;
- two matching-positive and four hard-negative conditions at every room/heading block;
- 18 matching-positive and 36 hard-negative trials;
- two consented recorded voices, each used in 18 hard-negative trials and twice per room/heading block;
- a frozen within-room randomized schedule using seed `730114`;
- no adaptive stopping or reordering after any preview, quality, or outcome data are visible.

For opposite-playback trials, −20° maps to +20° and +20° maps to −20°. A centred visible person has no literal opposite within the three-heading design, so the two opposite-playback conditions are counterbalanced between −20° and +20° across rooms.

## Frozen candidate and quality gates

The candidate remains minimum correlation `0.25`, maximum absolute lag `120 ms`, and three-sample smoothing. Its candidate-freeze fingerprint is `586882b1a72b6eff64baebc98556e988a047d2290f4f484178a0aeb07db52e46`. Confirmation-time threshold selection or retuning is prohibited.

The V2 quality gates are unchanged: at least 160 samples, at least 7000 ms span, at most 160 ms sample gap, at least 95% single-face rows, zero multiple-face rows, minimum median face scale 0.16, minimum audio variation 0.5 dB, and minimum normalized lip-aperture variation 0.002 in the three movement-required conditions.

## Required private bindings

Before the first confirmation preview or capture, bind and hash:

1. three opaque room records with dimensions, surfaces/furnishings, background level, and every camera, microphone, face, and playback mark;
2. two voice-stimulus records with consent basis, file SHA-256, duration, language, playback device, and fixed volume;
3. the computer OS/build, browser, camera, microphone, selected audio input, media settings, recorder hash, model, and runtime; and
4. an empty output directory and complete attempt ledger.

Use the same fixed camera and microphone configuration in every room. If the only reliable input is a headset microphone, mount it at a fixed marked position; do not wear it, because a moving near-mouth sensor would confound live speech with playback conditions.

Exact domestic or institutional room locations and voice identities remain private. The opaque bindings and hashes establish that they were fixed; they do not make the stimuli additional participants.

## Exclusions and repeats

Exclusions must be decided before any candidate or comparator outcome is computed. Only incomplete capture, missing/nonfinite streams, a frozen numeric quality failure, a setup deviation, withdrawn consent, or equipment safety may exclude an attempt. Retain the attempt and reason. Correct only that recorded issue, then repeat the same scheduled card. Never substitute another condition or remove a failed condition from the analysis.

## Analysis and confirmation rule

The trial is the inferential unit. Report matching-positive coverage, hard-negative false proposals, and the paired difference from the frozen Stage 3V spatial comparator. Report two-sided nominal 95% Wilson intervals, an exact two-sided McNemar test over paired hard negatives, and every endpoint by room, condition, heading, and voice.

Confirmation requires all of:

- 0/36 hard-negative trials with a proposal;
- at least 15/18 matching-positive trials with a proposal;
- zero wrong-sign proposals;
- maximum target error no greater than 8°;
- strictly fewer hard-negative proposals than the frozen spatial comparator; and
- every condition retained.

Even a pass would support only a candidate audiovisual association in this design. It would not establish speaker identity, intent, consent, authorization, general active-speaker performance, social benefit, or mechanical safety.

The five-column laptop instrument does not record acoustic direction or the input fields needed to replay the frozen Stage 3V spatial policy. Consequently, the Stage 3V paired primary endpoint, independently measured target-heading error, wrong-sign outcomes, and streaming first-proposal latency are not identifiable from these captures. The execution contract freezes this limitation before collection and permits only a clearly labelled exploratory geometry proxy; it must not be reported as the frozen Stage 3V comparator or used to declare the full V1 rule passed.

## Safety boundary

This is a passive-sensing protocol. It authorizes zero motion, torque, calibration, firmware, or motor-mode commands. Freezing this design does not clear the separate Reachy daemon-recovery or physical-motion blockers.

## Reproduce

```bash
python scripts/freeze_av_synchrony_confirmation_protocol.py --check
python scripts/freeze_av_synchrony_confirmation_execution.py --check
python -m unittest tests.test_av_synchrony_confirmation_protocol
python scripts/prepare_av_synchrony_confirmation_workspace.py --initialize --browser "Microsoft Edge 152.0.4191.53"
python scripts/prepare_av_synchrony_confirmation_workspace.py --status
```

The preparation command creates an ignored private workspace, a 54-row schedule ledger, six binding records, and an empty capture directory without opening any sensor. It never overwrites an existing binding. The background-level meter and confirmation recorder are retained for protocol development, but the current collection pause takes precedence over their availability. Do not seal or open Trial 1 until the identifiability decision above is resolved and refrozen.
