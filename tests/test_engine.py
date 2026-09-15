"""Tests for the whisper.cpp engine's failure reporting."""

from __future__ import annotations

import subprocess
import sys
import types
import unittest
from unittest import mock

if "sounddevice" not in sys.modules:
    try:
        import sounddevice  # noqa: F401
    except Exception:
        sys.modules["sounddevice"] = types.SimpleNamespace(
            query_devices=lambda *a, **k: [], InputStream=object
        )

from whytype.engine.whispercpp_engine import WhisperCppEngine  # noqa: E402


class RunFailureTest(unittest.TestCase):
    """A failed whisper-cli run must say *how* it failed.

    A build compiled for a CPU the user does not have dies before it can write
    to stderr. The old code raised a bare "whisper-cli failed" for that, which
    was indistinguishable from an ordinary error and took a disassembler to
    diagnose. The exit code has to survive into the message.
    """

    def _run_with(self, returncode, stderr):
        engine = WhisperCppEngine.__new__(WhisperCppEngine)
        proc = subprocess.CompletedProcess(
            args=[], returncode=returncode, stdout="", stderr=stderr
        )
        with mock.patch("subprocess.run", return_value=proc):
            with self.assertRaises(RuntimeError) as ctx:
                engine._run("whisper-cli", "model.bin", "audio.wav", use_gpu=False)
        return str(ctx.exception)

    def test_illegal_instruction_is_identifiable(self):
        # 0xC000001D = STATUS_ILLEGAL_INSTRUCTION, as a signed int from Popen.
        message = self._run_with(-1073741795, "")
        self.assertIn("0xC000001D", message)
        self.assertIn("CPU", message, "must hint at a CPU-compatibility problem")

    def test_stderr_detail_is_preserved(self):
        message = self._run_with(1, "error: failed to load model\n")
        self.assertIn("failed to load model", message)
        self.assertIn("0x00000001", message)

    def test_success_returns_joined_stdout(self):
        engine = WhisperCppEngine.__new__(WhisperCppEngine)
        proc = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=" hello \n world \n", stderr=""
        )
        with mock.patch("subprocess.run", return_value=proc):
            self.assertEqual(
                engine._run("whisper-cli", "m.bin", "a.wav", use_gpu=False),
                "hello world",
            )


if __name__ == "__main__":
    unittest.main()
