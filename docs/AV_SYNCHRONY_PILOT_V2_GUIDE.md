# V2 face-landmark synchrony development pilot

## Why V2 exists

The completed V1 pilot rejected frame-to-frame pixel change in a fixed mouth box: 0/240 settings met its selection rule. V2 does not revise that result. It replaces the visual instrument with face-tracked, scale-normalized lip aperture and separates threshold development from an untouched internal validation repetition.

This remains a small, single-person, single-setup development pilot. Even a pass would not validate identity, authorization, multi-speaker behavior, or the planned 54-trial study.

The pilot has now been completed. Its candidate, full attempt accounting, limitations, and integrity hashes are reported in [`AV_SYNCHRONY_PILOT_V2_RESULT.md`](AV_SYNCHRONY_PILOT_V2_RESULT.md).

Frozen protocol fingerprint: `afb6794ec5a94a6d6739142dd69e873c1aec2f6df307a8bf4b9b4cf6612e8754`.

## Recorder commissioning history

Recorder revision 1 produced three explicit quality-failed attempts for the first scheduled trial: 90, 86, and 86 samples against the 160-sample minimum. Revision 2 changed only instrument execution (GPU inference, 320×240 input, and a deadline-anchored scheduler), but its three attempts still produced only 142, 146, and 138 samples in eight seconds. All six attempts failed only `INSUFFICIENT_SAMPLES`, every failed CSV is retained privately, and no canonical V2 trial was accepted. Revision 3 uniformly extends all trials to ten seconds while preserving every quality and selection threshold. The manifest preserves both earlier protocol fingerprints.

## Install the pinned local assets

From the repository root, run once while online:

```bash
python scripts/fetch_av_synchrony_v2_assets.py --install
```

The installer verifies the pinned npm package tarball, extracts only an allowlist of browser runtime files, verifies each extracted file, and verifies the Face Landmarker model. Generated assets are ignored by Git. At capture time they are served from localhost; the page has no remote URL.

The implementation follows the official Face Landmarker web API's `VIDEO` mode and `detectForVideo` interface: [Google MediaPipe documentation](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/web_js). The pinned browser package is [`@mediapipe/tasks-vision` 1.0.1](https://www.npmjs.com/package/%40mediapipe/tasks-vision).

## Frozen safeguards

- Twelve randomized ten-second trials: six matching positives and six playback hard negatives.
- Repetitions one and two are the eight-trial development split; repetition three is a four-trial internal validation split.
- All conditions must pass the same fixed audio-dynamic-range gate, preventing playback volume from becoming a convenient negative classifier.
- Exactly one sufficiently large face must be present in at least 95% of rows; any multi-face row fails objective quality.
- Conditions requiring mouth motion must pass a fixed lip-aperture dynamic-range gate.
- A quality-failed capture is downloaded with an explicit failed-attempt filename, retained, and repeated without advancing.
- Threshold selection sees only the development split. Internal validation is evaluated once with the selected setting.

## Run locally

Keep Reachy powered off. Start a local server from the repository root:

```bash
python -m http.server 8765 --bind 127.0.0.1
```

Open `http://127.0.0.1:8765/tools/avsync_pilot_recorder_v2.html` in Chrome or Edge. Initialize the pinned model before granting camera and microphone access. The green points should remain on the two inner-lip and two outer-eye landmarks.

The first model-loading click does not request camera or microphone access. The second click does. After preview starts, keep exactly one face in view until the page says both the face and recorder-performance preflights are ready; then follow only the current randomized trial instruction. If the inference-speed preflight does not pass, stop rather than collecting another guaranteed quality failure.

Use the same consented recording, fixed speaker position, playback volume, chair, camera, microphone, and lighting throughout. Follow the randomized instruction displayed for each trial. Keep every canonical CSV and every explicitly named quality-failed attempt.

## Analyze

Put the twelve canonical CSVs in one directory and run:

```bash
python scripts/analyze_av_synchrony_pilot_v2.py --input PATH_TO_CSV_DIRECTORY --output PATH_TO_REPORT.json
```

When failed attempts are present in the same private directory, audit and hash the complete ledger separately:

```bash
python scripts/audit_av_synchrony_pilot_v2_attempts.py --input PATH_TO_CSV_DIRECTORY --output PATH_TO_PRIVATE_ATTEMPT_AUDIT.json
```

If no development setting is eligible, the V2 instrument is rejected. If development selection succeeds but internal validation fails, it is also rejected. If both pass, the result still only nominates a candidate: freeze the exact code, assets, and selected thresholds separately before collecting any confirmation data.

The completed run nominated a candidate and the separate local freeze has been created. Do not reuse the pilot files as confirmation data or retune the frozen candidate from them.

The deterministic freeze command re-runs the analysis and binds the selected setting to exact inputs, code, recorder, model, and runtime assets:

```bash
python scripts/freeze_av_synchrony_pilot_v2_candidate.py --input PATH_TO_CSV_DIRECTORY --output PATH_TO_PRIVATE_CANDIDATE_FREEZE.json
```

Do not publish numeric participant features without an explicit decision, and never discard or overwrite an inconvenient attempt.
