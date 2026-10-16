@echo off
setlocal enabledelayedexpansion
title VunVun's Macro Loader - V6.3.1
REM Always work from the folder this launcher is in ("Run as administrator" starts in System32)
cd /d "%~dp0"

echo.
echo VunVun's Macro Loader
echo =====================
echo.

if not exist "app\requirements.txt" (
    echo   [ERROR] app\requirements.txt was not found next to this launcher.
    echo.
    echo     1. UNZIP the download first: right-click the .zip, "Extract All...",
    echo        then run Windows_Launcher.bat from the extracted folder.
    echo     2. Don't use "Run as administrator" - just double-click it.
    echo.
    echo     Current folder: !CD!
    echo.
    pause
    exit /b 1
)

set "CACHE=.launcher"
if not exist "!CACHE!" mkdir "!CACHE!" >nul 2>&1
set "PY_EXE="

REM ---------------------------------------------------------------------------
REM [1/3] Find Python 3.11 - 3.14  (remembered after the first start, so this is instant)
REM ---------------------------------------------------------------------------
<nul set /p "=[1/3] Python ........ "

if exist "!CACHE!\python.txt" (
    set /p PY_EXE=<"!CACHE!\python.txt"
    if defined PY_EXE call :check_python "!PY_EXE!" || set "PY_EXE="
)
if not defined PY_EXE call :find_python
if not defined PY_EXE goto :no_python

> "!CACHE!\python.txt" echo !PY_EXE!
for /f "tokens=2 delims= " %%V in ('call "!PY_EXE!" --version 2^>^&1') do set "PY_VER=%%V"
echo Python !PY_VER!

REM ---------------------------------------------------------------------------
REM [2/3] Packages: only installed when requirements.txt changed or one is missing
REM ---------------------------------------------------------------------------
<nul set /p "=[2/3] Packages ...... "

if not exist "!CACHE!\cleaned.txt" (
    REM one-time removal of the old, huge OCR engine from earlier versions
    call "!PY_EXE!" -m pip uninstall -y easyocr torch torchvision >nul 2>&1
    if exist "!USERPROFILE!\.EasyOCR" rmdir /s /q "!USERPROFILE!\.EasyOCR" >nul 2>&1
    > "!CACHE!\cleaned.txt" echo done
)

set "NEED_INSTALL=1"
if exist "!CACHE!\requirements.txt" (
    fc /b "app\requirements.txt" "!CACHE!\requirements.txt" >nul 2>&1 && set "NEED_INSTALL=0"
)
if "!NEED_INSTALL!"=="0" (
    call "!PY_EXE!" -c "import importlib.util as u,sys; m=['customtkinter','mss','numpy','cv2','keyboard','rapidocr_onnxruntime','onnxruntime','pynput','pywinctl','screeninfo','PIL','requests']; sys.exit(0 if all(u.find_spec(x) for x in m) else 1)" >nul 2>&1 || set "NEED_INSTALL=1"
)

if "!NEED_INSTALL!"=="0" (
    echo up to date
) else (
    echo installing / updating - this takes a minute the first time...
    call "!PY_EXE!" -m pip install -r "app\requirements.txt" --disable-pip-version-check --no-warn-script-location -q
    if errorlevel 1 (
        echo.
        echo   [ERROR] Couldn't install the packages.
        echo     - Check your internet connection, then run the launcher again
        echo     - Install Microsoft Visual C++ Redistributable x64: https://aka.ms/vs/17/release/vc_redist.x64.exe
        echo     - Run it from the UNZIPPED folder, and not as administrator
        echo.
        pause
        exit /b 1
    )
    copy /y "app\requirements.txt" "!CACHE!\requirements.txt" >nul
    echo                       done
)

REM The text reader (OCR) needs the Microsoft Visual C++ Redistributable (x64)
if not exist "!SystemRoot!\System32\vcruntime140_1.dll" (
    echo.
    echo   [WARNING] Microsoft Visual C++ Redistributable x64 is missing.
    echo     Reading text on screen won't work until it's installed - events, items, OK popups.
    echo     Download: https://aka.ms/vs/17/release/vc_redist.x64.exe
    echo.
)

