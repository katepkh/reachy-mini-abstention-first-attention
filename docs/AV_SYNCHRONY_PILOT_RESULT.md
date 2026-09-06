# Audio–mouth synchrony development-pilot result

## Verdict

**Instrument rejected; no threshold selected.**

The frozen 12-trial, laptop-only development pilot was completed on 4 September 2026. None of the 240 predeclared threshold combinations met the selection rule. This is a useful negative engineering result: the fixed mouth-region frame-difference signal should not be carried into the 54-trial confirmation study.

This pilot used no robot connection or command and is not confirmation evidence, an identity test, or an authorization test.

## Attempt accounting

The browser produced 13 CSV downloads for 12 scheduled trial identifiers. `avsync-pilot-03` was captured twice. The later capture, which immediately preceded the uninterrupted remainder of the randomized schedule, is the primary development set; the earlier capture is retained as a duplicate-attempt sensitivity set. This choice does not change the verdict:

| Analysis set | Trial-03 source SHA-256 | Bundle SHA-256 | Eligible settings |
|---|---|---|---:|
| Primary, later trial 03 | `99645c997771b4c2a4bddf5fc49d275c9d5fba990b45cab88024a59d91ca606a` | `3e7e3aa380c43dde815a3ade0f72041f0a9879061b043aa7d3135b72322288b6` | 0 / 240 |
| Sensitivity, earlier trial 03 | `842ee68461c7f8f6aa84e1eaba5d79130531d2a3c9149e0abb444e9a8747f98f` | `55710b9a980254c3062429b5689e182363b314f11419ff8d81f7c27ab4046749` | 0 / 240 |

The machine-readable reports are [`av_synchrony_pilot_development_v1.json`](../evidence/analysis/av_synchrony_pilot_development_v1.json) and [`av_synchrony_pilot_duplicate_sensitivity_v1.json`](../evidence/analysis/av_synchrony_pilot_duplicate_sensitivity_v1.json). Their SHA-256 sidecars cover the exact reports. The source CSVs are not included in the public evidence tree pending an explicit publication decision.

## Data-quality checks

Every primary trial had exactly 200 numeric samples, a 7.955–7.969 s observation span, and a maximum inter-sample gap of 50.2–57.0 ms. Each file had exactly the frozen columns `timestamp_ms`, `audio_energy`, and `mouth_motion`; no raw audio, image pixels, transcript, name, or absolute timestamp was stored.

The positive trials had audio standard deviations of 0.00634–0.01074 and mouth-motion standard deviations of 0.00760–0.01782. The hard negatives had much lower audio standard deviations of 0.00136–0.00177 and mouth-motion standard deviations of 0.00519–0.01131. That amplitude difference may reflect source distance or recording level; it is not evidence of audiovisual ownership.

At the most permissive frozen dynamic-range thresholds and the widest frozen lag window, all six matching-positive trials still abstained. Their best correlations were only 0.069–0.152, below the minimum candidate threshold of 0.35. All six hard negatives abstained at the audio dynamic-range gate. Consequently, every one of the 240 frozen settings produced 0/6 positive candidates and 0/6 hard-negative candidates.

## Post-hoc diagnosis

A diagnostic sweep outside the frozen analysis expanded the lag window to ±1 s and tried simple temporal smoothing. It did not rescue the instrument. With no smoothing, median best correlation was 0.174 for matching positives and 0.203 for hard negatives. Smoothing increased some correlations but made the negative median at least as large as the positive median. These figures are post-hoc diagnostics, not candidate selection results.

The most plausible interpretation is that frame-to-frame pixel change in a fixed rectangular mouth region is not a credible lip-speech synchrony measurement. It responds to illumination, head motion, compression noise, and any facial motion in the box. More fundamentally, instantaneous acoustic RMS need not vary linearly with whole-region pixel difference even during genuine speech.

## Required next step

Do not relax the correlation threshold, select a favourable subset, or begin the 54-trial confirmation study. The separately versioned [`V2 face-landmark pilot`](AV_SYNCHRONY_PILOT_V2_GUIDE.md) now implements tracked, face-normalized lip aperture, uniform objective quality gates, a development-only threshold search, and untouched internal validation. It was frozen before collecting V2 data. Run that replacement pilot exactly as specified; only a successful V2 development and validation result can justify a later code/asset/threshold freeze.
