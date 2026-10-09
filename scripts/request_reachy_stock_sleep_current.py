"""One separately authorized stock sleep session; preserve every old journal.

Reuses the exact reviewed remote routine and original operator confirmation.
Default/help and --inspect are offline. --sleep-once is operator-run only.
No retries, microphone test, custom motion, daemon stop or automatic wake.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys


ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "scripts/request_reachy_stock_sleep.py"
ORIGINAL_SHA = "b5f8f6cd8939ee3652f9879ff18dbd4ce1ffc89c1befb1aaceed6ac71596ac0c"
REMOTE_SHA = "23fc379f757997863aae0d09bd785524667519f7bb2acf3c2421247802e1021d"
SESSION = "standard-sleep-20261008-01"
DIRECTORY = ROOT / "data/private/stock_sleep"
JOURNAL = DIRECTORY / (SESSION + ".jsonl")
AUTHORIZATION = DIRECTORY / (SESSION + "-authorization.json")


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def read_regular(path, limit=65536):
    path = Path(path)
    before = path.lstat()
    if (not stat.S_ISREG(before.st_mode) or path.is_symlink()
            or getattr(before, "st_file_attributes", 0) & 0x400 or before.st_size > limit):
        raise RuntimeError("unsafe_or_oversized_file")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as handle:
        opened = os.fstat(handle.fileno())
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise RuntimeError("file_identity_changed")
        data = handle.read(limit + 1)
        after = os.fstat(handle.fileno())
    if len(data) > limit or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError("file_changed_or_oversized")
    return data


def load_reviewed():
    payload = read_regular(ORIGINAL)
    if sha(payload) != ORIGINAL_SHA:
        raise RuntimeError("original_sleep_source_changed")
    namespace = {"__name__": "reviewed_stock_sleep", "__file__": str(ORIGINAL)}
    exec(compile(payload, str(ORIGINAL), "exec"), namespace)
    if sha(namespace["source_bytes"]()) != REMOTE_SHA:
        raise RuntimeError("remote_sleep_routine_changed")
    return namespace


def check_authorization():
    # Check each in-project parent, without creating or following a linked scope.
    for directory in (ROOT, ROOT / "data", ROOT / "data/private", DIRECTORY):
        info = directory.lstat()
        if (not stat.S_ISDIR(info.st_mode) or directory.is_symlink()
                or getattr(info, "st_file_attributes", 0) & 0x400):
            raise RuntimeError("unsafe_private_directory")
    expected = {"schema": "reachy-stock-sleep-session-authorization-v1", "session": SESSION,
                "original_sha256": ORIGINAL_SHA, "remote_sha256": REMOTE_SHA,
                "launcher_sha256": sha(read_regular(Path(__file__))),
                "journal_name": JOURNAL.name, "attempt_limit": 1,
                "approved": True, "live_confirmation_required": True,
                "automatic_retry": False, "microphone_authorized": False}
    approval = json.loads(read_regular(AUTHORIZATION, 8192))
    if (not isinstance(approval, dict) or any(approval.get(k) != v or type(approval.get(k)) is not type(v)
                                             for k, v in expected.items())):
        raise RuntimeError("missing_or_changed_session_authorization")
    if os.path.lexists(JOURNAL):
        raise RuntimeError("This session was already attempted. Do not retry. Send: " + str(JOURNAL))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--inspect", action="store_true")
    group.add_argument("--sleep-once", action="store_true")
    args = parser.parse_args(argv)
    if not args.inspect and not args.sleep_once:
        parser.print_help()
        return 0
    reviewed = load_reviewed()
    check_authorization()
    if args.inspect:
        print(json.dumps({"mode": "OFFLINE", "session": SESSION, "remote_sha256": REMOTE_SHA,
                          "attempt_available": True, "microphone_authorized": False}))
        return 0
    # Only the fixed local destination differs. The pinned routine and its
    # exclusive creation, fresh checks, terminal prompt and no-retry path stand.
    reviewed["JOURNAL"] = JOURNAL
    return reviewed["main"](["--sleep-once"])


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, KeyboardInterrupt) as error:
        print("STOP: " + (str(error) or type(error).__name__), file=sys.stderr)
        raise SystemExit(2)
