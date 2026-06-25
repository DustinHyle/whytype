"""whisper.cpp GGML model registry and download helpers.

Models are the GGML/GGUF ``.bin`` checkpoints used by whisper.cpp, downloaded
from the official Hugging Face repo. Quantized variants ("Compact") trade a
small amount of accuracy for much smaller files and faster inference.
"""

from __future__ import annotations

import os
import urllib.request
from typing import Callable, Optional

from platformdirs import user_cache_dir

APP_NAME = "WhyType"
MODEL_CACHE_DIR = os.path.join(user_cache_dir(APP_NAME), "models")

# Base URL for the official whisper.cpp GGML models.
_HF_BASE = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main"

# Valid model file magic: "ggml" (little-endian) or GGUF. Used to reject
# corrupt/truncated downloads that would otherwise crash whisper.cpp with
# "failed to initialize whisper context".
_GGML_MAGICS = (b"lmgg", b"GGUF")


def is_model_file_valid(path: str) -> bool:
    """True if the file exists and starts with a known GGML/GGUF magic."""
    try:
        with open(path, "rb") as f:
            return f.read(4) in _GGML_MAGICS
    except OSError:
        return False

# key -> metadata. "filename" is the GGML file as published on Hugging Face.
MODEL_REGISTRY = {
    "tiny": {
        "display": "Tiny",
        "size": "~75 MB",
        "speed": "Fastest",
        "accuracy": "Basic",
        "filename": "ggml-tiny.bin",
        "description": "Best for older computers. Fastest transcription with basic accuracy. Good for clear, simple speech.",
    },
    "base": {
        "display": "Base",
        "size": "~142 MB",
        "speed": "Fast",
        "accuracy": "Low",
        "filename": "ggml-base.bin",
        "description": "Good balance for everyday use. Runs well on most computers with acceptable accuracy.",
    },
    "small": {
        "display": "Small",
        "size": "~466 MB",
        "speed": "Moderate",
        "accuracy": "Good",
        "filename": "ggml-small.bin",
        "description": "Better at handling accents and background noise. Best choice for most users.",
    },
    "medium": {
        "display": "Medium",
        "size": "~1.5 GB",
        "speed": "Slow",
        "accuracy": "Better",
        "filename": "ggml-medium.bin",
        "description": "High accuracy for professional use. Requires a modern computer and more patience.",
    },
    "large-v3-turbo-q5_0": {
        "display": "Turbo (Compact)",
        "size": "~574 MB",
        "speed": "Fast",
        "accuracy": "Great",
        "filename": "ggml-large-v3-turbo-q5_0.bin",
        "description": "Quantized Large-v3 Turbo. Near-large accuracy at a fraction of the size and time. Great default with a GPU.",
    },
    "large-v3-turbo": {
        "display": "Turbo",
        "size": "~1.6 GB",
        "speed": "Moderate",
        "accuracy": "Great",
        "filename": "ggml-large-v3-turbo.bin",
        "description": "Large-v3 Turbo. Almost the accuracy of Large but substantially faster.",
    },
    "large-v3-q5_0": {
        "display": "Large (Compact)",
        "size": "~1.1 GB",
        "speed": "Slow",
        "accuracy": "Best",
        "filename": "ggml-large-v3-q5_0.bin",
        "description": "Quantized Large-v3. Maximum accuracy with a much smaller download than full Large.",
    },
    "large-v3": {
        "display": "Large",
        "size": "~3.1 GB",
        "speed": "Slowest",
        "accuracy": "Best",
        "filename": "ggml-large-v3.bin",
        "description": "Full-precision Large-v3. Maximum accuracy across languages and difficult audio. Very resource intensive.",
    },
}


def model_path(name: str) -> str:
    """Absolute path to the cached GGML file for a registry model name."""
    return os.path.join(MODEL_CACHE_DIR, MODEL_REGISTRY[name]["filename"])


def is_model_downloaded(name: str) -> bool:
    if name not in MODEL_REGISTRY:
        return False
    return os.path.exists(model_path(name))


def get_downloaded_models() -> list[str]:
    return [name for name in MODEL_REGISTRY if is_model_downloaded(name)]


def download_model(
    name: str,
    progress: Optional[Callable[[int, int], None]] = None,
) -> str:
    """Download and cache a GGML model. Returns the path to the .bin file.

    Streams to a ``.part`` file and renames on success, so an interrupted
    download never looks like a complete model. ``progress(done, total)`` is
    called as bytes arrive (``total`` is 0 if the server omits the length).

    A read timeout is used so a stalled connection raises instead of hanging
    forever.
    """
    if name not in MODEL_REGISTRY:
        raise ValueError(f"Unknown model: {name}")

    os.makedirs(MODEL_CACHE_DIR, exist_ok=True)
    dest = model_path(name)
    if os.path.exists(dest):
        if is_model_file_valid(dest):
            if progress:
                size = os.path.getsize(dest)
                progress(size, size)
            return dest
        # Existing file is corrupt — remove it and download a fresh copy.
        try:
            os.remove(dest)
        except OSError:
            pass

    url = f"{_HF_BASE}/{MODEL_REGISTRY[name]['filename']}"
    tmp = dest + ".part"
    req = urllib.request.Request(url, headers={"User-Agent": "WhyType"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp, open(tmp, "wb") as f:
            total = int(resp.headers.get("Content-Length", 0) or 0)
            done = 0
            head = b""
            while True:
                chunk = resp.read(1024 * 256)
                if not chunk:
                    break
                if len(head) < 4:
                    head += chunk[: 4 - len(head)]
                f.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)

        # Integrity checks — a truncated or wrong-type file would otherwise be
        # saved and later crash whisper.cpp ("failed to initialize whisper
        # context"). Fail loudly instead so the user can retry.
        if total and done != total:
            raise OSError(
                f"download incomplete ({done} of {total} bytes) — please retry"
            )
        if head not in _GGML_MAGICS:
            raise OSError(
                "downloaded file is not a valid model (it may be a network "
                "error page) — please retry"
            )
    except BaseException:
        # Don't leave a partial/corrupt .part behind on failure/cancel.
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    os.replace(tmp, dest)
    return dest
