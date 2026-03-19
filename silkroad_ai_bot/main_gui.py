"""
main_gui.py - الواجهة الرسومية الرئيسية
Silkroad AI Bot - نظام تحكم ذكي بالعربية
"""

import sys
import json
import os
import threading
import time
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QLineEdit, QPushButton, QTextEdit, QGroupBox,
    QFormLayout, QSpinBox, QCheckBox, QComboBox, QProgressBar,
    QStatusBar, QFrame, QGridLayout, QMessageBox, QListWidget,
    QListWidgetItem, QSplitter, QScrollArea, QFileDialog,
    QSystemTrayIcon, QAction, QMenu, QDoubleSpinBox, QSlider,
    QTableWidget, QTableWidgetItem, QHeaderView, QTimeEdit
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QTime
from PyQt5.QtGui import QFont, QTextCursor, QColor, QIcon, QPixmap, QPainter, QPen, QBrush

from ai_core import SilkroadAICore
from news_fetcher import NewsFetcher
from game_launcher import GameLauncher

CONFIG_FILE = "bot_config.json"

# قائمة السيرفرات المعروفة
KNOWN_SERVERS = {
    "— اختر سيرفر —":           ("", 15779),
    "iSRO Official":              ("gw.silkroadonline.net", 15779),
    "vSRO Official":              ("vSRO.silkroadonline.net", 15779),
    "SRO-R Official":             ("sro-r.com", 15779),
    "Silkroad R (EU)":            ("eu.silkroadonline.net", 15779),
    "Silkroad R (US)":            ("us.silkroadonline.net", 15779),
    "Arabia SRO (خاص)":          ("silkroadarabia.net", 15779),
    "SRO Legend (خاص)":          ("srolegend.net", 15779),
    "Silkroad Evo (خاص)":        ("silkroadevo.com", 15779),
    "Local / Localhost":          ("127.0.0.1", 15779),
    "Custom (يدوي)":             ("", 15779),
}


