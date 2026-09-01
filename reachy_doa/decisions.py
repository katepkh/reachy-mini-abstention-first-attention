"""Accepted/superseded trial accounting stored separately from raw files."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .config import DATA_DIR


DECISIONS_PATH = (DATA_DIR / "trial_decisions.json").resolve()


def load_decisions(path: Path = DECISIONS_PATH) -> dict[str, object]:
    resolved = path.resolve()
    if resolved != DECISIONS_PATH and DATA_DIR not in resolved.parents:
        raise ValueError("Trial decisions must remain inside the project data folder.")
    if not resolved.exists():
        return {"version": 1, "plans": {}}
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"version": 1, "plans": {}}
    if not isinstance(payload, dict) or not isinstance(payload.get("plans"), dict):
        return {"version": 1, "plans": {}}
    return payload


def _save(payload: dict[str, object], path: Path = DECISIONS_PATH) -> Path:
    resolved = path.resolve()
    if resolved != DECISIONS_PATH and DATA_DIR not in resolved.parents:
        raise ValueError("Trial decisions must remain inside the project data folder.")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return resolved


def record_accept(plan_id: str, step_index: int, csv_name: str) -> Path:
    payload = load_decisions()
    plans = payload.setdefault("plans", {})
    plan = plans.setdefault(plan_id, {})
    key = str(int(step_index))
    prior = plan.get(key, {}) if isinstance(plan.get(key), dict) else {}
    superseded = list(prior.get("superseded_files", []))
    old_accepted = prior.get("accepted_file")
    if old_accepted and old_accepted != csv_name and old_accepted not in superseded:
        superseded.append(old_accepted)
    plan[key] = {
        "accepted_file": csv_name,
        "superseded_files": sorted(set(superseded)),
        "decided_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    return _save(payload)


def record_superseded(plan_id: str, step_index: int, csv_name: str) -> Path:
    payload = load_decisions()
    plans = payload.setdefault("plans", {})
    plan = plans.setdefault(plan_id, {})
    key = str(int(step_index))
    prior = plan.get(key, {}) if isinstance(plan.get(key), dict) else {}
    superseded = list(prior.get("superseded_files", []))
    if csv_name not in superseded:
        superseded.append(csv_name)
    plan[key] = {
        "accepted_file": prior.get("accepted_file"),
        "superseded_files": sorted(set(superseded)),
        "decided_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    return _save(payload)


def reopen_accepted_step(plan_id: str, step_index: int) -> Path:
    """Preserve an accepted file as superseded and reopen its guided step."""
    payload = load_decisions()
    plans = payload.setdefault("plans", {})
    plan = plans.setdefault(plan_id, {})
    key = str(int(step_index))
    prior = plan.get(key, {}) if isinstance(plan.get(key), dict) else {}
    superseded = list(prior.get("superseded_files", []))
    old_accepted = prior.get("accepted_file")
    if old_accepted and old_accepted not in superseded:
        superseded.append(old_accepted)
    plan[key] = {
        "accepted_file": None,
        "superseded_files": sorted(set(superseded)),
        "decided_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    return _save(payload)


def disposition_for(csv_name: str) -> str:
    payload = load_decisions()
    for plan in payload.get("plans", {}).values():
        if not isinstance(plan, dict):
            continue
        for decision in plan.values():
            if not isinstance(decision, dict):
                continue
            if decision.get("accepted_file") == csv_name:
                return "accepted"
            if csv_name in decision.get("superseded_files", []):
                return "superseded"
    return "standalone"


def completed_prefix(plan_id: str) -> int:
    payload = load_decisions()
    plan = payload.get("plans", {}).get(plan_id, {})
    if not isinstance(plan, dict):
        return 0
    completed = 0
    while True:
        decision = plan.get(str(completed + 1), {})
        if not isinstance(decision, dict) or not decision.get("accepted_file"):
            return completed
        completed += 1


def bootstrap_guided_plan(plan_id: str, data_dir: Path = DATA_DIR) -> Path:
    """Infer a one-time ledger from legacy guided metadata; newest file wins."""
    grouped: dict[int, list[tuple[str, str]]] = {}
    for metadata_path in sorted(data_dir.glob("*_metadata.json")):
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        guided = metadata.get("guided_trial", {})
        if guided.get("plan_id") != plan_id or guided.get("step_index") is None:
            continue
        csv_name = str(metadata.get("csv_file", ""))
        if not csv_name or not (data_dir / csv_name).exists():
            continue
        grouped.setdefault(int(guided["step_index"]), []).append(
            (str(metadata.get("saved_at", "")), csv_name)
        )
    for step_index, candidates in sorted(grouped.items()):
        ordered = sorted(candidates)
        record_accept(plan_id, step_index, ordered[-1][1])
        for _, csv_name in ordered[:-1]:
            record_superseded(plan_id, step_index, csv_name)
    return DECISIONS_PATH
