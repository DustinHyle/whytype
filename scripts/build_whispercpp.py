#!/usr/bin/env python3
"""Build whisper.cpp's ``whisper-cli`` and stage it into ``whytype/bin/``.

Used by CI (and developers) to produce the native binary that carries GPU
acceleration. Built statically so a single self-contained binary ships — GPU
backends still dynamically load the *system* runtime (Vulkan loader / Metal),
which is the correct behaviour.

Usage:
    python scripts/build_whispercpp.py --backend auto
    python scripts/build_whispercpp.py --backend vulkan
    python scripts/build_whispercpp.py --backend cuda --ref v1.7.5
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

REPO = "https://github.com/ggml-org/whisper.cpp"
# Pin in CI for reproducible builds, e.g. --ref v1.7.5
DEFAULT_REF = "master"

# backend -> extra CMake flags
BACKEND_FLAGS = {
    "cpu": [],
    "vulkan": ["-DGGML_VULKAN=1"],
    "cuda": ["-DGGML_CUDA=1"],
    "metal": ["-DGGML_METAL=1"],
    "hipblas": ["-DGGML_HIP=1"],
}


def default_backend() -> str:
    if sys.platform == "darwin":
        return "metal"
    return "vulkan"  # cross-vendor: NVIDIA, AMD, Intel, incl. integrated


def run(cmd, **kw):
    print("+", " ".join(cmd))
    subprocess.check_call(cmd, **kw)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="auto", choices=["auto", *BACKEND_FLAGS])
    ap.add_argument("--ref", default=DEFAULT_REF, help="whisper.cpp git ref/tag")
    ap.add_argument("--jobs", default=str(os.cpu_count() or 4))
    args = ap.parse_args()

    backend = default_backend() if args.backend == "auto" else args.backend
    print(f"Building whisper-cli (backend={backend}, ref={args.ref})")

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bin_dir = os.path.join(repo_root, "whytype", "bin")
    os.makedirs(bin_dir, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "whisper.cpp")
        run(["git", "clone", "--depth", "1", "--branch", args.ref, REPO, src])

        build = os.path.join(src, "build")
        run([
            "cmake", "-B", build,
            "-DCMAKE_BUILD_TYPE=Release",
            "-DBUILD_SHARED_LIBS=OFF",
            "-DWHISPER_BUILD_TESTS=OFF",
            "-DWHISPER_BUILD_EXAMPLES=ON",
            *BACKEND_FLAGS[backend],
        ], cwd=src)
        run(["cmake", "--build", build, "--config", "Release",
             "-j", args.jobs, "--target", "whisper-cli"], cwd=src)

        exe = "whisper-cli.exe" if sys.platform == "win32" else "whisper-cli"
        found = None
        for root, _dirs, files in os.walk(build):
            if exe in files:
                found = os.path.join(root, exe)
                break
        if not found:
            raise SystemExit(f"Build succeeded but {exe} was not found under {build}")

        dest = os.path.join(bin_dir, exe)
        shutil.copy2(found, dest)
        if sys.platform != "win32":
            os.chmod(dest, 0o755)
        print(f"Staged: {dest} ({os.path.getsize(dest) // 1024} KB)")


if __name__ == "__main__":
    main()
