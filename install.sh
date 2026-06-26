#!/bin/bash
set -e

echo "========================================"
echo "        Why Type - Installer"
echo "========================================"
echo ""

# --- Determine source directory ---
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"

# --- Detect OS ---
OS="unknown"
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
else
    echo "Unsupported OS: $OSTYPE"
    exit 1
fi

# --- Do not run as root (breaks Homebrew and pip) ---
# On macOS, sudo makes `brew` refuse to run and makes pip's post-install
# byte-compile crash. This installer is per-user and never needs root.
if [ "$EUID" -eq 0 ]; then
    echo "ERROR: Do not run this installer with sudo / as root."
    echo "Run it as your normal user:"
    echo "    bash install.sh"
    exit 1
fi

# --- Set install directory (always per-user; no admin required) ---
if [ "$OS" == "macos" ]; then
    INSTALL_DIR="$HOME/Applications/Why Type.app"
    mkdir -p "$HOME/Applications"
else
    INSTALL_DIR="$HOME/.local/share/whytype"
fi

echo "Install directory: $INSTALL_DIR"

# --- Check for existing installation ---
_uninstall_existing() {
    local target="$1"
    if [ "$OS" == "macos" ]; then
        if [ -d "$target" ]; then
            echo "Why Type is already installed."
            read -p "Overwrite? [y/N]: " overwrite
            if [[ ! "$overwrite" =~ ^[Yy]$ ]]; then
                echo "Installation cancelled."
                exit 0
            fi
            rm -rf "$target"
        fi
    else
        if [ -d "$target" ]; then
            echo "Why Type is already installed."
            read -p "Overwrite? [y/N]: " overwrite
            if [[ ! "$overwrite" =~ ^[Yy]$ ]]; then
                echo "Installation cancelled."
                exit 0
            fi
            rm -rf "$target"
        fi
    fi
}

_uninstall_existing "$INSTALL_DIR"

# --- macOS: install dependencies via Homebrew ---
# Installs python3 (for the venv), portaudio (microphone capture), and
# whisper-cpp (the Metal-accelerated whisper-cli engine) if missing.
if [ "$OS" == "macos" ]; then
    if command -v brew &> /dev/null; then
        echo "Checking dependencies via Homebrew..."
        if ! command -v python3 &> /dev/null; then
            echo "  Installing python3..."
            brew install python || echo "  WARNING: 'brew install python' failed."
        fi
        if ! brew list portaudio &> /dev/null; then
            echo "  Installing portaudio (microphone support)..."
            brew install portaudio || echo "  WARNING: 'brew install portaudio' failed."
        fi
        if ! command -v whisper-cli &> /dev/null && ! command -v whisper-cpp &> /dev/null; then
            echo "  Installing whisper-cpp (Metal-accelerated transcription engine)..."
            echo "  (this can take a few minutes the first time)"
            brew install whisper-cpp || echo "  WARNING: 'brew install whisper-cpp' failed."
        fi
        echo "Dependency check complete."
        echo ""
    else
        echo ""
        echo "WARNING: Homebrew is not installed, so dependencies can't be installed"
        echo "automatically. Install Homebrew from https://brew.sh and re-run, or"
        echo "install these manually: python3, portaudio, whisper-cpp"
        echo ""
    fi
fi

# --- Check Python ---
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required but not found."
    if [ "$OS" == "macos" ]; then
        echo "Install it from: https://www.python.org/downloads/macos/"
        echo "Or run: brew install python3"
    else
        echo "Install it with your package manager:"
        echo "  Debian/Ubuntu: sudo apt install python3 python3-venv python3-pip"
        echo "  Fedora:        sudo dnf install python3 python3-virtualenv"
        echo "  Arch:          sudo pacman -S python python-virtualenv"
    fi
    exit 1
fi

# Check that venv module is available
if ! python3 -m venv --help &> /dev/null; then
    echo "ERROR: python3 venv module is not available."
    if [ "$OS" == "linux" ]; then
        echo "Install it with: sudo apt install python3-venv"
    fi
    exit 1
fi

PYVER=$(python3 --version 2>&1 | awk '{print $2}')
echo "Found Python $PYVER"

# Validate Python version (3.8+)
PY_MAJOR=$(echo "$PYVER" | cut -d. -f1)
PY_MINOR=$(echo "$PYVER" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 8 ]); then
    echo "ERROR: Python $PYVER is not supported. Python 3.8 or newer is required."
    exit 1
fi

