# 🆘 Troubleshooting Guide

Common issues and how to fix them.

---

## ❌ Launcher Issues

### Windows Launcher doesn't open
- Make sure Windows Defender doesn't block it (add to exceptions)
- Try right-click → Run as Administrator
- Try running from PowerShell: `.\Windows_Launcher.bat`

### macOS/Linux Launcher says "Permission Denied"
```bash
chmod +x Linux_Mac_Launcher.sh
bash Linux_Mac_Launcher.sh
```

### Launcher closes immediately
Check the error message that appears. Common causes:
- Python not installed → Install from python.org
- requirements.txt missing → Make sure you're in the spatial-macro/ folder
- Insufficient permissions → Try with admin/sudo

---

## ❌ Python Issues

### "Python not found" (Windows)
The launcher will offer to download Python automatically.

**Manual install:**
1. https://www.python.org/downloads/
2. Download Python 3.10 or newer
3. **IMPORTANT:** Check "Add Python to PATH"
4. Restart your computer
5. Try the launcher again

### "Python not found" (macOS/Linux)
```bash
# macOS
brew install python3

# Ubuntu/Debian
sudo apt-get update
sudo apt-get install python3

# Fedora/RedHat
sudo dnf install python3
```

### Wrong Python version
The launchers require Python 3.10+

Check your version:
```bash
python --version    # or python3 --version
```

If you have an older version, uninstall it and install Python 3.10+

---

## ❌ Dependency Issues

### "Module not found" error

**Solution:** Run the launcher again (it installs dependencies)

Or manually:
```bash
# Windows
python -m pip install -r requirements.txt

# macOS/Linux
python3 -m pip install -r requirements.txt
```

### Installation fails with "Permission Denied"

Try with admin/sudo:
```bash
# Windows: Right-click launcher → Run as Administrator

# macOS/Linux
sudo python3 -m pip install -r requirements.txt
```

### pip not found

Install pip or use the launcher (it should handle this):
```bash
# Windows
python -m ensurepip

# macOS/Linux
python3 -m ensurepip
```

---

## ❌ Runtime Issues

### Macro crashes on startup

**Check:**
1. Is Roblox installed and running?
2. Is the game window in Windowed/Borderless mode?
3. Is display scaling at 100%?

**Try:**
1. Close all other macro applications
2. Restart the launcher
3. Check if it's an OS-specific issue (experimental on macOS/Linux)

### OCR not working

The RapidOCR model downloads on first run (~500MB).

**Solution:**
1. Wait a few seconds on first run
2. Restart the macro if it fails
3. Check your internet connection

### Keyboard/Mouse not responding

Try these in order:
1. Run launcher as Administrator (Windows) or sudo (Mac/Linux)
2. Disable keyboard acceleration in Windows settings
3. Restart the macro
4. Check if another macro app is interfering

### Display/Screenshot errors

**Causes:**
- Game in fullscreen (need Windowed/Borderless)
- Display scaling not 100%
- Wrong screen resolution

**Solution:**
1. Set Roblox to Windowed or Borderless Windowed
2. Windows: Settings → Display → Scale = 100%
3. Use a standard resolution like 1920x1080
4. Restart macro

---

## ❌ System-Specific Issues

### Windows: Antivirus Warning

**Why:** The macro uses keyboard/mouse automation (looks like keylogger)

**Solution:**
1. Add project folder to antivirus exceptions
2. Windows Defender: Settings → Virus protection → Manage exclusions
3. Code is open-source and safe (check on GitHub)

### macOS: "Cannot open" warning

Right-click file → Open → Click "Open" in the dialog

### Linux: "X11 Display Server" error

This macro requires X11 (not Wayland):
```bash
export GDK_BACKEND=x11
bash Linux_Mac_Launcher.sh
```

### Linux: Keyboard hook failed

Requires elevated permissions:
```bash
sudo bash Linux_Mac_Launcher.sh
```

---

## 🧹 Complete Reinstall

### Windows
```batch
rem Uninstall everything
python -m pip uninstall -y customtkinter numpy opencv-python keyboard pynput pywinctl screeninfo mss rapidocr_onnxruntime pillow requests onnxruntime pyclipper six shapely pyyaml flatbuffers packaging protobuf

rem Clear cache
rmdir /s /q __pycache__

rem Reinstall
python -m pip install -r requirements.txt

rem Run
python main.py
```

### macOS/Linux
```bash
# Uninstall everything
python3 -m pip uninstall -y customtkinter numpy opencv-python keyboard pynput pywinctl screeninfo mss rapidocr_onnxruntime pillow requests

# Clear cache
find . -type d -name __pycache__ -exec rm -rf {} +
find . -name "*.pyc" -delete

# Reinstall
python3 -m pip install -r requirements.txt

# Run
python3 main.py
```

---

## 📞 Still Need Help?

1. Check the original README.txt
2. Read SETUP.md for detailed setup
3. Try a complete reinstall (see above)
4. Check system requirements (see START_HERE.txt)

**For experimental macOS/Linux support:** 
- Linux & macOS support is untested
- Issues are expected, report them
- Windows is the primary platform

---

## 💡 Pro Tips

- **Run as Administrator (Windows)** or **sudo (Linux/Mac)** for better compatibility
- **Keep display scaling at 100%** for consistent OCR performance
- **Use Windowed/Borderless mode** in Roblox
- **Disable other macro applications** to avoid conflicts
- **Check internet connection** on first run (for OCR model download)

---

See **SETUP.md** for installation instructions.
