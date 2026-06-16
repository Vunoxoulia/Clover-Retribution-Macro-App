# Clover-Retribution-Macro-App

Hello everyone this is my open source macro app

**How To Download**

Click the green "Code" button and extract as zip file

REREQUISITES & SYSTEM REQUIREMENTS
==================================

SOFTWARE REQUIREMENTS:
- Operating System: Windows 10 or Windows 11 (64-bit).
- Python: Version 3.10 to 3.13 (3.12.3 is recommended).

HARDWARE REQUIREMENTS:
- CPU: Intel Core i3 / AMD Ryzen 3 or better.
- RAM: 4GB Minimum (8GB+ recommended for OCR stability).
- GPU: Any modern GPU. (NVIDIA GPUs with CUDA support will make OCR significantly faster).

DISPLAY SETTINGS:
- Resolution: Optimized for 1920x1080.
- Windows Scaling: 100% is strongly recommended.
- Game Mode: Windowed or Borderless Windowed mode is required for screen capture.

INSTALLING PYTHON:
1. Download Python: Go to https://www.python.org/downloads/
2. Install Python: Run the installer. 
   *** IMPORTANT ***: Check the box that says "Add Python to PATH" during installation.
3. Verify Pip: Pip is usually installed with Python automatically.

HOW TO RUN
==========

double click or open Windows_Launcher.bat for windows users

double click or open Linux_Mac_Launcher.sh for Linux and Mac users this is however experimental im not sure if its going to work.

----------
Use this for daily use. It will automatically install required libraries, check for system dependencies, and start the macro.
Double-click this file to launch.

TROUBLESHOOTING: MALWARE WARNINGS
=================================
Some Antivirus software (including Windows Defender) may flag this project as "Malware", "Trojan", or "Keygen". These are **FALSE POSITIVES**.

Why is this happening?
1. Trojan/Keylogger: The macro uses libraries (keyboard, win32api) to simulate keystrokes and mouse clicks in Roblox. Since these libraries "hook" into your input, antivirus software flags them as potential keyloggers.
2. Keygen/Downloader: The `updater.py` script is designed to download the latest version from GitHub and replace local files. This behavior (downloading and modifying its own files) is a common trigger for "Keygen" or "Downloader" heuristics.

Is it safe?
Yes. The code is open-source. You can inspect `utils.py` to see exactly how keyboard/mouse inputs are handled, and `updater.py` to see how updates are processed.

USAGE
=====
- Select the desired macro from the tabs.
- Configure your settings in the 'Settings' tab if needed.
- Click 'Start' to begin the sequence.
- Focus the Roblox window immediately after starting.
