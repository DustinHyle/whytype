# Why Type Changelog

## v1.1.11 - macOS App Name

### Fixed
- macOS now shows **"Why Type"** instead of **"Python"** in the menu bar and Dock tooltip (the running bundle's name is set at startup), and the process shows as "Why Type" in Activity Monitor (launcher sets argv[0]). Note: system permission dialogs are tied to the on-disk bundle and may still differ until the app ships as a signed, packaged `.app`.

## v1.1.10 - macOS Native Launcher

### Fixed
- **App did nothing when double-clicked in Finder** (but worked when the inner `Contents/MacOS/Why Type` file was run directly): macOS will not reliably launch an `.app` from Finder whose main executable is a shell script. The installer now compiles a tiny native (Mach-O) launcher as the bundle executable, which Finder/Spotlight launch normally. Falls back to a script launcher only if no C compiler is present (with guidance to install Xcode Command Line Tools).

## v1.1.9 - macOS Bundle Registration

### Fixed
- **App did nothing on double-click on some Macs** (no window, no log): a freshly-built, unsigned bundle can be silently refused by macOS until it's registered. The installer now strips the quarantine flag and registers the app with Launch Services so it launches from Finder/Spotlight immediately.

## v1.1.8 - Launcher Robustness & Bootstrap Log

### Fixed
- The macOS/Linux launcher now falls back to `python3` if `python` is missing in the venv, and captures all startup output to a bootstrap log — so a crash before the app's own logging can no longer be a silent no-op with no diagnostics.

### Added
- Bootstrap log capturing launcher output: macOS `~/Library/Logs/WhyType/launch.log`, Linux `~/.local/state/WhyType/launch.log`.

## v1.1.7 - macOS Installer Fixes

### Fixed
- **macOS install failed when run with `sudo`**: pip's post-install byte-compile crashed on PySide6's template files under root's stdout encoding, leaving a half-installed app. The installer now refuses to run as root, and pip installs with `--no-compile` to avoid the crash entirely (also applied on Windows).
- **Removed the confusing "install for all users?" prompt**: macOS now always installs per-user into `~/Applications` — no admin, no sudo. (Running as root also broke Homebrew, so portaudio failed to install.)

## v1.1.6 - Microphone Picker

### Added
- **Choose your microphone** in Settings. A "Use default microphone" checkbox (on by default) keeps the OS-selected input device; unchecking it enables a dropdown to pick a specific microphone. If a saved device is later unplugged, the app falls back to the default automatically.

## v1.1.5 - Silence Handling & Mic Diagnostics

### Fixed
- **Typed "you" instead of the spoken words**: when the microphone captures silence (muted mic or wrong input device), Whisper hallucinates a filler word — almost always "you". The app now measures the recorded audio level and skips transcription when it is effectively silent, so no phantom word is typed.

### Added
- Logs the active input device name and each recording's peak/RMS level, so a "no audio / wrong microphone" problem is easy to diagnose from the log.

## v1.1.4 - macOS Runtime Fixes

### Fixed
- **Silent crash at launch on macOS** (`AttributeError: Key.insert`): pynput has no `Key.insert` on macOS, and the `SPECIAL_KEYS` dict was evaluated at import time, killing the process before logging started. `insert` is now included only when available.
- **Crash in the hotkey listener thread on macOS 15+** (`EXC_BREAKPOINT`/`SIGTRAP`): macOS 15 added a main-thread assertion inside `TISGetInputSourceProperty`, which pynput's listener called from a background thread. pynput's `keycode_context` is now cached (populated on the main thread) so the listener thread never touches Text Input Services.
- **Text transcribed but never typed on macOS**: keystroke injection silently fails without Accessibility permission. The app now requests Accessibility on first launch and, if it's missing, shows a clear error instead of falsely logging "Typed N characters".

### Added
- macOS dependency `pyobjc-framework-ApplicationServices` (for the Accessibility permission check).

## v1.1.3 - macOS Launch Fix & Dependency Install

### Fixed
- **macOS app did nothing on launch** (no menu-bar icon, no log): the `.app` launcher invoked the `whytype` console script, whose shebang contains the install path — and the kernel cannot parse a shebang with a space (`.../Why Type.app/...`), so it failed silently. The launcher now runs the venv Python directly (`python -m whytype`). The Linux launcher was made space-safe the same way.

### Added
- **macOS dependency auto-install**: `install.sh` now installs `python3`, `portaudio`, and `whisper-cpp` (the Metal-accelerated engine) via Homebrew when missing, with a clear message to install Homebrew if it isn't present.

## v1.1.2 - Model Integrity & GPU Resilience

### Fixed
- **"Failed to initialize whisper context"**: caused by a corrupt or truncated model file. Downloads are now verified (full Content-Length + GGML magic bytes) so a bad download is never saved; an already-corrupt model is detected up front with an actionable message and is automatically replaced on the next download.
- **GPU transcription failures** (driver/VRAM/init issues on some GPUs) now fall back to CPU automatically for the session instead of showing an error.

## v1.1.1 - Startup Crash Fix

### Fixed
- **App failed to start on some machines** (`AttributeError: '_SixMetaPathImporter' object has no attribute '_path'`): PySide6's `__feature__` import hook crashes when it processes `six`'s custom importer, which `pynput` pulls in. The crash depended on the installed PySide6/six versions. `pynput` is now imported before PySide6 so the offending `six.moves` import runs before the hook is armed.
- Settings model downloads now use a dropdown + single Download button (per-row buttons inside the scroll area received no mouse events on some Windows setups), with live progress, a download timeout, and partial-file cleanup.
- macOS/Linux: `whisper-cli` is now also found on PATH and in Homebrew locations (`/opt/homebrew/bin`, `/usr/local/bin`), so `brew install whisper-cpp` works without bundling a binary; `.sh` installers are packaged executable.

## v1.1.0 - whisper.cpp Engine + Cross-Vendor GPU Acceleration

### Changed
- **New transcription engine**: replaced PyTorch/openai-whisper with **whisper.cpp** via a bundled native `whisper-cli` binary. PyTorch and openai-whisper are no longer dependencies — installs are much smaller and start faster.
- **Models are now GGML/GGUF** (`.bin`), downloaded from the official whisper.cpp Hugging Face repo. Added Turbo and quantized "Compact" variants; corrected sizes.

### Added
- **GPU acceleration on any GPU**: Vulkan (NVIDIA, AMD, Intel — including integrated), Metal (Apple Silicon), and CUDA, with automatic CPU fallback.
- **Settings → Acceleration** selector: Automatic / GPU / CPU, with a "currently using" readout.
- **Startup GPU probe**: on Automatic/GPU the app verifies the GPU actually works and silently falls back to CPU if not (handles flaky integrated GPUs).
- **Pluggable engine architecture** (`whytype/engine/`) behind a `TranscriptionEngine` interface.
- **`scripts/build_whispercpp.py`** and CI steps to compile/bundle the engine binary per platform; installers verify the binary and check the Vulkan loader on Linux.

### Removed
- PyTorch, openai-whisper, and tiktoken dependencies (and their installer/build steps).

## v1.0.2 - Production Hardening

### Changed
- **New default shortcut**: Windows/Linux now default to `Ctrl+Win` (Super), macOS to `Ctrl+Cmd`. The Fn key is intentionally not used on macOS because it is never delivered to the keyboard listener. The previous default never matched the documentation.
- **Branded app icon**: ships a real microphone icon used for the tray, windows, Start Menu/desktop shortcuts, the Linux desktop entry, and the macOS app bundle (replacing the generic fallback icon).

### Fixed
- **Crash on Python 3.8**: `list[...]`/`tuple[...]` return annotations were evaluated at import and raised on the advertised minimum Python (3.8). Added `from __future__ import annotations`.
- **Misleading "no model" error**: a model that *failed to load* (corrupt checkpoint, torch error) was reported as "no model installed". Load failures are now surfaced with the real error and distinguished from an empty install.
- **Silent transcription failures**: a failed transcription is now shown to the user instead of being overwritten by the "Typing…/Ready" status with no text produced.
- **Version sprawl**: package, installers, and macOS bundle now all report `1.0.2`.
- **Settings could not capture modifier-only shortcuts** (e.g. `Ctrl+Win`); the capture widget now supports them.

### Added
- **Cross-platform single-instance lock** (POSIX lockfile) — previously Windows-only.
- **Wayland warning**: on Linux/Wayland the app now warns that global hotkeys and typing are limited.
- **macOS agent app**: the bundle sets `LSUIElement` so no stray Dock icon appears for the tray-only app.
- **Recording length cap** to bound memory on very long dictations.

### Corrected
- Documented Large model size (~3 GB, was listed as ~1.5 GB).

## v1.0.1 - Windows Runtime Fixes

### Fixed
- **Blank terminal window on launch**: Launcher now uses `pythonw.exe` (GUI subsystem) instead of `whytype.exe` (console subsystem). No visible terminal window appears.
- **Windows Terminal shortcut conflict**: Changed default shortcut from `Ctrl+Shift+Space` (conflicts with Windows Terminal command palette) to `Ctrl+Shift+F8`.
- **Model not recognized after install**: Installer now verifies the `.pt` file exists after download and writes the selected model to the config file. App also auto-detects downloaded models on first run.
- **Settings not discoverable**: Added standalone `Settings.bat` launcher and Start Menu shortcut (`Why Type Settings`).

### Added
- `--settings` CLI flag to open settings directly without starting the full tray app.
- `Settings.bat` and Start Menu `Why Type Settings` shortcut for direct settings access.
- Model download verification step in installer.

## v1.0.0 - Initial Release

### Known Issues in v1.0.0
- Console window visible on Windows because `whytype.exe` is a console binary.
- Default `Ctrl+Shift+Space` shortcut conflicts with Windows Terminal.
- Installer downloads model but does not update config; app reports "No transcription model installed."
- Settings only accessible via tray icon right-click; no standalone shortcut.
