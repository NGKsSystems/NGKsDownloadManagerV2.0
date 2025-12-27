@echo off
echo ===================================
echo NGK's Download Manager Setup
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

echo Python found, starting setup...
echo.

:: Run setup script
python setup.py

if errorlevel 1 (
    echo.
    echo Setup failed! Please check the error messages above.
    pause
    exit /b 1
)

echo.
echo Setup completed successfully!
echo You can now run the application with: python main.py
echo.
pause