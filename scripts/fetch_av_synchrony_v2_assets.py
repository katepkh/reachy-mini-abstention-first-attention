#!/usr/bin/env python3
"""Install or verify pinned local MediaPipe assets for the V2 pilot."""

from __future__ import annotations

import argparse
import hashlib
import io
import tarfile
from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = PROJECT_ROOT / "models" / "avsync_v2"
RUNTIME_ROOT = OUTPUT_ROOT / "runtime"
PACKAGE_URL = (
    "https://registry.npmjs.org/@mediapipe/tasks-vision/-/tasks-vision-1.0.1.tgz"
)
PACKAGE_SHA256 = "ee318eaa3d42230aa10910d114faf2a488c577c4e4d33c7cb04126924aca505f"
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)
MODEL_SHA256 = "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"
PACKAGE_MEMBERS = {
    "package/vision_bundle.mjs": (
        "vision_bundle.mjs",
        "d885630c297c0b20b1fe86096cb06291c4c8080876f27852e724f24ac603713f",
    ),
    "package/wasm/vision_wasm_internal.js": (
        "wasm/vision_wasm_internal.js",
        "e170ee67dd4e16c1a6fcd8840a206687e5a59b22c20e4a902bc445b095454d73",
    ),
    "package/wasm/vision_wasm_internal.wasm": (
        "wasm/vision_wasm_internal.wasm",
        "8da277a733926eacd0474b8704b36742d6ec3231c57a860c5b889dff8f1df886",
    ),
    "package/wasm/vision_wasm_module_internal.js": (
        "wasm/vision_wasm_module_internal.js",
        "da8934057f147b622e82cfb4c0dbd85461c598e268588b5a8ba9ca963a8ff82d",
    ),
    "package/wasm/vision_wasm_module_internal.wasm": (
        "wasm/vision_wasm_module_internal.wasm",
        "2dabd8e23c60984628beb7bb338764c81a08e6837145273f59578684b5d53c1b",
    ),
    "package/wasm/vision_wasm_nosimd_internal.js": (
        "wasm/vision_wasm_nosimd_internal.js",
        "e81d715a3d42cc3373602eb2f7aff795d164934db680e32496b65dab537f9658",
    ),
    "package/wasm/vision_wasm_nosimd_internal.wasm": (
        "wasm/vision_wasm_nosimd_internal.wasm",
        "a28483cd42e74e855bf5ebdb6b40d9b66a5b49e35e95020bc97669e6822a3192",
    ),
}


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _download(url: str) -> bytes:
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    return response.content


def install() -> None:
    archive = _download(PACKAGE_URL)
    if _sha256(archive) != PACKAGE_SHA256:
        raise RuntimeError("MediaPipe package hash does not match the frozen value.")
    model = _download(MODEL_URL)
    if _sha256(model) != MODEL_SHA256:
        raise RuntimeError("Face Landmarker model hash does not match the frozen value.")
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as package:
        for member_name, (relative, expected_hash) in PACKAGE_MEMBERS.items():
            member = package.getmember(member_name)
            if not member.isfile():
                raise RuntimeError(f"Pinned package member is not a file: {member_name}")
            handle = package.extractfile(member)
            if handle is None:
                raise RuntimeError(f"Could not read pinned package member: {member_name}")
            content = handle.read()
            if _sha256(content) != expected_hash:
                raise RuntimeError(f"Extracted asset hash mismatch: {member_name}")
            destination = RUNTIME_ROOT / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
    (OUTPUT_ROOT / "face_landmarker.task").write_bytes(model)


def check() -> None:
    expected = {
        RUNTIME_ROOT / relative: digest
        for relative, digest in PACKAGE_MEMBERS.values()
    }
    expected[OUTPUT_ROOT / "face_landmarker.task"] = MODEL_SHA256
    for path, digest in expected.items():
        if not path.is_file():
            raise RuntimeError(f"Missing V2 local asset: {path.relative_to(PROJECT_ROOT)}")
        if _sha256(path.read_bytes()) != digest:
            raise RuntimeError(f"V2 local asset hash mismatch: {path.relative_to(PROJECT_ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--install", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.install:
        install()
    check()
    action = "installed and verified" if args.install else "verified"
    print(f"PASS: pinned V2 MediaPipe assets {action}; no media was accessed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

