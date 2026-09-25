# Data card

## Contents

The public evidence bundle contains derived numeric CSV/JSON rows, trial metadata, protocol-compliance records, aggregate analyses, and SHA-256 freeze manifests for:

- the 15 accepted Stage 2A matrix trials;
- all public raw files listed for the Stage 3V V3 horizontal off-axis passive holdout;
- all public raw files listed for the Stage 3P targeted vertical visual-cue experiment;
- the Stage 4A V3 preflight, command-result, and post-failure diagnostic records.
- a privacy-minimized V2 pilot aggregate and candidate fingerprint, but not its private numeric attempts;
- a deterministic M5 fused-shadow synthetic contract artifact containing no live observation;
- the frozen 54-trial AV-synchrony confirmation design, which contains no confirmation outcomes; and
- generated-paper source/output hashes.

## Deliberately excluded

- raw camera frames or images of participants;
- raw audio or transcripts;
- face embeddings or identity labels;
- encrypted temporary audit clips and their key material;
- V2 pilot numeric audio-level and face-landmark CSVs, which remain hash-audited under the Git-ignored private data tree;
- private logs, local paths, virtual environments, credentials, and unrelated laboratory captures;
- participant demographics, because this was not a participant study.

## Intended use

- audit the stated frozen results;
- reproduce policy summaries and file hashes;
- inspect failure modes and experimental design;
- develop hypotheses for a genuinely independent study.

## Unsuitable use

- training identity, face-recognition, voice-recognition, or biometric models;
- estimating population-level performance;
- claiming safe autonomous control;
- treating row-level observations as independent participants;
- reconstructing speech or personal identity.

## Residual privacy and bias risk

Data minimization is not anonymization. Filenames and metadata include dates, controlled condition labels, headings, timing, and robot state. The collection represents one site and primary operator and therefore embeds narrow environmental and behavioral assumptions.

The current laptop AV instruments consume camera frames and microphone samples
transiently inside the local browser/runtime to derive numeric audio level,
face geometry, and lip aperture. The recorder saves and uploads no pixels or
waveforms. The M5 fusion contract itself receives only timestamps, an ephemeral
face-track label, heading, status/reason codes, correlation, and lag. A future
robot-integrated instrument must separately inventory transient processing on
Reachy, derived fields sent to the laptop, retention, and deletion; the present
record does not establish that future boundary.

The public V2 result exposes only aggregate trial outcomes and content hashes. Its 23 raw numeric attempt files are not public by default even though they contain no saved pixels, waveform, transcript, embedding, or name.

## Integrity

Source manifests retain the original relative paths and SHA-256 hashes. Public files are reorganized under `evidence/`; `scripts/verify_results.py` maps the original manifest paths to the public layout and checks every included raw artifact.
