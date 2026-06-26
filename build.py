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


def _fix_macos_libdynload(app: str) -> None:
    """Copy stdlib C extensions to the bundle root so the app launches.

    PyInstaller 6.x places stdlib C extensions under
    Contents/Frameworks/<pyname>/lib-dynload/, which is NOT searched during the
    bootloader's early bootstrap — so the app crashes with "No module named
    '_struct'". Setting them as binaries in the spec doesn't help because
    PyInstaller relocates Python extensions back to lib-dynload. So copy them
    up to Contents/Frameworks/ (the _MEIPASS root) directly. Version-agnostic:
    we glob whatever lib-dynload directory exists.
    """
    import glob
    frameworks = os.path.join(app, "Contents", "Frameworks")
    dynload_dirs = glob.glob(os.path.join(frameworks, "*", "lib-dynload"))
    if not dynload_dirs:
        print("WARNING: no lib-dynload directory found; cannot apply _struct fix.")
        return
    copied = 0
    for d in dynload_dirs:
        for so in glob.glob(os.path.join(d, "*.so")):
            dest = os.path.join(frameworks, os.path.basename(so))
            if not os.path.exists(dest):
                shutil.copy2(so, dest)
                copied += 1
    print(f"Copied {copied} stdlib C extensions to the bundle root (lib-dynload fix).")


def _post_process_macos_app() -> None:
    """Apply the lib-dynload fix, then ad-hoc sign so it launches on Apple
    Silicon. The Info.plist is set by the spec's BUNDLE() step.
    """
    app = f"dist/{APP_NAME}.app"
    if not os.path.isdir(app):
        print(f"WARNING: {app} not found; skipping macOS post-processing.")
        return
    _fix_macos_libdynload(app)
    # Sign AFTER copying files in, or the signature is invalidated.
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
        _post_process_macos_app()

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
