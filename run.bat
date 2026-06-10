@echo off
setlocal
title VunVun's Macro Loader - V5.3

echo ========================================
echo   Spatial Macro Launcher - Initializing
echo ========================================

:: 1. Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 goto :no_python

:: 2. Check if Pip is available
python -m pip --version >nul 2>&1
if errorlevel 1 goto :no_pip

:: 3. Check for VC++ Redistributable
if exist "C:\Windows\System32\vcruntime140.dll" goto :skip_vc_check

echo.
echo [IMPORTANT] Microsoft Visual C++ Redistributable is missing.
echo This is required for the macro's OCR (Text Recognition) to work.
echo.
set /p choice="Do you want to automatically download and install the VC++ Redistributable? (Y/N): "
if /i "%choice%"=="Y" (
    echo.
    echo [INFO] Downloading VC++ Redistributable (vc_redist.x64.exe)...
    curl -L -o vc_redist.x64.exe https://aka.ms/vs/17/release/vc_redist.x64.exe
    if errorlevel 1 (
        echo [ERROR] Automatic download failed.
        goto :vc_manual
    )
    echo [INFO] Starting Microsoft VC++ Installer...
    start vc_redist.x64.exe
    echo.
    echo Please finish the Microsoft VC++ installation, then restart this macro.
    pause
    exit /b
)

:vc_manual
echo.
echo [MANUAL INSTALL INSTRUCTIONS]
echo 1. Go to: https://aka.ms/vs/17/release/vc_redist.x64.exe
echo 2. Download and run the 'vc_redist.x64.exe' file.
echo 3. Restart the macro once finished.
echo.
pause
goto :skip_vc_check

:no_python
echo.
echo [ERROR] Python is missing!
echo Python is required to run this macro.
echo.
set /p choice="Do you want to automatically download the Python installer? (Y/N): "
if /i "%choice%"=="Y" (
    echo.
    echo [INFO] Downloading Python 3.12 installer...
    curl -L -o python_installer.exe https://www.python.org/ftp/python/3.12.3/python-3.12.3-amd64.exe
    if errorlevel 1 (
        echo [ERROR] Automatic download failed.
        goto :python_manual
    )
    echo [INFO] Starting installer... 
    echo.
    echo *** IMPORTANT ***: Check the box "Add Python to PATH" in the installer window!
    echo.
    start python_installer.exe
    echo After installing, please RESTART this macro window.
    pause
    exit /b
)

:python_manual
echo.
echo [MANUAL INSTALL INSTRUCTIONS]
echo 1. Go to: https://www.python.org/downloads/
echo 2. Download the latest version of Python.
echo 3. *** IMPORTANT ***: Check the box "Add Python to PATH" during installation.
echo 4. Restart the macro once finished.
echo.
pause
exit /b

:no_pip
echo.
echo [ERROR] Pip (Python Package Manager) is missing!
echo.
set /p choice="Do you want to automatically install Pip? (Y/N): "
if /i "%choice%"=="Y" (
    echo [INFO] Attempting to install pip...
    python -m ensurepip --upgrade
    if errorlevel 1 (
        echo [ERROR] Failed to install pip automatically.
        goto :pip_manual
    )
    goto :skip_vc_check
)

:pip_manual
echo.
echo [MANUAL INSTALL INSTRUCTIONS]
echo 1. Open a terminal (CMD) and type: python -m ensurepip --upgrade
echo 2. If that fails, you may need to reinstall Python and check "pip" in the installer.
echo.
pause
exit /b

:skip_vc_check

:: 4. Install/Update requirements
echo.
echo [1/2] Checking and installing dependencies...
python -m pip install -r requirements.txt --quiet --upgrade
if errorlevel 1 goto :pip_fail

:: 5. Run the Macro
echo [2/2] Starting Spatial Macro...
echo.
python main.py

if errorlevel 1 goto :macro_crash

echo.
echo Macro closed normally.
pause
exit /b

:pip_fail
echo.
echo [ERROR] Failed to install requirements. 
echo Please check your internet connection and make sure no other 
echo Python processes are running.
pause
exit /b

:macro_crash
echo.
echo [CRASH] The macro has stopped unexpectedly.
echo.
echo TROUBLESHOOTING:
echo 1. If you see DLL errors, install the VC++ Redistributable.
echo 2. Make sure you checked "Add Python to PATH" during installation.
echo 3. Check for any error messages above.
echo.
pause
exit /b