# --- Check for PortAudio ---
if [ "$OS" == "linux" ]; then
    if ! ldconfig -p 2>/dev/null | grep -q libportaudio; then
        echo ""
        echo "WARNING: PortAudio not detected. sounddevice may fail."
        echo "Install it with: sudo apt install libportaudio2"
        echo ""
    fi
elif [ "$OS" == "macos" ]; then
    if ! command -v brew &> /dev/null; then
        if ! [ -f /usr/local/lib/libportaudio.dylib ] && ! [ -f /opt/homebrew/lib/libportaudio.dylib ]; then
            echo ""
            echo "WARNING: PortAudio not detected. sounddevice may fail."
            echo "Install it with: brew install portaudio"
            echo ""
        fi
    elif ! brew list portaudio &>/dev/null; then
        echo ""
        echo "WARNING: PortAudio not detected. sounddevice may fail."
        echo "Install it with: brew install portaudio"
        echo ""
    fi
fi

# --- Check for the Vulkan loader (needed for GPU acceleration on Linux) ---
# Without it, Why Type still works on CPU; GPU acceleration just won't engage.
if [ "$OS" == "linux" ]; then
    if ! ldconfig -p 2>/dev/null | grep -q libvulkan.so.1; then
        echo ""
        echo "NOTE: Vulkan loader not detected. GPU acceleration will be disabled"
        echo "(the app will still run on CPU). To enable GPU acceleration install:"
        echo "  Debian/Ubuntu: sudo apt install libvulkan1 mesa-vulkan-drivers"
        echo "  Fedora:        sudo dnf install vulkan-loader mesa-vulkan-drivers"
        echo "  Arch:          sudo pacman -S vulkan-icd-loader vulkan-radeon vulkan-intel"
        echo ""
    fi
fi

# --- Create install directory and copy files ---
echo "Copying application files..."
if [ "$OS" == "macos" ]; then
    mkdir -p "$INSTALL_DIR/Contents/MacOS"
    mkdir -p "$INSTALL_DIR/Contents/Resources"
    cp -R "$SOURCE_DIR/whytype" "$INSTALL_DIR/Contents/Resources/"
    cp "$SOURCE_DIR/pyproject.toml" "$INSTALL_DIR/Contents/Resources/"
    cp "$SOURCE_DIR/requirements.txt" "$INSTALL_DIR/Contents/Resources/" 2>/dev/null || true
    cp "$SOURCE_DIR/README.md" "$INSTALL_DIR/Contents/Resources/" 2>/dev/null || true
else
    mkdir -p "$INSTALL_DIR"
    cp -R "$SOURCE_DIR/whytype" "$INSTALL_DIR/"
    cp "$SOURCE_DIR/pyproject.toml" "$INSTALL_DIR/"
    cp "$SOURCE_DIR/requirements.txt" "$INSTALL_DIR/" 2>/dev/null || true
    cp "$SOURCE_DIR/README.md" "$INSTALL_DIR/" 2>/dev/null || true
fi

# --- Verify / prepare the whisper.cpp engine binary ---
if [ "$OS" == "macos" ]; then
    WHISPER_BIN="$INSTALL_DIR/Contents/Resources/whytype/bin/whisper-cli"
else
    WHISPER_BIN="$INSTALL_DIR/whytype/bin/whisper-cli"
fi
if [ -f "$WHISPER_BIN" ]; then
    chmod +x "$WHISPER_BIN"
elif command -v whisper-cli &> /dev/null || command -v whisper-cpp &> /dev/null; then
    echo "Using whisper.cpp engine from PATH ($(command -v whisper-cli whisper-cpp 2>/dev/null | head -1))."
else
    echo ""
    echo "NOTE: no whisper.cpp engine binary is bundled and none was found on PATH."
    if [ "$OS" == "macos" ]; then
        echo "Install one (Metal-accelerated) with:  brew install whisper-cpp"
    else
        echo "Build one with: python3 scripts/build_whispercpp.py --backend auto"
        echo "or install whisper.cpp from your package manager."
    fi
    echo "The app will report the engine as missing until then."
    echo ""
fi

# --- Create virtual environment and install ---
echo ""
echo "Installing dependencies. This is quick — transcription runs on a bundled"
echo "whisper.cpp binary, so there is no PyTorch to download."
echo ""

if [ "$OS" == "macos" ]; then
    VENV_DIR="$INSTALL_DIR/Contents/Resources/.venv"
    cd "$INSTALL_DIR/Contents/Resources"
