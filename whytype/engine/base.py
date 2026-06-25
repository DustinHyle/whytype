"""Abstract transcription engine interface.

Decouples the application from any specific speech-to-text backend so that
engines (currently whisper.cpp) are interchangeable behind a stable API.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import numpy as np


class TranscriptionEngine(ABC):
    """A loadable speech-to-text model that transcribes audio arrays.

    Implementations must be safe to call ``transcribe()`` from a worker
    thread while the rest of the app runs on the GUI thread.
    """

    @abstractmethod
    def transcribe(self, audio_np: Optional[np.ndarray]) -> str:
        """Transcribe a 1-D float32 16 kHz mono array. Returns "" if empty."""

    @abstractmethod
    def is_ready(self) -> bool:
        """True if a model is loaded and ready to transcribe."""

    @abstractmethod
    def load_error(self) -> Optional[str]:
        """Last load failure message, or None.

        None together with ``is_ready()`` False means no model is installed
        (as opposed to a model that failed to load).
        """

    @abstractmethod
    def reload(self, model_name: str, custom_path: Optional[str] = None) -> None:
        """Reload with new parameters (or retry after a failed load)."""

    def set_device(self, device: str) -> None:
        """Select compute device ("cpu" or "gpu"). No-op for CPU-only engines."""

    def probe_backend(self) -> tuple[bool, str]:
        """Test GPU usability.

        Returns ``(gpu_active, label)``. ``gpu_active`` is whether a GPU
        backend is actually engaged; ``label`` is a human-readable summary
        (e.g. "Vulkan" or "CPU"). Engines without GPU support return
        ``(False, "CPU")``.
        """
        return (False, "CPU")
