"""Freeze and verify the evidence used by the offline shadow simulator."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from .config import DATA_DIR
from .decisions import load_decisions


MANIFEST_DIR = (DATA_DIR / "manifests").resolve()
FROZEN_MANIFEST = (MANIFEST_DIR / "frozen_split_v1.json").resolve()


def _inside_data(path: Path) -> Path:
    resolved = path.resolve()
    if resolved != DATA_DIR and DATA_DIR not in resolved.parents:
        raise ValueError("Evidence files must remain inside the project data folder.")
    return resolved


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _metadata(csv_path: Path) -> tuple[Path | None, dict[str, object]]:
    path = csv_path.with_name(f"{csv_path.stem}_metadata.json")
    if not path.exists():
        return None, {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return path, {}
    return path, payload if isinstance(payload, dict) else {}


def _guided_split(plan_id: str, repetition: int, label: str) -> tuple[str, str]:
    if plan_id == "direction-calibration":
        if repetition <= 3:
            return "development", "Calibration repetitions 1–3 tune the reliability envelope."
        return "evaluation", "Calibration repetitions 4–5 are held out."
    if plan_id == "two-speaker-conflict" and label == "overlap":
        if repetition == 2:
            return "development", "First procedurally correct overlap repetition."
        return "evaluation", "Second procedurally correct overlap repetition is held out."
    if repetition <= 2:
        return "development", "First two accepted repetitions are development evidence."
    return "evaluation", "Third accepted repetition is held out."


def _standalone_split(csv_name: str) -> tuple[str, str]:
    if "silence_take01" in csv_name:
        return "exploratory", "Initial long silence run predates the controlled protocol."
    if "silence_take02" in csv_name:
        return "development", "Silence development run; housemate speech was possible."
    if "silence_take03" in csv_name:
        return "development", "Silence development run; faint street noise was reported."
    if "silence_take04" in csv_name:
        return "evaluation", "Very-quiet silence run held out; faint motor hum was audible."
    return "exploratory", "Standalone trial is preserved but not assigned to formal evaluation."


def _fingerprint(entries: list[dict[str, object]]) -> str:
    canonical = json.dumps(entries, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_manifest() -> dict[str, object]:
    """Describe every CSV exactly once without modifying any raw trial file."""
    decisions = load_decisions()
    assigned: dict[str, dict[str, object]] = {}
    for plan_id, plan in decisions.get("plans", {}).items():
        if not isinstance(plan, dict):
            continue
        for step_key, decision in plan.items():
            if not isinstance(decision, dict):
                continue
            accepted = decision.get("accepted_file")
            if accepted:
                csv_path = _inside_data(DATA_DIR / str(accepted))
                metadata_path, metadata = _metadata(csv_path)
                guided = metadata.get("guided_trial", {})
                guided = guided if isinstance(guided, dict) else {}
                repetition = int(guided.get("repetition", 0) or 0)
                label = str(guided.get("label", ""))
                exclusion = decision.get("analysis_exclusion_reason")
                if exclusion:
                    split, reason = "excluded", str(exclusion)
                else:
                    split, reason = _guided_split(str(plan_id), repetition, label)
                assigned[csv_path.name] = {
                    "file": csv_path.name,
                    "metadata_file": metadata_path.name if metadata_path else None,
                    "plan_id": str(plan_id),
                    "step_index": int(step_key),
                    "label": label,
                    "condition": str(metadata.get("condition", "")),
                    "repetition": repetition,
                    "disposition": "accepted",
                    "split": split,
                    "reason": reason,
                    "csv_sha256": _sha256(csv_path),
                    "metadata_sha256": _sha256(metadata_path) if metadata_path else None,
                }
            for superseded in decision.get("superseded_files", []):
                csv_path = _inside_data(DATA_DIR / str(superseded))
                metadata_path, metadata = _metadata(csv_path)
                guided = metadata.get("guided_trial", {})
                guided = guided if isinstance(guided, dict) else {}
                assigned[csv_path.name] = {
                    "file": csv_path.name,
                    "metadata_file": metadata_path.name if metadata_path else None,
                    "plan_id": str(plan_id),
                    "step_index": int(step_key),
                    "label": str(guided.get("label", "")),
                    "condition": str(metadata.get("condition", "")),
                    "repetition": int(guided.get("repetition", 0) or 0),
                    "disposition": "superseded",
                    "split": "excluded",
                    "reason": "Superseded by the accepted attempt for this guided step.",
                    "csv_sha256": _sha256(csv_path),
                    "metadata_sha256": _sha256(metadata_path) if metadata_path else None,
                }

    for csv_path in sorted(DATA_DIR.glob("*.csv")):
        if csv_path.name in assigned:
            continue
        metadata_path, metadata = _metadata(csv_path)
        split, reason = _standalone_split(csv_path.name)
        assigned[csv_path.name] = {
            "file": csv_path.name,
            "metadata_file": metadata_path.name if metadata_path else None,
            "plan_id": None,
            "step_index": None,
            "label": "silence" if "silence" in csv_path.name else "standalone",
            "condition": str(metadata.get("condition", "")),
            "repetition": None,
            "disposition": "standalone",
            "split": split,
            "reason": reason,
            "csv_sha256": _sha256(csv_path),
            "metadata_sha256": _sha256(metadata_path) if metadata_path else None,
        }

    entries = [assigned[name] for name in sorted(assigned)]
    counts: dict[str, int] = {}
    for entry in entries:
        split = str(entry["split"])
        counts[split] = counts.get(split, 0) + 1
    return {
        "version": 1,
        "name": "Reachy Mini DoA shadow-attention frozen split v1",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "policy": {
            "development": "Calibration repetitions 1–3; first two repetitions elsewhere.",
            "evaluation": "Calibration repetitions 4–5; third repetition elsewhere.",
            "guardrail": "Evaluation files must not be used to tune policy parameters.",
        },
        "counts": counts,
        "fingerprint": _fingerprint(entries),
        "entries": entries,
    }


def write_manifest(path: Path = FROZEN_MANIFEST, force: bool = False) -> Path:
    resolved = _inside_data(path)
    if resolved.exists() and not force:
        raise FileExistsError("Frozen manifest already exists; validate it instead of replacing it.")
    payload = build_manifest()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return resolved


def load_manifest(path: Path = FROZEN_MANIFEST) -> dict[str, object]:
    resolved = _inside_data(path)
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("entries"), list):
        raise ValueError("Frozen manifest is malformed.")
    return payload


def validate_manifest(path: Path = FROZEN_MANIFEST) -> list[str]:
    payload = load_manifest(path)
    entries = payload["entries"]
    problems: list[str] = []
    if payload.get("fingerprint") != _fingerprint(entries):
        problems.append("Manifest entry fingerprint does not match.")
    for entry in entries:
        csv_path = _inside_data(DATA_DIR / str(entry["file"]))
        if not csv_path.exists():
            problems.append(f"Missing CSV: {csv_path.name}")
        elif _sha256(csv_path) != entry.get("csv_sha256"):
            problems.append(f"CSV changed after freeze: {csv_path.name}")
        metadata_name = entry.get("metadata_file")
        if metadata_name:
            metadata_path = _inside_data(DATA_DIR / str(metadata_name))
            if not metadata_path.exists():
                problems.append(f"Missing metadata: {metadata_path.name}")
            elif _sha256(metadata_path) != entry.get("metadata_sha256"):
                problems.append(f"Metadata changed after freeze: {metadata_path.name}")
    return problems


def entries_for_split(split: str, path: Path = FROZEN_MANIFEST) -> list[dict[str, object]]:
    payload = load_manifest(path)
    return [entry for entry in payload["entries"] if entry.get("split") == split]
