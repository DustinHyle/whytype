"""Tests for microphone device resolution."""

from __future__ import annotations

import sys
import types
import unittest
from unittest import mock

# sounddevice needs PortAudio, which CI runners may not have; stub it so the
# name-matching logic can be tested anywhere.
if "sounddevice" not in sys.modules:
    try:
        import sounddevice  # noqa: F401
    except Exception:
        sys.modules["sounddevice"] = types.SimpleNamespace(
            query_devices=lambda *a, **k: [], InputStream=object
        )

from whytype.recorder import AudioRecorder  # noqa: E402


class ResolveDeviceTest(unittest.TestCase):
    """Configured microphone names must survive Windows MME name padding."""

    # Windows MME caps device names at 31 characters, so an enumerated name can
    # carry trailing whitespace that the stripped, saved name does not. This is
    # the exact pair from a user's log.
    PADDED = "Microphone (3- Insta360 Link 2 "
    SAVED = "Microphone (3- Insta360 Link 2"

    def _devices(self, *names):
        return [{"name": n, "max_input_channels": 1} for n in names]

    def test_padded_device_name_still_matches(self):
        recorder = AudioRecorder(device=self.SAVED)
        with mock.patch(
            "whytype.recorder.sd.query_devices",
            return_value=self._devices("Other Mic", self.PADDED),
        ):
            self.assertEqual(
                recorder._resolve_device(),
                1,
                "a name padded by Windows MME must still match the saved one",
            )

    def test_exact_match_still_works(self):
        recorder = AudioRecorder(device="Blue Yeti")
        with mock.patch(
            "whytype.recorder.sd.query_devices",
            return_value=self._devices("Blue Yeti"),
        ):
            self.assertEqual(recorder._resolve_device(), 0)

    def test_missing_device_falls_back_to_default(self):
        recorder = AudioRecorder(device="Unplugged Mic")
        with mock.patch(
            "whytype.recorder.sd.query_devices",
            return_value=self._devices("Blue Yeti"),
        ):
            self.assertIsNone(recorder._resolve_device())

    def test_output_only_device_is_never_selected(self):
        recorder = AudioRecorder(device="Speakers")
        with mock.patch(
            "whytype.recorder.sd.query_devices",
            return_value=[{"name": "Speakers", "max_input_channels": 0}],
        ):
            self.assertIsNone(recorder._resolve_device())


if __name__ == "__main__":
    unittest.main()
