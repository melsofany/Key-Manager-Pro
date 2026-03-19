@echo off
cd /d "%~dp0"
chcp 65001 >nul 2>&1

echo ============================================
echo    Silkroad AI Bot - Starting...
echo ============================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    echo Please install Python from: https://www.python.org/downloads/
    echo During installation, check the box: "Add Python to PATH"
    pause
    exit /b 1
)

echo Installing required libraries...
pip install PyQt5 requests beautifulsoup4 --quiet --exists-action i

echo.
echo Launching bot...
python main_gui.py

if errorlevel 1 (
    echo.
    echo Bot exited with an error. See details above.
    pause
)
