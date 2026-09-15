"""System audio output muting.

Muting the speakers for the duration of a recording keeps music, videos or a
call from bleeding through the microphone and into the transcription.

Every platform backend is best-effort: if muting fails the recording must still
proceed, so all failures are logged and swallowed. The previous mute state is
captured on mute and restored on unmute, so a user who was already muted stays
muted.
"""

from __future__ import annotations

import logging
import queue
import subprocess
import sys
import threading
from typing import Optional

logger = logging.getLogger("whytype.audio_output")

# Hide the console window that would otherwise flash on every Windows call.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _run(cmd: list[str], timeout: float = 2.0) -> Optional[str]:
    """Run a helper command, returning stdout or None if it isn't usable."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=_NO_WINDOW if sys.platform == "win32" else 0,
        )
    except (OSError, subprocess.SubprocessError):
        logger.debug("Command failed: %s", " ".join(cmd), exc_info=True)
        return None
    if result.returncode != 0:
        logger.debug("Command %s exited %d: %s", cmd[0], result.returncode, result.stderr.strip())
        return None
    return result.stdout


def _endpoint_name(device) -> str:
    """Friendly name of a Core Audio device, for diagnostics only."""
    try:
        from pycaw.pycaw import AudioUtilities

        return AudioUtilities.CreateDevice(device).FriendlyName or "?"
    except Exception:
        return "?"


class OutputMuter:
    """Mutes and restores the system's default audio output device.

    Every backend is slow — osascript and wpctl are subprocesses, and Core Audio
    can block on device enumeration — so :meth:`mute` and :meth:`unmute` only
    enqueue the request and return immediately. Running them inline would delay
    the start of recording and clip the first words the user speaks, which is
    exactly what this feature exists to protect.

    A single worker thread applies requests in submission order, so a mute can
    never overtake the unmute that preceded it and strand the user in silence.
    """

    def __init__(self) -> None:
        # None = not currently muted by us. Otherwise the mute state we found
        # before muting, to be restored on unmute().
        self._previous: Optional[bool] = None
        # Serializes backend calls and access to _previous.
        self._lock = threading.Lock()
        self._queue: "queue.Queue[bool]" = queue.Queue()
        threading.Thread(
            target=self._run, name="whytype-muter", daemon=True
        ).start()

    def mute(self) -> None:
        """Request a mute. Applied asynchronously."""
        self._queue.put(True)

    def unmute(self) -> None:
        """Request the mute state captured by :meth:`mute` be restored."""
        self._queue.put(False)

    def restore_now(self) -> None:
        """Synchronously restore output, discarding pending requests.

        Used at shutdown: the worker is a daemon thread and would be killed
        mid-flight by interpreter exit, which could leave the user's speakers
        muted with no running app to unmute them.
        """
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        with self._lock:
            self._unmute_locked()

    def _run(self) -> None:
        while True:
            want_muted = self._queue.get()
            with self._lock:
                try:
                    if want_muted:
                        self._mute_locked()
                    else:
                        self._unmute_locked()
                except Exception:
                    logger.warning("Audio output mute request failed", exc_info=True)

    def _mute_locked(self) -> None:
        if self._previous is not None:
            return  # already muted by us
        try:
            previous = self._set_muted(True)
        except Exception:
            logger.warning("Could not mute system audio output", exc_info=True)
            return
        if previous is None:
            logger.warning("System audio output muting is unavailable on this system")
            return
        self._previous = previous
        logger.info("Muted system audio output (was muted=%s)", previous)

    def _unmute_locked(self) -> None:
        if self._previous is None:
            return
        if self._previous:
            # The user was already muted before we started; leave them muted.
            self._previous = None
            return
        try:
            restored = self._set_muted(False)
        except Exception:
            logger.warning("Could not restore system audio output", exc_info=True)
            return
        if restored is None:
            # Every backend failed — the output device may have been unplugged
            # mid-recording. Keep _previous set so a later unmute (or quit)
            # retries rather than silently leaving the user muted.
            logger.warning("Could not restore system audio output; will retry")
            return
        self._previous = None
        logger.info("Restored system audio output")

    # --- Platform backends ------------------------------------------------
    #
    # Each returns the mute state *before* the change, or None if this system
    # has no usable way to control output mute.

    def _set_muted(self, muted: bool) -> Optional[bool]:
        if sys.platform == "win32":
            return self._set_muted_windows(muted)
        if sys.platform == "darwin":
            return self._set_muted_macos(muted)
        return self._set_muted_linux(muted)

    def _set_muted_windows(self, muted: bool) -> Optional[bool]:
        """Core Audio endpoint mute via pycaw."""
        from ctypes import POINTER, cast

        import comtypes
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        # COM is per-thread. The worker thread has never been initialized, but
        # guard anyway: if COM is already up in a different apartment model,
        # CoInitialize raises and the existing apartment is fine to use — we
        # just must not uninitialize what we did not initialize.
        initialized = False
        try:
            comtypes.CoInitialize()
            initialized = True
        except Exception:
            logger.debug("COM already initialized on this thread", exc_info=True)

        try:
            speakers = AudioUtilities.GetSpeakers()
            interface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            previous = bool(volume.GetMute())
            volume.SetMute(1 if muted else 0, None)
            # Name the endpoint we acted on: muting the default render device
            # does nothing audible if playback is routed somewhere else, and
            # that is otherwise invisible in a bug report.
            logger.info(
                "Core Audio endpoint mute=%s on %r", muted, _endpoint_name(speakers)
            )
            # Release the COM proxies BEFORE tearing the apartment down. Python
            # only drops a frame's locals after `finally` runs, so leaving them
            # alive here would call Release() on a dead apartment.
            del volume, interface, speakers
            return previous
        finally:
            if initialized:
                comtypes.CoUninitialize()

    def _set_muted_macos(self, muted: bool) -> Optional[bool]:
        out = _run(["osascript", "-e", "output muted of (get volume settings)"])
        if out is None:
            return None
        previous = out.strip().lower() == "true"
        value = "true" if muted else "false"
        if _run(["osascript", "-e", f"set volume output muted {value}"]) is None:
            return None
        return previous

    def _set_muted_linux(self, muted: bool) -> Optional[bool]:
        """PipeWire (wpctl), then PulseAudio (pactl), then ALSA (amixer)."""
        value = "1" if muted else "0"

        # wpctl get-volume prints e.g. "Volume: 0.65 [MUTED]".
        out = _run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"])
        if out is not None:
            previous = "MUTED" in out
            if _run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", value]) is not None:
                return previous

        # pactl get-sink-mute prints "Mute: yes" / "Mute: no".
        out = _run(["pactl", "get-sink-mute", "@DEFAULT_SINK@"])
        if out is not None:
            previous = "yes" in out.lower()
            if _run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", value]) is not None:
                return previous

        # amixer prints "... [on]" / "... [off]" per channel; [off] means muted.
        out = _run(["amixer", "get", "Master"])
        if out is not None:
            previous = "[off]" in out
            action = "mute" if muted else "unmute"
            if _run(["amixer", "-q", "set", "Master", action]) is not None:
                return previous

        return None
