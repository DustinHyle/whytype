# -*- mode: python ; coding: utf-8 -*-
import os
import re
import sys
import glob
import sysconfig
from PyInstaller.utils.hooks import collect_all

APP_NAME = "WhyType"
DISPLAY_NAME = "Why Type"
BUNDLE_ID = "com.whytype.app"


def _version() -> str:
    text = open("whytype/__init__.py", encoding="utf-8").read()
    m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', text)
    return m.group(1) if m else "0.0.0"


datas = [('whytype/assets', 'whytype/assets'), ('whytype/bin', 'whytype/bin')]
binaries = []
hiddenimports = []

# --- Fix: put stdlib C extensions at the bundle root (macOS PyInstaller 6.x) ---
# PyInstaller 6.x places stdlib C extensions under "<pyname>/lib-dynload/",
# which is NOT on sys.path during early bootstrap — so _struct, zlib, etc. fail
# to import and the app crashes immediately ("No module named '_struct'").
# Copy every lib-dynload extension to the _MEIPASS root so the bootloader finds
# them. The path is derived from the *building* Python via sysconfig, so this is
# version-agnostic (works whether built with Python 3.11, 3.12, 3.99, ...).
_dynload = os.path.join(sysconfig.get_path('platstdlib'), 'lib-dynload')
if os.path.isdir(_dynload):
    binaries += [(so, '.') for so in glob.glob(os.path.join(_dynload, '*.so'))]

_icon = {
    'win32': 'whytype/assets/icon.ico',
    'darwin': 'whytype/assets/icon.icns',
}.get(sys.platform)

for _pkg in ('sounddevice', 'pynput', 'PySide6', 'platformdirs'):
    _d, _b, _h = collect_all(_pkg)
    datas += _d
    binaries += _b
    hiddenimports += _h


a = Analysis(
    ['whytype/__main__.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icon,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=APP_NAME,
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name=f'{APP_NAME}.app',
        icon=_icon,
        bundle_identifier=BUNDLE_ID,
        version=_version(),
        info_plist={
            'CFBundleName': DISPLAY_NAME,
            'CFBundleDisplayName': DISPLAY_NAME,
            'CFBundleShortVersionString': _version(),
            'CFBundleVersion': _version(),
            # Menu-bar / status-item app: no Dock icon.
            'LSUIElement': True,
            # Required on modern macOS or the app is killed on mic access.
            'NSMicrophoneUsageDescription':
                'Why Type needs microphone access to transcribe your speech into text.',
        },
    )
