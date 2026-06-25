#!/bin/bash
set -e

SILENT=0
if [ "$1" = "silent" ]; then
    SILENT=1
fi

OS="unknown"
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
else
    echo "Unsupported OS: $OSTYPE"
    exit 1
fi

if [ "$OS" == "macos" ]; then
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    if [[ "$SCRIPT_DIR" == *".app/Contents/MacOS"* ]]; then
        INSTALL_DIR="$(cd "$SCRIPT_DIR/../../" && pwd)"
    else
        INSTALL_DIR=""
        if [ -d "$HOME/Applications/Why Type.app" ]; then
            INSTALL_DIR="$HOME/Applications/Why Type.app"
        fi
        if [ -d "/Applications/Why Type.app" ]; then
            if [ -n "$INSTALL_DIR" ]; then
                echo "WARNING: Multiple installations found. Removing both."
                rm -rf "$HOME/Applications/Why Type.app"
                rm -rf "/Applications/Why Type.app"
                if [ $SILENT -eq 0 ]; then
                    echo "Uninstall complete."
                fi
                exit 0
            else
                INSTALL_DIR="/Applications/Why Type.app"
            fi
        fi
        if [ -z "$INSTALL_DIR" ]; then
            if [ $SILENT -eq 0 ]; then
                echo "Why Type does not appear to be installed."
            fi
            exit 1
        fi
    fi
else
    INSTALL_DIR="$HOME/.local/share/whytype"
fi

if [ ! -d "$INSTALL_DIR" ]; then
    if [ $SILENT -eq 0 ]; then
        echo "Why Type does not appear to be installed at $INSTALL_DIR."
    fi
    exit 1
fi

if [ $SILENT -eq 0 ]; then
    echo "========================================"
    echo "       Why Type - Uninstaller"
    echo "========================================"
    echo ""
    echo "This will remove Why Type from:"
    echo "  $INSTALL_DIR"
    echo ""
    read -p "Are you sure? [y/N]: " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        echo "Uninstall cancelled."
        exit 0
    fi
    echo ""
fi

if [ "$OS" == "linux" ]; then
    if [ $SILENT -eq 0 ]; then
        echo "Removing desktop entry..."
    fi
    rm -f "$HOME/.local/share/applications/whytype.desktop"
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
fi

if [ $SILENT -eq 0 ]; then
    echo "Removing application files..."
fi
rm -rf "$INSTALL_DIR"

if [ $SILENT -eq 0 ]; then
    echo ""
    echo "========================================"
    echo "Uninstall complete."
    echo ""
    echo "Note: Your settings and downloaded models"
    echo "were preserved in the platform cache directory."
    echo "========================================"
fi
