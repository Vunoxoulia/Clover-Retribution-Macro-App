@echo off
setlocal enabledelayedexpansion
title VunVun's Macro Loader - V6.2.4
echo ========================================
echo   Spatial Macro Launcher - Initializing
echo ========================================

REM Always work from the folder this launcher is in ("Run as administrator" starts in System32)
cd /d "%~dp0"
if not exist "requirements.txt" (
    echo.
    echo [ERROR] requirements.txt was not found next to this launcher.
    echo.
    echo   1. UNZIP the download first: right-click the .zip, "Extract All...",
    echo      then open the extracted folder and run Windows_Launcher.bat from there.
    echo      Running it from inside the .zip does NOT work.
    echo   2. Do NOT use "Run as administrator" - just double-click the launcher.
    echo.
    echo   Current folder: !CD!
    echo.
    pause
    exit /b 1
)


set "PY_EXE="


python --version >nul 2>&1
if !errorlevel! == 0 (
    set "PY_EXE=python"
    goto :python_ok
)


python3 --version >nul 2>&1
if !errorlevel! == 0 (
    set "PY_EXE=python3"
    goto :python_ok
)


py --version >nul 2>&1
if !errorlevel! == 0 (
    set "PY_EXE=py"
    goto :python_ok
)


echo [INFO] Scanning system for Python...
for /f "usebackq tokens=*" %%a in (`powershell -NoProfile -Command "Get-ItemProperty -Path 'HKLM:\SOFTWARE\Python\PythonCore\*\InstallPath', 'HKCU:\SOFTWARE\Python\PythonCore\*\InstallPath' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty '(default)' | ForEach-Object { Join-Path $_ 'python.exe' } | Where-Object { Test-Path $_ } | Select-Object -First 1"`) do (
    set "PY_EXE=%%a"
    goto :python_ok
)


for %%v in (313 312 311 310) do (
    if exist "!LocalAppData!\Programs\Python\Python%%v\python.exe" (
        set "PY_EXE=!LocalAppData!\Programs\Python\Python%%v\python.exe"
        goto :python_ok
    )
    if exist "!ProgramFiles!\Python%%v\python.exe" (
        set "PY_EXE=!ProgramFiles!\Python%%v\python.exe"
        goto :python_ok
    )
)


for /f "tokens=*" %%i in ('where python 2^>nul') do (
    echo %%i | findstr /i "WindowsApps" >nul
    if !errorlevel! neq 0 (
        %%i --version >nul 2>&1
        if !errorlevel! == 0 (
            set "PY_EXE=%%i"
            goto :python_ok
        )
    )
)

goto :no_python

:no_python
echo.
echo [ERROR] Python is missing!
echo Python is required to run this macro.
echo.
set /p "CHOICE=Do you want to automatically download the Python installer? (Y/N): "
if /i "!CHOICE!" neq "Y" exit

echo.
echo [INFO] Downloading Python 3.12 installer...
set "PY_URL=https://www.python.org/ftp/python/3.12.3/python-3.12.3-amd64.exe"
set "PY_INST=!TEMP!\python_installer_v54.exe"


curl -L -o "!PY_INST!" "!PY_URL!"
if !errorlevel! neq 0 (
    
    powershell -Command "Invoke-WebRequest -Uri '!PY_URL!' -OutFile '!PY_INST!'"
)

if not exist "!PY_INST!" (
    echo [ERROR] Download failed. Please install Python manually from python.org
    pause
    exit
)

echo [INFO] Starting installer...
echo.
echo  IMPORTANT: Check the box "Add Python to PATH" in the installer window!
echo.
start /wait "" "!PY_INST!" /passive PrependPath=1

echo.
echo [INFO] Installation finished.
echo [INFO] Please RESTART this macro window to apply changes.
pause
exit

:python_ok
REM "call" keeps the quotes when Python is in a folder with spaces (C:\Program Files\...)
set "PY_VER=unknown"
for /f "tokens=2 delims= " %%V in ('call "!PY_EXE!" --version 2^>^&1') do set "PY_VER=%%V"
REM Let Python check its own version (no fragile number parsing)
call "!PY_EXE!" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] Unsupported Python version: !PY_VER!
    echo This project requires Python 3.10 or newer.
    pause
    exit /b 1
)
echo [INFO] Using: !PY_EXE! - Python !PY_VER!


echo.
echo [INFO] Performing cleanup...


if exist "!LocalAppData!\Python\pythoncore-3.14-64\python.exe" (
    echo [CLEANING] Legacy 3.14 assets...
    "!LocalAppData!\Python\pythoncore-3.14-64\python.exe" -m pip uninstall -y easyocr torch torchvision >nul 2>&1
)


"!PY_EXE!" -m pip uninstall -y easyocr torch torchvision >nul 2>&1


if exist "!USERPROFILE!\.EasyOCR" (
    echo [INFO] Removing EasyOCR model cache...
    rmdir /s /q "!USERPROFILE!\.EasyOCR" >nul 2>&1
)
echo [SUCCESS] Cleanup complete.


echo.
echo [INFO] RapidOCR is now the default engine.
echo [INFO] No external software (like Tesseract) is required anymore!


REM The text reader (RapidOCR / onnxruntime) needs the Microsoft Visual C++ Redistributable (x64)
set "VC_OK=1"
if not exist "!SystemRoot!\System32\vcruntime140_1.dll" set "VC_OK=0"
if not exist "!SystemRoot!\System32\msvcp140.dll" set "VC_OK=0"
if "!VC_OK!"=="0" (
    echo.
    echo [WARNING] Microsoft Visual C++ Redistributable x64 was NOT found.
    echo   The macro needs it to read text on screen - OCR, events, items, OK popups.
    echo   Download and install it: https://aka.ms/vs/17/release/vc_redist.x64.exe
    echo   Then run this launcher again.
    echo.
    pause
)

echo.
echo [1/2] Syncing dependencies...
"!PY_EXE!" -m pip install -r requirements.txt --no-warn-script-location
if !errorlevel! neq 0 (
    echo [ERROR] Failed to install requirements.
    echo   Common fixes:
    echo   - Install Microsoft Visual C++ Redistributable x64: https://aka.ms/vs/17/release/vc_redist.x64.exe
    echo   - Check your internet connection, then run the launcher again
    echo   - Do not run it as administrator, and run it from the UNZIPPED folder
    pause
    exit
)


echo.
echo [2/2] Starting Spatial Macro...
echo [NOTICE] The first start may take a
echo moment to initialize the RapidOCR engine. Please wait!
echo.
"!PY_EXE!" main.py
if !errorlevel! neq 0 (
    echo.
    echo [CRASH] The macro has stopped unexpectedly.
    echo   If the error above mentions "DLL load failed" or onnxruntime, install
    echo   Microsoft Visual C++ Redistributable x64: https://aka.ms/vs/17/release/vc_redist.x64.exe
    pause
)
exit
