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

```bash
python scripts/verify_results.py
python scripts/regenerate_public_results.py --check
python -m unittest discover -s tests -p "test_*.py"
git diff --cached --name-only
```

Expected results: 171 evidence files verified, the generated public result summary matching frozen evidence, 142 tests passing, and no media/audit/private-environment files in the staged list.

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

The planned public URL is already recorded in `DISCORD_MESSAGE.md`. Confirm that the repository was created under `katepkh` before pushing.

## 5. Present it in Discord

Post the text from `DISCORD_MESSAGE.md`, attach `figures/architecture.png`, and link directly to `docs/RESEARCH_NOTE.md` or `docs/FAILURE_LEDGER.md` if discussion permits more than one link.

Do not upload a zip of the private lab directory. Do not lead with every stage/version. Lead with the falsified assumption—geometry is not source ownership—the fresh passive results, and the preserved physical failure. End with three specific questions so experts have something concrete to challenge.

## 6. GitHub release polish

- Confirm GitHub Actions passes.
- Add repository topics such as `reachy-mini`, `human-robot-interaction`, `direction-of-arrival`, `selective-prediction`, `runtime-assurance`, and `robotics-safety`.
- Pin the repository only after the public README renders correctly.
- Optionally create a `v0.1.0-research-preview` release after external review.
- Never rewrite a frozen result to improve the story; add a new version and retain the old evidence.
