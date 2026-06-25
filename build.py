#!/usr/bin/env python3
"""
Build Why Type into a standalone executable using PyInstaller.

Usage:
    python build.py           # Build a folder (faster startup, recommended)
    python build.py --onefile # Build a single executable (slower startup)
    python build.py clean     # Remove build artifacts
"""
import os
import sys
import shutil
import subprocess

APP_NAME = "WhyType"
DISPLAY_NAME = "Why Type"
BUNDLE_ID = "com.whytype.app"
ENTRY_POINT = "whytype/__main__.py"


def _read_version() -> str:
    import re
    text = open("whytype/__init__.py", encoding="utf-8").read()
    m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', text)
    return m.group(1) if m else "0.0.0"


def _post_process_macos_app() -> None:
    """Make the PyInstaller .app a proper macOS app: menu-bar agent, mic
    permission string, display name, and an ad-hoc signature so it launches.
    """
    import plistlib

    app = f"dist/{APP_NAME}.app"
    plist_path = os.path.join(app, "Contents", "Info.plist")
    if not os.path.exists(plist_path):
        print(f"WARNING: {plist_path} not found; skipping Info.plist patch.")
        return

    with open(plist_path, "rb") as f:
        info = plistlib.load(f)
    info["CFBundleName"] = DISPLAY_NAME
    info["CFBundleDisplayName"] = DISPLAY_NAME
    info["CFBundleIdentifier"] = BUNDLE_ID
    info["CFBundleShortVersionString"] = _read_version()
    info["CFBundleVersion"] = _read_version()
    # Menu-bar / status-item app: no Dock icon.
    info["LSUIElement"] = True
    # Required on modern macOS or the app is killed on mic access.
    info["NSMicrophoneUsageDescription"] = (
        "Why Type needs microphone access to transcribe your speech into text."
    )
    with open(plist_path, "wb") as f:
        plistlib.dump(info, f)
    print("Patched Info.plist (LSUIElement, mic permission, display name).")

    # Ad-hoc code signature — required for a downloaded unsigned app to launch
    # on Apple Silicon (hardened runtime). Not notarized; users still right-
    # click → Open the first time.
    try:
        subprocess.check_call(
            ["codesign", "--force", "--deep", "--sign", "-", app]
        )
        print("Ad-hoc signed the app bundle.")
    except Exception as e:  # codesign missing or failed — non-fatal
        print(f"WARNING: ad-hoc codesign failed ({e}); app may need manual Gatekeeper approval.")


def clean() -> None:
    print("Cleaning build artifacts...")
    for d in ["build", "dist"]:
        if os.path.isdir(d):
            shutil.rmtree(d)
    for f in [f"{APP_NAME}.spec"]:
        if os.path.exists(f):
            os.remove(f)
    print("Clean complete.")


def build(onefile: bool = False) -> None:
    try:
        import PyInstaller
    except ImportError:
        print("PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    mode_flag = "--onefile" if onefile else "--onedir"

    # Bundle the app icon assets + the native whisper-cli binary, and use the
    # platform icon for the executable.
    add_data = [
        f"whytype/assets{os.pathsep}whytype/assets",
        f"whytype/bin{os.pathsep}whytype/bin",
    ]
    icon = {
        "win32": "whytype/assets/icon.ico",
        "darwin": "whytype/assets/icon.icns",
    }.get(sys.platform)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        APP_NAME,
        "--noconfirm",
        "--clean",
        "--windowed",
        "--osx-bundle-identifier",
        BUNDLE_ID,
        mode_flag,
        # Include all package data to avoid missing files at runtime
        "--collect-all",
        "sounddevice",
        "--collect-all",
        "pynput",
        "--collect-all",
        "PySide6",
        "--collect-all",
        "platformdirs",
        ENTRY_POINT,
    ]

    for d in add_data:
        cmd[-1:-1] = ["--add-data", d]
    if icon:
        cmd[-1:-1] = ["--icon", icon]

    print("Building with PyInstaller...")
    print(" ".join(cmd))
    print("")
    subprocess.check_call(cmd)

    if sys.platform == "darwin" and not onefile:
        _post_process_macos_app()

    print("")
    if onefile:
        ext = ".exe" if sys.platform == "win32" else ""
        print(f"Build complete: dist/{APP_NAME}{ext}")
    else:
        folder = f"dist/{APP_NAME}"
        print(f"Build complete: {folder}/")
        if sys.platform == "win32":
            print(f"Run it: {folder}\\{APP_NAME}.exe")
        elif sys.platform == "darwin":
            print(f"Run it: open dist/{APP_NAME}.app")
        else:
            print(f"Run it: {folder}/{APP_NAME}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "clean" in args:
        clean()
    else:
        build(onefile="--onefile" in args)
