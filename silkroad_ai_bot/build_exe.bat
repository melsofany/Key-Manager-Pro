@echo off
chcp 65001 >nul
echo ============================================
echo    بناء Silkroad AI Bot - EXE Builder
echo ============================================

echo [1/4] تثبيت المكتبات...
pip install PyQt5 requests pyinstaller beautifulsoup4 --quiet
if errorlevel 1 ( echo خطأ في التثبيت! & pause & exit /b 1 )

echo [2/4] بناء EXE...
pyinstaller ^
    --onefile ^
    --windowed ^
    --name "SilkroadAIBot" ^
    --add-data "system_prompt.txt;." ^
    --hidden-import PyQt5.sip ^
    --hidden-import PyQt5.QtCore ^
    --hidden-import PyQt5.QtWidgets ^
    --hidden-import PyQt5.QtGui ^
    --hidden-import requests ^
    --hidden-import json ^
    --hidden-import winreg ^
    --hidden-import subprocess ^
    --hidden-import threading ^
    main_gui.py

if errorlevel 1 ( echo خطأ في البناء! & pause & exit /b 1 )

echo [3/4] نسخ الملفات...
if not exist "dist" mkdir dist
copy system_prompt.txt dist\ >nul 2>&1
if exist bot_config.json copy bot_config.json dist\ >nul 2>&1

echo [4/4] إنشاء اختصار التشغيل...
echo @echo off > dist\تشغيل.bat
echo chcp 65001 ^>nul >> dist\تشغيل.bat
echo cd /d "%%~dp0" >> dist\تشغيل.bat
echo start SilkroadAIBot.exe >> dist\تشغيل.bat

echo.
echo ============================================
echo    تم البناء بنجاح!
echo    dist\SilkroadAIBot.exe
echo ============================================
pause
