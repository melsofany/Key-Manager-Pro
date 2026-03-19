"""
game_launcher.py - إدارة تشغيل اللعبة وملف التنفيذ
يتولى: الكشف عن مسار اللعبة، تشغيل العميل، مراقبة العملية
"""

import os
import sys
import time
import subprocess
import threading

# Windows-only creation flags
_NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW — يخفي نافذة CMD عند استدعاء tasklist

# المسارات الافتراضية الشائعة للعبة
DEFAULT_PATHS = [
    r"C:\Silkroad",
    r"C:\iSRO",
    r"C:\JOYMAX\Silkroad",
    r"C:\Program Files\Silkroad",
    r"C:\Program Files (x86)\Silkroad",
    r"D:\Silkroad",
    r"D:\Games\Silkroad",
    r"C:\phBot",
    r"C:\Program Files\phBot",
    r"D:\phBot",
]

# الملفات التنفيذية الشائعة
COMMON_EXECUTABLES = [
    "sro_client.exe",
    "Silkroad.exe",
    "SR_Client.exe",
    "phBot.exe",
    "loader.exe",
    "Loader.exe",
    "start.exe",
    "Launch.exe",
]

PHBOT_EXECUTABLES = [
    "phBot.exe",
    "phBot Testing.exe",
]


class GameLauncher:
    def __init__(self, config: dict, logger):
        self.config = config
        self.log = logger
        self.game_process = None
        self.phbot_process = None
        self._monitor_thread = None
        self._monitoring = False

    # ─── كشف تلقائي ───────────────────────────────────────────────────────
    def auto_detect_game(self) -> str:
        """محاولة الكشف التلقائي عن مسار اللعبة"""
        for path in DEFAULT_PATHS:
            if os.path.isdir(path):
                for exe in COMMON_EXECUTABLES:
                    full = os.path.join(path, exe)
                    if os.path.isfile(full):
                        self.log(f"✅ تم اكتشاف اللعبة: {full}", "success")
                        return full

        if sys.platform == "win32":
            registry_result = self._search_registry()
            if registry_result:
                return registry_result

        current_dir = os.getcwd()
        for exe in COMMON_EXECUTABLES:
            full = os.path.join(current_dir, exe)
            if os.path.isfile(full):
                self.log(f"✅ وُجد في المجلد الحالي: {full}", "success")
                return full

        self.log("⚠️ لم يتم اكتشاف اللعبة تلقائياً — حدّد المسار يدوياً", "warning")
        return ""

    def _search_registry(self) -> str:
        """البحث في سجل Windows عن مسار اللعبة"""
        registry_keys = [
            r"SOFTWARE\JOYMAX\Silkroad",
            r"SOFTWARE\WOW6432Node\JOYMAX\Silkroad",
            r"SOFTWARE\phBot",
        ]
        try:
            import winreg
            for key_path in registry_keys:
                try:
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
                    path, _ = winreg.QueryValueEx(key, "InstallPath")
                    winreg.CloseKey(key)
                    if path and os.path.isdir(path):
                        for exe in COMMON_EXECUTABLES:
                            full = os.path.join(path, exe)
                            if os.path.isfile(full):
                                self.log(f"✅ وُجد في Registry: {full}", "success")
                                return full
                except (FileNotFoundError, OSError):
                    continue
        except ImportError:
            pass
        return ""

    def scan_folder(self, folder: str) -> list:
        """فحص مجلد وإرجاع قائمة الملفات التنفيذية"""
        found = []
        if not os.path.isdir(folder):
            return found
        try:
            for f in os.listdir(folder):
                if f.lower().endswith(".exe"):
                    full = os.path.join(folder, f)
                    size_mb = os.path.getsize(full) / (1024 * 1024)
                    found.append({
                        "name": f,
                        "path": full,
                        "size_mb": round(size_mb, 1),
                        "is_game":  any(f.lower() == e.lower() for e in COMMON_EXECUTABLES),
                        "is_phbot": any(f.lower() == e.lower() for e in PHBOT_EXECUTABLES),
                    })
        except PermissionError:
            pass
        return sorted(found, key=lambda x: (not x["is_game"], not x["is_phbot"], x["name"]))

    # ─── تشغيل اللعبة ─────────────────────────────────────────────────────
    def _shell_launch(self, exe_path: str, args: str = "", cwd: str = "") -> bool:
        """
        تشغيل EXE عبر ShellExecuteW مع runas لرفع صلاحيات UAC تلقائياً.
        يعمل حتى لو البرنامج يحتاج Admin. لا يُظهر نافذة CMD.
        """
        if sys.platform != "win32":
            # Linux/Mac — تشغيل مباشر بدون elevation
            subprocess.Popen(
                [exe_path] + (args.split() if args else []),
                cwd=cwd or os.path.dirname(exe_path),
            )
            return True

        try:
            import ctypes
            ret = ctypes.windll.shell32.ShellExecuteW(
                None,                              # hwnd
                "runas",                           # verb  → يطلب UAC إذا لزم
                exe_path,                          # مسار الملف
                args if args else None,            # arguments
                cwd or os.path.dirname(exe_path),  # مجلد العمل
                1,                                 # SW_SHOWNORMAL
            )
            # ShellExecuteW تُعيد > 32 عند النجاح
            if ret > 32:
                return True
            # أكواد الخطأ الشائعة
            err_map = {
                0:  "نفاد الذاكرة",
                2:  "الملف غير موجود",
                3:  "المجلد غير موجود",
                5:  "تم رفض الوصول (Access Denied)",
                8:  "ذاكرة غير كافية",
                32: "الملف مُقفَل من برنامج آخر",
            }
            msg = err_map.get(ret, f"خطأ رقم {ret}")
            self.log(f"❌ فشل ShellExecute: {msg}", "error")
            return False
        except Exception as e:
            self.log(f"❌ خطأ في تشغيل اللعبة: {e}", "error")
            return False

    def launch_game(self) -> bool:
        """تشغيل عميل اللعبة — يرفع UAC تلقائياً إن احتاج"""
        exe_path = self.config.get("game_exe_path", "")
        if not exe_path:
            self.log("❌ لم يتم تحديد مسار ملف اللعبة", "error")
            return False
        if not os.path.isfile(exe_path):
            self.log(f"❌ الملف غير موجود: {exe_path}", "error")
            return False

        if self.is_game_running():
            self.log("⚠️ اللعبة تعمل بالفعل", "warning")
            return True

        args   = self.config.get("game_launch_args", "").strip()
        folder = os.path.dirname(exe_path)
        self.log(f"🚀 جاري تشغيل: {os.path.basename(exe_path)} ...", "info")

        ok = self._shell_launch(exe_path, args, folder)
        if ok:
            self.log(f"✅ تم تشغيل اللعبة بنجاح", "success")
            self._start_monitor()
        return ok

    def launch_phbot(self) -> bool:
        """تشغيل phBot — يرفع UAC تلقائياً إن احتاج"""
        phbot_path = self.config.get("phbot_exe_path", "")
        if not phbot_path:
            self.log("⚠️ لم يتم تحديد مسار phBot", "warning")
            return False
        if not os.path.isfile(phbot_path):
            self.log(f"❌ phBot غير موجود: {phbot_path}", "error")
            return False

        self.log("🤖 جاري تشغيل phBot ...", "info")
        ok = self._shell_launch(phbot_path, "", os.path.dirname(phbot_path))
        if ok:
            self.log("✅ تم تشغيل phBot بنجاح", "success")
        return ok

    def launch_sequence(self) -> bool:
        """تشغيل متسلسل: اللعبة → phBot (إن وُجد) → الانتظار"""
        self.log("🔄 بدء تسلسل تشغيل اللعبة...", "info")
        if not self.launch_game():
            return False

        wait_secs = self.config.get("game_startup_wait", 8)
        self.log(f"⏳ انتظار {wait_secs} ثانية لتحميل اللعبة...", "info")
        time.sleep(wait_secs)

        if self.config.get("use_phbot") and self.config.get("phbot_exe_path"):
            self.launch_phbot()
            time.sleep(3)

        self.log("✅ تم تشغيل اللعبة بنجاح وجاهزة للبوت", "success")
        return True

    # ─── إغلاق اللعبة ─────────────────────────────────────────────────────
    def close_game(self):
        if self.game_process:
            try:
                self.game_process.terminate()
                self.log("🔴 تم إغلاق عميل اللعبة", "warning")
            except Exception as e:
                self.log(f"خطأ في الإغلاق: {e}", "error")
            self.game_process = None

    def close_phbot(self):
        if self.phbot_process:
            try:
                self.phbot_process.terminate()
                self.log("🔴 تم إغلاق phBot", "warning")
            except Exception as e:
                self.log(f"خطأ في إغلاق phBot: {e}", "error")
            self.phbot_process = None

    def restart_game(self):
        """إعادة تشغيل اللعبة عند الانقطاع"""
        self.log("🔄 إعادة تشغيل اللعبة...", "warning")
        self.close_game()
        time.sleep(2)
        self.launch_sequence()

    # ─── مراقبة العملية ───────────────────────────────────────────────────
    def is_game_running(self) -> bool:
        """التحقق من أن اللعبة تعمل — بدون فتح CMD"""
        if self.game_process:
            return self.game_process.poll() is None

        exe_path = self.config.get("game_exe_path", "")
        if not exe_path:
            return False
        exe_name = os.path.basename(exe_path).lower()
        return self._find_process_by_name(exe_name)

    def is_phbot_running(self) -> bool:
        if self.phbot_process:
            return self.phbot_process.poll() is None
        phbot_path = self.config.get("phbot_exe_path", "")
        if not phbot_path:
            return False
        return self._find_process_by_name(os.path.basename(phbot_path).lower())

    def _find_process_by_name(self, exe_name: str) -> bool:
        """البحث عن عملية بالاسم بدون فتح نافذة CMD"""
        if sys.platform != "win32":
            return False
        # أولاً: حاول psutil (أسرع وأنظف)
        try:
            import psutil
            for p in psutil.process_iter(["name"]):
                if p.info["name"] and p.info["name"].lower() == exe_name:
                    return True
            return False
        except ImportError:
            pass
        # ثانياً: tasklist مع CREATE_NO_WINDOW
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {exe_name}", "/NH"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=_NO_WINDOW,
            )
            return exe_name.lower() in result.stdout.lower()
        except Exception:
            return False

    def get_process_status(self) -> dict:
        return {
            "game_running":  self.is_game_running(),
            "phbot_running": self.is_phbot_running(),
            "game_pid":  self.game_process.pid  if self.game_process  and self.game_process.poll()  is None else None,
            "phbot_pid": self.phbot_process.pid if self.phbot_process and self.phbot_process.poll() is None else None,
        }

    def _start_monitor(self):
        """مراقبة مستمرة للعملية وإعادة التشغيل إن توقفت"""
        if self._monitoring:
            return
        self._monitoring = True
        def _monitor():
            while self._monitoring:
                time.sleep(10)
                if self.game_process and self.game_process.poll() is not None:
                    if self.config.get("auto_restart_game", False):
                        self.log("⚠️ اللعبة أُغلقت — إعادة التشغيل تلقائياً...", "warning")
                        self.launch_game()
        threading.Thread(target=_monitor, daemon=True).start()

    def stop_monitor(self):
        self._monitoring = False
