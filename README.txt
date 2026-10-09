HOW TO RUN SPATIAL MACRO
========================

WHAT'S NEW IN V6.1
===================
- fixed Event Notifier not working with multiple Roblox windows (each window now posts its own events and does its own /clear)
- fixed Event Notifier not posting events that were already in chat when you turned alerts on
- fixed "Same event again after" blocking other windows (it now counts per window)
- fixed the Skill Macro pressing keys in the middle of an event check (it now waits until the check and /clear are done)
- fixed Event alerts turning on by themselves when opening the app (always OFF at start now)
- fixed the Skill Macro not clicking "Ok" popups while running (no need to turn on Always Click OK anymore)
- fixed staying on the wrong window after an "Ok" popup was clicked in another Roblox window
- fixed Library / Mining routes going off-course when an "Ok" popup appears mid-walk (the walk now pauses, clicks Ok, then continues where it was)
- fixed an error message spam after leaving the Skill Macro page

WHAT'S NEW IN V6
=================
- NEW Skill Macro: auto uses your skills when they're ready, in the order you pick
- Skill Combo: press one key to do a chain of moves
- Item auto-use: uses an item (hotkey + M1) when a message like "Obtained Copper!" shows up
- Loadouts: save different skill setups and switch between them
- NEW Event Notifier: sends server events from chat to your Discord (works in every macro or on its own)
- Mouse aim: make moves aim at a spot on the screen before casting
- added Setup Guides with pictures for every macro, Events and OK Popup (click "How to Setup" or "? Help")
- Library Macro: new ways to find the wisp's buttons if the auto one doesn't work
- Library Macro: new minigame detector, it knows when to click clovers and when to walk
- Library Macro: Test Path button works now (also on F3)
- Mining Macro: routes now use however many ores you record
- cleaner and faster menus, with the same big ON/OFF buttons everywhere
- Library Macro: can hide the chat during the minigame so it isn't clicked as a clover
- fixed the macro window not coming back when you press Esc while selecting an area, spot or color

PREREQUISITES & SYSTEM REQUIREMENTS
==================================

SOFTWARE REQUIREMENTS:
- Operating System: Windows 10 or Windows 11 (64-bit).
- Python: Version 3.10 or newer (3.12.3 is recommended).
- Microsoft Visual C++ Redistributable (x64): Required for OCR features.
  (run.bat will check for this and provide a download link if missing).

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