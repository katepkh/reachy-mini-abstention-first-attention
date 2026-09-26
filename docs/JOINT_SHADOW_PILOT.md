# Frozen joint-shadow no-motion pilot

Status: **STRUCTURE FROZEN — COLLECTION GATE CLOSED**

The joint instrument passed one real commissioning capture on 26 September
2026. That capture established simultaneous observability of one face, laptop
audio/lip features, and Reachy's GET-only direction-of-arrival state. It is not
part of this pilot and may not be used for fitting or validation.

The old laptop-only synchrony setting abstained on the commissioning positive
(`correlation=0.199`, selected lag at the `-120 ms` boundary). A diagnostic
scan found that the apparent positive correlation increased at wider lags, but
one commissioning capture cannot justify widening the gate. This pilot tests a
predeclared grid against hard negatives before accepting any transferred
setting.

## Scope

- 21 ten-second trials: seven conditions repeated in three balanced blocks.
- Repetitions 1–2 are development; repetition 3 is internal validation.
- Trial order is deterministically randomized inside each block.
- Reachy provides GET-only DoA observations.
- No robot application, movement, response, raw-media saving, or upload.
- This is an engineering pilot, not confirmation or publication evidence.

Print the frozen order from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts\print_joint_shadow_pilot_schedule.py
```

The full machine-readable protocol is available with `--json`. Its fingerprint
must remain unchanged throughout collection.

## Conditions

1. Visible continuous live speech.
2. Visible interrupted live speech.
3. Silent visible face with fixed phone playback from a colocated mark no more
   than 10° from the face heading.
4. Silent out-of-time mouthing with unrelated fixed playback from that same
   colocated mark.
5. Visible silence.
6. Live speech with no usable face in frame; no playback.
7. Silent visible face with playback from a conflict mark at least 45° from
   the face heading.

The phone position, playback file, volume, laptop, Reachy, camera field of view,
and room marks remain fixed. Do not substitute live reading for the fixed phone
recording in playback conditions.

Before trial 1, bind the playback file SHA-256, phone make/model and volume,
colocated and conflict phone marks, room/setup identifier, laptop and Reachy
marks, camera field-of-view estimate, and operator mark. The values can remain
private, but they must be checked across all 21 captures. Collection does not
open until the offline pilot-analysis code is also frozen and tested.

## Capture rule

Follow the printed order exactly. Enter the printed `trial_id`; the joint
recorder binds and locks its scheduled condition and ten-second duration from
the frozen protocol. Confirm valid/fresh DoA and the required face state, then
capture. The recorder uses the trial ID as the CSV/metadata filename and embeds
the instrument and pilot fingerprints plus the frozen schedule fields in
metadata. Keep both files private.

If an objective quality check fails, retain that attempt privately, correct
only the stated problem, and repeat the same scheduled trial. Do not advance or
substitute a condition.

## Frozen analysis boundary

Only repetitions 1 and 2 may select a candidate setting. A candidate must
abstain on every development hard negative/control and propose on at least
three of four development positives. Ties prefer the higher correlation
threshold, tighter spatial threshold, narrower lag window, and less smoothing.
If no setting qualifies, the pilot fails without relaxing a gate.

Repetition 3 is opened only after selection is frozen. It must accept both
positives and abstain on all five negative/control trials. Failure requires a
new protocol version; it cannot be repaired by retuning on repetition 3.

The pilot compares the fused candidate with acoustic-only, visual-activity-only,
spatial-only, and non-abstaining baselines. Final sample size, held-out rooms,
physical motion, attention hold, audio response, and end-to-end claims remain
downstream.
