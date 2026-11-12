"""The version shown on a user's computer must be the version installed.

whytype/__init__.py is the single source. The installers once hardcoded a
version string that was never updated, so Add/Remove Programs (Windows) and
Finder (macOS) showed 1.1.16 on machines running 1.2.x.
"""

from __future__ import annotations

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
_VERSION = re.compile(r"\b\d+\.\d+\.\d+\b")


class VersionTest(unittest.TestCase):
    def test_pyproject_matches_package(self):
        import whytype

        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        m = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), whytype.__version__)

    def test_installers_do_not_hardcode_a_version(self):
        for name in ("install.bat", "install.sh", "uninstall.bat", "uninstall.sh"):
            text = (ROOT / name).read_text(encoding="utf-8")
            # Python 3.12.0 is the interpreter the Windows installer
            # downloads, not Why Type's version.
            text = re.sub(r"[Pp]ython[-/ ]3\.\d+\.\d+|python-3\.\d+\.\d+", "", text)
            self.assertEqual(
                _VERSION.findall(text), [],
                f"{name} hardcodes a version; read whytype.__version__ instead",
            )


if __name__ == "__main__":
    unittest.main()