else
    VENV_DIR="$INSTALL_DIR/.venv"
    cd "$INSTALL_DIR"
fi

python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# --no-compile: skip byte-compiling installed packages. PySide6 ships
# template (.tmpl.py) files that are not valid Python; pip's post-install
# compile can choke on them (and crashes outright under odd stdout encodings),
# which is harmless to skip — Python compiles on first import anyway.
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install --no-compile .

# --- Ask for model ---
echo ""
echo "========================================"
echo "No transcription model is installed yet."
echo ""
echo "1) Tiny    - Fastest, basic accuracy      (~75 MB)"
echo "2) Base    - Fast, good balance            (~142 MB)"
echo "3) Small   - Moderate, better accents      (~466 MB)  [recommended]"
echo "4) Medium  - Slow, high accuracy           (~1.5 GB)"
echo "5) Large   - Slowest, maximum accuracy     (~3.1 GB)"
echo "6) Skip    - Download later from Settings"
echo "========================================"
read -p "Choose a model to download [1-6, default 3]: " model_choice

# Default to Small (the recommended balance) when the user just presses Enter.
case $model_choice in
    1) MODEL_NAME="tiny" ;;
    2) MODEL_NAME="base" ;;
    3|"") MODEL_NAME="small" ;;
    4) MODEL_NAME="medium" ;;
    5) MODEL_NAME="large-v3" ;;
    6) MODEL_NAME="" ;;
    *) MODEL_NAME="small" ;;
esac

if [ -n "$MODEL_NAME" ]; then
    echo ""
    echo "Downloading $MODEL_NAME model..."
    set +e
    "$VENV_DIR/bin/python" -c "from whytype.models import download_model; download_model('$MODEL_NAME')"
    DOWNLOAD_STATUS=$?
    set -e
    if [ $DOWNLOAD_STATUS -eq 0 ]; then
        echo "Model downloaded successfully."
    else
        echo "Model download failed. You can try again later from Settings."
    fi
else
    echo "Skipping model download. You can download one later from Settings."
fi

# --- Create launcher / app bundle ---
if [ "$OS" == "macos" ]; then
    echo ""
    echo "Creating app bundle..."

    cat > "$INSTALL_DIR/Contents/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>Why Type</string>
    <key>CFBundleDisplayName</key>
    <string>Why Type</string>
    <key>CFBundleIdentifier</key>
    <string>com.whytype.app</string>
    <key>CFBundleVersion</key>
    <string>1.1.15</string>
    <key>CFBundleShortVersionString</key>
    <string>1.1.15</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleExecutable</key>
    <string>Why Type</string>
    <key>CFBundleIconFile</key>
    <string>icon</string>
    <key>LSUIElement</key>
    <true/>
    <key>NSMicrophoneUsageDescription</key>
    <string>Why Type needs microphone access to transcribe your speech into text.</string>
</dict>
</plist>
EOF

    # App icon for the Dock / Finder
    cp "$SOURCE_DIR/whytype/assets/icon.icns" "$INSTALL_DIR/Contents/Resources/icon.icns" 2>/dev/null || true

    # The bundle's main executable must be a real (Mach-O) binary — macOS will
    # silently refuse to launch an .app from Finder whose CFBundleExecutable is
    # a shell script (running the script directly works, double-click does not).
    # So compile a tiny native launcher that execs the venv Python. Fall back to
    # a shell script only if no C compiler is available.
    LAUNCHER="$INSTALL_DIR/Contents/MacOS/Why Type"
    CC_BIN="$(command -v cc || command -v clang || true)"
    LAUNCHER_C="$(mktemp /tmp/whytype_launcher.XXXXXX).c"
    cat > "$LAUNCHER_C" << 'CEOF'
#include <stdlib.h>
#include <unistd.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <mach-o/dyld.h>

/* Resolve <bundle>/Contents/Resources, redirect output to the launch log,
   then exec the venv Python with `-m whytype`. */
