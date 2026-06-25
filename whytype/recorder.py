"""Microphone audio capture using sounddevice."""

from __future__ import annotations

import logging
import threading
from typing import Optional

import numpy as np
import sounddevice as sd

logger = logging.getLogger("whytype.recorder")


def list_input_devices() -> list[str]:
    """Return the names of available input (microphone) devices, de-duplicated."""
    names: list[str] = []
    try:
        for dev in sd.query_devices():
            if dev.get("max_input_channels", 0) > 0:
                name = dev.get("name", "").strip()
                if name and name not in names:
                    names.append(name)
    except Exception:
        logger.debug("Could not list input devices", exc_info=True)
    return names


class AudioRecorder:
    """Records audio from the default input device into a NumPy array."""

    def __init__(
        self,
        samplerate: int = 16000,
        max_seconds: int = 300,
        device: Optional[str] = None,
    ) -> None:
        self.samplerate = samplerate
        # Preferred input device name, or None for the OS default.
        self._device = device or None
        # Cap captured audio so a forgotten recording cannot grow unbounded
        # in memory. Frames beyond the cap are dropped.
        self._max_frames = samplerate * max_seconds
        self._frame_count = 0
        self._capped = False
        self._recording: Optional[list[np.ndarray]] = None
        self._stream: Optional[sd.InputStream] = None
        self._lock = threading.Lock()

    def set_input_device(self, device: Optional[str]) -> None:
        """Set the preferred microphone by name (None/"" = OS default)."""
        with self._lock:
            self._device = device or None

    def _resolve_device(self):
        """Map the configured device name to a sounddevice index.

        Returns None (the OS default) when no device is set or the named one
        is not currently available.
        """
        if not self._device:
            return None
        try:
            for idx, dev in enumerate(sd.query_devices()):
                if dev.get("max_input_channels", 0) > 0 and dev.get("name") == self._device:
                    return idx
        except Exception:
            logger.debug("Could not enumerate devices", exc_info=True)
        logger.warning(
            "Configured microphone '%s' not found; using the default.", self._device
        )
        return None

    def start(self) -> None:
        """Start recording. Raises if the microphone is unavailable."""
        with self._lock:
            if self._stream is not None and self._stream.active:
                raise RuntimeError("Recording is already in progress")
            self._recording = []
            self._frame_count = 0
            self._capped = False
            try:
                # Log which input device is actually being used, to diagnose
                # "no audio / wrong mic" problems.
                device_index = self._resolve_device()
                try:
                    dev = sd.query_devices(
                        device_index if device_index is not None else None,
                        kind="input",
                    )
                    logger.info("Recording from input device: %s", dev.get("name", "?"))
                except Exception:
                    logger.debug("Could not query input device", exc_info=True)
                self._stream = sd.InputStream(
                    samplerate=self.samplerate,
                    channels=1,
                    dtype=np.float32,
                    device=device_index,
                    callback=self._callback,
                )
                self._stream.start()
            except Exception:
                self._recording = None
                self._stream = None
                raise

    def _callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        with self._lock:
            if self._recording is None or self._capped:
                return
            if self._frame_count >= self._max_frames:
                self._capped = True
                return
            self._recording.append(indata.copy())
            self._frame_count += frames

    def stop(self) -> Optional[np.ndarray]:
        """Stop recording and return the captured audio as a 1-D float32 array."""
        # Capture references under the lock, then release it before
        # stopping the stream to avoid deadlocking with the callback thread.
        stream: Optional[sd.InputStream] = None
        chunks: Optional[list[np.ndarray]] = None

        with self._lock:
            stream = self._stream
            self._stream = None
            chunks = self._recording
            self._recording = None

        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass

        if chunks:
            return np.concatenate(chunks, axis=0).flatten()
        return None

    def is_recording(self) -> bool:
        with self._lock:
            return self._stream is not None and self._stream.active