class BotWorker(QThread):
    log_signal = pyqtSignal(str, str)
    status_signal = pyqtSignal(dict)
    stopped = pyqtSignal()

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.running = False
        self.core = SilkroadAICore(config, self.emit_log)

    def emit_log(self, msg, level="info"):
        self.log_signal.emit(msg, level)

    def run(self):
        self.running = True
        self.core.start()
        while self.running:
            try:
                self.status_signal.emit(self.core.get_status())
            except Exception as e:
                self.emit_log(f"خطأ: {e}", "error")
            time.sleep(1)
        self.stopped.emit()

    def stop(self):
        self.running = False
        self.core.stop()

    def execute_chat_action(self, result: dict) -> str:
        return self.core.handle_chat_action(result)

    def get_ai_client(self):
        return self.core.ai

    def get_memory(self):
        return self.core.memory


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.bot_worker = None
        self.config = self._load_config()
        self.start_time = None
        self.news_fetcher = None
        self._launcher = None
        self._session_kills = 0
        self._session_xp = 0
        self._hp_history = []
        self._mp_history = []
        self._break_active = False
        self._next_break_at = None
        self._setup_ui()
        self._apply_theme()
        self._setup_tray()
        self._setup_scheduler_timer()
        self._log("مرحباً بك في Silkroad AI Bot — نظام التحكم الذكي", "success")
        self._log("أدخل إعداداتك واضغط تشغيل، أو تحدث مع AI في تبويب الشات", "info")

    # ─────────────────────── UI Setup ────────────────────────────────────
    def _setup_ui(self):
        self.setWindowTitle("⚔️ Silkroad AI Bot — نظام التحكم الذكي")
        self.setMinimumSize(1100, 750)
        self.setLayoutDirection(Qt.RightToLeft)

        root = QWidget()
        self.setCentralWidget(root)
        vbox = QVBoxLayout(root)
        vbox.setSpacing(6)
        vbox.addWidget(self._build_header())

        self.tabs = QTabWidget()
        self.tabs.setLayoutDirection(Qt.RightToLeft)
        self.tabs.addTab(self._build_settings_tab(),  "⚙️ الإعدادات")
        self.tabs.addTab(self._build_bot_tab(),       "🤖 البوت")
        self.tabs.addTab(self._build_skills_tab(),    "🗡️ المهارات")
        self.tabs.addTab(self._build_schedule_tab(),  "⏰ الجدولة")
        self.tabs.addTab(self._build_chat_tab(),      "💬 الشات")
        self.tabs.addTab(self._build_news_tab(),      "📰 الأخبار")
        self.tabs.addTab(self._build_memory_tab(),    "🧠 الذاكرة")
        self.tabs.addTab(self._build_logs_tab(),      "📋 السجل")
        vbox.addWidget(self.tabs)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("⚪ البوت متوقف")

    def _build_header(self):
        f = QFrame(); f.setObjectName("header")
        h = QHBoxLayout(f)
        t = QLabel("⚔️ Silkroad AI Bot Controller")
        t.setFont(QFont("Arial", 17, QFont.Bold))
        t.setStyleSheet("color:#FFD700;")
        s = QLabel("تحكم ذكي بالذكاء الاصطناعي DeepSeek | تعلّم، شات، أخبار")
        s.setStyleSheet("color:#AAAAAA; font-size:10px;")
        col = QVBoxLayout(); col.addWidget(t); col.addWidget(s)
        h.addLayout(col)
        return f

    # ─── Settings ─────────────────────────────────────────────────────────
    def _build_settings_tab(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(10)

        # DeepSeek
        g1 = QGroupBox("🔑 DeepSeek AI"); f1 = QFormLayout()
        self.e_key = QLineEdit(self.config.get("deepseek_api_key",""))
        self.e_key.setEchoMode(QLineEdit.Password)
        self.e_key.setPlaceholderText("sk-xxxxxxxxxxxxxxxxxxxx")
        self.e_model = QComboBox()
        self.e_model.addItems(["deepseek-chat","deepseek-reasoner"])
        self.e_model.setCurrentText(self.config.get("deepseek_model","deepseek-chat"))
        f1.addRow("مفتاح API:", self.e_key)
        f1.addRow("النموذج:", self.e_model)
        g1.setLayout(f1)

        # Login
        g2 = QGroupBox("🎮 بيانات الدخول"); f2 = QFormLayout()

        # Server dropdown
        self.e_srv = QComboBox()
        self.e_srv.setLayoutDirection(Qt.LeftToRight)
        self.e_srv.addItems(list(KNOWN_SERVERS.keys()))
        saved_srv = self.config.get("server_name", "— اختر سيرفر —")
        if saved_srv in KNOWN_SERVERS:
            self.e_srv.setCurrentText(saved_srv)
        else:
            self.e_srv.setCurrentText("Custom (يدوي)")

        self.e_ip   = QLineEdit(self.config.get("server_ip",""))
        self.e_ip.setPlaceholderText("0.0.0.0 أو domain.com")
        self.e_port = QSpinBox(); self.e_port.setRange(1,65535)
        self.e_port.setValue(self.config.get("server_port",15779))
        self.e_uid  = QLineEdit(self.config.get("login_id",""))
        self.e_pwd  = QLineEdit(self.config.get("login_password",""))
        self.e_pwd.setEchoMode(QLineEdit.Password)
        self.e_pin  = QLineEdit(self.config.get("login_pincode",""))
        self.e_pin.setEchoMode(QLineEdit.Password)
        self.e_pin.setPlaceholderText("اختياري")
        self.e_char = QLineEdit(self.config.get("char_name",""))

        # Auto-fill IP/Port when server selected
        def _on_server_changed(name):
            ip, port = KNOWN_SERVERS.get(name, ("", 15779))
            if ip:
                self.e_ip.setText(ip)
                self.e_port.setValue(port)
        self.e_srv.currentTextChanged.connect(_on_server_changed)

        for lbl, w_ in [("السيرفر:", self.e_srv), ("IP:", self.e_ip),
                        ("البورت:", self.e_port), ("المستخدم:", self.e_uid),
                        ("كلمة المرور:", self.e_pwd), ("PIN:", self.e_pin),
                        ("اسم الشخصية:", self.e_char)]:
            f2.addRow(lbl, w_)
        g2.setLayout(f2)

        # Combat
        g3 = QGroupBox("⚔️ القتال"); f3 = QFormLayout()
        self.e_hp   = QSpinBox(); self.e_hp.setRange(1,99)
        self.e_hp.setValue(self.config.get("hp_threshold",45)); self.e_hp.setSuffix(" %")
        self.e_mon  = QSpinBox(); self.e_mon.setRange(1,20)
        self.e_mon.setValue(self.config.get("monster_threshold",5))
        self.e_spot = QSpinBox(); self.e_spot.setRange(1,30)
        self.e_spot.setValue(self.config.get("spot_empty_minutes",2)); self.e_spot.setSuffix(" دقيقة")
        self.e_zone = QLineEdit(self.config.get("farming_zone",""))
        self.e_zone.setPlaceholderText("X:1234 Y:5678")
        self.e_hp_pot = QSpinBox(); self.e_hp_pot.setRange(1, 95)
        self.e_hp_pot.setValue(self.config.get("hp_potion_threshold", 60)); self.e_hp_pot.setSuffix(" %")
        self.e_mp_pot = QSpinBox(); self.e_mp_pot.setRange(1, 95)
        self.e_mp_pot.setValue(self.config.get("mp_potion_threshold", 40)); self.e_mp_pot.setSuffix(" %")

        self.chk_login    = QCheckBox("تسجيل دخول تلقائي عند الانقطاع")
        self.chk_login.setChecked(self.config.get("auto_login", True))
        self.chk_quest    = QCheckBox("قبول وتسليم المهام تلقائياً")
        self.chk_quest.setChecked(self.config.get("auto_quest", True))
        self.chk_news     = QCheckBox("متابعة أخبار اللعبة تلقائياً")
        self.chk_news.setChecked(self.config.get("auto_news", True))
        self.chk_auto_pot = QCheckBox("استخدام البوشن تلقائياً (HP/MP)")
        self.chk_auto_pot.setChecked(self.config.get("use_auto_potion", True))
        self.chk_use_phbot = QCheckBox("استخدام phBot كوسيط (Plugin Mode)")
        self.chk_use_phbot.setChecked(self.config.get("use_phbot", False))
        self.chk_ks_escape = QCheckBox("هروب تلقائي عند KS")
        self.chk_ks_escape.setChecked(self.config.get("ks_auto_escape", True))

        for lbl, w_ in [("حد HP:", self.e_hp), ("حد الوحوش:", self.e_mon),
                        ("وقت المنطقة الفارغة:", self.e_spot), ("منطقة الزراعة:", self.e_zone),
                        ("HP بوشن عند:", self.e_hp_pot), ("MP بوشن عند:", self.e_mp_pot)]:
            f3.addRow(lbl, w_)
        for chk in [self.chk_auto_pot, self.chk_login, self.chk_quest,
                    self.chk_news, self.chk_use_phbot, self.chk_ks_escape]:
            f3.addRow("", chk)
        g3.setLayout(f3)

        # Game Launcher
        g4 = QGroupBox("🎮 مسار اللعبة وملف التشغيل"); f4 = QFormLayout()

        # Game EXE path
        self.e_game_exe = QLineEdit(self.config.get("game_exe_path", ""))
        self.e_game_exe.setPlaceholderText(r"مثال: C:\Silkroad\sro_client.exe")
        row_game = QHBoxLayout()
        row_game.addWidget(self.e_game_exe)
        btn_browse_game = QPushButton("📂 تصفح")
        btn_browse_game.setMaximumWidth(75)
        btn_browse_game.clicked.connect(lambda: self._browse_exe(self.e_game_exe, "ملف تشغيل اللعبة"))
        row_game.addWidget(btn_browse_game)
        btn_detect = QPushButton("🔍 كشف تلقائي")
        btn_detect.setMaximumWidth(110)
        btn_detect.setStyleSheet("background:#1A3A5C;")
        btn_detect.clicked.connect(self._auto_detect_game)
        row_game.addWidget(btn_detect)
        f4.addRow("ملف اللعبة (.exe):", row_game)

        # Game folder
        self.e_game_folder = QLineEdit(self.config.get("game_folder", ""))
        self.e_game_folder.setPlaceholderText(r"مثال: C:\Silkroad")
        row_folder = QHBoxLayout()
        row_folder.addWidget(self.e_game_folder)
        btn_browse_folder = QPushButton("📂 تصفح")
        btn_browse_folder.setMaximumWidth(75)
        btn_browse_folder.clicked.connect(self._browse_folder)
        row_folder.addWidget(btn_browse_folder)
        btn_scan = QPushButton("🔎 فحص المجلد")
        btn_scan.setMaximumWidth(110)
        btn_scan.setStyleSheet("background:#1A3A1A;")
        btn_scan.clicked.connect(self._scan_game_folder)
        row_folder.addWidget(btn_scan)
        f4.addRow("مجلد اللعبة:", row_folder)

        # phBot EXE path
        self.e_phbot_exe = QLineEdit(self.config.get("phbot_exe_path", ""))
        self.e_phbot_exe.setPlaceholderText(r"مثال: C:\phBot\phBot.exe")
        row_phbot = QHBoxLayout()
        row_phbot.addWidget(self.e_phbot_exe)
        btn_browse_phbot = QPushButton("📂 تصفح")
        btn_browse_phbot.setMaximumWidth(75)
        btn_browse_phbot.clicked.connect(lambda: self._browse_exe(self.e_phbot_exe, "ملف phBot"))
        row_phbot.addWidget(btn_browse_phbot)
        f4.addRow("ملف phBot (اختياري):", row_phbot)

        # Launch args
        self.e_launch_args = QLineEdit(self.config.get("game_launch_args", ""))
        self.e_launch_args.setPlaceholderText("مثال: /data /language:arabic  (اتركه فارغاً إذا لم تكن متأكداً)")
        f4.addRow("وسيطات التشغيل:", self.e_launch_args)

        # Startup wait
        self.e_startup_wait = QSpinBox()
        self.e_startup_wait.setRange(3, 60)
        self.e_startup_wait.setValue(self.config.get("game_startup_wait", 8))
        self.e_startup_wait.setSuffix(" ثانية")
        f4.addRow("انتظار تحميل اللعبة:", self.e_startup_wait)

        self.chk_auto_restart = QCheckBox("إعادة تشغيل اللعبة تلقائياً إذا أُغلقت")
        self.chk_auto_restart.setChecked(self.config.get("auto_restart_game", False))
        self.chk_launch_on_start = QCheckBox("تشغيل اللعبة تلقائياً عند تشغيل البوت")
        self.chk_launch_on_start.setChecked(self.config.get("launch_on_bot_start", False))
        f4.addRow("", self.chk_auto_restart)
        f4.addRow("", self.chk_launch_on_start)
        g4.setLayout(f4)

        # Exe list (scan results)
        self.exe_list_label = QLabel("")
        self.exe_list_label.setStyleSheet("color:#87CEEB; font-size:10px;")
        self.exe_list_label.setWordWrap(True)

        btn = QPushButton("💾 حفظ الإعدادات")
        btn.setMinimumHeight(40)
        btn.setStyleSheet("background:#1B5E20; font-size:14px; font-weight:bold;")
        btn.clicked.connect(self._save_config)

        row1 = QHBoxLayout(); row1.addWidget(g1); row1.addWidget(g2)
        row2 = QHBoxLayout(); row2.addWidget(g3); row2.addWidget(g4)
        lay.addLayout(row1); lay.addLayout(row2)
        lay.addWidget(self.exe_list_label)
        lay.addWidget(btn)
        return w

    # ─── Bot Control ──────────────────────────────────────────────────────
    def _build_bot_tab(self):
        w = QWidget(); lay = QVBoxLayout(w)

        g_status = QGroupBox("📊 حالة الشخصية"); grid = QGridLayout()
        self.lbl = {}
        for i,(k,t) in enumerate([("char","الشخصية"),("level","المستوى"),
                                   ("pos","الموقع"),("target","الهدف"),
                                   ("monsters","الوحوش"),("weapon","السلاح"),
                                   ("combat","القتال"),("action","آخر أمر AI")]):
            r,c = divmod(i,4)
            grid.addWidget(QLabel(f"{t}:"), r, c*2)
            lbl = QLabel("—"); lbl.setStyleSheet("color:#87CEEB;")
            grid.addWidget(lbl, r, c*2+1)
            self.lbl[k] = lbl
        self.hp_bar = QProgressBar(); self.hp_bar.setFormat("HP %v/%m")
        self.mp_bar = QProgressBar(); self.mp_bar.setFormat("MP %v/%m")
        self.hp_bar.setStyleSheet("QProgressBar::chunk{background:#e53935;}")
        self.mp_bar.setStyleSheet("QProgressBar::chunk{background:#1565C0;}")
        grid.addWidget(self.hp_bar, 2, 0, 1, 4)
        grid.addWidget(self.mp_bar, 3, 0, 1, 4)
        g_status.setLayout(grid)

        # Game process status panel
        g_game = QGroupBox("🎮 حالة اللعبة")
        game_layout = QHBoxLayout()
        self.lbl_game_status  = QLabel("⚪ اللعبة: غير مشغّلة")
        self.lbl_phbot_status = QLabel("⚪ phBot: غير مشغّل")
        self.lbl_game_status.setStyleSheet("color:#AAAAAA; font-weight:bold;")
        self.lbl_phbot_status.setStyleSheet("color:#AAAAAA; font-weight:bold;")
        btn_launch_game  = QPushButton("🚀 تشغيل اللعبة")
        btn_launch_phbot = QPushButton("🤖 تشغيل phBot")
        btn_launch_seq   = QPushButton("⚡ تشغيل الكل")
        btn_close_game   = QPushButton("🔴 إغلاق اللعبة")
        btn_launch_game.setStyleSheet("background:#0D47A1;")
        btn_launch_phbot.setStyleSheet("background:#1B5E20;")
        btn_launch_seq.setStyleSheet("background:#4A148C; font-weight:bold;")
        btn_close_game.setStyleSheet("background:#7B1FA2;")
        btn_launch_game.clicked.connect(self._launch_game)
        btn_launch_phbot.clicked.connect(self._launch_phbot)
        btn_launch_seq.clicked.connect(self._launch_sequence)
        btn_close_game.clicked.connect(self._close_game)
        for w_ in [self.lbl_game_status, self.lbl_phbot_status,
                   btn_launch_game, btn_launch_phbot, btn_launch_seq, btn_close_game]:
            game_layout.addWidget(w_)
        g_game.setLayout(game_layout)

        g_ctrl = QGroupBox("🤖 تحكم البوت"); h = QHBoxLayout()
        self.btn_start = QPushButton("▶️ تشغيل البوت")
        self.btn_stop  = QPushButton("⏹️ إيقاف البوت")
        self.btn_test  = QPushButton("🧪 اختبار AI")
        self.btn_stop.setEnabled(False)
        for btn, color, fn in [
            (self.btn_start,"#1B5E20",self._start_bot),
            (self.btn_stop, "#B71C1C",self._stop_bot),
            (self.btn_test, "#1A237E",self._test_ai),
        ]:
            btn.setMinimumHeight(48); btn.setStyleSheet(f"background:{color}; font-size:14px;")
            btn.clicked.connect(fn); h.addWidget(btn)
        g_ctrl.setLayout(h)

        g_stats = QGroupBox("📈 إحصائيات"); sg = QGridLayout()
        self.st = {}
        for i,(k,t) in enumerate([("cmds","أوامر AI"),("dc","انقطاع"),
                                   ("uptime","وقت التشغيل"),("ai","حالة AI"),
                                   ("decisions","قرارات محفوظة"),("success","معدل النجاح")]):
            r,c = divmod(i,2)
            sg.addWidget(QLabel(f"{t}:"), r, c*2)
            lbl = QLabel("—"); self.st[k] = lbl; sg.addWidget(lbl, r, c*2+1)
        self.st["ai"].setText("⚪ متوقف")
        g_stats.setLayout(sg)

        lay.addWidget(g_status); lay.addWidget(g_game)
        lay.addWidget(g_ctrl); lay.addWidget(g_stats)
        self._uptime_timer = QTimer(); self._uptime_timer.timeout.connect(self._tick_uptime)
        self._game_check_timer = QTimer(); self._game_check_timer.timeout.connect(self._check_game_status)
        self._game_check_timer.start(3000)
        return w

    # ─── Chat Tab ─────────────────────────────────────────────────────────
    def _build_chat_tab(self):
        w = QWidget(); lay = QVBoxLayout(w)

        info = QLabel(
            "💬 تحدث مع البوت بالعربية — يمكنك إعطاء أوامر أو طرح أسئلة\n"
            "أمثلة: 'وقّف البوت'  •  'فعّل الدفاع'  •  'ما أفضل مهارة للـ Giant؟'  •  'تقرير'"
        )
        info.setWordWrap(True)
        info.setStyleSheet("background:#1A2744; padding:8px; border-radius:6px; color:#AAD4FF;")

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setFont(QFont("Arial", 11))
        self.chat_display.setStyleSheet("background:#0A0A0A; border:1px solid #333;")

        inp_row = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("اكتب أمرك أو سؤالك هنا...")
        self.chat_input.setMinimumHeight(38)
        self.chat_input.returnPressed.connect(self._send_chat)
        btn_send = QPushButton("إرسال ▶")
        btn_send.setMinimumHeight(38)
        btn_send.setStyleSheet("background:#1565C0; font-weight:bold;")
        btn_send.clicked.connect(self._send_chat)
        btn_clear_chat = QPushButton("مسح")
        btn_clear_chat.setMinimumHeight(38)
        btn_clear_chat.clicked.connect(self._clear_chat)
        inp_row.addWidget(self.chat_input)
        inp_row.addWidget(btn_send)
        inp_row.addWidget(btn_clear_chat)

        quick = QGroupBox("أوامر سريعة")
        qh = QHBoxLayout()
        for label, cmd in [
            ("⏸ إيقاف مؤقت","وقّف البوت"),("▶ استئناف","استأنف البوت"),
            ("🛡 دفاع","فعّل وضع الدفاع"),("📊 تقرير","أعطني تقرير الجلسة"),
            ("💡 نصيحة","ما أفضل استراتيجية الآن؟"),("📜 مهام","اقبل جميع المهام"),
        ]:
            btn = QPushButton(label); btn.setMaximumWidth(130)
            btn.clicked.connect(lambda checked, c=cmd: self._quick_cmd(c))
            qh.addWidget(btn)
        quick.setLayout(qh)

        lay.addWidget(info)
        lay.addWidget(self.chat_display, stretch=1)
        lay.addLayout(inp_row)
        lay.addWidget(quick)
        return w

    # ─── News Tab ─────────────────────────────────────────────────────────
    def _build_news_tab(self):
        w = QWidget(); lay = QVBoxLayout(w)

        ctrl = QHBoxLayout()
        self.btn_fetch_news = QPushButton("🔄 تحديث الأخبار الآن")
        self.btn_fetch_news.setStyleSheet("background:#37474F;")
        self.btn_fetch_news.clicked.connect(self._fetch_news)
        self.btn_tips = QPushButton("💡 نصائح AI بناءً على الأخبار")
        self.btn_tips.setStyleSheet("background:#4A148C;")
        self.btn_tips.clicked.connect(self._get_tips)
        self.news_status = QLabel("⚪ لم يتم الجلب بعد")
        ctrl.addWidget(self.btn_fetch_news)
        ctrl.addWidget(self.btn_tips)
        ctrl.addWidget(self.news_status)
        ctrl.addStretch()

        self.news_list = QListWidget()
        self.news_list.setStyleSheet("background:#0D0D0D; color:#E0E0E0; font-size:12px;")
        self.news_list.itemClicked.connect(self._show_news_detail)

        self.news_detail = QTextEdit()
        self.news_detail.setReadOnly(True)
        self.news_detail.setStyleSheet("background:#111; color:#CCC;")
        self.news_detail.setMaximumHeight(180)

        self.ai_news_analysis = QTextEdit()
        self.ai_news_analysis.setReadOnly(True)
        self.ai_news_analysis.setPlaceholderText("تحليل AI للأخبار سيظهر هنا...")
        self.ai_news_analysis.setStyleSheet("background:#0D1929; color:#87CEEB; font-size:12px;")
        self.ai_news_analysis.setMaximumHeight(150)

        lay.addLayout(ctrl)
        lay.addWidget(QLabel("📰 قائمة الأخبار:"))
        lay.addWidget(self.news_list, stretch=1)
        lay.addWidget(QLabel("📄 تفاصيل:"))
        lay.addWidget(self.news_detail)
        lay.addWidget(QLabel("🤖 تحليل AI:"))
        lay.addWidget(self.ai_news_analysis)
        return w

    # ─── Memory Tab ───────────────────────────────────────────────────────
    def _build_memory_tab(self):
        w = QWidget(); lay = QVBoxLayout(w)

        ctrl = QHBoxLayout()
        btn_refresh = QPushButton("🔄 تحديث الإحصائيات")
        btn_refresh.clicked.connect(self._refresh_memory)
        btn_clear = QPushButton("🗑️ مسح الذاكرة")
        btn_clear.setStyleSheet("background:#B71C1C;")
        btn_clear.clicked.connect(self._clear_memory)
        btn_export = QPushButton("📄 تصدير تقرير الجلسة")
        btn_export.setStyleSheet("background:#1A3A5C;")
        btn_export.clicked.connect(self._export_session_report)
        ctrl.addWidget(btn_refresh); ctrl.addWidget(btn_export)
        ctrl.addWidget(btn_clear); ctrl.addStretch()

        g_stats = QGroupBox("📊 إحصائيات الذاكرة"); sg = QGridLayout()
        self.mem_lbl = {}
        for i,(k,t) in enumerate([
            ("decisions","إجمالي القرارات"),("deaths","وفيات مسجّلة"),
            ("success","معدل النجاح"),("lessons","دروس مستفادة"),
            ("errors","أنماط أخطاء"),("rotation","أفضل روتين مهارات"),
        ]):
            r,c = divmod(i,2)
            sg.addWidget(QLabel(f"{t}:"), r, c*2)
            lbl = QLabel("—"); lbl.setStyleSheet("color:#FFD700;")
            sg.addWidget(lbl, r, c*2+1); self.mem_lbl[k] = lbl
        g_stats.setLayout(sg)

        g_lessons = QGroupBox("📚 آخر الدروس المستفادة")
        vl = QVBoxLayout()
        self.lessons_text = QTextEdit()
        self.lessons_text.setReadOnly(True)
        self.lessons_text.setFont(QFont("Arial", 10))
        self.lessons_text.setStyleSheet("background:#0D1929; color:#87CEEB;")
        vl.addWidget(self.lessons_text); g_lessons.setLayout(vl)

        g_skills = QGroupBox("⚔️ أداء المهارات"); vl2 = QVBoxLayout()
        self.skills_text = QTextEdit()
        self.skills_text.setReadOnly(True)
        self.skills_text.setStyleSheet("background:#0D1929; color:#90EE90;")
        self.skills_text.setMaximumHeight(150)
        vl2.addWidget(self.skills_text); g_skills.setLayout(vl2)

        lay.addLayout(ctrl); lay.addWidget(g_stats)
        lay.addWidget(g_lessons, stretch=1); lay.addWidget(g_skills)
        return w

    # ─── Logs Tab ─────────────────────────────────────────────────────────
    def _build_logs_tab(self):
        w = QWidget(); lay = QVBoxLayout(w)
        tools = QHBoxLayout()
        btn_clear = QPushButton("🗑️ مسح"); btn_clear.clicked.connect(self._clear_logs)
        btn_save  = QPushButton("💾 حفظ"); btn_save.clicked.connect(self._save_logs)
        tools.addStretch(); tools.addWidget(btn_save); tools.addWidget(btn_clear)
        lay.addLayout(tools)
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setFont(QFont("Consolas", 9))
        self.log_area.setStyleSheet("background:#050505; color:#D0D0D0;")
        lay.addWidget(self.log_area)
        return w

    # ─── Theme ────────────────────────────────────────────────────────────
    def _apply_theme(self):
        self.setStyleSheet("""
            QMainWindow,QWidget{background:#121212;color:#E0E0E0;}
            QTabWidget::pane{border:1px solid #2a2a2a;}
            QTabBar::tab{background:#1A1A1A;color:#888;padding:8px 14px;border-radius:4px 4px 0 0;}
            QTabBar::tab:selected{background:#252525;color:#FFD700;border-bottom:2px solid #FFD700;}
            QGroupBox{border:1px solid #2a2a2a;border-radius:6px;margin-top:12px;padding:8px;
                      font-weight:bold;color:#FFD700;}
            QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 4px;}
            QLineEdit,QSpinBox,QComboBox{background:#1A1A1A;border:1px solid #3a3a3a;
                border-radius:4px;padding:5px;color:#E0E0E0;}
            QLineEdit:focus,QSpinBox:focus{border-color:#FFD700;}
            QPushButton{background:#1E1E1E;border:1px solid #3a3a3a;border-radius:5px;
                padding:6px 12px;color:#DDD;}
            QPushButton:hover{background:#2a2a2a;border-color:#FFD700;}
            QPushButton:disabled{background:#111;color:#444;border-color:#222;}
            QProgressBar{border:1px solid #333;border-radius:4px;text-align:center;background:#111;}
            QListWidget{background:#0D0D0D;border:1px solid #2a2a2a;}
            QListWidget::item:selected{background:#1A2744;}
            QFrame#header{background:#0D0D0D;border-bottom:2px solid #FFD700;padding:6px;}
            QStatusBar{background:#080808;color:#888;}
            QCheckBox{color:#CCC;} QCheckBox::indicator{width:15px;height:15px;
                border:1px solid #555;background:#1A1A1A;border-radius:3px;}
            QCheckBox::indicator:checked{background:#FFD700;border-color:#FFD700;}
        """)

    # ─── Logging ──────────────────────────────────────────────────────────
    def _log(self, msg, level="info"):
        colors = {"info":"#87CEEB","warning":"#FFA500","error":"#FF5555",
                  "success":"#55FF55","ai":"#DA70D6"}
        icons  = {"info":"ℹ","warning":"⚠","error":"✖","success":"✔","ai":"🤖"}
        c = colors.get(level,"#E0E0E0"); i = icons.get(level,"•")
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_area.insertHtml(
            f'<span style="color:#555">[{ts}]</span> '
            f'<span style="color:{c}">{i} {msg}</span><br>'
        )
        self.log_area.moveCursor(QTextCursor.End)

    def _clear_logs(self):
        self.log_area.clear(); self._log("تم مسح السجل", "info")

    def _save_logs(self):
        fname = f"log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(fname,"w",encoding="utf-8") as f:
            f.write(self.log_area.toPlainText())
        self._log(f"تم الحفظ: {fname}", "success")

    # ─── RTL-safe dialogs ─────────────────────────────────────────────────
    def _msg_box(self, title: str, text: str, kind: str = "info") -> int:
        """يعرض نافذة رسالة آمنة مع RTL (يمنع مشكلة عدم عمل الأزرار)"""
        dlg = QMessageBox(self)
        dlg.setLayoutDirection(Qt.LeftToRight)   # الإصلاح الأساسي
        dlg.setWindowTitle(title)
        dlg.setText(text)
        icon_map = {
            "info":     QMessageBox.Information,
            "warning":  QMessageBox.Warning,
            "error":    QMessageBox.Critical,
            "question": QMessageBox.Question,
        }
        dlg.setIcon(icon_map.get(kind, QMessageBox.Information))
        if kind == "question":
            dlg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            dlg.setDefaultButton(QMessageBox.No)
        return dlg.exec_()

    # ─── Config ───────────────────────────────────────────────────────────
    def _collect_config(self) -> dict:
        """تجميع قيم الإعدادات من الواجهة"""
        cfg = {
            "deepseek_api_key":    self.e_key.text().strip(),
            "deepseek_model":      self.e_model.currentText(),
            "server_name":         self.e_srv.currentText(),
            "server_ip":           self.e_ip.text().strip(),
            "server_port":         self.e_port.value(),
            "login_id":            self.e_uid.text().strip(),
            "login_password":      self.e_pwd.text(),
            "login_pincode":       self.e_pin.text(),
            "char_name":           self.e_char.text().strip(),
            "hp_threshold":        self.e_hp.value(),
            "monster_threshold":   self.e_mon.value(),
            "spot_empty_minutes":  self.e_spot.value(),
            "farming_zone":        self.e_zone.text().strip(),
            "hp_potion_threshold": self.e_hp_pot.value(),
            "mp_potion_threshold": self.e_mp_pot.value(),
            "use_auto_potion":     self.chk_auto_pot.isChecked(),
            "auto_login":          self.chk_login.isChecked(),
            "auto_quest":          self.chk_quest.isChecked(),
            "auto_news":           self.chk_news.isChecked(),
            "use_phbot":           self.chk_use_phbot.isChecked(),
            "ks_auto_escape":      self.chk_ks_escape.isChecked(),
            "game_exe_path":       self.e_game_exe.text().strip(),
            "game_folder":         self.e_game_folder.text().strip(),
            "phbot_exe_path":      self.e_phbot_exe.text().strip(),
            "game_launch_args":    self.e_launch_args.text().strip(),
            "game_startup_wait":   self.e_startup_wait.value(),
            "auto_restart_game":   self.chk_auto_restart.isChecked(),
            "launch_on_bot_start": self.chk_launch_on_start.isChecked(),
        }
        # Skills tab fields (optional - only if tab built)
        if hasattr(self, "skill_checks"):
            for sid, chk in self.skill_checks.items():
                cfg[f"skill_{sid}_enabled"] = chk.isChecked()
        if hasattr(self, "e_rotation"):
            cfg["skill_rotation"] = self.e_rotation.text().strip()
        if hasattr(self, "e_skill_delay"):
            cfg["skill_delay_ms"] = self.e_skill_delay.value()
        if hasattr(self, "e_buff_interval"):
            cfg["buff_interval_sec"] = self.e_buff_interval.value()
        if hasattr(self, "e_berserk_hp"):
            cfg["berserk_hp_min"] = self.e_berserk_hp.value()
        if hasattr(self, "e_pot_delay"):
            cfg["potion_delay_ms"] = self.e_pot_delay.value()
        if hasattr(self, "e_pot_stack"):
            cfg["potion_stack_size"] = self.e_pot_stack.value()
        if hasattr(self, "chk_mp_combat_only"):
            cfg["mp_potion_combat_only"] = self.chk_mp_combat_only.isChecked()
        # Scheduler tab fields (optional)
        if hasattr(self, "chk_scheduled"):
            cfg["use_scheduler"]        = self.chk_scheduled.isChecked()
            cfg["schedule_start_hour"]  = self.e_sched_start.time().hour()
            cfg["schedule_stop_hour"]   = self.e_sched_stop.time().hour()
            cfg["schedule_max_hours"]   = self.e_max_hours.value()
            cfg["pause_on_repeated_dc"] = self.chk_pause_on_dc.isChecked()
            cfg["use_breaks"]           = self.chk_breaks.isChecked()
            cfg["break_interval_min"]   = self.e_break_interval.value()
            cfg["break_duration_min"]   = self.e_break_duration.value()
        return cfg

    def _save_config_silent(self):
        """حفظ بدون نافذة تأكيد — للاستخدام الداخلي"""
        self.config = self._collect_config()
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            self._log("✔ تم حفظ الإعدادات", "success")
        except Exception as e:
            self._log(f"خطأ في الحفظ: {e}", "error")

    def _save_config(self):
        """حفظ مع نافذة تأكيد — لزر الحفظ اليدوي"""
        self._save_config_silent()
        self._msg_box("حفظ", "✔ تم حفظ الإعدادات بنجاح!", "info")

    # ─── Browse Helpers ───────────────────────────────────────────────────
    def _browse_exe(self, target_field: QLineEdit, title: str):
        path, _ = QFileDialog.getOpenFileName(
            self, f"اختر {title}", "", "ملفات تنفيذية (*.exe);;كل الملفات (*)"
        )
        if path:
            target_field.setText(path)
            # تحديث مجلد اللعبة تلقائياً
            if target_field is self.e_game_exe:
                folder = os.path.dirname(path)
                self.e_game_folder.setText(folder)
                self._log(f"✅ تم تحديد ملف اللعبة: {path}", "success")
            elif target_field is self.e_phbot_exe:
                self._log(f"✅ تم تحديد phBot: {path}", "success")

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "اختر مجلد اللعبة", self.e_game_folder.text() or "C:\\"
        )
        if folder:
            self.e_game_folder.setText(folder)
            self._log(f"📂 مجلد اللعبة: {folder}", "info")

    def _auto_detect_game(self):
        self._log("🔍 جاري الكشف التلقائي عن اللعبة...", "info")
        def run():
            launcher = GameLauncher(self.config, self._log)
            path = launcher.auto_detect_game()
            if path:
                self.e_game_exe.setText(path)
                self.e_game_folder.setText(os.path.dirname(path))
            else:
                self._log("لم يُعثر على اللعبة. حدّد المسار يدوياً.", "warning")
        threading.Thread(target=run, daemon=True).start()

    def _scan_game_folder(self):
        folder = self.e_game_folder.text().strip()
        if not folder or not os.path.isdir(folder):
            self._msg_box("تحذير", "حدّد مجلد اللعبة أولاً!", "warning"); return
        self._log(f"🔎 فحص المجلد: {folder}", "info")
        launcher = GameLauncher(self.config, self._log)
        exes = launcher.scan_folder(folder)
        if not exes:
            self._log("لا توجد ملفات .exe في هذا المجلد", "warning"); return
        lines = []
        for e in exes[:12]:
            tag = "🎮" if e["is_game"] else ("🤖" if e["is_phbot"] else "•")
            lines.append(f"{tag} {e['name']} ({e['size_mb']} MB)")
            if e["is_game"] and not self.e_game_exe.text():
                self.e_game_exe.setText(e["path"])
            if e["is_phbot"] and not self.e_phbot_exe.text():
                self.e_phbot_exe.setText(e["path"])
        self.exe_list_label.setText("ملفات موجودة: " + "  |  ".join(lines))
        self._log(f"وُجد {len(exes)} ملف تنفيذي", "success")

    def _load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, encoding="utf-8") as f:
                    return json.load(f)
            except: pass
        return {}

    # ─── Game Launcher Methods ────────────────────────────────────────────
    def _get_launcher(self) -> GameLauncher:
        if self._launcher is None:
            self._launcher = GameLauncher(self.config, self._log)
        else:
            self._launcher.config = self.config
        return self._launcher

    def _launch_game(self):
        self._save_config_silent()
        def run(): self._get_launcher().launch_game()
        threading.Thread(target=run, daemon=True).start()

    def _launch_phbot(self):
        self._save_config_silent()
        def run(): self._get_launcher().launch_phbot()
        threading.Thread(target=run, daemon=True).start()

    def _launch_sequence(self):
        self._save_config_silent()
        def run(): self._get_launcher().launch_sequence()
        threading.Thread(target=run, daemon=True).start()

    def _close_game(self):
        launcher = self._get_launcher()
        launcher.close_game()
        launcher.close_phbot()

    def _check_game_status(self):
        try:
            launcher = self._get_launcher()
            status = launcher.get_process_status()
            if status["game_running"]:
                pid = status.get("game_pid", "")
                self.lbl_game_status.setText(f"🟢 اللعبة: تعمل (PID:{pid})")
                self.lbl_game_status.setStyleSheet("color:#00FF00; font-weight:bold;")
            else:
                self.lbl_game_status.setText("⚪ اللعبة: غير مشغّلة")
                self.lbl_game_status.setStyleSheet("color:#AAAAAA; font-weight:bold;")
            if status["phbot_running"]:
                pid = status.get("phbot_pid", "")
                self.lbl_phbot_status.setText(f"🟢 phBot: يعمل (PID:{pid})")
                self.lbl_phbot_status.setStyleSheet("color:#00FF00; font-weight:bold;")
            else:
                self.lbl_phbot_status.setText("⚪ phBot: غير مشغّل")
                self.lbl_phbot_status.setStyleSheet("color:#AAAAAA; font-weight:bold;")
        except Exception:
            pass

    # ─── Bot Control ──────────────────────────────────────────────────────
    def _start_bot(self):
        self._save_config_silent()
        if not self.config.get("deepseek_api_key"):
            self._msg_box("تحذير", "يرجى إدخال مفتاح DeepSeek API أولاً!\n\nاذهب إلى تبويب الإعدادات وأدخل المفتاح.", "warning")
            return
        # تشغيل اللعبة تلقائياً إذا كان الخيار مفعّلاً
        if self.config.get("launch_on_bot_start") and self.config.get("game_exe_path"):
            self._log("🚀 تشغيل اللعبة أولاً...", "info")
            threading.Thread(target=self._get_launcher().launch_sequence, daemon=True).start()
        self._log("جاري تشغيل البوت...", "info")
        self.bot_worker = BotWorker(self.config)
        self.bot_worker.log_signal.connect(self._log)
        self.bot_worker.status_signal.connect(self._update_status)
        self.bot_worker.stopped.connect(self._on_bot_stopped)
        self.bot_worker.start()
        self.btn_start.setEnabled(False); self.btn_stop.setEnabled(True)
        self.st["ai"].setText("🟢 يعمل"); self.st["ai"].setStyleSheet("color:#55FF55;")
        self.start_time = time.time()
        self._uptime_timer.start(1000)
        self.status_bar.showMessage("🟢 البوت يعمل")
        if self.config.get("auto_news"):
            self._init_news_fetcher()

    def _stop_bot(self):
        if self.bot_worker: self._log("إيقاف...", "warning"); self.bot_worker.stop()

    def _on_bot_stopped(self):
        self.btn_start.setEnabled(True); self.btn_stop.setEnabled(False)
        self.st["ai"].setText("⚪ متوقف"); self.st["ai"].setStyleSheet("color:#888;")
        self._uptime_timer.stop(); self.status_bar.showMessage("⚪ متوقف")
        if self.news_fetcher: self.news_fetcher.stop()
        self._log("تم إيقاف البوت وحفظ الذاكرة", "warning")

    def _test_ai(self):
        key = self.e_key.text().strip()
        if not key:
            self._msg_box("تحذير", "أدخل مفتاح API أولاً!", "warning"); return
        self._log("اختبار الاتصال بـ DeepSeek...", "info")
        def run():
            from deepseek_client import DeepSeekClient
            ok = DeepSeekClient(key, self.e_model.currentText()).test_connection()
            self._log("✅ DeepSeek يعمل!" if ok else "❌ فشل الاتصال. تحقق من المفتاح.", "success" if ok else "error")
        threading.Thread(target=run, daemon=True).start()

    # ─── Status Update ────────────────────────────────────────────────────
    def _update_status(self, s: dict):
        self.lbl["char"].setText(s.get("char_name","—"))
        self.lbl["level"].setText(str(s.get("level","—")))
        self.lbl["pos"].setText(f"X:{s.get('x',0):.0f} Y:{s.get('y',0):.0f}")
        self.lbl["target"].setText(s.get("target","لا يوجد"))
        self.lbl["monsters"].setText(str(s.get("nearby_monsters",0)))
        self.lbl["weapon"].setText(s.get("weapon","—"))
        self.lbl["combat"].setText("⚔️ قتال" if s.get("in_combat") else "😴 هادئ")
        self.lbl["action"].setText(s.get("last_action","—"))
        hp, mhp = s.get("hp",0), s.get("max_hp",100)
        mp, mmp = s.get("mp",0), s.get("max_mp",100)
        self.hp_bar.setMaximum(mhp); self.hp_bar.setValue(hp)
        self.mp_bar.setMaximum(mmp); self.mp_bar.setValue(mp)

        hp_pct = int((hp / max(mhp, 1)) * 100)
        if hp_pct < 30:
            self.hp_bar.setStyleSheet("QProgressBar::chunk{background:#FF1744;}")
        elif hp_pct < 60:
            self.hp_bar.setStyleSheet("QProgressBar::chunk{background:#FF6D00;}")
        else:
            self.hp_bar.setStyleSheet("QProgressBar::chunk{background:#e53935;}")

        self.st["cmds"].setText(str(s.get("total_commands",0)))
        self.st["dc"].setText(str(s.get("dc_count",0)))

        self._session_kills = s.get("session_kills", self._session_kills)
        self._session_xp    = s.get("session_xp", self._session_xp)

        if self.bot_worker:
            mem = self.bot_worker.get_memory()
            stats = mem.get_stats()
            self.st["decisions"].setText(str(stats["total_decisions"]))
            self.st["success"].setText(stats["success_rate"])

    def _tick_uptime(self):
        if self.start_time:
            e = int(time.time()-self.start_time)
            self.st["uptime"].setText(f"{e//3600:02d}:{(e%3600)//60:02d}:{e%60:02d}")

    # ─── Chat ─────────────────────────────────────────────────────────────
    def _chat_bubble(self, text, is_user=True):
        color  = "#1A3A5C" if is_user else "#1A2A1A"
        align  = "right" if is_user else "left"
        prefix = "👤" if is_user else "🤖"
        ts = datetime.now().strftime("%H:%M")
        self.chat_display.insertHtml(
            f'<div style="text-align:{align};margin:4px;">'
            f'<span style="background:{color};border-radius:8px;padding:6px 10px;display:inline-block;">'
            f'{prefix} {text}'
            f'</span>'
            f'<span style="color:#555;font-size:9px;"> {ts}</span></div><br>'
        )
        self.chat_display.moveCursor(QTextCursor.End)

    def _send_chat(self):
        msg = self.chat_input.text().strip()
        if not msg: return
        self.chat_input.clear()
        self._chat_bubble(msg, is_user=True)

        def process():
            try:
                if self.bot_worker:
                    ai = self.bot_worker.get_ai_client()
                    state = self.bot_worker.core.get_status()
                    result = ai.chat_command(msg, state)
                    action_result = self.bot_worker.execute_chat_action(result)
                    reply = result.get("reply", "تم تنفيذ الأمر")
                    if action_result and action_result != "تم":
                        reply += f"\n→ {action_result}"
                    self._chat_bubble(reply, is_user=False)
                    bot_action = result.get("bot_action", "idle")
                    if bot_action not in ("idle","info","report"):
                        self._log(f"💬 شات → {bot_action}: {reply}", "ai")
                else:
                    from deepseek_client import DeepSeekClient
                    key = self.config.get("deepseek_api_key","")
                    if not key:
                        self._chat_bubble("❌ يرجى إدخال مفتاح DeepSeek في الإعدادات", is_user=False)
                        return
                    ai = DeepSeekClient(key, self.config.get("deepseek_model","deepseek-chat"))
                    reply = ai.free_chat(msg)
                    self._chat_bubble(reply, is_user=False)
            except Exception as e:
                self._chat_bubble(f"❌ خطأ: {e}", is_user=False)

        threading.Thread(target=process, daemon=True).start()

    def _quick_cmd(self, cmd: str):
        self.chat_input.setText(cmd)
        self._send_chat()

    def _clear_chat(self):
        self.chat_display.clear()
        if self.bot_worker:
            self.bot_worker.get_ai_client().clear_history()

    # ─── News ─────────────────────────────────────────────────────────────
    def _init_news_fetcher(self):
        if not self.bot_worker: return
        ai = self.bot_worker.get_ai_client()
        self.news_fetcher = NewsFetcher(ai, self._log, self._on_news_received)
        self.news_fetcher.start()
        self._log("📰 متابعة الأخبار مفعّلة", "info")

    def _on_news_received(self, items, analysis):
        self.news_list.clear()
        for n in items:
            item = QListWidgetItem(f"[{n.source}] {n.title[:80]}")
            item.setData(Qt.UserRole, n)
            self.news_list.addItem(item)
        self.ai_news_analysis.setPlainText(analysis)
        self.news_status.setText(f"✅ آخر تحديث: {datetime.now().strftime('%H:%M')}")

    def _show_news_detail(self, item):
        news = item.data(Qt.UserRole)
        if news:
            self.news_detail.setPlainText(
                f"المصدر: {news.source}\n"
                f"العنوان: {news.title}\n\n"
                f"{news.summary}"
            )

    def _fetch_news(self):
        self._log("جلب الأخبار...", "info")
        self.news_status.setText("🔄 جاري الجلب...")
        def run():
            if not self.news_fetcher:
                key = self.config.get("deepseek_api_key","")
                if not key:
                    self._log("أدخل مفتاح API أولاً", "error"); return
                from deepseek_client import DeepSeekClient
                ai = DeepSeekClient(key, self.config.get("deepseek_model","deepseek-chat"))
                self.news_fetcher = NewsFetcher(ai, self._log, self._on_news_received)
            items = self.news_fetcher.fetch_all()
            if not items:
                self.news_status.setText("⚠️ لم يتم جلب أخبار")
        threading.Thread(target=run, daemon=True).start()

    def _get_tips(self):
        def run():
            if not self.news_fetcher:
                self._log("اجلب الأخبار أولاً", "warning"); return
            self._log("جلب نصائح AI...", "info")
            tips = self.news_fetcher.get_game_tips()
            self.ai_news_analysis.setPlainText(f"💡 نصائح بناءً على الأخبار:\n\n{tips}")
        threading.Thread(target=run, daemon=True).start()

    # ─── Memory ───────────────────────────────────────────────────────────
    def _refresh_memory(self):
        if not self.bot_worker:
            self._log("شغّل البوت أولاً لعرض الذاكرة", "warning"); return
        mem   = self.bot_worker.get_memory()
        stats = mem.get_stats()
        sess  = mem.get_session_summary()
        self.mem_lbl["decisions"].setText(str(stats["total_decisions"]))
        self.mem_lbl["deaths"].setText(str(stats["deaths_recorded"]))
        self.mem_lbl["success"].setText(stats["success_rate"])
        self.mem_lbl["lessons"].setText(str(stats["lessons_learned"]))
        self.mem_lbl["errors"].setText(str(stats["error_patterns"]))
        best = mem.get_best_rotation()
        from ai_core import SKILL_NAMES_AR
        rotation_str = " → ".join(SKILL_NAMES_AR.get(s, str(s)) for s in best)
        self.mem_lbl["rotation"].setText(rotation_str)
        self._log(
            f"📊 الجلسة: قتل={sess['kills']}  XP={sess['xp']:,}  Gold={sess['gold']:,}  "
            f"وفيات={sess['deaths']}  قتل/ساعة={sess['kills_per_hour']}",
            "info"
        )
        self.lessons_text.setPlainText(mem.get_lessons_summary())
        skill_lines = []
        for sid, st in mem.skill_stats.items():
            rate = (st["success"] / max(st["used"], 1)) * 100
            from ai_core import SKILL_NAMES_AR
            name = SKILL_NAMES_AR.get(int(sid), sid)
            skill_lines.append(f"{name}: {st['used']} استخدام | نجاح {rate:.0f}%")
        self.skills_text.setPlainText("\n".join(skill_lines) or "لا توجد بيانات مهارات بعد")

    def _export_session_report(self):
        if not self.bot_worker:
            self._msg_box("تحذير", "شغّل البوت أولاً لتتوفر بيانات للتصدير.", "warning")
            return
        mem    = self.bot_worker.get_memory()
        report = mem.export_session_report()
        fname  = f"session_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        try:
            with open(fname, "w", encoding="utf-8") as f:
                f.write(report)
            self._log(f"📄 تم تصدير التقرير: {fname}", "success")
            self._msg_box("تصدير ناجح", f"تم حفظ التقرير:\n{fname}", "info")
        except Exception as e:
            self._log(f"خطأ في التصدير: {e}", "error")

    def _clear_memory(self):
        r = self._msg_box("تأكيد", "هل تريد مسح الذاكرة المحفوظة؟", "question")
        if r == QMessageBox.Yes:
            import os
            for f in ["bot_memory.json", "news_cache.json"]:
                if os.path.exists(f): os.remove(f)
            self._log("تم مسح الذاكرة", "warning")

    # ─── Skills Tab ───────────────────────────────────────────────────────
    def _build_skills_tab(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(10)

        g_skills = QGroupBox("⚔️ تفعيل/تعطيل المهارات")
        sg = QGridLayout(); sg.setSpacing(8)
        self.skill_checks = {}
        skills_list = [
            (7650, "داريديفل (Daredevil)",      True),
            (7652, "ضربة أرضية (Ground Impact)", True),
            (7654, "طعنة (Stab)",                True),
            (7656, "هجوم جماعي (Turn Fresh)",    True),
            (7910, "جلد حديدي (Iron Skin)",      True),
            (7660, "برسيرك (Berserk)",            False),
            (7662, "돌진 (Charge)",               False),
        ]
        for i, (sid, name, default) in enumerate(skills_list):
            r, c = divmod(i, 2)
            chk = QCheckBox(f"  {name}  [ID: {sid}]")
            chk.setChecked(self.config.get(f"skill_{sid}_enabled", default))
            chk.setStyleSheet("color:#87CEEB; font-size:11px;")
            sg.addWidget(chk, r, c)
            self.skill_checks[sid] = chk
        g_skills.setLayout(sg)

        g_rot = QGroupBox("🔄 ترتيب روتين الهجوم (IDs مفصولة بفاصلة)")
        rl = QVBoxLayout()
        default_rot = self.config.get("skill_rotation", "7650,7652,7654,7656")
        self.e_rotation = QLineEdit(default_rot)
        self.e_rotation.setPlaceholderText("مثال: 7650,7652,7654,7656")
        rot_info = QLabel("💡 الترتيب هو تسلسل المهارات في وضع القتال الاحتياطي (Fallback Mode)")
        rot_info.setStyleSheet("color:#888; font-size:10px;")
        rot_info.setWordWrap(True)
        rl.addWidget(self.e_rotation)
        rl.addWidget(rot_info)
        g_rot.setLayout(rl)

        g_timing = QGroupBox("⏱️ توقيت المهارات")
        tf = QFormLayout()
        self.e_skill_delay = QSpinBox()
        self.e_skill_delay.setRange(300, 5000)
        self.e_skill_delay.setValue(self.config.get("skill_delay_ms", 800))
        self.e_skill_delay.setSuffix(" ms")
        self.e_buff_interval = QSpinBox()
        self.e_buff_interval.setRange(10, 120)
        self.e_buff_interval.setValue(self.config.get("buff_interval_sec", 30))
        self.e_buff_interval.setSuffix(" ثانية")
        self.e_berserk_hp = QSpinBox()
        self.e_berserk_hp.setRange(50, 100)
        self.e_berserk_hp.setValue(self.config.get("berserk_hp_min", 70))
        self.e_berserk_hp.setSuffix(" %")
        tf.addRow("تأخير بين المهارات:", self.e_skill_delay)
        tf.addRow("تجديد Buffs كل:", self.e_buff_interval)
        tf.addRow("Berserk عند HP أعلى من:", self.e_berserk_hp)
        g_timing.setLayout(tf)

        g_potion = QGroupBox("💊 إعدادات البوشن")
        pf = QFormLayout()
        self.e_pot_delay = QSpinBox()
        self.e_pot_delay.setRange(500, 5000)
        self.e_pot_delay.setValue(self.config.get("potion_delay_ms", 1500))
        self.e_pot_delay.setSuffix(" ms")
        self.e_pot_stack = QSpinBox()
        self.e_pot_stack.setRange(1, 999)
        self.e_pot_stack.setValue(self.config.get("potion_stack_size", 100))
        self.chk_mp_combat_only = QCheckBox("استخدام MP بوشن فقط في القتال")
        self.chk_mp_combat_only.setChecked(self.config.get("mp_potion_combat_only", False))
        pf.addRow("تأخير البوشن:", self.e_pot_delay)
        pf.addRow("حجم الكدسة (Stack):", self.e_pot_stack)
        pf.addRow("", self.chk_mp_combat_only)
        g_potion.setLayout(pf)

        btn_save_skills = QPushButton("💾 حفظ إعدادات المهارات")
        btn_save_skills.setMinimumHeight(38)
        btn_save_skills.setStyleSheet("background:#1B5E20; font-size:13px; font-weight:bold;")
        btn_save_skills.clicked.connect(self._save_config_silent)

        row = QHBoxLayout(); row.addWidget(g_skills); row.addWidget(g_potion)
        lay.addLayout(row)
        lay.addWidget(g_rot)
        lay.addWidget(g_timing)
        lay.addWidget(btn_save_skills)
        return w

    # ─── Schedule Tab ──────────────────────────────────────────────────────
    def _build_schedule_tab(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(10)

        g_sched = QGroupBox("⏰ جدولة جلسات الزراعة")
        sf = QFormLayout()
        self.chk_scheduled = QCheckBox("تفعيل الجدولة التلقائية")
        self.chk_scheduled.setChecked(self.config.get("use_scheduler", False))

        self.e_sched_start = QTimeEdit()
        self.e_sched_start.setDisplayFormat("HH:mm")
        self.e_sched_start.setTime(QTime(self.config.get("schedule_start_hour", 22), 0))

        self.e_sched_stop = QTimeEdit()
        self.e_sched_stop.setDisplayFormat("HH:mm")
        self.e_sched_stop.setTime(QTime(self.config.get("schedule_stop_hour", 6), 0))

        self.e_max_hours = QSpinBox()
        self.e_max_hours.setRange(1, 24)
        self.e_max_hours.setValue(self.config.get("schedule_max_hours", 8))
        self.e_max_hours.setSuffix(" ساعة")

        self.chk_pause_on_dc = QCheckBox("إيقاف مؤقت عند انقطاع متكرر (3+ مرات)")
        self.chk_pause_on_dc.setChecked(self.config.get("pause_on_repeated_dc", True))

        sf.addRow("", self.chk_scheduled)
        sf.addRow("بدء الزراعة:", self.e_sched_start)
        sf.addRow("إيقاف الزراعة:", self.e_sched_stop)
        sf.addRow("الحد الأقصى:", self.e_max_hours)
        sf.addRow("", self.chk_pause_on_dc)
        g_sched.setLayout(sf)

        self.schedule_status_lbl = QLabel("⚪ الجدولة غير مفعّلة")
        self.schedule_status_lbl.setStyleSheet(
            "color:#FFD700; font-size:13px; font-weight:bold; "
            "background:#1A1A1A; padding:8px; border-radius:5px;"
        )

        g_breaks = QGroupBox("☕ استراحات تلقائية (Anti-Ban)")
        bf = QFormLayout()
        self.chk_breaks = QCheckBox("استراحة دورية مع إيقاف البوت مؤقتاً")
        self.chk_breaks.setChecked(self.config.get("use_breaks", False))
        self.e_break_interval = QSpinBox()
        self.e_break_interval.setRange(30, 360)
        self.e_break_interval.setValue(self.config.get("break_interval_min", 90))
        self.e_break_interval.setSuffix(" دقيقة")
        self.e_break_duration = QSpinBox()
        self.e_break_duration.setRange(1, 30)
        self.e_break_duration.setValue(self.config.get("break_duration_min", 5))
        self.e_break_duration.setSuffix(" دقيقة")
        bf.addRow("", self.chk_breaks)
        bf.addRow("استراحة كل:", self.e_break_interval)
        bf.addRow("مدة الاستراحة:", self.e_break_duration)
        g_breaks.setLayout(bf)

        g_session = QGroupBox("📊 ملخص الجلسة الحالية")
        sl = QGridLayout()
        self.sched_lbl = {}
        for i, (k, t) in enumerate([
            ("kills",   "وحوش منتهية"),
            ("xp",      "XP تقريبي"),
            ("gold",    "Gold تقريبي"),
            ("breaks",  "استراحات نُفّذت"),
            ("uptime2", "وقت نشط"),
            ("dc_count2", "انقطاعات"),
        ]):
            r, c = divmod(i, 2)
            sl.addWidget(QLabel(f"{t}:"), r, c * 2)
            lbl = QLabel("—")
            lbl.setStyleSheet("color:#FFD700; font-weight:bold;")
            sl.addWidget(lbl, r, c * 2 + 1)
            self.sched_lbl[k] = lbl
        g_session.setLayout(sl)

        btn_save_sched = QPushButton("💾 حفظ إعدادات الجدولة")
        btn_save_sched.setMinimumHeight(38)
        btn_save_sched.setStyleSheet("background:#4A148C; font-size:13px; font-weight:bold;")
        btn_save_sched.clicked.connect(self._save_config_silent)

        lay.addWidget(g_sched)
        lay.addWidget(self.schedule_status_lbl)
        lay.addWidget(g_breaks)
        lay.addWidget(g_session)
        lay.addWidget(btn_save_sched)
        return w

    # ─── System Tray ──────────────────────────────────────────────────────
    def _setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        pix = QPixmap(32, 32)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setBrush(QBrush(QColor("#FFD700")))
        p.setPen(QPen(QColor("#B8860B"), 2))
        p.drawEllipse(4, 4, 24, 24)
        p.setPen(QPen(QColor("#000"), 2))
        p.setFont(QFont("Arial", 12, QFont.Bold))
        p.drawText(8, 22, "⚔")
        p.end()
        self.tray = QSystemTrayIcon(QIcon(pix), self)
        menu = QMenu()
        menu.setLayoutDirection(Qt.RightToLeft)
        act_show  = QAction("🔍 إظهار", self); act_show.triggered.connect(self.show)
        act_start = QAction("▶ تشغيل البوت", self); act_start.triggered.connect(self._start_bot)
        act_stop  = QAction("⏹ إيقاف البوت",  self); act_stop.triggered.connect(self._stop_bot)
        act_quit  = QAction("❌ إغلاق",        self); act_quit.triggered.connect(self.close)
        for a in [act_show, act_start, act_stop, act_quit]:
            menu.addAction(a)
        self.tray.setContextMenu(menu)
        self.tray.setToolTip("Silkroad AI Bot")
        self.tray.activated.connect(lambda r: self.show() if r == QSystemTrayIcon.DoubleClick else None)
        self.tray.show()

    # ─── Scheduler Timer ──────────────────────────────────────────────────
    def _setup_scheduler_timer(self):
        self._sched_timer = QTimer()
        self._sched_timer.timeout.connect(self._scheduler_tick)
        self._sched_timer.start(30_000)
        self._session_break_count = 0

    def _scheduler_tick(self):
        now = datetime.now()
        # Update session summary labels
        if hasattr(self, "sched_lbl"):
            self.sched_lbl["kills"].setText(str(self._session_kills))
            self.sched_lbl["xp"].setText(f"{self._session_xp:,}")
            self.sched_lbl["gold"].setText(f"{self._session_kills * 450:,}")
            self.sched_lbl["breaks"].setText(str(self._session_break_count))
            if self.start_time:
                elapsed = int(time.time() - self.start_time)
                h, m = elapsed // 3600, (elapsed % 3600) // 60
                self.sched_lbl["uptime2"].setText(f"{h:02d}:{m:02d}")
            if self.bot_worker:
                self.sched_lbl["dc_count2"].setText(str(self.bot_worker.core.dc_count))

        if not self.config.get("use_scheduler", False):
            if hasattr(self, "schedule_status_lbl"):
                self.schedule_status_lbl.setText("⚪ الجدولة غير مفعّلة")
            return

        start_h = self.config.get("schedule_start_hour", 22)
        stop_h  = self.config.get("schedule_stop_hour",  6)
        cur_h   = now.hour
        in_window = (start_h > stop_h and (cur_h >= start_h or cur_h < stop_h)) or \
                    (start_h <= stop_h and start_h <= cur_h < stop_h)

        if in_window and not self.bot_worker:
            if hasattr(self, "schedule_status_lbl"):
                self.schedule_status_lbl.setText("🟢 في نافذة الزراعة — جارٍ التشغيل...")
            self._start_bot()
        elif not in_window and self.bot_worker:
            if hasattr(self, "schedule_status_lbl"):
                self.schedule_status_lbl.setText("🔴 خارج نافذة الزراعة — إيقاف...")
            self._stop_bot()
        elif in_window:
            if hasattr(self, "schedule_status_lbl"):
                self.schedule_status_lbl.setText(
                    f"🟢 جلسة نشطة | نافذة: {start_h:02d}:00 → {stop_h:02d}:00"
                )
        # Handle breaks
        if self.config.get("use_breaks") and self.bot_worker and not self._break_active:
            interval_sec = self.config.get("break_interval_min", 90) * 60
            if self.start_time and (time.time() - self.start_time) % interval_sec < 35:
                self._break_active = True
                dur = self.config.get("break_duration_min", 5)
                self._log(f"☕ استراحة تلقائية لمدة {dur} دقيقة...", "warning")
                self._session_break_count += 1
                if hasattr(self, "schedule_status_lbl"):
                    self.schedule_status_lbl.setText(f"☕ استراحة — {dur} دقيقة")
                self.bot_worker.core.pause()
                QTimer.singleShot(dur * 60 * 1000, self._end_break)

    def _end_break(self):
        self._break_active = False
        if self.bot_worker:
            self.bot_worker.core.resume()
            self._log("▶️ انتهت الاستراحة — استئناف الزراعة", "success")

    # ─── Close ────────────────────────────────────────────────────────────
    def closeEvent(self, event):
        if self.bot_worker and self.bot_worker.isRunning():
            self.bot_worker.stop(); self.bot_worker.wait(3000)
        if self.news_fetcher: self.news_fetcher.stop()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Silkroad AI Bot")
    app.setFont(QFont("Arial", 10))
    w = MainWindow(); w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
