@echo off
echo ========================================
echo  Spatial Library Macro - Build Script
echo ========================================
echo.

REM Install all requirements first
echo [1/4] Installing requirements...
pip install -r requirements.txt

REM Install PyInstaller if not present
echo [2/4] Checking PyInstaller...
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

REM Clean previous builds
echo [3/4] Cleaning previous builds...
if exist build rmdir /s /q build >nul 2>&1
if exist dist rmdir /s /q dist >nul 2>&1
if exist *.spec del *.spec >nul 2>&1

REM Build executable
echo [4/4] Building executable...
echo This may take several minutes...
echo.

set ICON_PARAM=
set ADD_DATA=
if exist "Vunoxoulia.ico" (
    set ICON_PARAM=--icon="Vunoxoulia.ico"
    set ADD_DATA=--add-data "Vunoxoulia.ico;."
)

python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "Spatial_Library_Macro" ^
    %ICON_PARAM% ^
    %ADD_DATA% ^
    --hidden-import=customtkinter ^
    --hidden-import=mss ^
    --hidden-import=cv2 ^
    --hidden-import=numpy ^
    --hidden-import=keyboard ^
    --hidden-import=win32api ^
    --hidden-import=win32con ^
    --hidden-import=win32gui ^
    --hidden-import=PIL ^
    --hidden-import=PIL.Image ^
    --hidden-import=gui ^
    --hidden-import=logic ^
    --hidden-import=utils ^
    --hidden-import=settings ^
    --hidden-import=overlay ^
    --hidden-import=easyocr ^
    --collect-all=customtkinter ^
    --collect-all=easyocr ^
    --distpath=dist ^
    --workpath=build ^
    --specpath=. ^
    main.py

if errorlevel 1 (
    echo.
    echo BUILD FAILED!
    pause
    exit /b 1
)

echo.
echo ========================================
echo  BUILD SUCCESS!
echo  Output: dist\Spatial_Library_Macro.exe
echo ========================================
echo.
pause
