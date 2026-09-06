"""Local accepted-step checkpoint for Stage 3V."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone

from .config import DATA_DIR, MANIFEST_PATH, PROGRESS_PATH, STUDY_PROFILE


REPLACEMENT_PLAN_PATH = (DATA_DIR / "replacement_plan.json").resolve()


def _write_json_atomic(path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    # Windows file watchers and antivirus scanners can briefly hold a newly
    # written JSON file open, causing an otherwise valid atomic replace to
    # raise WinError 5.  Retrying the same bounded replace preserves atomicity
    # and prevents a transient reader from losing accepted-trial progress.
    for attempt in range(10):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(0.05)


def load_progress_state(max_steps: int) -> dict[str, object]:
    try:
        payload = json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
        accepted = int(payload.get("accepted_steps", 0))
    except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"accepted_steps": 0, "accepted_csv_files": []}
    if not 0 <= accepted <= max_steps:
        return {"accepted_steps": 0, "accepted_csv_files": []}
    files = payload.get("accepted_csv_files", [])
    if not isinstance(files, list) or not all(isinstance(item, str) for item in files):
        files = []
    return {"accepted_steps": accepted, "accepted_csv_files": files[:accepted]}


def load_progress(max_steps: int) -> int:
    return int(load_progress_state(max_steps)["accepted_steps"])


def save_progress(
    accepted_steps: int,
    max_steps: int,
    accepted_csv_files: list[str] | None = None,
) -> None:
    if not 0 <= accepted_steps <= max_steps:
        raise ValueError("Stage 3V progress is outside the protocol bounds.")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": (
            "reachy-stage3p-cue-confirmation-progress-v1"
            if STUDY_PROFILE == "stage3p_cue_confirmation"
            else "reachy-stage3p-confirmation-progress-v6"
            if STUDY_PROFILE == "stage3p_confirmation_v6"
            else "reachy-stage3p-confirmation-progress-v5"
            if STUDY_PROFILE == "stage3p_confirmation_v5"
            else "reachy-stage3p-confirmation-progress-v3"
            if STUDY_PROFILE == "stage3p_confirmation_v3"
            else "reachy-stage3p-calibration-progress-v1"
            if STUDY_PROFILE == "stage3p_calibration"
            else "reachy-stage3p-confirmation-progress-v2"
            if STUDY_PROFILE == "stage3p_confirmation_v2"
            else "reachy-stage3p-confirmation-progress-v1"
            if STUDY_PROFILE == "stage3p_confirmation"
            else "reachy-stage3p-vad-diagnostic-progress-v1"
            if STUDY_PROFILE == "stage3p_vad_diagnostic"
            else "reachy-stage3p-development-progress-v1"
            if STUDY_PROFILE == "stage3p_development"
            else "reachy-stage3v-progress-v1"
        ),
        "accepted_steps": accepted_steps,
        "total_steps": max_steps,
        "accepted_csv_files": list(accepted_csv_files or [])[:accepted_steps],
        "updated_time_iso": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "contains_pixels": False,
        "contains_audio": False,
        "contains_transcript": False,
    }
    if STUDY_PROFILE in {
        "stage3p_development", "stage3p_calibration", "stage3p_vad_diagnostic",
        "stage3p_confirmation", "stage3p_confirmation_v2", "stage3p_confirmation_v3",
        "stage3p_confirmation_v5",
        "stage3p_confirmation_v6",
        "stage3p_cue_confirmation",
    }:
        try:
            manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            fingerprint = str(manifest["fingerprint"])
        except (FileNotFoundError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("The frozen Stage 3P manifest or fingerprint is unavailable.") from exc
        payload.update(
            {
                "status": (
                    "COLLECTION_COMPLETE"
                    if accepted_steps == max_steps
                    else "COLLECTION_IN_PROGRESS"
                    if accepted_steps
                    else "FROZEN_PROTOCOL_COLLECTION_NOT_STARTED"
                ),
                "protocol_fingerprint": fingerprint,
            }
        )
    _write_json_atomic(PROGRESS_PATH, payload)


def load_pending_replacement(max_steps: int) -> dict[str, object] | None:
    """Return one validated pending replacement plan, if present."""
    try:
        payload = json.loads(REPLACEMENT_PLAN_PATH.read_text(encoding="utf-8"))
        step_index = int(payload.get("step_index", 0))
        resume_accepted_steps = int(payload.get("resume_accepted_steps", max_steps))
        prefix = payload.get("prefix_files", [])
        suffix = payload.get("suffix_files", [])
    except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    if (
        payload.get("status") != "PENDING"
        or not 1 <= step_index <= max_steps
        or not step_index <= resume_accepted_steps <= max_steps
    ):
        return None
    if not isinstance(prefix, list) or not all(isinstance(item, str) for item in prefix):
        return None
    if not isinstance(suffix, list) or not all(isinstance(item, str) for item in suffix):
        return None
    if len(prefix) != step_index - 1 or len(suffix) != resume_accepted_steps - step_index:
        return None
    return {**payload, "resume_accepted_steps": resume_accepted_steps}


def stage_step_replacement(step_index: int, max_steps: int, reason: str) -> dict[str, object]:
    """Reopen exactly one completed step while retaining every other file."""
    current = load_progress_state(max_steps)
    files = list(current["accepted_csv_files"])
    accepted_steps = int(current["accepted_steps"])
    if len(files) != accepted_steps:
        raise ValueError("Accepted Stage 3V progress is internally inconsistent.")
    index = int(step_index)
    if not 1 <= index <= accepted_steps:
        raise ValueError("Only an already-accepted Stage 3V step can be replaced.")
    if load_pending_replacement(max_steps) is not None:
        raise ValueError("A Stage 3V replacement is already pending.")

    stamp = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d-%H%M%S")
    backup_path = (DATA_DIR / f"progress_before_step{index:02d}_replacement_{stamp}.json").resolve()
    backup_path.write_text(PROGRESS_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    payload: dict[str, object] = {
        "schema": "reachy-stage3v-step-replacement-v1",
        "status": "PENDING",
        "step_index": index,
        "reason": str(reason),
        "original_file": files[index - 1],
        "resume_accepted_steps": accepted_steps,
        "prefix_files": files[: index - 1],
        "suffix_files": files[index:],
        "progress_backup_file": backup_path.name,
        "created_time_iso": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "contains_pixels": False,
        "contains_audio": False,
        "contains_transcript": False,
    }
    _write_json_atomic(REPLACEMENT_PLAN_PATH, payload)
    save_progress(index - 1, max_steps, files[: index - 1])
    return payload


def synchronise_pending_replacement(max_steps: int) -> dict[str, object] | None:
    """Rebase a pending replacement if a stale session accepted later steps.

    Streamlit sessions keep independent in-memory state. A tab that has not yet
    observed the replacement checkpoint may briefly continue from its old index.
    This function preserves those later accepted files, extends the replacement
    suffix, and restores the on-disk checkpoint to immediately before the target.
    """
    plan = load_pending_replacement(max_steps)
    if plan is None:
        return None
    step_index = int(plan["step_index"])
    current = load_progress_state(max_steps)
    accepted_steps = int(current["accepted_steps"])
    files = list(current["accepted_csv_files"])
    prefix = list(plan["prefix_files"])
    if accepted_steps == step_index - 1 and files == prefix:
        return plan
    if accepted_steps < step_index or len(files) != accepted_steps:
        raise ValueError("Pending replacement checkpoint is inconsistent.")
    if files[: step_index - 1] != prefix:
        raise ValueError("Accepted prefix changed while a replacement was pending.")
    if files[step_index - 1] != str(plan["original_file"]):
        raise ValueError("The pending replacement target changed unexpectedly.")
    previous_suffix = list(plan["suffix_files"])
    current_suffix = files[step_index:]
    if current_suffix[: len(previous_suffix)] != previous_suffix:
        raise ValueError("Previously retained steps changed while replacement was pending.")
    updated: dict[str, object] = {
        **plan,
        "resume_accepted_steps": accepted_steps,
        "suffix_files": current_suffix,
        "rebased_time_iso": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }
    _write_json_atomic(REPLACEMENT_PLAN_PATH, updated)
    save_progress(step_index - 1, max_steps, prefix)
    return updated


def complete_step_replacement(
    step_index: int,
    replacement_file: str,
    accepted_prefix: list[str],
    max_steps: int,
) -> list[str]:
    """Substitute one accepted file and restore the retained suffix atomically."""
    plan = load_pending_replacement(max_steps)
    if plan is None or int(plan["step_index"]) != int(step_index):
        raise ValueError("No matching Stage 3V replacement is pending.")
    prefix = list(plan["prefix_files"])
    suffix = list(plan["suffix_files"])
    if list(accepted_prefix) != prefix:
        raise ValueError("Accepted prefix changed during the replacement.")
    replacement = str(replacement_file)
    if not replacement or not (DATA_DIR / replacement).is_file():
        raise ValueError("The replacement CSV is missing.")
    combined = [*prefix, replacement, *suffix]
    resume_accepted_steps = int(plan["resume_accepted_steps"])
    if len(combined) != resume_accepted_steps or len(set(combined)) != resume_accepted_steps:
        raise ValueError("Replacement would produce an incomplete or duplicate protocol.")
    for filename in combined:
        path = (DATA_DIR / filename).resolve()
        if path.parent != DATA_DIR or not path.is_file():
            raise ValueError(f"Retained Stage 3V file is missing: {filename}")

    save_progress(resume_accepted_steps, max_steps, combined)
    completed = {
        **plan,
        "status": "COMPLETED",
        "replacement_file": replacement,
        "completed_time_iso": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }
    _write_json_atomic(REPLACEMENT_PLAN_PATH, completed)
    return combined