int main(void) {
    char raw[PATH_MAX]; uint32_t size = sizeof(raw);
    if (_NSGetExecutablePath(raw, &size) != 0) return 1;
    char exe[PATH_MAX];
    if (!realpath(raw, exe)) return 1;            /* .../Contents/MacOS/Why Type */
    char *p = strrchr(exe, '/'); if (p) *p = 0;   /* .../Contents/MacOS */
    p = strrchr(exe, '/'); if (p) *p = 0;         /* .../Contents */
    char res[PATH_MAX];
    snprintf(res, sizeof(res), "%s/Resources", exe);

    char py[PATH_MAX]; struct stat st;
    snprintf(py, sizeof(py), "%s/.venv/bin/python3", res);
    if (stat(py, &st) != 0)
        snprintf(py, sizeof(py), "%s/.venv/bin/python", res);

    const char *home = getenv("HOME");
    if (home) {
        char dir[PATH_MAX];
        snprintf(dir, sizeof(dir), "%s/Library/Logs/WhyType", home);
        mkdir(dir, 0755);
        char log[PATH_MAX];
        snprintf(log, sizeof(log), "%s/launch.log", dir);
        freopen(log, "a", stdout);
        freopen(log, "a", stderr);
    }
    chdir(res);
    /* argv[0] = "Why Type" so the process shows as Why Type (not python3) in
       Activity Monitor / `ps`. macOS Python derives sys.executable from
       _NSGetExecutablePath, not argv[0], so the venv still resolves. */
    execl(py, "Why Type", "-m", "whytype", (char *)NULL);
    perror("execl failed");
    return 1;
}
CEOF

    if [ -n "$CC_BIN" ] && "$CC_BIN" -O2 -o "$LAUNCHER" "$LAUNCHER_C" 2>/dev/null; then
        echo "Built native launcher."
    else
        echo "No C compiler found; using a script launcher (double-click may not"
        echo "work from Finder — run from Terminal or install Xcode Command Line"
        echo "Tools with 'xcode-select --install' and re-run)."
        cat > "$LAUNCHER" << 'EOF'
#!/bin/bash
DIR="$(cd "$(dirname "$0")/../Resources" && pwd)"
PY="$DIR/.venv/bin/python"
[ -x "$PY" ] || PY="$DIR/.venv/bin/python3"
LOG_DIR="$HOME/Library/Logs/WhyType"
mkdir -p "$LOG_DIR"
exec "$PY" -m whytype >> "$LOG_DIR/launch.log" 2>&1
EOF
    fi
    rm -f "$LAUNCHER_C"
    chmod +x "$LAUNCHER"

    # Make the freshly-built bundle launchable from Finder/Spotlight:
    #  - strip any quarantine flag inherited from the downloaded zip, and
    #  - register it with Launch Services so double-click works immediately.
    # Without this, macOS can silently refuse to launch an unregistered,
    # unsigned bundle (the app appears to "do nothing").
    xattr -dr com.apple.quarantine "$INSTALL_DIR" 2>/dev/null || true
    /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$INSTALL_DIR" 2>/dev/null || true

    echo ""
    echo "App bundle created at: $INSTALL_DIR"
    echo "You can drag it to your Dock for quick access."

else
    echo ""
    echo "Creating launcher..."
    mkdir -p "$INSTALL_DIR/bin"
    cat > "$INSTALL_DIR/bin/whytype" << 'EOF'
#!/bin/bash
DIR="$(cd "$(dirname "$0")/.." && pwd)"
PY="$DIR/.venv/bin/python"
[ -x "$PY" ] || PY="$DIR/.venv/bin/python3"
LOG_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/WhyType"
mkdir -p "$LOG_DIR"
exec "$PY" -m whytype >> "$LOG_DIR/launch.log" 2>&1
EOF
    chmod +x "$INSTALL_DIR/bin/whytype"

    # Desktop entry
    echo "Creating desktop entry..."
    mkdir -p "$HOME/.local/share/applications"
    cat > "$HOME/.local/share/applications/whytype.desktop" << EOF
[Desktop Entry]
Name=Why Type
Comment=Voice dictation with local AI
Exec=$INSTALL_DIR/bin/whytype
Icon=$INSTALL_DIR/whytype/assets/icon.png
Type=Application
Terminal=false
Categories=Utility;AudioVideo;
Keywords=dictation;voice;transcription;whisper;
EOF
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
    echo ""
    echo "Desktop entry created. Search 'Why Type' in your applications menu."
fi

echo ""
echo "========================================"
echo "Installation complete!"
echo ""
if [ "$OS" == "macos" ]; then
    echo "Why Type was installed to your personal Applications folder:"
    echo "  $INSTALL_DIR"
    echo "Launch it from Spotlight (Cmd+Space, type 'Why Type') or Finder."
    echo "On first launch, grant Accessibility + Microphone when prompted."
else
    echo "Launch with:"
    echo "  $INSTALL_DIR/bin/whytype"
    echo ""
    echo "Or find 'Why Type' in your applications menu."
fi
echo "========================================"
