"""One reviewed replacement after the fixed session's pre-login rejection.

Preserves the old launcher, helper and all four failure records byte-for-byte.
Default/help and --inspect are offline. --run-once retains the original live
gates and checks exact remote-path absence before any deployment. No reset,
automatic retry, new microphone pair, timing change or cleanup deletion.
"""
import argparse
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "scripts/run_reachy_mic_input.py"
BASE_SHA = "ebbd6d521e06f845899f36acd91e83dd51bf0c4163276f96218695aaf68d9bc2"
HELPER_SHA = "19e54ed1fae751b96565268688faa6048d11a8fac6e1336228efffd22c44d908"
SESSION = "missing-pair-v3-04"
ATTEMPT = "login-replacement-01"
LOCAL = ROOT / "data/private/mic_closeout" / SESSION
REVIEW_ROOT = ROOT / "data/private/mic_input_preparation" / SESSION
REVIEW = REVIEW_ROOT / "login-failure-review-v1.json"
REVIEW_SHA = "184dd7c780a7334a0c655825688a600d4c7f2c3a0ac45be3c4cb4d08ffc226c3"
AUTHORIZATION = REVIEW_ROOT / (ATTEMPT + "-authorization.json")
STARTED = LOCAL / (ATTEMPT + "-started.json")
ORIGINAL_FILES = {"authorization.json", "closeout.json", "deployment.json", "interrupted.json"}
DEPENDENCIES = {
    "scripts/run_reachy_mic_diagnostic.py": "d38f202b9375f8bf542f991bfebdc52e7f442b839f15939e9108488f46267d9c",
    "scripts/copy_reachy_mic_preflight.py": "0fef4e2647bf4b63a47ac6b80db6991baba9df072f7a8646a44ceb199ff60617",
    "tools/reachy_mic_health_input_run.py": HELPER_SHA,
}


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def read_regular(path, limit=100000):
    before = path.lstat()
    if (not stat.S_ISREG(before.st_mode) or path.is_symlink()
            or getattr(before, "st_file_attributes", 0) & 0x400 or before.st_size > limit):
        raise RuntimeError("unsafe_or_oversized_file")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as source:
        opened = os.fstat(source.fileno())
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise RuntimeError("file_identity_changed")
        payload = source.read(limit + 1)
        after = os.fstat(source.fileno())
    if len(payload) > limit or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError("file_changed_or_oversized")
    return payload


def load_reviewed():
    payload = read_regular(BASE)
    if sha(payload) != BASE_SHA:
        raise RuntimeError("original_launcher_changed")
    for relative, expected in DEPENDENCIES.items():
        if sha(read_regular(ROOT / relative)) != expected:
            raise RuntimeError("reviewed_dependency_changed")
    ns = {"__name__": "reviewed_input_session", "__file__": str(BASE)}
    exec(compile(payload, str(BASE), "exec"), ns)
    return ns


def required_authorization(ns):
    return {"schema": "reachy-mic-login-replacement-authorization-v1", "session": SESSION,
            "attempt": ATTEMPT, "approved": True, "run_limit": 1, "automatic_retry": False,
            "wrapper_sha256": sha(read_regular(Path(__file__))), "original_launcher_sha256": BASE_SHA,
            "helper_sha256": HELPER_SHA, "review_sha256": REVIEW_SHA,
            "local_scope": str(LOCAL.resolve()), "remote_scope": ns["REMOTE_SCOPE"],
            "microphone_indices": [2, 3], "pair_limit": 1,
            "same_inventory_scopes_approved": True, "os_residuals_accepted": True,
            "restoration_risk_accepted": True, "live_setup_confirmation_required": True,
            "remote_absence_required_before_deployment": True}


def review_and_authorization(ns):
    for path in (ROOT, ROOT / "data", ROOT / "data/private", LOCAL.parent, LOCAL,
                 REVIEW_ROOT.parent, REVIEW_ROOT):
        ns["private_local_directory"](path)
    payload = read_regular(REVIEW)
    if sha(payload) != REVIEW_SHA:
        raise RuntimeError("login_failure_review_changed")
    review = json.loads(payload)
    if (review.get("status") != "PRELOGIN_FAILURE_REVIEWED_REMOTE_CHECK_REQUIRED"
            or review.get("session") != SESSION or review.get("local_scope") != str(LOCAL)
            or review.get("remote_scope") != ns["REMOTE_SCOPE"]
            or set(review.get("file_sha256", {})) != ORIGINAL_FILES):
        raise RuntimeError("wrong_failure_review")
    for name, expected in review["file_sha256"].items():
        if sha(read_regular(LOCAL / name)) != expected:
            raise RuntimeError("original_failure_record_changed")
    ns["authorization"](LOCAL)  # Also verifies all nine earlier close-outs and source-bound preparation.
    approved = json.loads(read_regular(AUTHORIZATION, 16384))
    if json.dumps(approved, sort_keys=True) != json.dumps(required_authorization(ns), sort_keys=True):
        raise RuntimeError("matching_replacement_approval_required")
    return review


