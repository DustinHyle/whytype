"""Pluggable transcription engines.

``create_engine`` returns the active engine implementation (whisper.cpp),
keeping the rest of the app unaware of the backend.
"""

from __future__ import annotations

from typing import Optional

from whytype.engine.base import TranscriptionEngine
from whytype.engine.whispercpp_engine import WhisperCppEngine

__all__ = ["TranscriptionEngine", "create_engine"]


def create_engine(
    model_name: str = "",
    custom_path: Optional[str] = None,
    device: str = "cpu",
) -> TranscriptionEngine:
    """Construct the active transcription engine (whisper.cpp)."""
    return WhisperCppEngine(
        model_name=model_name, custom_path=custom_path, device=device
    )
