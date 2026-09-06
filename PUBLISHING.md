# Publishing checklist

The repository is intentionally prepared locally before any public write. Review each item once; do not upload the original laboratory folder.

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

Expected results: 171 evidence files verified, the generated public result summary and exploratory robustness artifacts current, the frozen candidate-bound confirmation design current, nine synthetic fault cases, V1/V2 pilot manifests, and both end-to-end pilot dry runs current, four fresh mock-process failure rehearsals matching the frozen report, all manuscript artifacts current, the successor review manifest matching, 265 tests passing, and no media/audit/private-environment files in the staged list.

## 3. Commit locally

```bash
git commit -m "Release abstention-first Reachy Mini research preview"
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
- Optionally create a `v0.1.0-research-preview` release after external review.
- Never rewrite a frozen result to improve the story; add a new version and retain the old evidence.
