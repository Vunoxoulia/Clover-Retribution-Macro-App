@echo off
setlocal

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in your PATH.
    echo.
    echo Please install Python from https://www.python.org/downloads/
    echo and make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b
)

:: Install requirements
echo Checking requirements...
pip install -r requirements.txt --quiet

:: Run the macro
echo Starting...
python main.py
pause