REM ---------------------------------------------------------------------------
REM [3/3] Start
REM ---------------------------------------------------------------------------
echo [3/3] Starting ...... the macro window opens in a moment
echo.
call "!PY_EXE!" "app\main.py"
if errorlevel 1 (
    echo.
    echo   [CRASH] The macro stopped unexpectedly - see the error above.
    echo     "DLL load failed" / onnxruntime: install Microsoft Visual C++ Redistributable x64
    echo     https://aka.ms/vs/17/release/vc_redist.x64.exe
    echo.
    pause
)
exit /b 0


REM ===========================================================================
:check_python
REM  ok (errorlevel 0) when %1 runs and is Python 3.11 - 3.14: the versions the text reader
REM  (onnxruntime 1.27.0) has builds for. 3.10 is too old for it, 3.15 too new (pip finds nothing).
call "%~1" -c "import sys; sys.exit(0 if (3, 11) <= sys.version_info[:2] <= (3, 14) else 1)" >nul 2>&1
exit /b %errorlevel%

:find_python
REM  1. the official "py" launcher, asking for a SUPPORTED version (3.12 first) - not just the newest
for %%v in (3.12 3.13 3.11 3.14) do (
    for /f "delims=" %%P in ('py -%%v -c "import sys; print(sys.executable)" 2^>nul') do (
        call :check_python "%%P" && (set "PY_EXE=%%P" & exit /b 0)
    )
)
REM  2. python on PATH (skipping the Microsoft Store shortcut that only opens the Store)
for /f "delims=" %%P in ('where python 2^>nul') do (
    echo %%P | findstr /i "WindowsApps" >nul || (
        call :check_python "%%P" && (set "PY_EXE=%%P" & exit /b 0)
    )
)
REM  3. the usual install folders
for %%v in (312 313 311 314) do (
    for %%R in ("!LocalAppData!\Programs\Python\Python%%v" "!ProgramFiles!\Python%%v") do (
        if exist "%%~R\python.exe" (
            call :check_python "%%~R\python.exe" && (set "PY_EXE=%%~R\python.exe" & exit /b 0)
        )
    )
)
exit /b 1

:no_python
set "OTHER_PY="
for /f "tokens=2 delims= " %%V in ('python --version 2^>nul') do set "OTHER_PY=%%V"
if not defined OTHER_PY for /f "tokens=2 delims= " %%V in ('py --version 2^>nul') do set "OTHER_PY=%%V"
if defined OTHER_PY (echo Python !OTHER_PY! - not supported) else (echo not found)
echo.
if defined OTHER_PY (
    echo   [NOTE] You have Python !OTHER_PY!, but the macro needs Python 3.11 - 3.14.
    echo       Its text reader, onnxruntime, isn't available for other versions.
    echo       Python 3.12 can be installed NEXT TO it - your current Python stays as it is.
) else (
    echo   [ERROR] Python 3.11 - 3.14 is needed and wasn't found.
)
echo.
set /p "CHOICE=  Download and install Python 3.12 now? (Y/N): "
if /i not "!CHOICE!"=="Y" exit /b 1
set "PY_URL=https://www.python.org/ftp/python/3.12.3/python-3.12.3-amd64.exe"
set "PY_INST=!TEMP!\python_installer_vunvun.exe"
echo.
echo   Downloading Python 3.12 ...
curl -L -s -o "!PY_INST!" "!PY_URL!" || powershell -NoProfile -Command "Invoke-WebRequest -Uri '!PY_URL!' -OutFile '!PY_INST!'"
if not exist "!PY_INST!" (
    echo   [ERROR] Download failed. Install Python from python.org, then run this again.
    pause
    exit /b 1
)
echo   Installing ... tick "Add Python to PATH" if the installer asks.
start /wait "" "!PY_INST!" /passive PrependPath=1
echo.
echo   Done. Close this window and run the launcher again.
pause
exit /b 0
