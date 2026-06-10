HOW TO RUN SPATIAL MACRO
========================

WHAT'S NEW IN V5.3
=================
- Improved Color Detection: Switched to HSV color space for clover detection. This significantly improves reliability for Bronze and Silver clovers.
- Dependency Checker: `run.bat` now checks for the Microsoft Visual C++ Redistributable.
- Robust OCR: Added error handling for OCR initialization to prevent crashes.
- Improved Startup: `run.bat` now automatically checks if Python is installed and upgrades packages.
- Advanced OCR Matching: Enhanced detection for moves with Roman Numerals (e.g., Arcane Door I-V).
- Visual Testing: The Move OCR Test now moves your mouse to the detected location to verify accuracy.

PREREQUISITES
=============
To run this macro, you MUST have Python installed on your computer.

1. Download Python: Go to https://www.python.org/downloads/
2. Install Python: Run the installer. 
   *** IMPORTANT ***: Check the box that says "Add Python to PATH" during installation.
3. Verify Pip: Pip is usually installed with Python automatically.

HOW TO RUN
==========

1. run.bat
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

[Explanations for each macro to be added by user]
