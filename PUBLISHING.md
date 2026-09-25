# Publishing checklist

The repository is intentionally prepared locally before any public write. Publication is not the current critical-path objective. Review each item once; do not upload the original laboratory folder, and do not publish merely because a local commit passes software checks.

Before this checklist, read the five canonical records linked from the README. Publication remains blocked while `M14` is `BLOCKED` in `docs/MILESTONE_MATRIX.md`.

## 1. Confirm public identity

- Confirmed public citation and copyright name: `Kate P.`
- Confirmed Git identity for the first commit:

```bash
git config user.name "Kate P."
git config user.email "katepakhomova.work@gmail.com"
```

## 2. Re-run release gates

Use the frozen Python 3.12 environment from [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md) for every Python command below.

```bash
python scripts/verify_results.py
python scripts/check_project_alignment.py
python scripts/regenerate_public_results.py --check
python scripts/run_stage3v_robustness.py --check
python scripts/freeze_av_synchrony_protocol.py --check
python scripts/run_av_synchrony_faults.py --check
python scripts/freeze_av_synchrony_pilot_protocol.py --check
python scripts/run_av_synchrony_pilot_dry_run.py --check
python scripts/freeze_av_synchrony_pilot_v2_protocol.py --check
python scripts/run_av_synchrony_pilot_v2_dry_run.py --check
python scripts/freeze_av_synchrony_confirmation_protocol.py --check
python scripts/build_paper_artifacts.py --check
python scripts/run_offline_fault_rehearsal.py --check
python scripts/build_successor_review_manifest.py --check
python -m unittest discover -s tests -p "test_*.py"
python scripts/verify_paper_artifacts.py --check
git diff --cached --name-only
```

Expected results: the canonical alignment check passes; evidence and generated artifacts remain internally consistent; the full curated test suite passes; and no media, correspondence, approval record, audit secret, private environment, or generated paper PDF appears in the staged list. Test counts may grow and must not be treated as robot-trial counts.

## 3. Commit locally

```bash
git commit -m "Update Reachy Mini research workspace"
```

## 4. Create an empty public GitHub repository

Suggested name: `reachy-mini-abstention-first-attention`.

Create it without an auto-generated README, licence, or `.gitignore`, because those files already exist locally. Then connect and push:

```bash
git remote add origin https://github.com/katepkh/reachy-mini-abstention-first-attention.git
git push -u origin main
```

Confirm that the repository was created under `katepkh` before pushing.

## 5. GitHub release polish

- Confirm GitHub Actions passes.
- Add repository topics such as `reachy-mini`, `human-robot-interaction`, `direction-of-arrival`, `selective-prediction`, `runtime-assurance`, and `robotics-safety`.
- Pin the repository only after the public README renders correctly.
- Do not create a research-completion or submission release until the charter's integrated, validated, publishable, and claim gates have been reviewed explicitly.
- Never rewrite a frozen result to improve the story; add a new version and retain the old evidence.
