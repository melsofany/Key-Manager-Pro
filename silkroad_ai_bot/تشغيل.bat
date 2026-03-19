@echo off
chcp 65001 >nul
echo ============================================
echo    Silkroad AI Bot - تشغيل البرنامج
echo ============================================
echo.

REM تحقق من وجود Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [خطأ] Python غير مثبت!
    echo يرجى تنزيل Python من: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM تثبيت المتطلبات إذا لم تكن مثبتة
echo تثبيت المكتبات المطلوبة...
pip install PyQt5 requests --quiet

echo تشغيل البرنامج...
python main_gui.py

pause