def require_absent_paths(paths):
    """Exact-path metadata only. Permission errors and links never count as absent."""
    for path in paths:
        try:
            os.lstat(path)
        except FileNotFoundError:
            continue
        raise RuntimeError("unexpected_remote_session_path_no_replacement")


def absence_receipt(ns):
    return {"attempt": ATTEMPT, "status": "ABSENT_BEFORE_DEPLOY",
            "paths": [ns[k] for k in ("REMOTE_SCOPE", "REMOTE", "REMOTE_AUTH")],
            "forensic_erasure_claim": False}


def configure_replacement(ns, review):
    original_source, original_write = ns["remote_source"], ns["write_new"]
    original_preflight = ns["validate_preflight"]

    def source(mode):
        result = original_source(mode)
        if mode != "deploy":
            return result
        marker = '    print(json.dumps(report, allow_nan=False), flush=True)'
        if result.count(marker) != 1:
            raise RuntimeError("unexpected_reviewed_deployment_source")
        result = result.replace(marker, '    report["login_replacement_precheck"] = ' + repr(absence_receipt(ns)) + '\n' + marker)
        ending = "\nremote_deploy()\n"
        if not result.endswith(ending):
            raise RuntimeError("unexpected_reviewed_deployment_entry")
        return (result[:-len(ending)] + "\n" + inspect.getsource(require_absent_paths)
                + "\nrequire_absent_paths((REMOTE_SCOPE, REMOTE, REMOTE_AUTH))\nremote_deploy()\n")

    def validate_preflight(payload):
        result = original_preflight(payload)
        if json.dumps(result.get("login_replacement_precheck"), sort_keys=True) != json.dumps(absence_receipt(ns), sort_keys=True):
            raise RuntimeError("remote_absence_not_verified")
        return result

    def begin(directory):
        if Path(directory) != LOCAL:
            raise RuntimeError("wrong_replacement_scope")
        current = review_and_authorization(ns)
        rows = ns["local_inventory"](LOCAL)
        if rows != current["local_after_inventory"] or os.path.lexists(STARTED):
            raise RuntimeError("replacement_spent_or_local_inventory_changed")
        original_write(STARTED, {"schema": "reachy-mic-replacement-start-v1", "session": SESSION,
            "attempt": ATTEMPT, "status": "PENDING", "utc": ns["utc_now"](),
            "helper_sha256": HELPER_SHA, "review_sha256": REVIEW_SHA,
            "local_scope": str(LOCAL), "remote_scope": ns["REMOTE_SCOPE"],
            "local_before": rows, "automatic_retry": False, "forensic_erasure_claim": False})
        return ns["authorization"](LOCAL)

    def write(path, value):
        path = Path(path)
        if path.parent != LOCAL:
            raise RuntimeError("wrong_replacement_output_scope")
        if path.name in {"deployment.json", "interrupted.json", "execution-exit.json"}:
            path = path.with_name(ATTEMPT + "-" + path.name)
        elif not re.fullmatch(r"review-[0-9]{8}T[0-9]{6}-[a-f0-9]{8}\.json", path.name):
            raise RuntimeError("unexpected_replacement_output_name")
        original_write(path, value)  # Exclusive write; never replace an old result.

    ns.update(remote_source=source, validate_preflight=validate_preflight, begin_local=begin, write_new=write)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--inspect", action="store_true")
    modes.add_argument("--run-once", action="store_true")
    modes.add_argument("--collect-only", action="store_true")
    args = parser.parse_args(argv)
    if not any((args.inspect, args.run_once, args.collect_only)):
        parser.print_help()
        return 0
    ns = load_reviewed()
    review = review_and_authorization(ns)
    configure_replacement(ns, review)
    if args.inspect:
        available = ns["local_inventory"](LOCAL) == review["local_after_inventory"] and not os.path.lexists(STARTED)
        print(json.dumps({"mode": "OFFLINE", "session": SESSION, "attempt": ATTEMPT,
                          "attempt_available": available, "remote_absence_check_pending": True,
                          "recording_started": False}))
        return 0
    if args.collect_only:
        started = json.loads(read_regular(STARTED))
        if started.get("attempt") != ATTEMPT or started.get("helper_sha256") != HELPER_SHA:
            raise RuntimeError("matching_replacement_start_required")
        ns["collect"](LOCAL)
        return 0
    print("ONE reviewed login-failure replacement. Original records stay intact. No automatic retry.", flush=True)
    return ns["run_once"](LOCAL)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        print("STOP: " + (str(error) or type(error).__name__), file=sys.stderr)
        print("Pause the phone and preserve the records. Do not rerun or reboot.", file=sys.stderr)
        print("Private close-out scope: " + str(LOCAL), file=sys.stderr)
        raise SystemExit(2)
