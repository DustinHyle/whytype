"""Tests for hotkey handling: stuck keys, cancel on other keys, delayed mute.

pynput cannot be imported headless (it needs an X server on Linux), so a
minimal stand-in using Windows virtual-key codes is installed instead, and the
app is built without running its Qt-heavy constructor.
"""

from __future__ import annotations

import enum
import sys
import types
import unittest
from dataclasses import dataclass
from unittest import mock


@dataclass(frozen=True)
class FakeKeyCode:
    vk: int
    char: str = None


_VKS = {
    "ctrl": 0x11, "ctrl_l": 0xA2, "ctrl_r": 0xA3,
    "shift": 0x10, "shift_l": 0xA0, "shift_r": 0xA1,
    "alt": 0x12, "alt_l": 0xA4, "alt_r": 0xA5, "alt_gr": 0xA5,
    "cmd": 0x5B, "cmd_l": 0x5B, "cmd_r": 0x5C,
    "space": 0x20, "tab": 0x09, "enter": 0x0D, "esc": 0x1B,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "home": 0x24, "end": 0x23, "page_up": 0x21, "page_down": 0x22,
    "delete": 0x2E, "insert": 0x2D, "backspace": 0x08,
    **{f"f{i}": 0x6F + i for i in range(1, 13)},
}
FakeKey = enum.Enum("Key", {k: FakeKeyCode(v) for k, v in _VKS.items()})


class FakeTimer:
    """Stand-in for QTimer that fires only when told to."""

    def __init__(self, on_timeout=None) -> None:
        self.active = False
        self.on_timeout = on_timeout

    def start(self, *_args) -> None:
        self.active = True

    def stop(self) -> None:
        self.active = False

    def fire(self) -> None:
        if self.active:
            self.active = False
            self.on_timeout()


class FakeSignal:
    def __init__(self, slot=None) -> None:
        self.slot = slot

    def emit(self, *args) -> None:
        if self.slot is not None:
            self.slot(*args)


class FakeRecorder:
    def __init__(self) -> None:
        self.recording = False

    def start(self) -> None:
        self.recording = True

    def stop(self):
        self.recording = False
        return None


class FakeMuter:
    """Records backend writes; an unmute only writes after a mute."""

    def __init__(self, calls: list) -> None:
        self.calls = calls
        self.muted = False

    def mute(self) -> None:
        self.calls.append("mute")
        self.muted = True

    def unmute(self) -> None:
        if self.muted:
            self.calls.append("unmute")
            self.muted = False


class FakeConfig:
    shortcut = "ctrl+win"
    recording_mode = "hold"
    mute_output_while_recording = True
    mute_delay_ms = 600


def _load_app_module(testcase):
    keyboard = types.ModuleType("pynput.keyboard")
    keyboard.Key = FakeKey
    keyboard.KeyCode = FakeKeyCode
    keyboard.Listener = object
    pynput = types.ModuleType("pynput")
    pynput.keyboard = keyboard
    patcher = mock.patch.dict(
        sys.modules, {"pynput": pynput, "pynput.keyboard": keyboard}
    )
    patcher.start()
    testcase.addCleanup(patcher.stop)
    sys.modules.pop("whytype.app", None)
    testcase.addCleanup(lambda: sys.modules.pop("whytype.app", None))
    import whytype.app as app_mod

    return app_mod


class HotkeyTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = _load_app_module(self)
        # Keys physically down according to the fake GetAsyncKeyState.
        self.down: set[int] = set()
        self.transcribed: list = []
        user32 = types.SimpleNamespace(
            GetAsyncKeyState=lambda vk: 0x8000 if vk in self.down else 0
        )
        for p in (
            mock.patch("ctypes.windll", types.SimpleNamespace(user32=user32), create=True),
            mock.patch.object(self.mod.sys, "platform", "win32"),
            mock.patch.object(self.mod, "_KEY_STATE_TRUSTED", True),
            # Record transcription requests instead of running them.
            mock.patch.object(
                self.mod.threading, "Thread",
                lambda target, args, daemon: types.SimpleNamespace(
                    start=lambda: self.transcribed.append(args)
                ),
            ),
        ):
            p.start()
            self.addCleanup(p.stop)

        app = self.mod.WhyTypeApp.__new__(self.mod.WhyTypeApp)
        app.config = FakeConfig()
        app.recorder = FakeRecorder()
        app.transcriber = types.SimpleNamespace(is_ready=lambda: True)
        app._state = "idle"
        app._pressed_modifiers = set()
        app._shortcut_triggered = False
        app._stop_pending = False
        app._cancel_pending = False
        app._indicator = None
        self.backend_calls: list[str] = []
        app._muter = FakeMuter(self.backend_calls)
        app._mute_timer = FakeTimer(app._mute_output)
        app._hold_watchdog = FakeTimer(app._check_hold_released)
        app.signaler = types.SimpleNamespace(
            start_recording=FakeSignal(app._on_start_recording),
            stop_recording=FakeSignal(app._on_stop_recording),
            cancel_recording=FakeSignal(app._on_cancel_recording),
            status_changed=FakeSignal(),
        )
        app._show_indicator = lambda _s: None
        app._hide_indicator = lambda: None
        self.app = app

    def press(self, name: str) -> None:
        key = FakeKey[name]
        self.down.add(key.value.vk)
        self.app._on_key_press(key)

    def release(self, name: str) -> None:
        key = FakeKey[name]
        self.down.discard(key.value.vk)
        self.app._on_key_release(key)


class StuckKeyTest(HotkeyTestBase):
    def test_missed_win_release_does_not_let_ctrl_fire(self):
        # Win's release was never delivered: it is in the set but physically up.
        self.app._pressed_modifiers.add(FakeKey.cmd)
        self.press("ctrl_l")
        self.assertEqual(self.app._state, "idle", "Ctrl alone started a recording")
        self.assertNotIn(FakeKey.cmd, self.app._pressed_modifiers)

    def test_real_shortcut_still_fires(self):
        self.press("ctrl_l")
        self.press("cmd")
        self.assertEqual(self.app._state, "recording")

    def test_watchdog_stops_recording_after_missed_release(self):
        self.press("ctrl_l")
        self.press("cmd")
        self.down.clear()  # both released, but the listener never heard it
        self.app._hold_watchdog.fire()
        self.assertEqual(self.app._state, "transcribing")

    def test_watchdog_leaves_held_shortcut_alone(self):
        self.press("ctrl_l")
        self.press("cmd")
        self.app._hold_watchdog.fire()
        self.assertEqual(self.app._state, "recording")


class CancelOnOtherKeyTest(HotkeyTestBase):
    def test_ctrl_win_left_cancels(self):
        self.press("ctrl_l")
        self.press("cmd")
        self.assertEqual(self.app._state, "recording")
        self.press("left")
        self.assertEqual(self.app._state, "idle")
        self.assertFalse(self.app.recorder.recording)
        self.assertFalse(self.app._mute_timer.active)
        self.assertEqual(self.backend_calls, [], "output was touched")
        # Releasing everything must not transcribe the discarded audio.
        self.release("left")
        self.release("cmd")
        self.release("ctrl_l")
        self.assertEqual(self.transcribed, [])
        self.assertEqual(self.app._state, "idle")

    def test_cancel_after_mute_restores_output(self):
        self.press("ctrl_l")
        self.press("cmd")
        self.app._mute_timer.fire()
        self.press("left")
        self.assertEqual(self.backend_calls, ["mute", "unmute"])

    def test_more_keys_while_held_do_not_restart(self):
        self.press("ctrl_l")
        self.press("cmd")
        self.press("left")
        self.release("left")
        self.press("right")
        self.assertEqual(self.app._state, "idle")

    def test_cancel_latched_before_start_finishes(self):
        self.app._cancel_pending = True
        self.app._on_start_recording()
        self.assertEqual(self.app._state, "idle")
        self.assertFalse(self.app.recorder.recording)


class DelayedMuteTest(HotkeyTestBase):
    def test_quick_tap_never_touches_output(self):
        self.press("ctrl_l")
        self.press("cmd")
        self.release("cmd")  # before the 600 ms timer fires
        self.assertEqual(self.app._state, "transcribing")
        self.app._mute_timer.fire()  # cancelled: does nothing
        self.assertEqual(self.backend_calls, [])

    def test_long_hold_mutes_once(self):
        self.press("ctrl_l")
        self.press("cmd")
        self.app._mute_timer.fire()
        self.release("cmd")
        self.assertEqual(self.backend_calls, ["mute", "unmute"])
        self.assertEqual(len(self.transcribed), 1)


if __name__ == "__main__":
    unittest.main()
