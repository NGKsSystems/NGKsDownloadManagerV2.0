@echo off
echo ===================================
echo Starting NGK's Download Manager
echo ===================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

:: Check if main.py exists
if not exist "main.py" (
    echo Error: main.py not found
    echo Make sure you're running this from the correct directory
    pause
    exit /b 1
)

echo Starting application...
python main.py

if errorlevel 1 (
    echo.
    echo Application exited with an error.
    pause
)