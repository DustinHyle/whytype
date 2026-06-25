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
ENTRY_POINT = "whytype/__main__.py"


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
