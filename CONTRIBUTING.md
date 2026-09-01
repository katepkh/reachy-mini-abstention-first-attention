# Contributing

Contributions are welcome when they preserve the project's evidence boundaries.

- Open an issue describing the failure mode, experimental condition, and expected safety behavior before a large change.
- Keep policy versions immutable after they have seen held-out outcomes. Create a new version instead of editing a frozen one.
- Preserve failed trials and superseded attempts; never relabel them as passing.
- Add hard negatives before optimizing positive coverage.
- Do not commit raw audio, video, face images, transcripts, identity labels, secrets, robot credentials, or local audit sidecars.
- Run `python scripts/verify_results.py` and the unit tests before proposing a change.
- Separate passive/shadow evidence from any hardware command path and document every command-capable dependency.

By contributing, you agree that your contribution is licensed under Apache-2.0.

