# Public test suite

These are the self-contained unit tests for the curated implementation. They do not require a robot, camera, microphone, network, private launcher, or unpublished laboratory dataset.

The private development tree also contained UI/launcher safety tests and replay tests tied to the complete internal evidence layout. Those tests were not copied into this public suite because their fixtures and applications are intentionally excluded. The published frozen artifacts are instead checked by `scripts/verify_results.py`, including all 171 source-file hashes represented by the public manifests.

Run:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

