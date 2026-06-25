"""Main application entry point for WhyType.

Manages the system tray, global hotkey listener, audio recording,
transcription, and text typing pipeline.
"""

from __future__ import annotations

import os
import sys
import threading
from typing import Optional

from whytype.config import Config
from whytype.logger import setup_logging

logger = setup_logging()

# --- Import-order workaround: pynput/six before PySide6 ---
# pynput depends on `six`, whose `_SixMetaPathImporter` crashes PySide6's
# `__feature__` (shibokensupport) import hook with:
#   AttributeError: '_SixMetaPathImporter' object has no attribute '_path'
# The crash happens while executing `from six.moves import queue` inside
# pynput. Importing pynput here — BEFORE PySide6 installs its hook — runs that
# statement hook-free; later (cached) imports never re-execute it. Without this
# the app fails to start on some PySide6/six version combinations.
try:
    import pynput  # noqa: F401
    import pynput.keyboard  # noqa: F401
except Exception:
    # If pynput genuinely can't import, the graceful check below reports it.
    pass


def _patch_pynput_macos15() -> None:
    """Cache pynput's keycode_context result so the listener thread never calls
    TISGetInputSourceProperty from a background thread.

    macOS 15+ added dispatch_assert_queue(main_queue) inside
    islGetInputSourceListWithAdditions (called by TISGetInputSourceProperty),
    causing pynput's keyboard Listener to crash on startup (EXC_BREAKPOINT /
    SIGTRAP in the listener thread). The context value is stable for the
    lifetime of the process, so caching it — populated on the main thread — is
    safe and keeps the background listener thread away from TSM.
    """
    if sys.platform != "darwin":
        return
    try:
        import contextlib as _cl
        from pynput._util import darwin as _pd
        import pynput.keyboard._darwin as _kd

        _cache: list = [None]
        _orig = _pd.keycode_context

        @_cl.contextmanager
        def _cached_keycode_context():
            if _cache[0] is not None:
                yield _cache[0]
                return
            with _orig() as ctx:
                _cache[0] = ctx
                yield ctx

        # Patch both names: keyboard._darwin binds keycode_context at import
        # time (`from pynput._util.darwin import keycode_context`), so patching
        # only the source module would not affect the listener's reference.
        _pd.keycode_context = _cached_keycode_context
        _kd.keycode_context = _cached_keycode_context
        logger.debug("Applied pynput macOS 15 TSM main-thread patch")
    except Exception:
        logger.debug("Could not apply pynput macOS 15 patch (non-fatal)", exc_info=True)


_patch_pynput_macos15()


def _set_macos_app_name() -> None:
    """Show "Why Type" (not "Python") in the macOS menu bar and Dock tooltip.

    Because the app runs under the venv's python interpreter, macOS labels it
    "Python" by default. Patching the running bundle's info dictionary at
    startup — before Qt creates the NSApplication — relabels it. (Permission
    dialogs are governed by the on-disk bundle and may still differ unless the
    app is packaged as a proper signed .app.)
    """
    if sys.platform != "darwin":
        return
    try:
        from Foundation import NSBundle

        bundle = NSBundle.mainBundle()
        if bundle is None:
            return
        info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
        if info is not None:
            info["CFBundleName"] = "Why Type"
            info["CFBundleDisplayName"] = "Why Type"
    except Exception:
        logger.debug("Could not set macOS app name", exc_info=True)


# --- Single-instance enforcement (cross-platform) ---
# Windows uses a named mutex; POSIX uses an exclusive lock on a lockfile.
# Strong references are kept at module scope so the lock lives for the
# lifetime of the process.
_MUTEX_HANDLE: Optional[int] = None
_LOCK_FILE = None


