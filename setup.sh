#!/bin/bash

echo "========================================="
echo "Spatial Macro - macOS/Linux Launcher"
echo "========================================="
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR" || exit 1

# Check if requirements.txt exists
if [ ! -f "requirements.txt" ]; then
    echo "❌ requirements.txt not found!"
    exit 1
fi

# Detect OS
OS_TYPE="unknown"
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS_TYPE="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS_TYPE="macos"
fi

echo "[INFO] OS detected: $OS_TYPE"
echo ""

# Check for Python 3
if command -v python3 &> /dev/null; then
    PY_EXE="python3"
elif command -v python &> /dev/null; then
    if python --version 2>&1 | grep -q "Python 3"; then
        PY_EXE="python"
    else
        echo "❌ Python 3 not found"
        exit 1
    fi
else
    echo "❌ Python 3 is not installed."
    echo ""
    if [ "$OS_TYPE" == "macos" ]; then
        echo "Please install Python:"
        echo "  brew install python3"
    else
        echo "Please install Python:"
        echo "  Ubuntu/Debian: sudo apt-get install python3"
        echo "  Fedora/RedHat: sudo dnf install python3"
    fi
    exit 1
fi

echo "[INFO] Using: $PY_EXE"
$PY_EXE --version

echo ""
echo "[INFO] Installing dependencies..."
$PY_EXE -m pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "❌ Installation failed"
    exit 1
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "[INFO] Starting macro..."
$PY_EXE main.py
