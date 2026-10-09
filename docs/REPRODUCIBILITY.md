# Reproducibility record

## One-command verification

Create a Python 3.12 environment, install `requirements-test.lock`, install this repository without dependency resolution, and install the hash-pinned public model/runtime assets as shown below. Then run with that environment's interpreter:

```bash
.venv/Scripts/python scripts/verify_paper_artifacts.py --check
```

The command verifies:

- 171 manifest-listed evidence files and frozen headline assertions;
- the generated public result summary;
- Stage 3V robustness, frozen AV-synchrony designs, and synthetic/offline rehearsals;
- all four manuscript tables and both manuscript figures against seven hashed inputs;
- the complete successor review manifest; and
- the curated software test suite.

The exact offline build environment and its known historical device gaps are frozen in [`reproducibility_environment_v1.json`](../evidence/manifests/reproducibility_environment_v1.json).

It is offline and opens no robot, camera, microphone, or external network connection. The deterministic successful-run record is [`paper_artifact_verification_v1.txt`](../evidence/analysis/paper_artifact_verification_v1.txt).

## Installation

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-test.lock
.venv/Scripts/python -m pip install --no-deps -e .
.venv/Scripts/python scripts/fetch_av_synchrony_v2_assets.py --install
.venv/Scripts/python scripts/verify_paper_artifacts.py --check
```

On POSIX systems, use `.venv/bin/python` instead. `requirements-test.lock` records the exact tested Python 3.12 resolution; `pyproject.toml` declares broader supported dependency ranges.

Asset installation downloads the public MediaPipe package and face-landmarker
model, checks the pinned archive/model/member hashes, and writes only the ignored
`models/avsync_v2/` runtime/model paths. It does not access sensors or private run
records. The joint-pilot execution-manifest check needs these exact bytes even
though it performs no model inference. CI performs this setup before offline
verification; do not publish the model downloads or replace a hash to accept a
different release. Use `--check` instead of `--install` to verify existing assets
without a download.

## Generated-paper contract

Run `python scripts/build_paper_artifacts.py --write` only when deliberately refreshing outputs after an accepted evidence change. CI uses `--check`. The generator reads frozen JSON, verifies the public evidence first, and writes:

- four Markdown tables under `docs/paper/generated/`;
- `figures/architecture.svg`;
- `figures/safety-coverage-frontier.svg`; and
- a source/output SHA-256 manifest.

The same tables are embedded in [`MANUSCRIPT.md`](MANUSCRIPT.md). The verifier fails if the embedded copies diverge from generated content.

## Boundaries

Offline verification cannot reproduce live acquisition, robot transport, deleted encrypted audit clips, unit-specific torque state, room acoustics, or the private V2 numeric files. A hash establishes byte identity, not experimental correctness. The hardware/software inventory explicitly lists missing historical device fields.
