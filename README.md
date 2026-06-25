# Why Type

Cross-platform voice dictation app that transcribes speech locally with whisper.cpp and types it into the active text field.

## ⬇️ Download & Install

**[Download the latest version →](https://github.com/DustinHyle/whytype/releases/latest)**
then follow the simple step-by-step **[Install Guide](INSTALL.md)** for Windows,
Mac, or Linux. No account or sign-in required.

## Features

- **Local transcription** — runs Whisper (via whisper.cpp) entirely on your machine (no cloud required)
- **GPU accelerated, any GPU** — uses your GPU via Vulkan (NVIDIA, AMD, Intel — including integrated), Metal (Apple Silicon), or CUDA, with automatic CPU fallback
- **Global hotkey** — hold or toggle a keyboard shortcut to record from anywhere
- **Simulated typing** — transcribed text is typed character-by-character into the focused field
- **Choose your model** — download only the models you want, switch between them anytime
- **Custom models** — use your own GGML/GGUF whisper.cpp model

## Default Shortcut

Platform-appropriate defaults (all customizable in Settings):

| Platform | Default shortcut |
|----------|------------------|
| Windows  | `Ctrl + Win` |
| Linux    | `Ctrl + Super` |
| macOS    | `Ctrl + Cmd` |

> **macOS note:** the Fn (globe) key cannot be used as a shortcut — the keyboard
> backend never receives it — so macOS uses `Ctrl + Cmd` instead.

## Quick Start

> For full step-by-step instructions see the **[Install Guide](INSTALL.md)**.
> Download builds from the
> [Releases page](https://github.com/DustinHyle/whytype/releases/latest).

### Windows

1. Download **`whytype-windows.zip`**, right-click → **Extract All**.
2. Double-click **`install.bat`**.
3. **Security approval:** if a blue **"Windows protected your PC"** (SmartScreen) box appears, click **More info → Run anyway** (the app isn't from the Microsoft Store, so this is expected).
4. Launch **Why Type** from the Start Menu.

To uninstall, run `%LOCALAPPDATA%\Programs\WhyType\uninstall.bat` or use **Add/Remove Programs**.

### macOS (drag and drop)

1. Download **`whytype-macos.zip`** and double-click to unzip — you'll get **Why Type**.
2. Drag **Why Type** into your **Applications** folder.
3. **Security approvals** (one-time — the app isn't notarized yet):
   - **Gatekeeper (macOS Sequoia 15+):** double-click **Why Type**, click **Done** on the "could not verify" dialog (**not** "Move to Trash"), then go to **System Settings → Privacy & Security → Open Anyway**. On older macOS you can instead **right-click → Open → Open**.
   - **Microphone:** allow it when prompted (needed to hear your speech).
   - **Accessibility:** macOS will prompt to open **System Settings → Privacy & Security → Accessibility** — turn **Why Type** on. This is required for the app to type for you. **Quit and reopen** Why Type after enabling it.

To uninstall, drag **Why Type** from Applications to the Trash.

### Linux

1. Download **`whytype-linux.zip`**, extract it, and run:
   ```bash
   ./install.sh
   ```
2. The installer sets up the app in `~/.local/share/whytype` and creates a desktop entry. (No special OS security prompt; you may be asked to install PortAudio/Vulkan drivers — see the Install Guide.)

To uninstall, run `~/.local/share/whytype/uninstall.sh`.

## Acceleration (CPU / GPU)

Transcription runs on a bundled native `whisper-cli` (whisper.cpp) binary. GPU
acceleration is portable across vendors:

| Hardware | Backend |
|----------|---------|
| NVIDIA (discrete) | CUDA or Vulkan |
| AMD / Intel — discrete **and integrated** | Vulkan |
| Apple Silicon (M-series) | Metal |
| No GPU / unsupported | CPU |

In **Settings → Acceleration**, choose **Automatic** (use GPU when available,
fall back to CPU), **GPU**, or **CPU**. On Automatic/GPU the app probes the GPU
at startup and silently falls back to CPU if it isn't usable — so flaky
integrated GPUs can't break dictation.

> **Linux:** GPU acceleration needs the Vulkan loader and drivers
> (`libvulkan1` + `mesa-vulkan-drivers`, or vendor drivers). Without them the
> app still works on CPU.

## Manual Development Setup

```bash
# Clone or navigate to the project directory
cd whytype

# Create a virtual environment
python -m venv .venv

# Activate it
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install Python dependencies (no PyTorch — transcription is native)
pip install -e .

# Build the whisper.cpp engine binary (requires CMake + a C/C++ toolchain;
# Vulkan SDK on Win/Linux or Xcode on macOS for GPU support)
python scripts/build_whispercpp.py --backend auto

# Run
python -m whytype
```

## Standalone Executable

To build a standalone executable with PyInstaller (no Python required on the target machine):

```bash
pip install pyinstaller
python build.py
```

The output is in `dist/WhyType/`:
- **Windows**: `dist/WhyType/WhyType.exe`
- **macOS**: `dist/WhyType.app`
- **Linux**: `dist/WhyType/WhyType`

For a single-file executable:

```bash
python build.py --onefile
```

## Releases & Packaging

Distribution archives are named with version and platform so the filename
always says what's inside, e.g. `whytype-1.1.0-windows.zip`. To produce them:

```bash
# Build the engine binary for this platform first (stages whytype/bin/)
python scripts/build_whispercpp.py --backend auto

# Installer bundle -> dist/whytype-<version>-<platform>.zip
python scripts/package.py

# Standalone (PyInstaller) -> dist/whytype-<version>-<platform>-standalone.zip
python build.py
python scripts/package.py --standalone-dir dist/WhyType
```

CI (`.github/workflows/build.yml`) does this automatically for Windows, macOS,
and Linux, and attaches the archives to a GitHub Release when a `v*` tag is
pushed. The version is read from `whytype/__init__.py`.

## Usage

The app runs silently in your system tray. Right-click the tray icon for the menu, or double-click to open settings.

> **Tip:** If you can't find the tray icon, look in the system tray overflow area (the "^" icon on Windows 11), or open **Start Menu > Why Type Settings** to access settings directly.

### Recording

- **Hold mode** (default): Hold the shortcut to record. Release to transcribe and type.
- **Toggle mode**: Press the shortcut once to start, press again to stop.

### Settings

Open **Settings** from the tray menu to configure:

| Setting | Description |
|---------|-------------|
| Shortcut | Capture a new global keyboard shortcut |
| Recording mode | Hold or Toggle |
| Microphone | Use the system default, or pick a specific input device |
| Acceleration | Automatic / GPU / CPU |
| Installed Models | Select from downloaded models or a custom model path |
| Available Models | Download new models with descriptions to help you choose |

### Model Options

The app ships with **no models** (GGML/GGUF whisper.cpp models). Open Settings and download the one that fits your needs:

| Model | Size | Speed | Accuracy | Best For |
|-------|------|-------|----------|----------|
| **Tiny** | ~75 MB | Fastest | Basic | Older computers, clear simple speech |
| **Base** | ~142 MB | Fast | Low | Everyday use on most computers |
| **Small** | ~466 MB | Moderate | Good | Accents, background noise |
| **Medium** | ~1.5 GB | Slow | Better | Professional use, high accuracy |
| **Turbo (Compact)** | ~574 MB | Fast | Great | Best all-round with a GPU |
| **Turbo** | ~1.6 GB | Moderate | Great | Near-large accuracy, much faster |
| **Large (Compact)** | ~1.1 GB | Slow | Best | Max accuracy, smaller download |
| **Large** | ~3.1 GB | Slowest | Best | Multiple languages, difficult audio |

"Compact" models are quantized — much smaller and faster with negligible accuracy loss. Models are downloaded to the platform-appropriate cache directory and can be switched between at any time from Settings.

## Platform Notes

### macOS

- **Accessibility permission**: The app needs permission to simulate keystrokes. macOS will prompt you the first time you try to type. Go to **System Settings → Privacy & Security → Accessibility** and add the app if prompted.
- **Microphone permission**: Allow microphone access when prompted.

### Linux

- **X11**: Works out of the box on most X11-based desktops.
- **Wayland**: Global hotkeys and keystroke simulation are limited under Wayland. You may need to run under XWayland or use a compositor-specific workaround.
- **GPU acceleration**: Install the Vulkan loader and drivers — `libvulkan1` + `mesa-vulkan-drivers` (Debian/Ubuntu), `vulkan-loader` + `mesa-vulkan-drivers` (Fedora), or `vulkan-icd-loader` + `vulkan-radeon`/`vulkan-intel` (Arch). Without them the app runs on CPU.
- **Input permissions**: If global hotkeys fail, add your user to the `input` group:
  ```bash
  sudo usermod -a -G input $USER
  # Log out and back in for changes to take effect
  ```

### Windows

- Runs without additional permissions.
- Windows Defender or antivirus may briefly flag the app on first mic access. Allow it if prompted.

## Project Structure

```
whytype/
├── whytype/                  # Python package
│   ├── app.py                # Main application, tray icon, hotkey handling
│   ├── config.py             # Settings persistence
│   ├── models.py             # GGML model registry and download helpers
│   ├── recorder.py           # Microphone audio capture
│   ├── typer.py              # Simulated keyboard input
│   ├── engine/               # Pluggable transcription engines
│   │   ├── base.py           # TranscriptionEngine interface
│   │   └── whispercpp_engine.py  # whisper.cpp subprocess engine
│   ├── assets/               # App icon (png/ico/icns)
│   ├── bin/                  # Bundled whisper-cli binary (built per platform)
│   └── ui/
│       └── settings_dialog.py
├── scripts/
│   └── build_whispercpp.py   # Build/stage the whisper.cpp engine binary
├── install.bat               # Windows installer
├── uninstall.bat             # Windows uninstaller
├── install.sh                # macOS/Linux installer
├── uninstall.sh              # macOS/Linux uninstaller
├── build.py                  # PyInstaller standalone build script
├── pyproject.toml            # Python packaging metadata
├── requirements.txt          # Runtime dependencies
└── README.md
```

## License

MIT
