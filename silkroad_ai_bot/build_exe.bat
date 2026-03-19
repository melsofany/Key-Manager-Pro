@echo off
cd /d "%~dp0"
chcp 65001 >nul 2>&1

echo ============================================
echo    Silkroad AI Bot - EXE Builder
echo ============================================
echo.

echo [1/4] Installing required libraries...
pip install PyQt5 requests pyinstaller beautifulsoup4 --quiet
if errorlevel 1 (
    echo ERROR: Failed to install libraries!
    pause
    exit /b 1
)

echo [2/4] Building EXE file...
pyinstaller --onefile --windowed --name "SilkroadAIBot" ^
    --add-data "system_prompt.txt;." ^
    --hidden-import PyQt5.sip ^
    --hidden-import PyQt5.QtCore ^
    --hidden-import PyQt5.QtWidgets ^
    --hidden-import PyQt5.QtGui ^
    --hidden-import requests ^
    --hidden-import winreg ^
    --hidden-import subprocess ^
    --hidden-import threading ^
    main_gui.py

if errorlevel 1 (
    echo ERROR: Build failed!
    pause
    exit /b 1
)

echo [3/4] Copying extra files to dist...
if not exist "dist" mkdir dist
copy system_prompt.txt dist\ >nul 2>&1
if exist bot_config.json copy bot_config.json dist\ >nul 2>&1

echo [4/4] Creating run shortcut...
(
    echo @echo off
    echo cd /d "%%~dp0"
    echo start SilkroadAIBot.exe
) > "dist\Run Bot.bat"

echo.
echo ============================================
echo    Build successful!
echo    Output: dist\SilkroadAIBot.exe
echo ============================================
pause
