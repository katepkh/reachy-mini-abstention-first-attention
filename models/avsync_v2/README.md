# Local V2 landmark assets

The replacement synchrony pilot serves its face-landmark runtime and model from localhost. The large generated assets are intentionally ignored by Git; install and hash-check them with:

```bash
python scripts/fetch_av_synchrony_v2_assets.py --install
```

The frozen V2 protocol records the exact URLs and SHA-256 values. The installer pins `@mediapipe/tasks-vision` 1.0.1, checks the npm tarball before extracting an allowlist of runtime files, checks every extracted file, and checks the official float16 Face Landmarker model. At capture time the page makes no remote request and saves no pixels, waveform, embedding, or transcript.

The model is a feature extractor, not an identity system. Its landmarks remain sensitive to lighting, pose, occlusion, camera quality, and model error.

