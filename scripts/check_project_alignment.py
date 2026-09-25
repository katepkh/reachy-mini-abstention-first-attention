#!/usr/bin/env python3
"""Fail closed when canonical project alignment records or status warnings drift."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = (
    "docs/PROJECT_CHARTER.md",
    "docs/MILESTONE_MATRIX.md",
    "docs/DECISION_LOG.md",
    "docs/NOVELTY_CLAIMS_LEDGER.md",
    "docs/STRATEGY_GATE.md",
)
FORBIDDEN = (
    "The submission-ready, venue-neutral manuscript",
    "Read the venue-neutral submission draft",
    "Prioritize an audited repository release and submission-ready manuscript",
    "## Immediate: publishable research preview",
)


def check() -> list[str]:
    failures: list[str] = []
    for relative in CANONICAL:
        path = ROOT / relative
        if not path.is_file():
            failures.append(f"missing canonical record: {relative}")
            continue
        text = path.read_text(encoding="utf-8")
        if "Canonical status: **ACTIVE**" not in text:
            failures.append(f"canonical record is not marked ACTIVE: {relative}")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for relative in CANONICAL:
        if relative not in readme:
            failures.append(f"README does not link canonical record: {relative}")

    searchable = [ROOT / "README.md", ROOT / "PUBLISHING.md", ROOT / "docs/RESEARCH_NOTE.md"]
    for path in searchable:
        text = path.read_text(encoding="utf-8")
        for phrase in FORBIDDEN:
            if phrase in text:
                failures.append(f"premature framing remains in {path.relative_to(ROOT)}: {phrase}")

    pdf_dir = ROOT / "output" / "pdf"
    pdfs = sorted(pdf_dir.glob("*.pdf")) if pdf_dir.is_dir() else []
    for path in pdfs:
        failures.append(f"premature generated paper PDF remains: {path.relative_to(ROOT)}")

    manuscript = (ROOT / "docs/MANUSCRIPT.md").read_text(encoding="utf-8")
    warning = "Working evidence manuscript — not submission-ready"
    if warning not in manuscript:
        failures.append("MANUSCRIPT.md is missing the working-draft warning")
    return failures


def main() -> int:
    failures = check()
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print("PASS: canonical project records and anti-drift status warnings are present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