def _enforce_single_instance() -> None:
    """Exit early if another copy of Why Type is already running."""
    global _MUTEX_HANDLE, _LOCK_FILE
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            _Mutex = ctypes.windll.kernel32.CreateMutexW
            _Mutex.argtypes = [wintypes.LPCVOID, wintypes.BOOL, wintypes.LPCWSTR]
            _Mutex.restype = wintypes.HANDLE
            _MUTEX_HANDLE = _Mutex(None, False, "WhyType_SingleInstance_Mutex")
            if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
                print("Why Type is already running. Look for the tray icon.", file=sys.stderr)
                sys.exit(0)
        except Exception:
            pass
    else:
        try:
            import fcntl
            from platformdirs import user_runtime_dir

            lock_dir = user_runtime_dir("WhyType") or "/tmp"
            os.makedirs(lock_dir, exist_ok=True)
            _LOCK_FILE = open(os.path.join(lock_dir, "whytype.lock"), "w")
            fcntl.flock(_LOCK_FILE, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, BlockingIOError):
            print("Why Type is already running. Look for the tray icon.", file=sys.stderr)
            sys.exit(0)
        except Exception:
            pass


def _icon_path() -> Optional[str]:
    """Absolute path to the bundled app icon, or None if unavailable.

    Resolves correctly both when running from source and when frozen by
    PyInstaller (where data files live under sys._MEIPASS).
    """
    if getattr(sys, "frozen", False):
        base = os.path.join(
            getattr(sys, "_MEIPASS", os.path.dirname(sys.executable)),
            "whytype",
            "assets",
        )
    else:
        base = os.path.join(os.path.dirname(__file__), "assets")
    path = os.path.join(base, "icon.png")
    return path if os.path.exists(path) else None


# --- Graceful dependency imports ---
# Each optional dependency is wrapped so that a missing or broken library
# produces a clear error message instead of a raw traceback.

_PYSIDE6_ERROR: Optional[str] = None
_QT_CLASSES = {}
try:
    from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox, QDialog
    from PySide6.QtGui import QIcon, QAction, QCursor, QPixmap
    from PySide6.QtCore import QObject, Signal, Qt, QTimer
    _QT_CLASSES["QApplication"] = QApplication
    _QT_CLASSES["QSystemTrayIcon"] = QSystemTrayIcon
    _QT_CLASSES["QMenu"] = QMenu
    _QT_CLASSES["QMessageBox"] = QMessageBox
    _QT_CLASSES["QDialog"] = QDialog
    _QT_CLASSES["QIcon"] = QIcon
    _QT_CLASSES["QAction"] = QAction
    _QT_CLASSES["QCursor"] = QCursor
    _QT_CLASSES["QPixmap"] = QPixmap
    _QT_CLASSES["QObject"] = QObject
    _QT_CLASSES["Signal"] = Signal
    _QT_CLASSES["Qt"] = Qt
    _QT_CLASSES["QTimer"] = QTimer
except Exception as exc:
    _PYSIDE6_ERROR = str(exc)
    logger.exception("PySide6 import failed")

_PYNPUT_ERROR: Optional[str] = None
_PYNPUT_CLASSES = {}
try:
    from pynput.keyboard import Key, Listener
    _PYNPUT_CLASSES["Key"] = Key
    _PYNPUT_CLASSES["Listener"] = Listener
except Exception as exc:
    _PYNPUT_ERROR = str(exc)
    logger.exception("pynput import failed")

_RECORDER_ERROR: Optional[str] = None
try:
    from whytype.recorder import AudioRecorder
except Exception as exc:
    _RECORDER_ERROR = str(exc)
    logger.exception("recorder import failed")

_TRANSCRIBER_ERROR: Optional[str] = None
try:
    from whytype.engine import TranscriptionEngine, create_engine
except Exception as exc:
    _TRANSCRIBER_ERROR = str(exc)
    logger.exception("transcriber import failed")

_TYPER_ERROR: Optional[str] = None
try:
    from whytype.typer import TextTyper
except Exception as exc:
    _TYPER_ERROR = str(exc)
    logger.exception("typer import failed")

_UI_ERROR: Optional[str] = None
try:
    from whytype.ui.settings_dialog import SettingsDialog
except Exception as exc:
    _UI_ERROR = str(exc)
    logger.exception("UI import failed")


