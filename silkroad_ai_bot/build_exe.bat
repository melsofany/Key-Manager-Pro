@echo off
echo ============================================
echo    بناء Silkroad AI Bot - EXE Builder
echo ============================================
echo.

REM تثبيت المتطلبات
echo [1/3] تثبيت المكتبات المطلوبة...
pip install -r requirements.txt
if errorlevel 1 (
    echo خطأ في تثبيت المكتبات!
    pause
    exit /b 1
)

echo.
echo [2/3] بناء ملف EXE...
pyinstaller ^
    --onefile ^
    --windowed ^
    --name "SilkroadAIBot" ^
    --add-data "system_prompt.txt;." ^
    --add-data "bot_config.json;." 2>nul ^
    --hidden-import PyQt5.sip ^
    --hidden-import requests ^
    main_gui.py

if errorlevel 1 (
    echo خطأ في عملية البناء!
    pause
    exit /b 1
)

echo.
echo [3/3] نسخ الملفات الإضافية...
if not exist "dist" mkdir dist
copy system_prompt.txt dist\ >nul 2>&1
if exist bot_config.json copy bot_config.json dist\ >nul 2>&1

echo.
echo ============================================
echo    تم البناء بنجاح!
echo    الملف موجود في: dist\SilkroadAIBot.exe
echo ============================================
pause
