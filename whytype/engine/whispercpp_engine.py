"""whisper.cpp transcription engine (subprocess).

Shells out to a bundled ``whisper-cli`` binary. The recorded audio array is
written to a temporary 16 kHz mono WAV, transcribed, and the binary's stdout
is parsed back into text. The native binary is what carries GPU acceleration
(Vulkan / Metal / CUDA); this Python layer is backend-agnostic.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import wave
from typing import Optional

import numpy as np

logger = logging.getLogger("whytype.engine")

from whytype.engine.base import TranscriptionEngine
from whytype.models import (
    get_downloaded_models,
    is_model_downloaded,
    is_model_file_valid,
    model_path,
)


def find_binary() -> Optional[str]:
    """Locate the whisper-cli binary: env override, bundled, then PATH."""
    override = os.environ.get("WHYTYPE_WHISPER_CLI")
    if override and os.path.exists(override):
        return override

    exe = "whisper-cli.exe" if sys.platform == "win32" else "whisper-cli"
    if getattr(sys, "frozen", False):
        base = os.path.join(
            getattr(sys, "_MEIPASS", os.path.dirname(sys.executable)), "whytype", "bin"
        )
    else:
        base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "bin")
    bundled = os.path.join(base, exe)
    if os.path.exists(bundled):
        return bundled

    # PATH fallback — e.g. Homebrew's whisper-cpp formula installs whisper-cli.
    for name in ("whisper-cli", "whisper-cpp", "whisper", "main"):
        found = shutil.which(name)
        if found:
            return found

    # macOS GUI apps (launched from Finder/Spotlight) get a minimal PATH that
    # excludes Homebrew, so check its known locations explicitly.
    if sys.platform == "darwin":
        for d in ("/opt/homebrew/bin", "/usr/local/bin"):
            for name in ("whisper-cli", "whisper-cpp"):
                p = os.path.join(d, name)
                if os.path.exists(p):
                    return p
    return None


class WhisperCppEngine(TranscriptionEngine):
    """Transcribes audio via a whisper.cpp ``whisper-cli`` subprocess."""

    def __init__(
        self,
        model_name: str = "",
        custom_path: Optional[str] = None,
        device: str = "cpu",
    ) -> None:
        self._model_name = model_name
        self._custom_path = custom_path
        self._device = device  # "cpu" or "gpu" (Auto resolves to one of these)
        self._lock = threading.Lock()
        self._binary = find_binary()
        self._model_file: Optional[str] = None
        self._load_error: Optional[str] = None
        self._resolve_model()

    def _resolve_model(self) -> None:
        if self._binary is None:
            with self._lock:
                self._model_file = None
                self._load_error = (
                    "The whisper.cpp engine (whisper-cli) was not found. "
                    "Reinstall Why Type to restore it."
                )
            return

        if self._custom_path and os.path.exists(self._custom_path):
            resolved = self._custom_path
        elif self._model_name and is_model_downloaded(self._model_name):
            resolved = model_path(self._model_name)
        else:
            downloaded = get_downloaded_models()
            if downloaded:
                self._model_name = downloaded[0]
                resolved = model_path(self._model_name)
            else:
                resolved = None  # nothing installed — benign, not an error

        # A corrupt/truncated model would otherwise crash whisper.cpp with
        # "failed to initialize whisper context" at transcribe time. Detect it
        # up front and report something the user can act on.
        if resolved is not None and not is_model_file_valid(resolved):
            with self._lock:
                self._model_file = None
                self._load_error = (
                    "The transcription model file looks corrupt or incomplete.\n\n"
                    "Open Settings and download it again — Why Type will "
                    "automatically replace the bad file."
                )
            return

        with self._lock:
            self._model_file = resolved
            self._load_error = None

    def reload(self, model_name: str = "", custom_path: Optional[str] = None) -> None:
        self._model_name = model_name
        self._custom_path = custom_path
        # The binary may have been installed since construction.
        if self._binary is None:
            self._binary = find_binary()
        self._resolve_model()

    def set_device(self, device: str) -> None:
        with self._lock:
            self._device = device

    # Backend init markers whisper.cpp logs to stderr when a GPU is engaged.
    _GPU_MARKERS = (
        ("CUDA", ("ggml_cuda", "cuda0", "using cuda")),
        ("Metal", ("ggml_metal", "using metal")),
        ("Vulkan", ("ggml_vulkan", "vulkan0", "vulkan device", "vulkan backend")),
        ("ROCm", ("ggml_hip", "rocm", "hipblas")),
        ("SYCL", ("ggml_sycl",)),
    )

    def probe_backend(self) -> tuple[bool, str]:
        """Run a short clip with GPU enabled and report the backend in use.

        Returns ``(gpu_active, label)``. A CPU-only binary, an unavailable
        GPU, or a backend-init failure all yield ``(False, "CPU")`` — which
        is the signal to fall back to CPU.
        """
        with self._lock:
            binary = self._binary
            model_file = self._model_file
        if binary is None or model_file is None:
            return (False, "CPU")

        wav_path = self._write_wav(np.zeros(4800, dtype=np.float32))  # 0.3s
        kwargs = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        try:
            proc = subprocess.run(
                [binary, "-m", model_file, "-f", wav_path, "--no-timestamps"],
                capture_output=True, text=True, timeout=180, **kwargs
            )
        except Exception:
            return (False, "CPU")
        finally:
            try:
                os.remove(wav_path)
            except OSError:
                pass

        if proc.returncode != 0:
            return (False, "CPU")
        err = (proc.stderr or "").lower()
        for label, subs in self._GPU_MARKERS:
            if any(s in err for s in subs):
                return (True, label)
        return (False, "CPU")

    def transcribe(self, audio_np: Optional[np.ndarray]) -> str:
        with self._lock:
            binary = self._binary
            model_file = self._model_file
            device = self._device
        if binary is None or model_file is None or audio_np is None or len(audio_np) == 0:
            return ""

        wav_path = self._write_wav(audio_np)
        try:
            try:
                return self._run(binary, model_file, wav_path, use_gpu=(device != "cpu"))
            except RuntimeError:
                # If a GPU run fails (driver/VRAM/init issues), fall back to CPU
                # once and stay on CPU for the session instead of erroring.
                if device != "cpu":
                    logger.warning("GPU transcription failed; retrying on CPU")
                    with self._lock:
                        self._device = "cpu"
                    return self._run(binary, model_file, wav_path, use_gpu=False)
                raise
        finally:
            try:
                os.remove(wav_path)
            except OSError:
                pass

    def _run(self, binary: str, model_file: str, wav_path: str, use_gpu: bool) -> str:
        cmd = [
            binary,
            "-m", model_file,
            "-f", wav_path,
            "-l", "auto",
            "--no-timestamps",
            "--no-prints",
        ]
        if not use_gpu:
            cmd.append("--no-gpu")

        kwargs = {}
        if sys.platform == "win32":
            # Keep the silent tray app from flashing a console window.
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600, **kwargs
        )
        if proc.returncode != 0:
            raise RuntimeError(
                (proc.stderr or "whisper-cli failed").strip().splitlines()[-1]
                if proc.stderr else "whisper-cli failed"
            )
        lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
        return " ".join(lines).strip()

    @staticmethod
    def _write_wav(audio_np: np.ndarray) -> str:
        """Write a float32 mono array to a temp 16 kHz 16-bit PCM WAV."""
        clipped = np.clip(audio_np, -1.0, 1.0)
        pcm = (clipped * 32767.0).astype("<i2")
        fd, path = tempfile.mkstemp(suffix=".wav", prefix="whytype_")
        os.close(fd)
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(pcm.tobytes())
        return path

    def is_ready(self) -> bool:
        with self._lock:
            return self._binary is not None and self._model_file is not None

    def load_error(self) -> Optional[str]:
        with self._lock:
            return self._load_error
