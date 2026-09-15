"""Tests for system audio output muting.

The Windows backend is the reason this file exists. It cannot be exercised on
CI (the runners have no audio endpoint) and it broke twice in a row without
anything noticing: pycaw changed the return type of
``AudioUtilities.GetSpeakers()`` between releases, and our version floor admits
both. These tests stub pycaw so the Windows control flow is verified on every
platform.
"""

from __future__ import annotations

import sys
import time
import types
import unittest
from unittest import mock


class FakeVolume:
    """Stand-in for IAudioEndpointVolume."""

    def __init__(self) -> None:
        self.muted = False

    def GetMute(self):  # noqa: N802 (COM naming)
        return self.muted

    def SetMute(self, value, _ctx):  # noqa: N802 (COM naming)
        self.muted = bool(value)


class NewStyleDevice:
    """pycaw >= 20251023: GetSpeakers() returns an AudioDevice wrapper.

    It has no Activate(); the endpoint interface comes from EndpointVolume.
    """

    FriendlyName = "Speakers (Test)"

    def __init__(self) -> None:
        self.EndpointVolume = FakeVolume()


class OldStyleDevice:
    """pycaw <= 20230407: GetSpeakers() returns a raw IMMDevice."""

    def __init__(self) -> None:
        self.volume = FakeVolume()
        self.activated = False

    def Activate(self, _iid, _ctx, _params):  # noqa: N802 (COM naming)
        self.activated = True
        return self.volume


class WindowsMuteTest(unittest.TestCase):
    """The Windows backend must drive both pycaw API shapes."""

    def _install_pycaw_stub(self, device):
        comtypes = types.ModuleType("comtypes")
        comtypes.CLSCTX_ALL = 1
        comtypes.CoInitialize = lambda: None
        comtypes.CoUninitialize = lambda: None

        pycaw_mod = types.ModuleType("pycaw.pycaw")
        pycaw_mod.IAudioEndpointVolume = type(
            "IAudioEndpointVolume", (), {"_iid_": "iid"}
        )
        pycaw_mod.AudioUtilities = type(
            "AudioUtilities",
            (),
            {
                "GetSpeakers": staticmethod(lambda: device),
                "CreateDevice": staticmethod(
                    lambda d: types.SimpleNamespace(FriendlyName="Legacy")
                ),
            },
        )

        patcher = mock.patch.dict(
            sys.modules,
            {
                "comtypes": comtypes,
                "pycaw": types.ModuleType("pycaw"),
                "pycaw.pycaw": pycaw_mod,
            },
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _muter(self):
        sys.modules.pop("whytype.audio_output", None)
        import whytype.audio_output as ao

        self.addCleanup(lambda: sys.modules.pop("whytype.audio_output", None))
        # POINTER/cast are meaningless against Python stubs; make them identity
        # so the old-pycaw branch's real control flow is what gets exercised.
        for target, repl in (
            ("ctypes.POINTER", lambda t: t),
            ("ctypes.cast", lambda obj, _t: obj),
        ):
            p = mock.patch(target, repl)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(ao.sys, "platform", "win32")
        p.start()
        self.addCleanup(p.stop)
        return ao.OutputMuter()

    def test_new_style_device_mutes_and_restores(self):
        device = NewStyleDevice()
        self._install_pycaw_stub(device)
        muter = self._muter()

        self.assertIs(muter._set_muted(True), False)  # previous state
        self.assertTrue(device.EndpointVolume.muted)
        muter._set_muted(False)
        self.assertFalse(device.EndpointVolume.muted)

    def test_old_style_device_mutes_and_restores(self):
        device = OldStyleDevice()
        self._install_pycaw_stub(device)
        muter = self._muter()

        self.assertIs(muter._set_muted(True), False)
        self.assertTrue(device.activated, "old pycaw must go through Activate()")
        self.assertTrue(device.volume.muted)
        muter._set_muted(False)
        self.assertFalse(device.volume.muted)

    def test_already_muted_user_is_left_muted(self):
        device = NewStyleDevice()
        device.EndpointVolume.muted = True
        self._install_pycaw_stub(device)
        muter = self._muter()

        muter._mute_locked()
        muter._unmute_locked()
        self.assertTrue(
            device.EndpointVolume.muted,
            "a user who was already muted must stay muted",
        )


class MuterQueueTest(unittest.TestCase):
    """Requests are applied in order and restore_now() is synchronous."""

    def _muter(self, applied):
        from whytype.audio_output import OutputMuter

        muter = OutputMuter()
        muter._set_muted = lambda m: (applied.append(m), False)[1]
        return muter

    def test_requests_apply_in_submission_order(self):
        """A mute must never overtake the unmute that preceded it.

        Out-of-order application would leave the user's speakers muted with no
        pending request to restore them.
        """
        applied: list[bool] = []
        muter = self._muter(applied)
        for _ in range(5):
            muter.mute()
            muter.unmute()
        deadline = time.monotonic() + 5.0
        while len(applied) < 10 and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(
            applied,
            [True, False] * 5,
            "requests were applied out of submission order",
        )

    def test_restore_now_is_synchronous(self):
        applied: list[bool] = []
        muter = self._muter(applied)
        muter._previous = False  # pretend we muted
        muter.restore_now()
        self.assertEqual(applied, [False])
        self.assertIsNone(muter._previous)


if __name__ == "__main__":
    unittest.main()