# Only define these if pynput loaded successfully
if _PYNPUT_CLASSES:
    Key = _PYNPUT_CLASSES["Key"]
    Listener = _PYNPUT_CLASSES["Listener"]

    SPECIAL_KEYS = {
        "space": Key.space,
        "tab": Key.tab,
        "enter": Key.enter,
        "return": Key.enter,
        "esc": Key.esc,
        "escape": Key.esc,
        "up": Key.up,
        "down": Key.down,
        "left": Key.left,
        "right": Key.right,
        "home": Key.home,
        "end": Key.end,
        "pageup": Key.page_up,
        "pagedown": Key.page_down,
        "delete": Key.delete,
        # Key.insert does not exist in pynput on macOS; including it
        # unconditionally would raise AttributeError at import time (before
        # logging is set up) and crash the app silently on launch.
        **({"insert": Key.insert} if hasattr(Key, "insert") else {}),
        "backspace": Key.backspace,
        "f1": Key.f1,
        "f2": Key.f2,
        "f3": Key.f3,
        "f4": Key.f4,
        "f5": Key.f5,
        "f6": Key.f6,
        "f7": Key.f7,
        "f8": Key.f8,
        "f9": Key.f9,
        "f10": Key.f10,
        "f11": Key.f11,
        "f12": Key.f12,
    }

    # Modifier name aliases are normalized to a canonical token so that, e.g.,
    # "win"/"super"/"cmd" (which share the same physical key) compare equal.
    _MOD_ALIASES = {
        "ctrl": "ctrl",
        "control": "ctrl",
        "shift": "shift",
        "alt": "alt",
        "opt": "alt",
        "option": "alt",
        "cmd": "meta",
        "command": "meta",
        "super": "meta",
        "win": "meta",
        "meta": "meta",
    }

    # Canonical modifier token -> set of pynput keys that satisfy it.
    MODIFIER_KEYS = {
        "ctrl": {Key.ctrl, Key.ctrl_l, Key.ctrl_r},
        "shift": {Key.shift, Key.shift_l, Key.shift_r},
        "alt": {Key.alt, Key.alt_l, Key.alt_r, Key.alt_gr},
        "meta": {Key.cmd, Key.cmd_l, Key.cmd_r},
    }

    def _parse_shortcut(shortcut_str: str) -> tuple[set[str], Optional[str]]:
        parts = [p.strip().lower() for p in shortcut_str.split("+") if p.strip()]
        modifiers = set()
        key = None
        for p in parts:
            if p in _MOD_ALIASES:
                modifiers.add(_MOD_ALIASES[p])
            else:
                key = p
        return modifiers, key

    def _key_to_name(key: Key) -> Optional[str]:
        for name, pynput_key in SPECIAL_KEYS.items():
            if key == pynput_key:
                return name
        try:
            return key.char.lower()
        except AttributeError:
            return None
else:
    SPECIAL_KEYS = {}
    MODIFIER_KEYS = {}

    def _parse_shortcut(shortcut_str: str) -> tuple[set[str], Optional[str]]:
        return set(), None

    def _key_to_name(key) -> Optional[str]:
        return None


class Signaler(QObject):
    """Qt signal bridge for cross-thread communication."""

    start_recording = Signal()
    stop_recording = Signal()
    transcribe_done = Signal(str)
    transcribe_failed = Signal(str)
    typing_done = Signal()
    show_settings = Signal()
    status_changed = Signal(str)


