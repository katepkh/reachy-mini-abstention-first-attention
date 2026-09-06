"""Isolated, consented, encrypted local audit-clip capture.

The recorder is optional and never supplies evidence to the Stage 3V policy.
FFmpeg runs in a separate below-normal-priority process. Plaintext exists only
while that process is capturing and is encrypted immediately when it stops.
"""

from __future__ import annotations

import base64
import json
import os
import re
import secrets
import shutil
import struct
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from .config import AUDIT_DIR, PROJECT_ROOT


MAGIC = b"R3VAUD1\n"
INDEX_PATH = (AUDIT_DIR / "audit_index.json").resolve()
TEMP_DIR = (AUDIT_DIR / ".plaintext_capture").resolve()
MINIMUM_PASSPHRASE_LENGTH = 12
RETENTION_OPTIONS_HOURS = (1, 24, 168)


@dataclass(frozen=True, slots=True)
class AuditDeviceInventory:
    ffmpeg_path: str
    video_devices: tuple[str, ...]
    audio_devices: tuple[str, ...]
    error_code: str = ""


@dataclass(frozen=True, slots=True)
class AuditClip:
    clip_id: str
    trial_id: str
    encrypted_file: str
    started_time_iso: str
    completed_time_iso: str
    expires_time_iso: str
    duration_seconds: float
    video_device: str
    audio_device: str
    encryption: str
    status: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    # Windows file watchers and antivirus scanners may briefly hold the index
    # open between write and replace.  Keep the operation atomic and retry only
    # that transient sharing violation, matching the progress-checkpoint writer.
    for attempt in range(10):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(0.05)


def _load_index() -> dict[str, Any]:
    try:
        payload = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        if payload.get("schema") == "reachy-stage3v-audit-index-v1" and isinstance(
            payload.get("clips"), list
        ):
            return payload
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError):
        pass
    return {
        "schema": "reachy-stage3v-audit-index-v1",
        "local_encrypted_media_only": True,
        "cloud_transfer": False,
        "clips": [],
    }


def _save_clip_record(clip: AuditClip) -> None:
    payload = _load_index()
    clips = [row for row in payload["clips"] if row.get("clip_id") != clip.clip_id]
    clips.append({**clip.as_dict(), "review_verdict": "UNREVIEWED", "reviewed_time_iso": None})
    payload["clips"] = clips
    _atomic_json(INDEX_PATH, payload)


def find_ffmpeg() -> Path | None:
    configured = os.environ.get("REACHY_AUDIT_FFMPEG", "").strip()
    candidates = [Path(configured)] if configured else []
    command = shutil.which("ffmpeg")
    if command:
        candidates.append(Path(command))
    candidates.extend(
        sorted(
            (PROJECT_ROOT.parent / "work" / "video_deps" / "imageio_ffmpeg" / "binaries").glob(
                "ffmpeg*.exe"
            )
        )
    )
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            if resolved.is_file():
                return resolved
        except OSError:
            continue
    return None


