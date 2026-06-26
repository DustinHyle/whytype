#!/usr/bin/env python3
"""
Build Why Type into a standalone app/executable from WhyType.spec.

Usage:
    python build.py        # Build from WhyType.spec (recommended)
    python build.py clean   # Remove build artifacts
"""
import os
import sys
import shutil
import subprocess

APP_NAME = "WhyType"


def _codesign_macos_app() -> None:
    """Ad-hoc sign the .app so it launches on Apple Silicon (hardened runtime).

    The Info.plist (LSUIElement, mic permission, names) is set by the spec's
    BUNDLE() step, so it doesn't need patching here. Not notarized; users still
    approve it once via System Settings → Privacy & Security.
    """
    app = f"dist/{APP_NAME}.app"
    if not os.path.isdir(app):
        print(f"WARNING: {app} not found; skipping codesign.")
        return
    try:
        subprocess.check_call(["codesign", "--force", "--deep", "--sign", "-", app])
        print("Ad-hoc signed the app bundle.")
    except Exception as e:  # codesign missing or failed — non-fatal
        print(f"WARNING: ad-hoc codesign failed ({e}); app may need manual Gatekeeper approval.")


def clean() -> None:
    print("Cleaning build artifacts...")
    # Note: WhyType.spec is hand-written source — never delete it.
    for d in ["build", "dist"]:
        if os.path.isdir(d):
            shutil.rmtree(d)
    print("Clean complete.")


def build() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # Build from WhyType.spec — the single source of truth. The spec carries
    # the macOS lib-dynload fix (stdlib C extensions at the bundle root, so
    # _struct/zlib load at bootstrap) and the .app Info.plist, version-agnostic.
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "WhyType.spec",
    ]
    print("Building from WhyType.spec ...")
    print(" ".join(cmd))
    print("")
    subprocess.check_call(cmd)

    if sys.platform == "darwin":
        _codesign_macos_app()

    print("")
    if sys.platform == "win32":
        print(f"Build complete: dist/{APP_NAME}/{APP_NAME}.exe")
    elif sys.platform == "darwin":
        print(f"Build complete: open dist/{APP_NAME}.app")
    else:
        print(f"Build complete: dist/{APP_NAME}/{APP_NAME}")


if __name__ == "__main__":
    if "clean" in sys.argv[1:]:
        clean()
    else:
        build()