class WhyTypeApp:
    """Core application managing tray, hotkeys, recording, and transcription."""

    def __init__(self, settings_only: bool = False) -> None:
        self._settings_only = settings_only
        self._deps_ok = self._check_dependencies()
        if not self._deps_ok:
            sys.exit(1)

        _set_macos_app_name()  # relabel "Python" -> "Why Type" before NSApplication

        QApplication = _QT_CLASSES["QApplication"]
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.app.setApplicationName("Why Type")
        self.app.setApplicationDisplayName("Why Type")
        _app_icon_path = _icon_path()
        if _app_icon_path:
            self.app.setWindowIcon(_QT_CLASSES["QIcon"](_app_icon_path))

        self.config = Config()
        self._auto_select_model()
        self.recorder = AudioRecorder(device=self.config.input_device or None)
        self.typer = TextTyper()
        self.transcriber: Optional[TranscriptionEngine] = None
        self._accel_status = "CPU"
        self._load_transcriber()

        self.signaler = Signaler()
        self.signaler.start_recording.connect(self._on_start_recording)
        self.signaler.stop_recording.connect(self._on_stop_recording)
        self.signaler.transcribe_done.connect(self._on_transcribe_done)
        self.signaler.transcribe_failed.connect(self._on_transcribe_failed)
        self.signaler.typing_done.connect(self._on_typing_done)
        self.signaler.show_settings.connect(self._show_settings)
        self.signaler.status_changed.connect(self._update_status)

        self._state = "idle"  # idle, recording, transcribing, typing
        self._listener: Optional[Listener] = None
        self._pressed_modifiers: set[Key] = set()
        self._shortcut_triggered = False

        self.tray_icon: Optional[QSystemTrayIcon] = None
        self._tray_menu: Optional[QMenu] = None
        self._build_tray()
        self._apply_device()

    def _auto_select_model(self) -> None:
        """If no model is configured but models are downloaded, auto-select one."""
        if not self.config.model:
            from whytype.models import get_downloaded_models
            downloaded = get_downloaded_models()
            if downloaded:
                self.config.model = downloaded[0]
                self.config.save()
                logger.info("Auto-selected model: %s", downloaded[0])

    def _check_dependencies(self) -> bool:
        """Verify all runtime dependencies are available. Return False on fatal errors."""
        fatal = []
        if _PYSIDE6_ERROR:
            fatal.append(f"GUI library (PySide6) failed to load:\n{_PYSIDE6_ERROR}")
        if _PYNPUT_ERROR:
            fatal.append(
                f"Keyboard input library (pynput) failed to load:\n{_PYNPUT_ERROR}\n\n"
                "Linux: make sure you are running under X11 (not Wayland), "
                "or add your user to the 'input' group.\n"
                "macOS: grant Accessibility permission when prompted."
            )
        if _RECORDER_ERROR:
            fatal.append(
                f"Audio library failed to load:\n{_RECORDER_ERROR}\n\n"
                "Linux: install PortAudio (sudo apt install libportaudio2).\n"
                "macOS: install PortAudio (brew install portaudio)."
            )
        if _TRANSCRIBER_ERROR:
            fatal.append(f"Transcription library failed to load:\n{_TRANSCRIBER_ERROR}")
        if _TYPER_ERROR:
            fatal.append(f"Text typing library failed to load:\n{_TYPER_ERROR}")
        if _UI_ERROR:
            fatal.append(f"Settings UI failed to load:\n{_UI_ERROR}")

        if fatal:
            msg = "Why Type cannot start because required components are missing:\n\n"
            msg += "\n\n".join(f"• {err}" for err in fatal)
            # Try to show a GUI error; fall back to console if Qt is broken
            if _QT_CLASSES:
                QMessageBox = _QT_CLASSES["QMessageBox"]
                QMessageBox.critical(None, "Why Type - Startup Error", msg)
            else:
                print(msg, file=sys.stderr)
            logger.error("Startup dependency check failed: %s", fatal)
            return False

        logger.info("All dependencies loaded successfully")
        return True

    def _load_transcriber(self) -> None:
        try:
            self.transcriber = create_engine(
                model_name=self.config.model,
                custom_path=self.config.custom_model_path or None,
            )
            err = self.transcriber.load_error()
            if err:
                # Not fatal at construction time; surfaced when the user tries
                # to record or after a settings change, with proper context.
                logger.error("Transcription model failed to load: %s", err)
            else:
                logger.info("Transcriber loaded (model=%s)", self.config.effective_model())
        except Exception:
            logger.exception("Failed to construct transcriber")
            self.transcriber = None

    def _apply_device(self) -> None:
        """Resolve the configured device against real hardware and apply it.

        For "auto"/"gpu" we probe the GPU and fall back to CPU if it is not
        usable — this is what makes flaky integrated GPUs safe. The resulting
        human-readable status is stored for the Settings readout.
        """
        choice = self.config.device
        if self.transcriber is None or not self.transcriber.is_ready():
            self._accel_status = {
                "cpu": "CPU",
                "gpu": "GPU (set once a model is installed)",
            }.get(choice, "Automatic")
            return

        if choice == "cpu":
            self.transcriber.set_device("cpu")
            self._accel_status = "CPU"
            return

        gpu_ok, label = self.transcriber.probe_backend()
        if gpu_ok:
            self.transcriber.set_device("gpu")
            self._accel_status = f"GPU ({label})"
            logger.info("Using GPU acceleration: %s", label)
        else:
            self.transcriber.set_device("cpu")
            if choice == "gpu":
                self._accel_status = "CPU (no usable GPU found)"
                logger.warning("GPU requested but unavailable; using CPU")
                if self.tray_icon is not None and self.tray_icon.supportsMessages():
                    QSystemTrayIcon = _QT_CLASSES["QSystemTrayIcon"]
                    self.tray_icon.showMessage(
                        "Why Type - GPU unavailable",
                        "No usable GPU was found; falling back to CPU. "
                        "You can switch to CPU in Settings to hide this.",
                        QSystemTrayIcon.MessageIcon.Warning,
                        8000,
                    )
            else:
                self._accel_status = "CPU (automatic)"
            logger.info("Using CPU for transcription")

    def _app_icon(self):
        """Return the branded app icon, falling back to a theme/standard icon."""
        QIcon = _QT_CLASSES["QIcon"]
        path = _icon_path()
        if path:
            icon = QIcon(path)
            if not icon.isNull():
                return icon
        icon = QIcon.fromTheme("audio-input-microphone")
        if icon.isNull():
            icon = self.app.style().standardIcon(
                self.app.style().StandardPixmap.SP_MessageBoxInformation
            )
        return icon

    def _tray_qicon(self):
        """Build a QIcon with menu-bar-sized pixmaps.

        The bundled icon.png is 256x256. QSystemTrayIcon does not reliably
        downscale one large pixmap to menu-bar size on macOS (it renders far
        too large and clips to invisibility, or doesn't show at all). Adding
        explicitly scaled pixmaps (22/44/88) gives Qt the resolutions the menu
        bar picks at 1x / 2x / 3x.
        """
        QIcon = _QT_CLASSES["QIcon"]
        QPixmap = _QT_CLASSES["QPixmap"]
        Qt = _QT_CLASSES["Qt"]
        path = _icon_path()
        if not path:
            return self._app_icon()
        base = QPixmap(path)
        if base.isNull():
            return self._app_icon()
        icon = QIcon()
        for size in (22, 44, 88):
            icon.addPixmap(base.scaled(
                size, size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        return icon

    def _build_tray(self) -> None:
        QSystemTrayIcon = _QT_CLASSES["QSystemTrayIcon"]
        QAction = _QT_CLASSES["QAction"]

        self.tray_icon = QSystemTrayIcon(self.app)
        self.tray_icon.setIcon(self._tray_qicon())
        self.tray_icon.setToolTip("Why Type")

        # Build menu explicitly and keep strong references to EVERYTHING
        self._tray_menu = QMenu()
        self._status_action = QAction("Status: Ready", self._tray_menu)
        self._status_action.setEnabled(False)
        self._tray_menu.addAction(self._status_action)
        self._tray_menu.addSeparator()

        self._settings_action = QAction("Settings...", self._tray_menu)
        self._settings_action.triggered.connect(self.signaler.show_settings)
        self._tray_menu.addAction(self._settings_action)

        self._quit_action = QAction("Quit", self._tray_menu)
        self._quit_action.triggered.connect(self.quit)
        self._tray_menu.addAction(self._quit_action)

        # Do NOT use setContextMenu — it is unreliable on Windows 11.
        # Instead handle activation manually and popup the menu ourselves.
        self.tray_icon.activated.connect(self._tray_activated)
        self.tray_icon.show()

        # Diagnostic: a geometry of (0, <screen_height>, 38, 0) means the icon
        # was created but never placed in the menu bar (the macOS LaunchServices
        # bundle-identity bug). A real rect means it's visible.
        logger.info(
            "Tray icon: available=%s visible=%s geometry=%s",
            QSystemTrayIcon.isSystemTrayAvailable(),
            self.tray_icon.isVisible(),
            self.tray_icon.geometry(),
        )

        # Show a startup notification so the user knows the app is running
        if self.tray_icon.supportsMessages():
            self.tray_icon.showMessage(
                "Why Type is running",
                f"Shortcut: {self.config.shortcut}\nRight-click the tray icon for Settings or Quit.",
                QSystemTrayIcon.MessageIcon.Information,
                8000,
            )

    def _tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Context:
            # Manual popup — more reliable than setContextMenu on Windows 11
            QCursor = _QT_CLASSES["QCursor"]
            self._tray_menu.popup(QCursor.pos())
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.signaler.show_settings.emit()

    def _update_status(self, status: str) -> None:
        if self._status_action is not None:
            self._status_action.setText(f"Status: {status}")
        self.tray_icon.setToolTip(f"Why Type — {status}")
        logger.info("Status: %s", status)

    def _show_error(self, message: str) -> None:
        QMessageBox = _QT_CLASSES["QMessageBox"]
        QMessageBox.critical(None, "Why Type - Error", message)
        logger.error(message)

    def _start_listener(self) -> None:
        self._stop_listener()
        self._pressed_modifiers = set()
        self._shortcut_triggered = False
        try:
            self._listener = Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release,
            )
            self._listener.start()
            logger.info("Global hotkey listener started")
        except Exception as e:
            logger.exception("Failed to start global hotkey listener")
            self._show_error(
                f"Failed to start global hotkey listener:\n{e}\n\n"
                "Linux: Try running under X11 or add your user to the 'input' group.\n"
                "macOS: Grant Accessibility permission in System Settings."
            )

    def _stop_listener(self) -> None:
        if self._listener is not None:
            listener = self._listener
            self._listener = None
            listener.stop()
            listener.join(timeout=2.0)
            logger.info("Global hotkey listener stopped")

    def _check_shortcut_match(self) -> bool:
        if not _PYNPUT_CLASSES:
            return False
        modifiers, key = _parse_shortcut(self.config.shortcut)
        if not modifiers and not key:
            return False

        active_mods = set()
        for mod_name, keys in MODIFIER_KEYS.items():
            if self._pressed_modifiers & keys:
                active_mods.add(mod_name)
        if active_mods != modifiers:
            return False

        if key is None:
            return True

        for k in self._pressed_modifiers:
            name = _key_to_name(k)
            if name == key:
                return True
            if key in SPECIAL_KEYS and k == SPECIAL_KEYS[key]:
                return True
        return False

    def _on_key_press(self, key: Key) -> None:
        self._pressed_modifiers.add(key)
        if self._shortcut_triggered:
            return
        if self._check_shortcut_match():
            self._shortcut_triggered = True
            mode = self.config.recording_mode
            if mode == "hold":
                if self._state == "idle":
                    self.signaler.start_recording.emit()
            elif mode == "toggle":
                if self._state == "idle":
                    self.signaler.start_recording.emit()
                elif self._state == "recording":
                    self.signaler.stop_recording.emit()

    def _on_key_release(self, key: Key) -> None:
        self._pressed_modifiers.discard(key)
        if not self._shortcut_triggered:
            return

        modifiers, target_key = _parse_shortcut(self.config.shortcut)
        released_target = False

        if target_key:
            if target_key in SPECIAL_KEYS:
                if key == SPECIAL_KEYS[target_key]:
                    released_target = True
            else:
                try:
                    if key.char and key.char.lower() == target_key:
                        released_target = True
                except AttributeError:
                    pass
        else:
            released_target = True

        still_holding = False
        for mod_name in modifiers:
            if self._pressed_modifiers & MODIFIER_KEYS.get(mod_name, set()):
                still_holding = True
                break

        if released_target or not still_holding:
            self._shortcut_triggered = False
            if self.config.recording_mode == "hold" and self._state == "recording":
                self.signaler.stop_recording.emit()

    def _on_start_recording(self) -> None:
        if self._state != "idle":
            return

        if self.transcriber is None or not self.transcriber.is_ready():
            self.signaler.status_changed.emit("Loading model...")
            self.app.processEvents()
            self._load_transcriber()
            self._apply_device()

        if self.transcriber is None or not self.transcriber.is_ready():
            self.signaler.status_changed.emit("Ready")
            load_error = self.transcriber.load_error() if self.transcriber else None
            if load_error:
                self._show_error(
                    "The transcription model failed to load:\n\n"
                    f"{load_error}\n\n"
                    "Try re-downloading it or selecting a different model in Settings."
                )
            else:
                QMessageBox = _QT_CLASSES["QMessageBox"]
                QMessageBox.information(
                    None,
                    "Why Type - No Model",
                    "No transcription model is installed.\n\n"
                    "Open Settings to download a model before recording.",
                )
            self.signaler.show_settings.emit()
            return

        try:
            self.recorder.start()
            self._state = "recording"
            self.signaler.status_changed.emit("Recording...")
            logger.info("Recording started")
        except Exception as e:
            logger.exception("Failed to start recording")
            self._show_error(f"Failed to start recording:\n{e}")
            self._state = "idle"

    def _on_stop_recording(self) -> None:
        if self._state != "recording":
            return
        audio = self.recorder.stop()
        self._state = "transcribing"
        self.signaler.status_changed.emit("Transcribing...")
        logger.info("Recording stopped, transcribing...")
        thread = threading.Thread(target=self._transcribe, args=(audio,), daemon=True)
        thread.start()

    # Below this peak amplitude the recording is effectively silent. Whisper
    # hallucinates filler words ("you", "Thank you.") on silence, so we skip
    # transcription entirely rather than type a phantom word.
    _SILENCE_PEAK = 0.01

    def _transcribe(self, audio: Optional[object]) -> None:
        if self.transcriber is None:
            self.signaler.transcribe_done.emit("")
            return

        # Log the captured level so a "no audio" problem (wrong mic, muted
        # input) is diagnosable, and gate out silence to avoid hallucinations.
        try:
            import numpy as _np
            if audio is not None and len(audio) > 0:
                arr = _np.asarray(audio, dtype=_np.float32)
                peak = float(_np.max(_np.abs(arr)))
                rms = float(_np.sqrt(_np.mean(arr * arr)))
                logger.info(
                    "Captured audio: %.2fs, peak=%.4f, rms=%.4f",
                    len(arr) / 16000.0, peak, rms,
                )
                if peak < self._SILENCE_PEAK:
                    logger.warning(
                        "Audio is silent (peak %.4f < %.4f) — skipping. The "
                        "microphone may be muted or the wrong input device is "
                        "selected.", peak, self._SILENCE_PEAK,
                    )
                    self.signaler.transcribe_done.emit("")
                    return
        except Exception:
            logger.debug("Could not measure audio level", exc_info=True)

        try:
            text = self.transcriber.transcribe(audio)
            self.signaler.transcribe_done.emit(text)
            logger.info("Transcription complete (%d chars)", len(text))
        except Exception as e:
            logger.exception("Transcription failed")
            self.signaler.transcribe_failed.emit(str(e))

    def _on_transcribe_done(self, text: str) -> None:
        self._state = "typing"
        self.signaler.status_changed.emit("Typing...")
        thread = threading.Thread(target=self._do_type, args=(text,), daemon=True)
        thread.start()

    def _on_transcribe_failed(self, error: str) -> None:
        self._state = "idle"
        self.signaler.status_changed.emit("Ready")
        self._show_error(f"Transcription failed:\n\n{error}")

    def _check_accessibility(self) -> bool:
        """Return True if the process can inject keystrokes (macOS Accessibility).

        On macOS, typing into other apps requires the process to be listed under
        System Settings › Privacy & Security › Accessibility. This triggers the
        OS prompt on first launch so the user can grant it. Non-macOS always
        returns True.
        """
        if sys.platform != "darwin":
            return True
        try:
            from HIServices import (
                AXIsProcessTrustedWithOptions,
                kAXTrustedCheckOptionPrompt,
            )
            trusted = AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True})
            if not trusted:
                logger.warning(
                    "Accessibility permission not granted; keyboard injection will fail"
                )
                QSystemTrayIcon = _QT_CLASSES.get("QSystemTrayIcon")
                if self.tray_icon and QSystemTrayIcon and self.tray_icon.supportsMessages():
                    self.tray_icon.showMessage(
                        "Why Type needs Accessibility permission",
                        "Go to System Settings → Privacy & Security → Accessibility "
                        "and enable Why Type (or Python), then restart the app.",
                        QSystemTrayIcon.MessageIcon.Warning,
                        12000,
                    )
            return trusted
        except Exception:
            logger.debug("Could not check Accessibility permission", exc_info=True)
            return True  # assume OK if the check itself can't run

    def _do_type(self, text: str) -> None:
        # macOS silently drops injected keystrokes when Accessibility permission
        # is missing — CGEventPost returns no error — so the "typed N chars" log
        # would lie. Detect and surface it instead.
        if sys.platform == "darwin":
            try:
                import HIServices
                if not HIServices.AXIsProcessTrusted():
                    logger.warning(
                        "Skipping type_text: Accessibility permission not granted"
                    )
                    self.signaler.transcribe_failed.emit(
                        "Why Type cannot type text because it lacks Accessibility "
                        "permission.\n\n"
                        "Open System Settings → Privacy & Security → Accessibility, "
                        "enable Why Type (or the Python entry), then restart Why Type."
                    )
                    self.signaler.typing_done.emit()
                    return
            except Exception:
                pass
        try:
            self.typer.type_text(text)
            logger.info("Typed %d characters", len(text))
        except Exception:
            logger.exception("Typing failed")
        self.signaler.typing_done.emit()

    def _on_typing_done(self) -> None:
        self._state = "idle"
        self.signaler.status_changed.emit("Ready")

    def _show_settings(self) -> None:
        self._stop_listener()
        QDialog = _QT_CLASSES["QDialog"]
        dialog = SettingsDialog(self.config, accel_status=self._accel_status)
        result = dialog.exec()
        if result == QDialog.DialogCode.Accepted:
            self.recorder.set_input_device(self.config.input_device or None)
            self.signaler.status_changed.emit("Loading model...")
            self.app.processEvents()
            try:
                if self.transcriber is None:
                    self._load_transcriber()
                else:
                    self.transcriber.reload(
                        model_name=self.config.model,
                        custom_path=self.config.custom_model_path or None,
                    )
            except Exception as e:
                logger.exception("Failed to load model after settings change")
                self._show_error(f"Failed to load model:\n{e}")
            if self.transcriber is not None and self.transcriber.load_error():
                self._show_error(
                    "The selected transcription model failed to load:\n\n"
                    f"{self.transcriber.load_error()}"
                )
            self._apply_device()
            self._start_listener()
            self.signaler.status_changed.emit("Ready")
        else:
            self._start_listener()

    def run(self) -> int:
        if self._settings_only:
            self._show_settings()
            return 0

        self._check_accessibility()
        self._start_listener()
        if self.tray_icon is None:
            self._show_error(
                "System tray is not available on this system. "
                "The app requires a system tray to run."
            )
            return 1
        if not self.tray_icon.isVisible():
            logger.warning("Tray icon reports not visible; may be in overflow area")
        self._warn_if_wayland()
        logger.info("WhyType started successfully")
        return self.app.exec()

    def _warn_if_wayland(self) -> None:
        """On Wayland, global hotkeys and synthetic typing are unreliable."""
        if sys.platform != "linux":
            return
        session = os.environ.get("XDG_SESSION_TYPE", "").lower()
        if session == "wayland" or os.environ.get("WAYLAND_DISPLAY"):
            logger.warning("Wayland session detected; hotkeys/typing may not work")
            if self.tray_icon is not None and self.tray_icon.supportsMessages():
                QSystemTrayIcon = _QT_CLASSES["QSystemTrayIcon"]
                self.tray_icon.showMessage(
                    "Why Type - Wayland detected",
                    "Global hotkeys and typing are limited under Wayland. "
                    "If the shortcut does not work, run under an X11/XWayland "
                    "session.",
                    QSystemTrayIcon.MessageIcon.Warning,
                    10000,
                )

    def quit(self) -> None:
        logger.info("WhyType shutting down")
        self._stop_listener()
        self.recorder.stop()
        self.app.quit()


def main() -> None:
    settings_only = "--settings" in sys.argv
    if not settings_only:
        _enforce_single_instance()
    app = WhyTypeApp(settings_only=settings_only)
    sys.exit(app.run())
