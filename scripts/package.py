#!/usr/bin/env python3
"""Package WhyType into versioned, platform-tagged archives.

Names always carry the version and platform so the filename tells you exactly
what's inside, e.g. ``whytype-1.1.0-windows.zip``.

Two artifact types:
  * installer bundle  (default): source + installers + the bundled whisper-cli
    engine binary. The user extracts and runs install.bat / install.sh.
  * standalone        (--standalone-dir DIR): zips a PyInstaller output folder
    (no Python required on the target machine).

Usage:
    python scripts/package.py                          # installer bundle, host platform
    python scripts/package.py --platform windows
    python scripts/package.py --standalone-dir dist/WhyType
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")

# Top-level items included in the installer bundle.
BUNDLE_ITEMS = [
    "whytype",  # includes whytype/bin/<engine binary> and whytype/assets
    "scripts",
    "install.bat",
    "uninstall.bat",
    "install.sh",
    "uninstall.sh",
    "build.py",
    "WhyType.spec",
    "pyproject.toml",
    "requirements.txt",
    "README.md",
    "CHANGELOG.md",
]
SKIP_DIRS = {"__pycache__", ".venv", "build", "dist", ".git"}
SKIP_EXTS = {".pyc", ".pyo"}


def get_version() -> str:
    text = open(os.path.join(ROOT, "whytype", "__init__.py"), encoding="utf-8").read()
    m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', text)
    if not m:
        raise SystemExit("Could not read __version__ from whytype/__init__.py")
    return m.group(1)


def host_platform() -> str:
    return {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")


def _add_file(zf: zipfile.ZipFile, fp: str, arcname: str) -> None:
    """Add a file, preserving its mode but forcing shell scripts executable.

    Python's zipfile would otherwise lose the execute bit, so install.sh would
    extract non-executable (``permission denied`` when run directly).
    """
    arcname = arcname.replace(os.sep, "/")
    zi = zipfile.ZipInfo.from_file(fp, arcname)
    zi.compress_type = zipfile.ZIP_DEFLATED
    if arcname.endswith(".sh"):
        zi.external_attr = 0o755 << 16
    with open(fp, "rb") as f:
        zf.writestr(zi, f.read())


def _add_tree(zf: zipfile.ZipFile, root_item: str) -> None:
    full = os.path.join(ROOT, root_item)
    if not os.path.exists(full):
        return
    if os.path.isfile(full):
        _add_file(zf, full, root_item)
        return
    for dirpath, dirnames, filenames in os.walk(full):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if os.path.splitext(fn)[1] in SKIP_EXTS:
                continue
            fp = os.path.join(dirpath, fn)
            _add_file(zf, fp, os.path.relpath(fp, ROOT))


def build_bundle(platform: str, version: str) -> str:
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, f"whytype-{version}-{platform}.zip")
    if os.path.exists(out):
        os.remove(out)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in BUNDLE_ITEMS:
            _add_tree(zf, item)
    return out


def build_standalone(src_dir: str, platform: str, version: str) -> str:
    if not os.path.isdir(src_dir):
        raise SystemExit(f"Standalone dir not found: {src_dir}")
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, f"whytype-{version}-{platform}-standalone.zip")
    if os.path.exists(out):
        os.remove(out)
    parent = os.path.dirname(os.path.abspath(src_dir))
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirpath, dirnames, filenames in os.walk(src_dir):
            for fn in filenames:
                fp = os.path.join(dirpath, fn)
                zf.write(fp, os.path.relpath(fp, parent))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--platform", choices=["windows", "macos", "linux"],
                    default=host_platform())
    ap.add_argument("--standalone-dir", default=None,
                    help="Zip this PyInstaller output folder instead of the bundle.")
    args = ap.parse_args()
    version = get_version()

    if args.standalone_dir:
        out = build_standalone(args.standalone_dir, args.platform, version)
    else:
        out = build_bundle(args.platform, version)
        bindir = os.path.join(ROOT, "whytype", "bin")
        has_bin = os.path.isdir(bindir) and any(
            f.startswith("whisper-cli") for f in os.listdir(bindir)
        )
        if not has_bin:
            print("WARNING: no whisper-cli engine binary in whytype/bin/ — "
                  "run scripts/build_whispercpp.py before packaging.")

    print(f"Wrote {out} ({os.path.getsize(out) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
