#!/bin/bash

# --- VunVun's Macro Loader (Linux/macOS) ---
echo "========================================"
echo "  Spatial Macro Launcher - Initializing "
echo "========================================"

echo ""
echo "!!! EXPERIMENTAL NOTICE !!!"
echo "Linux and macOS support is currently experimental and untested."
echo "If you encounter any issues, please report them on Discord."
echo "========================================"
echo ""

# 1. Detect OS
OS_TYPE="unknown"
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS_TYPE="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS_TYPE="macos"
fi

# 2. Check for Python 3
if command -v python3 &> /dev/null; then
    PY_EXE="python3"
elif command -v python &> /dev/null; then
    # Check if 'python' is actually version 3
    if python --version 2>&1 | grep -q "Python 3"; then
        PY_EXE="python"
    fi
fi

if [ -z "$PY_EXE" ]; then
    echo "[ERROR] Python 3 is not installed."
    if [ "$OS_TYPE" == "macos" ]; then
        echo "Please run: brew install python"
    else
        echo "Please run: sudo apt install python3"
    fi
    exit 1
fi

# Use detected executable for remainder of script
echo "[INFO] Using: $PY_EXE"

# 3. Migration Cleanup (Remove EasyOCR/Torch)
echo "[INFO] Performing V5.4 Cleanup..."
$PY_EXE -m pip uninstall -y easyocr torch torchvision &> /dev/null
rm -rf ~/.EasyOCR &> /dev/null

# 4. Check for RapidOCR (V5.4 Migration)
echo "[INFO] RapidOCR is now the default engine."
echo "[INFO] No external software (like Tesseract) is required anymore!"

# 5. Install Python Requirements
echo "[INFO] Syncing Python dependencies..."
$PY_EXE -m pip install -r requirements.txt

# 6. Run Macro
echo "[INFO] Starting Spatial Macro..."
echo "[NOTICE] If this is your first time using V5.4, it may take a"
echo "moment to initialize the RapidOCR engine. Please wait!"
$PY_EXE main.py
