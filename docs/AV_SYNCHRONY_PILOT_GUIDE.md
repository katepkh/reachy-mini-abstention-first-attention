# Laptop-only audio–mouth synchrony pilot

> **Completed development result:** the 12-trial run rejected this fixed-box instrument; no threshold was selected. Do not reuse it for confirmation. See [`AV_SYNCHRONY_PILOT_RESULT.md`](AV_SYNCHRONY_PILOT_RESULT.md).

## What is ready

This is a 12-trial **development pilot**, not the 54-trial confirmation study. Reachy is not used and should remain powered off.

The pilot exists to answer three engineering questions:

1. Does a simple local microphone-energy signal covary with a crude mouth-region motion signal during visible live speech?
2. Does it abstain for a silent visible face beside playback and for deliberately time-shifted silent mouthing?
3. Which candidate correlation, lag, and dynamic-range thresholds deserve freezing before new confirmation data?

The manifest [`av_synchrony_pilot_protocol_v1.json`](../evidence/manifests/av_synchrony_pilot_protocol_v1.json) fixes 12 trials, their random order, required CSV schema, a 240-candidate threshold grid, and the deterministic selection rule. A successful development result is still not confirmation evidence.

## Before recording

- Keep Reachy powered off; the robot is irrelevant to this pilot.
- Use only your own voice or a recording whose speaker consented to this use.
- Use Chrome or Edge on the laptop with one stable camera/microphone setup.
- Keep lighting, camera position, chair position, playback volume, and speaker position fixed.
- Close video-call effects, automatic framing, and virtual microphones if possible.
- Prepare one ordinary speech recording for the two playback conditions.
- Do not publish the downloaded numeric files until you have inspected their residual privacy/context fields. The recorder contains no name or transcript, but timestamps and condition labels still reveal context.

## Start the recorder

From the repository root:

```bash
python -m http.server 8000
```

Open `http://localhost:8000/tools/avsync_pilot_recorder.html`, enable the local preview, and align your mouth with the dashed box. The browser asks for camera and microphone permission. The page makes no upload request and does not encode or save the raw streams.

For every scheduled trial:

1. Read the displayed condition.
2. Prepare the playback speaker before pressing Start.
3. Hold your head and laptop still; facial or camera motion is a known confound.
4. Press Start and follow the condition for eight seconds.
5. Confirm that the correctly named CSV downloaded before continuing.

The two positive conditions are continuous live speech and interrupted live speech. The negatives are a silent still face beside playback and silent mouthing with unrelated/time-shifted playback. Each appears three times in frozen random order.

## Important instrumentation limitation

The browser uses pixel change in a fixed mouth-region box. It does **not** track lip landmarks or identity. Head movement, illumination changes, screen flicker, camera auto-exposure, and a badly positioned face can mimic mouth motion. That is precisely why this is a pilot. If the signal is not credible, replace the instrument before the confirmation study rather than relaxing the outcome rule.

## Analyze the twelve CSVs

Put the twelve exact files in one directory, then run:

```bash
python scripts/analyze_av_synchrony_pilot.py --input PATH_TO_CSV_DIRECTORY --output PATH_TO_DEVELOPMENT_REPORT.json
```

The analyzer requires every frozen filename, rejects malformed/gapped inputs, hashes the numeric sources, evaluates all 240 declared threshold candidates, and applies the frozen selection rule. It reports either no eligible setting or one development candidate.

Do not edit individual CSV values, remove an inconvenient trial, or call the selected threshold final. First review signal traces and failure reasons. If the instrumentation is credible, generate a separate code-and-threshold freeze before collecting any confirmation trial.

## Verify the pipeline without recording yourself

```bash
python scripts/freeze_av_synchrony_pilot_protocol.py --check
python scripts/run_av_synchrony_pilot_dry_run.py --check
python -m unittest tests.test_av_synchrony_pilot
```

The dry run uses constructed temporary arrays and deletes them afterward. It tests the file loader, input gates, 240-candidate search, and selection logic; it does not calibrate anything real.
