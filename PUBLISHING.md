# Publishing checklist

The repository is intentionally prepared locally before any public write. Publication is not the current critical-path objective. Review each item once; do not upload the original laboratory folder, and do not publish merely because a local commit passes software checks.

Before this checklist, read the five canonical records linked from the README. Publication remains blocked while `M14` is `BLOCKED` in `docs/MILESTONE_MATRIX.md`.

## Current development checkpoint

The 2026-10-09 update is a development backup and status correction, not a
submission, research-completion release, or new hardware authorization. It
must descend from sanitized public commit `2c6f50b` without restoring discarded
history. Review every outgoing commit, not only the final tree. Keep local
private records intact and ignored; this public repository is not their backup.

Include reviewed source, tests, protocols and appropriately labelled derived
evidence. Exclude raw recordings, screenshots, private setup/approval/close-out
records, correspondence, credentials and personal filesystem paths. Generic
vendor-account paths and the existing example private-LAN endpoint in code are
configuration defaults, not a published password or current connection authority.
Historical one-shot launchers are provenance, not commands for readers to rerun.
Do not rewrite their pinned sources or frozen experimental artifacts to make a
release check pass. Unresolved input/reporting defects must remain explicit.

The pre-upload audit found the last confirmed GitHub save at sanitized commit
`2c6f50b` on 2026-09-06 (17:38 BST), with 12 later local commits through
`1514beb` on 2026-10-01 (02:22 BST), plus the newer uncommitted work. A later
publication review was deferred; no later successful upload was verified.
This checkpoint preserves that backlog without rewriting the public ancestor.
The public source tests passed on Windows: 1,977 Python tests ran, with 13
platform-dependent skips; all 24 JavaScript unit tests passed. These counts are
software checks, not new trials. Fresh headless browser and Linux hardware
checks are not claimed. CI and the uploaded branch head must be checked after
the push; private material still requires a separate non-public backup.

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

## 4. Update the existing GitHub repository

Verify `origin` is the existing repository below, refresh its head, and inspect
the outgoing history and staged files again. Never force-push, overwrite remote
work or create a duplicate repository as part of a backup:

```bash
git remote get-url origin
git fetch origin main
git log --oneline origin/main..HEAD
git push origin main
```

Expected remote: `https://github.com/katepkh/reachy-mini-abstention-first-attention.git`.
After the push, independently verify that GitHub's branch head matches the
reviewed local commit. A local commit or a successful test is not an upload.

## 5. GitHub release polish

- Confirm GitHub Actions passes.
- Add repository topics such as `reachy-mini`, `human-robot-interaction`, `direction-of-arrival`, `selective-prediction`, `runtime-assurance`, and `robotics-safety`.
- Pin the repository only after the public README renders correctly.
- Do not create a research-completion or submission release until the charter's integrated, validated, publishable, and claim gates have been reviewed explicitly.
- Never rewrite a frozen result to improve the story; add a new version and retain the old evidence.