def discover_windows_devices(ffmpeg_path: Path | None = None) -> AuditDeviceInventory:
    executable = (ffmpeg_path or find_ffmpeg())
    if executable is None:
        return AuditDeviceInventory("", (), (), "FFMPEG_UNAVAILABLE")
    try:
        completed = subprocess.run(
            [
                str(executable),
                "-hide_banner",
                "-list_devices",
                "true",
                "-f",
                "dshow",
                "-i",
                "dummy",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=12,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return AuditDeviceInventory(str(executable), (), (), "DEVICE_DISCOVERY_FAILED")
    videos: list[str] = []
    audios: list[str] = []
    # Some Windows camera drivers are reported by FFmpeg as ``(none)`` even
    # though their DirectShow category is video.
    pattern = re.compile(r'"(?P<name>.+)" \((?P<kind>video|audio|none)\)')
    for line in completed.stderr.splitlines():
        match = pattern.search(line)
        if not match:
            continue
        target = videos if match.group("kind") in {"video", "none"} else audios
        if match.group("name") not in target:
            target.append(match.group("name"))
    error = "" if videos and audios else "CAMERA_OR_MICROPHONE_UNAVAILABLE"
    return AuditDeviceInventory(str(executable), tuple(videos), tuple(audios), error)


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    if len(passphrase) < MINIMUM_PASSPHRASE_LENGTH:
        raise ValueError(f"Audit passphrase must contain at least {MINIMUM_PASSPHRASE_LENGTH} characters.")
    return Scrypt(salt=salt, length=32, n=2**14, r=8, p=1).derive(passphrase.encode("utf-8"))


def encrypt_media_file(
    plaintext_path: Path,
    encrypted_path: Path,
    *,
    passphrase: str,
    public_metadata: dict[str, Any],
) -> None:
    encrypt_media_bytes(
        plaintext_path.read_bytes(),
        encrypted_path,
        passphrase=passphrase,
        public_metadata=public_metadata,
    )


def encrypt_media_bytes(
    raw: bytes,
    encrypted_path: Path,
    *,
    passphrase: str,
    public_metadata: dict[str, Any],
) -> None:
    """Encrypt media already held in RAM without creating a plaintext file."""
    if not raw:
        raise ValueError("Audit media is empty.")
    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(12)
    header = {
        "schema": "reachy-stage3v-encrypted-audit-clip-v1",
        "cipher": "AES-256-GCM",
        "kdf": "scrypt-n16384-r8-p1",
        "salt_b64": base64.b64encode(salt).decode("ascii"),
        "nonce_b64": base64.b64encode(nonce).decode("ascii"),
        **public_metadata,
    }
    header_bytes = json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8")
    encrypted = AESGCM(_derive_key(passphrase, salt)).encrypt(nonce, raw, header_bytes)
    encrypted_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = encrypted_path.with_suffix(encrypted_path.suffix + ".tmp")
    temporary.write_bytes(MAGIC + struct.pack(">I", len(header_bytes)) + header_bytes + encrypted)
    temporary.replace(encrypted_path)


def store_external_audit_bytes(
    trial_id: str,
    media: bytes,
    *,
    passphrase: str,
    retention_hours: int,
    source_label: str = "external-device-upload",
) -> AuditClip:
    """Encrypt an externally recorded countdown+trial clip directly from RAM."""
    if int(retention_hours) not in RETENTION_OPTIONS_HOURS:
        raise ValueError("Unsupported audit retention period.")
    clip_id = uuid.uuid4().hex
    completed = datetime.now(timezone.utc).astimezone()
    expires = completed + timedelta(hours=int(retention_hours))
    encrypted_name = f"{trial_id}_{clip_id}.r3audit"
    encrypted_path = (AUDIT_DIR / encrypted_name).resolve()
    metadata = {
        "clip_id": clip_id,
        "trial_id": str(trial_id),
        "started_time_iso": None,
        "completed_time_iso": completed.isoformat(timespec="seconds"),
        "expires_time_iso": expires.isoformat(timespec="seconds"),
        "duration_seconds": None,
        "status": "EXTERNAL_UPLOADED",
        "source_label": source_label,
        "cloud_transfer": False,
    }
    encrypt_media_bytes(
        media,
        encrypted_path,
        passphrase=passphrase,
        public_metadata=metadata,
    )
    clip = AuditClip(
        clip_id=clip_id,
        trial_id=str(trial_id),
        encrypted_file=encrypted_name,
        started_time_iso="",
        completed_time_iso=metadata["completed_time_iso"],
        expires_time_iso=metadata["expires_time_iso"],
        duration_seconds=0.0,
        video_device=source_label,
        audio_device=source_label,
        encryption="AES-256-GCM+scrypt",
        status="EXTERNAL_UPLOADED",
    )
    _save_clip_record(clip)
    return clip


def decrypt_media_bytes(path: Path, *, passphrase: str) -> tuple[dict[str, Any], bytes]:
    payload = path.read_bytes()
    if not payload.startswith(MAGIC) or len(payload) < len(MAGIC) + 4:
        raise ValueError("Not a Stage 3V encrypted audit clip.")
    offset = len(MAGIC)
    header_length = struct.unpack(">I", payload[offset : offset + 4])[0]
    header_start = offset + 4
    header_end = header_start + header_length
    header_bytes = payload[header_start:header_end]
    header = json.loads(header_bytes.decode("utf-8"))
    salt = base64.b64decode(header["salt_b64"])
    nonce = base64.b64decode(header["nonce_b64"])
    decrypted = AESGCM(_derive_key(passphrase, salt)).decrypt(
        nonce,
        payload[header_end:],
        header_bytes,
    )
    return header, decrypted


class AuditRecorder:
    """One external camera+microphone capture for countdown plus trial."""

    def __init__(
        self,
        *,
        ffmpeg_path: str,
        video_device: str,
        audio_device: str,
        passphrase: str,
        retention_hours: int,
    ) -> None:
        if int(retention_hours) not in RETENTION_OPTIONS_HOURS:
            raise ValueError("Unsupported audit retention period.")
        _derive_key(passphrase, b"stage3v-audit-validation-salt")
        self.ffmpeg_path = str(Path(ffmpeg_path).resolve())
        self.video_device = str(video_device)
        self.audio_device = str(audio_device)
        self.passphrase = passphrase
        self.retention_hours = int(retention_hours)
        self.clip_id = uuid.uuid4().hex
        self.trial_id = ""
        self.started_time: datetime | None = None
        self.started_monotonic: float | None = None
        self._plaintext_path: Path | None = None
        self._process: subprocess.Popen[bytes] | None = None

    def start(self, trial_id: str) -> None:
        if self._process is not None:
            raise RuntimeError("AUDIT_RECORDER_ALREADY_RUNNING")
        if not Path(self.ffmpeg_path).is_file():
            raise RuntimeError("FFMPEG_UNAVAILABLE")
        self.trial_id = str(trial_id)
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        self._plaintext_path = (TEMP_DIR / f"{self.clip_id}.mp4").resolve()
        input_spec = f'video="{self.video_device}":audio="{self.audio_device}"'
        command = [
            self.ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "dshow",
            "-rtbufsize",
            "128M",
            "-i",
            input_spec,
            "-vf",
            "scale='min(640,iw)':-2,fps=10",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-b:v",
            "800k",
            "-c:a",
            "aac",
            "-b:a",
            "64k",
            "-movflags",
            "+faststart",
            str(self._plaintext_path),
        ]
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(
            subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0
        )
        self._process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        time.sleep(0.4)
        if self._process.poll() is not None:
            self._cleanup_plaintext()
            self._process = None
            raise RuntimeError("AUDIT_CAPTURE_START_FAILED")
        self.started_time = datetime.now(timezone.utc).astimezone()
        self.started_monotonic = time.perf_counter()

    def stop_and_encrypt(self, *, status: str = "CAPTURED") -> AuditClip:
        process = self._process
        if process is None or self._plaintext_path is None or self.started_time is None:
            raise RuntimeError("AUDIT_RECORDER_NOT_RUNNING")
        try:
            if process.stdin is not None:
                process.stdin.write(b"q\n")
                process.stdin.flush()
            process.wait(timeout=8)
        except (OSError, subprocess.SubprocessError):
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.SubprocessError:
                process.kill()
                process.wait(timeout=3)
        finally:
            self._process = None
        if not self._plaintext_path.is_file() or self._plaintext_path.stat().st_size == 0:
            self._cleanup_plaintext()
            raise RuntimeError("AUDIT_CAPTURE_EMPTY")

        completed = datetime.now(timezone.utc).astimezone()
        expires = completed + timedelta(hours=self.retention_hours)
        encrypted_name = f"{self.trial_id}_{self.clip_id}.r3audit"
        encrypted_path = (AUDIT_DIR / encrypted_name).resolve()
        duration = max(0.0, time.perf_counter() - float(self.started_monotonic or 0.0))
        metadata = {
            "clip_id": self.clip_id,
            "trial_id": self.trial_id,
            "started_time_iso": self.started_time.isoformat(timespec="seconds"),
            "completed_time_iso": completed.isoformat(timespec="seconds"),
            "expires_time_iso": expires.isoformat(timespec="seconds"),
            "duration_seconds": duration,
            "status": status,
            "cloud_transfer": False,
        }
        try:
            encrypt_media_file(
                self._plaintext_path,
                encrypted_path,
                passphrase=self.passphrase,
                public_metadata=metadata,
            )
        finally:
            self._cleanup_plaintext()
        clip = AuditClip(
            clip_id=self.clip_id,
            trial_id=self.trial_id,
            encrypted_file=encrypted_path.name,
            started_time_iso=metadata["started_time_iso"],
            completed_time_iso=metadata["completed_time_iso"],
            expires_time_iso=metadata["expires_time_iso"],
            duration_seconds=duration,
            video_device=self.video_device,
            audio_device=self.audio_device,
            encryption="AES-256-GCM+scrypt",
            status=status,
        )
        _save_clip_record(clip)
        return clip

    def abort_and_delete(self) -> None:
        process = self._process
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.SubprocessError:
                process.kill()
        self._process = None
        self._cleanup_plaintext()

    def _cleanup_plaintext(self) -> None:
        path = self._plaintext_path
        if path is not None:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        self._plaintext_path = None


def list_audit_clips() -> list[dict[str, Any]]:
    return list(_load_index()["clips"])


def record_audit_review(clip_id: str, verdict: str) -> dict[str, Any]:
    normalized = str(verdict).upper()
    if normalized not in {"COMPLIANT", "NONCOMPLIANT"}:
        raise ValueError("Audit verdict must be COMPLIANT or NONCOMPLIANT.")
    payload = _load_index()
    matched: dict[str, Any] | None = None
    for row in payload["clips"]:
        if row.get("clip_id") == clip_id:
            row["review_verdict"] = normalized
            row["reviewed_time_iso"] = datetime.now(timezone.utc).astimezone().isoformat(
                timespec="seconds"
            )
            matched = row
            break
    if matched is None:
        raise ValueError("Unknown audit clip.")
    _atomic_json(INDEX_PATH, payload)
    return matched


def delete_audit_clip(clip_id: str, *, reason: str) -> bool:
    payload = _load_index()
    retained: list[dict[str, Any]] = []
    deleted = False
    for row in payload["clips"]:
        if row.get("clip_id") != clip_id:
            retained.append(row)
            continue
        path = (AUDIT_DIR / str(row.get("encrypted_file") or "")).resolve()
        if path.parent == AUDIT_DIR:
            path.unlink(missing_ok=True)
        deleted = True
    payload["clips"] = retained
    payload.setdefault("deletion_log", []).append(
        {
            "clip_id": clip_id,
            "reason": str(reason),
            "deleted": deleted,
            "time_iso": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        }
    )
    _atomic_json(INDEX_PATH, payload)
    return deleted


def purge_expired_audit_clips(now: datetime | None = None) -> list[str]:
    current = now or datetime.now(timezone.utc).astimezone()
    deleted: list[str] = []
    for row in list_audit_clips():
        try:
            expires = datetime.fromisoformat(str(row["expires_time_iso"]))
        except (KeyError, TypeError, ValueError):
            continue
        if expires <= current and delete_audit_clip(str(row["clip_id"]), reason="RETENTION_EXPIRED"):
            deleted.append(str(row["clip_id"]))
    return deleted
