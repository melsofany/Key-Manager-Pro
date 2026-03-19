@echo off
chcp 65001 >nul
echo ============================================
echo    بناء Silkroad AI Bot - EXE Builder
echo ============================================

echo [1/3] تثبيت المكتبات...
pip install PyQt5 requests pyinstaller --quiet
if errorlevel 1 ( echo خطأ في التثبيت! & pause & exit /b 1 )

echo [2/3] بناء EXE...
pyinstaller ^
    --onefile ^
    --windowed ^
    --name "SilkroadAIBot" ^
    --add-data "system_prompt.txt;." ^
    --hidden-import PyQt5.sip ^
    --hidden-import requests ^
    --hidden-import json ^
    main_gui.py

if errorlevel 1 ( echo خطأ في البناء! & pause & exit /b 1 )

echo [3/3] نسخ الملفات...
if not exist "dist" mkdir dist
copy system_prompt.txt dist\ >nul 2>&1
if exist bot_config.json copy bot_config.json dist\ >nul 2>&1

echo.
echo ============================================
echo    تم البناء بنجاح!
echo    dist\SilkroadAIBot.exe
echo ============================================
pause
