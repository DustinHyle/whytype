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

# --- Trim unused Qt modules ---
# PySide6 ships ~100 Qt modules; Why Type imports only QtCore, QtGui and
# QtWidgets. Collecting them all put a 227 MB copy of Chromium
# (QtWebEngineCore) into the macOS .app — four times over, once the framework
# symlinks were resolved. Two things are needed: `excludes` below keeps those
# modules out of the dependency graph so the PySide6 hook never collects them,
# and this filter is the safety net for a library that still arrives as a
# dependency of one we keep.
# Note the optional "6": macOS names frameworks QtWebEngineCore.framework,
# while Linux/Windows name the shared libraries libQt6WebEngineCore.so.6.
_QT_DROP = re.compile(
    r"""Qt6?(3D|Bluetooth|Canvas|Charts|DataVisualization|Designer|Graphs
        |Help|HttpServer|Labs|Location|Lottie|Multimedia|NetworkAuth|Nfc|Pdf
        |Positioning|Qml|Quick|RemoteObjects|Scxml|Sensors|SerialBus
        |SerialPort|ShaderTools|SpatialAudio|Sql|Test|TextToSpeech
        |VirtualKeyboard|Web)""",
    re.VERBOSE,
)
# Payloads that ride along with those modules but are not named "Qt*".
# libicudata is deliberately NOT listed: QtCore links it for text handling on
# Linux, so dropping it to save 30 MB would break the app.
_EXTRA_DROP = re.compile(
    r"(qtwebengine|icudtl\.dat|libffmpeg|/qml/|qmlls|qmlformat)", re.I
)


def _keep(entry) -> bool:
    """True if a collected (src, dest) entry belongs in the bundle."""
    paths = [p for p in entry[:2] if isinstance(p, str)]
    return not any(_QT_DROP.search(p) or _EXTRA_DROP.search(p) for p in paths)


# PySide6 is deliberately NOT collect_all'd: its PyInstaller hook already
# collects the Qt libraries for whichever PySide6.Qt* modules actually enter
# the dependency graph, and collect_all defeats that by dragging in all ~100.
_packages = ['sounddevice', 'pynput', 'platformdirs']
if sys.platform == 'win32':
    # Core Audio mute (mute-while-recording). COM interfaces are resolved
    # dynamically, so collect_all is needed to bundle them.
    _packages += ['pycaw', 'comtypes']

for _pkg in _packages:
    _d, _b, _h = collect_all(_pkg)
    datas += _d
    binaries += _b
    hiddenimports += _h

# Keep the excluded Qt modules out of the dependency graph, so the PySide6
# hook never collects their libraries in the first place.
excludes = ['PySide6.' + m for m in (
    'Qt3DAnimation', 'Qt3DCore', 'Qt3DExtras', 'Qt3DInput', 'Qt3DLogic',
    'Qt3DRender', 'QtBluetooth', 'QtCharts', 'QtDataVisualization',
    'QtDesigner', 'QtGraphs', 'QtHelp', 'QtHttpServer', 'QtLocation',
    'QtMultimedia', 'QtMultimediaWidgets', 'QtNetworkAuth', 'QtNfc',
    'QtPdf', 'QtPdfWidgets', 'QtPositioning', 'QtQml', 'QtQuick',
    'QtQuick3D', 'QtQuickControls2', 'QtQuickWidgets', 'QtRemoteObjects',
    'QtScxml', 'QtSensors', 'QtSerialBus', 'QtSerialPort', 'QtSpatialAudio',
    'QtSql', 'QtTest', 'QtTextToSpeech', 'QtWebChannel', 'QtWebEngineCore',
    'QtWebEngineQuick', 'QtWebEngineWidgets', 'QtWebSockets', 'QtWebView',
)]


def _trim(entries):
    return [e for e in entries if _keep(e)]


a = Analysis(
    ['whytype/__main__.py'],
    pathex=[],
    binaries=_trim(binaries),
    datas=_trim(datas),
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
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
