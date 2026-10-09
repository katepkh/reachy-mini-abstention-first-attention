"""Automatic synthetic terminal check. No microphone, robot API or settings I/O.

Use only isolated pseudo-terminals created here, never the operator's terminal.
The caller supplies the verified candidate's exact TerminalInputReader class.
This checks Linux terminal compatibility, not real capture-load behavior.
"""

import os
import time


def terminal_selfcheck(reader_type):
    if os.name != "posix":
        raise RuntimeError("posix_terminal_required")
    import termios

    checks = []
    cases = (("one_enter", (b"\n",), ("enter",)),
             ("split_blank_line", (b" \t", b"\n"), ("enter",)),
             ("duplicate_enters_visible", (b"\n\n",), ("enter", "enter")),
             ("text_classified_not_saved", (b"synthetic\n",), ("text",)),
             ("canonical_eof", (b"\x04",), ("eof",)))
    for name, fragments, expected in cases:
        master, slave = os.openpty()
        stream = None
        reader = None
        try:
            stream = os.fdopen(slave, "rb", buffering=0)
            before = termios.tcgetattr(slave)
            if not before[3] & termios.ICANON:
                raise RuntimeError("synthetic_terminal_not_canonical")
            reader = reader_type(stream)
            start = time.monotonic()
            for fragment in fragments:
                if os.write(master, fragment) != len(fragment):
                    raise RuntimeError("synthetic_terminal_short_write")
            # Deliberately leave the main consumer idle; reader works independently.
            time.sleep(.05)
            observations = []
            deadline = start + 2
            while len(observations) < len(expected) and time.monotonic() < deadline:
                observations.extend(reader.drain())
                if len(observations) < len(expected):
                    time.sleep(.005)
            if tuple(e["kind"] for e in observations) != expected:
                raise RuntimeError("synthetic_terminal_event_mismatch")
            if any(not start <= e["observed_at"] <= reader.observed_through for e in observations):
                raise RuntimeError("synthetic_terminal_timestamp_mismatch")
            reader.close()
            if reader.thread.is_alive() or stream.closed or termios.tcgetattr(slave) != before:
                raise RuntimeError("synthetic_terminal_cleanup_or_modes_changed")
            checks.append({"name": name, "ok": True, "event_count": len(observations),
                           "elapsed_ms": round((time.monotonic() - start) * 1000, 3),
                           "reader_exited": True, "terminal_modes_unchanged": True})
        finally:
            try:
                if reader is not None:
                    reader.close()
            finally:
                try:
                    if stream is not None:
                        stream.close()
                    else:
                        os.close(slave)
                finally:
                    os.close(master)
    return {"schema": "reachy-input-pty-selfcheck-v1", "status": "PASS", "checks": checks,
            "input_source": "isolated_synthetic_pty", "physical_keyboard_tested": False,
            "capture_load_tested": False, "audio_opened": False, "settings_changed": False}
