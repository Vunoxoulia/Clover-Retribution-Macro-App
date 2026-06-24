# 🚀 Setup & Installation Guide

Everything you need to run the Spatial Macro.

---

## ⚡ Quick Start

### 🪟 Windows
1. Go into `spatial-macro/` folder
2. Double-click **Windows_Launcher.bat**
3. Macro will auto-detect Python, download if needed, install dependencies, and launch

### 🍎 macOS
1. Go into `spatial-macro/` folder
2. Open Terminal here
3. Run: `bash Linux_Mac_Launcher.sh`
4. Follow prompts

### 🐧 Linux
1. Go into `spatial-macro/` folder
2. Open Terminal here
3. Run: `bash Linux_Mac_Launcher.sh`
4. Follow prompts

---

## ✅ System Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| **OS** | Windows 10 | Windows 11 |
| **Python** | 3.10 | 3.11+ |
| **RAM** | 4GB | 8GB+ |
| **Display** | 1920x1080 | 1920x1080+ |

**Note:** Linux & macOS support is experimental and untested.

---

## 📋 What the Launcher Does

The launchers automatically:
1. ✅ Detect your Python installation
2. ✅ Download Python if not found (Windows only)
3. ✅ Uninstall old dependencies (migration from v5.3)
4. ✅ Install required packages from `requirements.txt`
5. ✅ Launch the macro
6. ✅ Show errors if something fails

---

## 🔧 Manual Setup (if launcher fails)

### Windows
```batch
python -m pip install -r requirements.txt
python main.py
```

### macOS/Linux
```bash
python3 -m pip install -r requirements.txt
python3 main.py
```

---

## 🪟 Windows: Python Not Found?

The launcher will ask if you want to download Python automatically.

**To install manually:**
1. Go to https://www.python.org/downloads/
2. Download Python 3.10+
3. **IMPORTANT:** Check "Add Python to PATH" during installation
4. Restart your computer
5. Try the launcher again

---

## 🐧 macOS: Install Python

```bash
# Using Homebrew (easiest)
brew install python3

# Or download from https://www.python.org/downloads/
```

---

## 🐧 Linux: Install Python

### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install python3 python3-pip
```

### Fedora/RedHat
```bash
sudo dnf install python3 python3-pip
```

---

## 🆘 Troubleshooting

### "Python not found"
- Windows: Install from python.org with "Add Python to PATH" checked
- macOS: Install with `brew install python3`
- Linux: Install with apt or dnf (see above)

### "Permission denied" (macOS/Linux)
```bash
chmod +x Linux_Mac_Launcher.sh
bash Linux_Mac_Launcher.sh
```

### "Module not found" error
Run the launcher again to reinstall dependencies:
```bash
# Windows: Double-click Windows_Launcher.bat again
# macOS/Linux: bash Linux_Mac_Launcher.sh
```

### "OCR not working"
The RapidOCR model downloads on first run. Wait a moment and try again.

---

## 📦 What Gets Installed

Via `requirements.txt`:
- customtkinter
- numpy
- opencv-python
- keyboard
- pynput
- pywinctl
- screeninfo
- mss
- rapidocr_onnxruntime
- pillow
- requests

---

## 🧹 Reinstall Everything

### Windows
```batch
rem Delete old dependencies
python -m pip uninstall -y customtkinter numpy opencv-python keyboard pynput pywinctl screeninfo mss rapidocr_onnxruntime pillow requests

rem Reinstall
python -m pip install -r requirements.txt
```

### macOS/Linux
```bash
# Delete old dependencies
python3 -m pip uninstall -y customtkinter numpy opencv-python keyboard pynput pywinctl screeninfo mss rapidocr_onnxruntime pillow requests

# Reinstall
python3 -m pip install -r requirements.txt
```

---

See **START_HERE.txt** for a quick overview.  
See **TROUBLESHOOTING.md** for common issues.
