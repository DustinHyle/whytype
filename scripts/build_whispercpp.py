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
import platform
import shutil
import subprocess
import sys
import tempfile

REPO = "https://github.com/ggml-org/whisper.cpp"
# Pinned, not "master": an unpinned build makes every release a different
# upstream snapshot, so a regression lands in users' hands with nothing in the
# repo recording what changed.
DEFAULT_REF = "v1.9.4"

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


def _portability_flags() -> list:
    """CMake flags that keep the binary runnable on machines other than this one.

    ggml defaults GGML_NATIVE=ON, i.e. -march=native, which bakes the *build*
    machine's instruction set into the binary. CI runners are not a fixed CPU:
    the v1.2.1 Windows build landed on a runner with AVX-512 and shipped 5,911
    AVX-512 instructions, so it died with an illegal instruction — no stderr,
    just a non-zero exit — on every user whose CPU lacks it. The v1.2.0 build
    of the same source had none. Whether a release runs at all must not depend
    on which runner GitHub happened to allocate.

    The baseline is AVX2/FMA/F16C (Intel Haswell, 2013; AMD Excavator, 2015),
    which the working v1.2.0 binary already relied on.
    """
    flags = ["-DGGML_NATIVE=OFF"]
    if platform.machine().lower() in ("x86_64", "amd64", "x86", "i386", "i686"):
        flags += [
            "-DGGML_AVX=ON",
            "-DGGML_AVX2=ON",
            "-DGGML_FMA=ON",
            "-DGGML_F16C=ON",
            "-DGGML_AVX512=OFF",
        ]
    return flags


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

        def configure_and_build(bk: str) -> None:
            if os.path.isdir(build):
                shutil.rmtree(build)
            run([
                "cmake", "-B", build,
                "-DCMAKE_BUILD_TYPE=Release",
                "-DBUILD_SHARED_LIBS=OFF",
                "-DWHISPER_BUILD_TESTS=OFF",
                "-DWHISPER_BUILD_EXAMPLES=ON",
                *_portability_flags(),
                *BACKEND_FLAGS[bk],
            ], cwd=src)
            run(["cmake", "--build", build, "--config", "Release",
                 "-j", args.jobs, "--target", "whisper-cli"], cwd=src)

        try:
            configure_and_build(backend)
        except subprocess.CalledProcessError:
            # GPU backends need extra SDKs (Vulkan/SPIRV headers, etc.) that may
            # be missing; never fail the whole build — fall back to a CPU binary
            # so a working engine always ships. (The app also falls back to CPU
            # at runtime if a GPU is unusable.)
            if backend != "cpu":
                print(f"WARNING: '{backend}' backend build failed; "
                      f"falling back to a CPU-only engine.")
                backend = "cpu"
                configure_and_build("cpu")
            else:
                raise

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
