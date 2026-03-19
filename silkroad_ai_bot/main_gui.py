"""
Silkroad AI Bot Controller - واجهة التحكم الذكي
نظام تحكم ذكي بالذكاء الاصطناعي DeepSeek لشخصية Warrior مستوى 116
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
    QStatusBar, QFrame, QSplitter, QGridLayout, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QThread
from PyQt5.QtGui import QFont, QColor, QPalette, QIcon, QTextCursor

from ai_core import SilkroadAICore

CONFIG_FILE = "bot_config.json"


class LogSignal(QObject):
    new_log = pyqtSignal(str, str)


class BotWorker(QThread):
    log_signal = pyqtSignal(str, str)
    status_signal = pyqtSignal(dict)
    stopped = pyqtSignal()

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.running = False
        self.core = SilkroadAICore(config, self.emit_log)

    def emit_log(self, message, level="info"):
        self.log_signal.emit(message, level)

    def run(self):
        self.running = True
        self.core.start()
        while self.running:
            try:
                status = self.core.get_status()
                self.status_signal.emit(status)
                time.sleep(1)
            except Exception as e:
                self.emit_log(f"خطأ في البوت: {e}", "error")
                time.sleep(2)
        self.stopped.emit()

    def stop(self):
        self.running = False
        self.core.stop()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.bot_worker = None
        self.config = self.load_config()
        self.setup_ui()
        self.apply_dark_theme()
        self.log("مرحباً بك في نظام التحكم الذكي Silkroad AI", "success")
        self.log("قم بإدخال بيانات الإعداد ثم اضغط على زر التشغيل", "info")

    def setup_ui(self):
        self.setWindowTitle("🗡️ Silkroad AI Bot - نظام التحكم الذكي")
        self.setMinimumSize(1000, 700)
        self.setLayoutDirection(Qt.RightToLeft)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(8)

        header = self.create_header()
        main_layout.addWidget(header)

        tabs = QTabWidget()
        tabs.setLayoutDirection(Qt.RightToLeft)
        tabs.addTab(self.create_settings_tab(), "⚙️ الإعدادات")
        tabs.addTab(self.create_bot_tab(), "🤖 التحكم بالبوت")
        tabs.addTab(self.create_logs_tab(), "📋 السجل")
        tabs.addTab(self.create_files_tab(), "📁 ملفات البوت")
        main_layout.addWidget(tabs)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("⚪ البوت متوقف")

    def create_header(self):
        frame = QFrame()
        frame.setObjectName("header")
        layout = QHBoxLayout(frame)

        title = QLabel("⚔️ Silkroad AI Bot Controller")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Arial", 18, QFont.Bold))
        title.setStyleSheet("color: #FFD700; padding: 10px;")

        subtitle = QLabel("نظام التحكم الذكي بالذكاء الاصطناعي DeepSeek")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setFont(QFont("Arial", 10))
        subtitle.setStyleSheet("color: #AAAAAA;")

        v = QVBoxLayout()
        v.addWidget(title)
        v.addWidget(subtitle)
        layout.addLayout(v)
        return frame

    def create_settings_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # DeepSeek API
        api_group = QGroupBox("🔑 إعدادات DeepSeek AI")
        api_layout = QFormLayout()
        self.deepseek_key = QLineEdit(self.config.get("deepseek_api_key", ""))
        self.deepseek_key.setEchoMode(QLineEdit.Password)
        self.deepseek_key.setPlaceholderText("sk-xxxxxxxxxxxxxxxxxxxxxxxx")
        self.deepseek_model = QComboBox()
        self.deepseek_model.addItems(["deepseek-chat", "deepseek-reasoner"])
        self.deepseek_model.setCurrentText(self.config.get("deepseek_model", "deepseek-chat"))
        api_layout.addRow("مفتاح API:", self.deepseek_key)
        api_layout.addRow("النموذج:", self.deepseek_model)
        api_group.setLayout(api_layout)

        # Game Login
        login_group = QGroupBox("🎮 بيانات تسجيل الدخول")
        login_layout = QFormLayout()
        self.server_name = QLineEdit(self.config.get("server_name", ""))
        self.server_name.setPlaceholderText("iSRO / Theia / Legends...")
        self.server_ip = QLineEdit(self.config.get("server_ip", ""))
        self.server_ip.setPlaceholderText("XX.XX.XX.XX")
        self.server_port = QSpinBox()
        self.server_port.setRange(1, 65535)
        self.server_port.setValue(self.config.get("server_port", 15779))
        self.login_id = QLineEdit(self.config.get("login_id", ""))
        self.login_password = QLineEdit(self.config.get("login_password", ""))
        self.login_password.setEchoMode(QLineEdit.Password)
        self.login_pincode = QLineEdit(self.config.get("login_pincode", ""))
        self.login_pincode.setEchoMode(QLineEdit.Password)
        self.login_pincode.setPlaceholderText("اختياري")
        self.char_name = QLineEdit(self.config.get("char_name", ""))
        login_layout.addRow("اسم السيرفر:", self.server_name)
        login_layout.addRow("IP السيرفر:", self.server_ip)
        login_layout.addRow("بورت السيرفر:", self.server_port)
        login_layout.addRow("اسم المستخدم:", self.login_id)
        login_layout.addRow("كلمة المرور:", self.login_password)
        login_layout.addRow("الرقم السري (PIN):", self.login_pincode)
        login_layout.addRow("اسم الشخصية:", self.char_name)
        login_group.setLayout(login_layout)

        # phBot Settings
        phbot_group = QGroupBox("🔧 إعدادات phBot (اختياري)")
        phbot_layout = QFormLayout()
        self.phbot_host = QLineEdit(self.config.get("phbot_host", "127.0.0.1"))
        self.phbot_port_spin = QSpinBox()
        self.phbot_port_spin.setRange(1, 65535)
        self.phbot_port_spin.setValue(self.config.get("phbot_port", 8080))
        self.use_phbot = QCheckBox("استخدام phBot")
        self.use_phbot.setChecked(self.config.get("use_phbot", False))
        phbot_layout.addRow("", self.use_phbot)
        phbot_layout.addRow("عنوان phBot:", self.phbot_host)
        phbot_layout.addRow("منفذ phBot:", self.phbot_port_spin)
        phbot_group.setLayout(phbot_layout)

        # Combat Settings
        combat_group = QGroupBox("⚔️ إعدادات القتال")
        combat_layout = QFormLayout()
        self.hp_threshold = QSpinBox()
        self.hp_threshold.setRange(1, 99)
        self.hp_threshold.setValue(self.config.get("hp_threshold", 45))
        self.hp_threshold.setSuffix(" %")
        self.monster_threshold = QSpinBox()
        self.monster_threshold.setRange(1, 20)
        self.monster_threshold.setValue(self.config.get("monster_threshold", 5))
        self.spot_empty_minutes = QSpinBox()
        self.spot_empty_minutes.setRange(1, 30)
        self.spot_empty_minutes.setValue(self.config.get("spot_empty_minutes", 2))
        self.spot_empty_minutes.setSuffix(" دقيقة")
        self.farming_zone = QLineEdit(self.config.get("farming_zone", ""))
        self.farming_zone.setPlaceholderText("مثال: Roc Mountain - X:1234 Y:5678")
        self.auto_login = QCheckBox("تسجيل دخول تلقائي عند الانقطاع")
        self.auto_login.setChecked(self.config.get("auto_login", True))
        self.auto_quest = QCheckBox("قبول وتسليم المهام تلقائياً")
        self.auto_quest.setChecked(self.config.get("auto_quest", True))
        combat_layout.addRow("حد HP للدفاع:", self.hp_threshold)
        combat_layout.addRow("حد عدد الوحوش:", self.monster_threshold)
        combat_layout.addRow("وقت المنطقة الفارغة:", self.spot_empty_minutes)
        combat_layout.addRow("منطقة الزراعة:", self.farming_zone)
        combat_layout.addRow("", self.auto_login)
        combat_layout.addRow("", self.auto_quest)
        combat_group.setLayout(combat_layout)

        save_btn = QPushButton("💾 حفظ الإعدادات")
        save_btn.setMinimumHeight(40)
        save_btn.setStyleSheet("background-color: #2E7D32; font-size: 14px; font-weight: bold;")
        save_btn.clicked.connect(self.save_config)

        row1 = QHBoxLayout()
        row1.addWidget(api_group)
        row1.addWidget(login_group)

        row2 = QHBoxLayout()
        row2.addWidget(phbot_group)
        row2.addWidget(combat_group)

        layout.addLayout(row1)
        layout.addLayout(row2)
        layout.addWidget(save_btn)
        return widget

    def create_bot_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Status Panel
        status_group = QGroupBox("📊 حالة الشخصية")
        status_grid = QGridLayout()

        self.lbl_char = QLabel("—")
        self.lbl_level = QLabel("—")
        self.lbl_hp = QLabel("—")
        self.lbl_mp = QLabel("—")
        self.lbl_pos = QLabel("—")
        self.lbl_target = QLabel("—")
        self.lbl_monsters = QLabel("—")
        self.lbl_weapon = QLabel("—")
        self.lbl_combat = QLabel("—")
        self.lbl_ai_action = QLabel("—")

        hp_bar_layout = QVBoxLayout()
        self.hp_bar = QProgressBar()
        self.hp_bar.setStyleSheet("QProgressBar::chunk { background: #e53935; }")
        self.mp_bar = QProgressBar()
        self.mp_bar.setStyleSheet("QProgressBar::chunk { background: #1565C0; }")
        hp_bar_layout.addWidget(QLabel("HP:"))
        hp_bar_layout.addWidget(self.hp_bar)
        hp_bar_layout.addWidget(QLabel("MP:"))
        hp_bar_layout.addWidget(self.mp_bar)

        status_grid.addWidget(QLabel("الشخصية:"), 0, 0)
        status_grid.addWidget(self.lbl_char, 0, 1)
        status_grid.addWidget(QLabel("المستوى:"), 0, 2)
        status_grid.addWidget(self.lbl_level, 0, 3)
        status_grid.addWidget(QLabel("الموقع:"), 1, 0)
        status_grid.addWidget(self.lbl_pos, 1, 1)
        status_grid.addWidget(QLabel("الهدف:"), 1, 2)
        status_grid.addWidget(self.lbl_target, 1, 3)
        status_grid.addWidget(QLabel("الوحوش القريبة:"), 2, 0)
        status_grid.addWidget(self.lbl_monsters, 2, 1)
        status_grid.addWidget(QLabel("السلاح:"), 2, 2)
        status_grid.addWidget(self.lbl_weapon, 2, 3)
        status_grid.addWidget(QLabel("حالة القتال:"), 3, 0)
        status_grid.addWidget(self.lbl_combat, 3, 1)
        status_grid.addWidget(QLabel("آخر أمر AI:"), 3, 2)
        status_grid.addWidget(self.lbl_ai_action, 3, 3)

        right_panel = QVBoxLayout()
        right_panel.addLayout(hp_bar_layout)

        full_status = QHBoxLayout()
        full_status.addLayout(right_panel)
        full_status.addLayout(status_grid)
        status_group.setLayout(full_status)

        # Control Buttons
        ctrl_group = QGroupBox("🎮 التحكم")
        ctrl_layout = QHBoxLayout()

        self.start_btn = QPushButton("▶️ تشغيل البوت")
        self.start_btn.setMinimumHeight(50)
        self.start_btn.setStyleSheet("background-color: #1B5E20; font-size: 15px; font-weight: bold;")
        self.start_btn.clicked.connect(self.start_bot)

        self.stop_btn = QPushButton("⏹️ إيقاف البوت")
        self.stop_btn.setMinimumHeight(50)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("background-color: #B71C1C; font-size: 15px; font-weight: bold;")
        self.stop_btn.clicked.connect(self.stop_bot)

        self.test_ai_btn = QPushButton("🧪 اختبار DeepSeek")
        self.test_ai_btn.setMinimumHeight(50)
        self.test_ai_btn.setStyleSheet("background-color: #1A237E; font-size: 15px;")
        self.test_ai_btn.clicked.connect(self.test_deepseek)

        ctrl_layout.addWidget(self.start_btn)
        ctrl_layout.addWidget(self.stop_btn)
        ctrl_layout.addWidget(self.test_ai_btn)
        ctrl_group.setLayout(ctrl_layout)

        # Quick Stats
        stats_group = QGroupBox("📈 إحصائيات الجلسة")
        stats_layout = QGridLayout()
        self.stat_commands = QLabel("0")
        self.stat_kills = QLabel("0")
        self.stat_uptime = QLabel("00:00:00")
        self.stat_dc_count = QLabel("0")
        self.stat_ai_state = QLabel("⚪ متوقف")
        stats_layout.addWidget(QLabel("أوامر AI:"), 0, 0)
        stats_layout.addWidget(self.stat_commands, 0, 1)
        stats_layout.addWidget(QLabel("إعادة اتصال:"), 0, 2)
        stats_layout.addWidget(self.stat_dc_count, 0, 3)
        stats_layout.addWidget(QLabel("وقت التشغيل:"), 1, 0)
        stats_layout.addWidget(self.stat_uptime, 1, 1)
        stats_layout.addWidget(QLabel("حالة AI:"), 1, 2)
        stats_layout.addWidget(self.stat_ai_state, 1, 3)
        stats_group.setLayout(stats_layout)

        layout.addWidget(status_group)
        layout.addWidget(ctrl_group)
        layout.addWidget(stats_group)

        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_uptime)
        self.start_time = None

        return widget

    def create_logs_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        tools = QHBoxLayout()
        clear_btn = QPushButton("🗑️ مسح السجل")
        clear_btn.clicked.connect(self.clear_logs)
        save_logs_btn = QPushButton("💾 حفظ السجل")
        save_logs_btn.clicked.connect(self.save_logs)
        self.log_filter = QComboBox()
        self.log_filter.addItems(["الكل", "معلومات", "تحذير", "خطأ", "ذكاء اصطناعي", "نجاح"])
        tools.addWidget(QLabel("تصفية:"))
        tools.addWidget(self.log_filter)
        tools.addStretch()
        tools.addWidget(save_logs_btn)
        tools.addWidget(clear_btn)
        layout.addLayout(tools)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setFont(QFont("Consolas", 10))
        self.log_area.setStyleSheet("background-color: #0D0D0D; color: #E0E0E0;")
        layout.addWidget(self.log_area)
        return widget

    def create_files_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        info = QLabel(
            "📁 ملفات البوت\n\n"
            "لاستخدام البوت بشكل مستقل بدون phBot:\n"
            "• شغّل standalone_bot.py مباشرة\n\n"
            "لاستخدام البوت مع phBot:\n"
            "• انسخ phbot_plugin.py إلى مجلد plugins في phBot\n"
            "• تأكد من تشغيل local_server.py أولاً\n\n"
            "لبناء EXE:\n"
            "• شغّل build_exe.bat\n"
            "• ستجد الملف في مجلد dist"
        )
        info.setWordWrap(True)
        info.setStyleSheet("font-size: 13px; padding: 20px; line-height: 2;")

        open_folder_btn = QPushButton("📂 فتح مجلد الملفات")
        open_folder_btn.setMinimumHeight(40)
        open_folder_btn.clicked.connect(self.open_folder)

        build_btn = QPushButton("🔨 بناء EXE الآن")
        build_btn.setMinimumHeight(40)
        build_btn.setStyleSheet("background-color: #4A148C; font-size: 14px;")
        build_btn.clicked.connect(self.build_exe)

        layout.addWidget(info)
        layout.addWidget(open_folder_btn)
        layout.addWidget(build_btn)
        layout.addStretch()
        return widget

    def apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #121212; color: #E0E0E0; }
            QTabWidget::pane { border: 1px solid #333; }
            QTabBar::tab { background: #1E1E1E; color: #AAA; padding: 8px 16px; border-radius: 4px 4px 0 0; }
            QTabBar::tab:selected { background: #2D2D2D; color: #FFD700; border-bottom: 2px solid #FFD700; }
            QGroupBox { border: 1px solid #333; border-radius: 6px; margin-top: 12px; padding: 8px; font-weight: bold; color: #FFD700; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QLineEdit, QSpinBox, QComboBox { background: #1E1E1E; border: 1px solid #444; border-radius: 4px; padding: 5px; color: #E0E0E0; }
            QLineEdit:focus, QSpinBox:focus { border-color: #FFD700; }
            QPushButton { background-color: #1E1E1E; border: 1px solid #444; border-radius: 6px; padding: 8px 16px; color: #E0E0E0; }
            QPushButton:hover { background-color: #2D2D2D; border-color: #FFD700; }
            QPushButton:disabled { background-color: #111; color: #555; border-color: #222; }
            QLabel { color: #E0E0E0; }
            QCheckBox { color: #E0E0E0; }
            QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #555; background: #1E1E1E; border-radius: 3px; }
            QCheckBox::indicator:checked { background: #FFD700; border-color: #FFD700; }
            QProgressBar { border: 1px solid #333; border-radius: 4px; text-align: center; background: #1E1E1E; }
            QFrame#header { background: linear-gradient(#1A1A1A, #0D0D0D); border-bottom: 2px solid #FFD700; }
            QStatusBar { background: #0D0D0D; color: #AAA; }
        """)

    def log(self, message, level="info"):
        colors = {
            "info": "#87CEEB",
            "warning": "#FFA500",
            "error": "#FF4444",
            "success": "#44FF44",
            "ai": "#DA70D6",
        }
        color = colors.get(level, "#E0E0E0")
        icons = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "success": "✅", "ai": "🤖"}
        icon = icons.get(level, "•")
        timestamp = datetime.now().strftime("%H:%M:%S")
        html = f'<span style="color:#666">[{timestamp}]</span> <span style="color:{color}">{icon} {message}</span><br>'
        self.log_area.insertHtml(html)
        self.log_area.moveCursor(QTextCursor.End)

    def clear_logs(self):
        self.log_area.clear()
        self.log("تم مسح السجل", "info")

    def save_logs(self):
        fname = f"bot_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(fname, "w", encoding="utf-8") as f:
            f.write(self.log_area.toPlainText())
        self.log(f"تم حفظ السجل في: {fname}", "success")

    def save_config(self):
        self.config = {
            "deepseek_api_key": self.deepseek_key.text().strip(),
            "deepseek_model": self.deepseek_model.currentText(),
            "server_name": self.server_name.text().strip(),
            "server_ip": self.server_ip.text().strip(),
            "server_port": self.server_port.value(),
            "login_id": self.login_id.text().strip(),
            "login_password": self.login_password.text(),
            "login_pincode": self.login_pincode.text(),
            "char_name": self.char_name.text().strip(),
            "use_phbot": self.use_phbot.isChecked(),
            "phbot_host": self.phbot_host.text().strip(),
            "phbot_port": self.phbot_port_spin.value(),
            "hp_threshold": self.hp_threshold.value(),
            "monster_threshold": self.monster_threshold.value(),
            "spot_empty_minutes": self.spot_empty_minutes.value(),
            "farming_zone": self.farming_zone.text().strip(),
            "auto_login": self.auto_login.isChecked(),
            "auto_quest": self.auto_quest.isChecked(),
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)
        self.log("✔ تم حفظ الإعدادات بنجاح", "success")
        QMessageBox.information(self, "حفظ", "تم حفظ الإعدادات بنجاح!")

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, encoding="utf-8") as f:
                return json.load(f)
        return {}

    def start_bot(self):
        if not self.config.get("deepseek_api_key"):
            QMessageBox.warning(self, "تحذير", "يرجى إدخال مفتاح DeepSeek API أولاً!")
            return
        self.log("جاري تشغيل البوت...", "info")
        self.bot_worker = BotWorker(self.config)
        self.bot_worker.log_signal.connect(self.log)
        self.bot_worker.status_signal.connect(self.update_status)
        self.bot_worker.stopped.connect(self.on_bot_stopped)
        self.bot_worker.start()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.stat_ai_state.setText("🟢 يعمل")
        self.stat_ai_state.setStyleSheet("color: #44FF44;")
        self.start_time = time.time()
        self.status_timer.start(1000)
        self.status_bar.showMessage("🟢 البوت يعمل")

    def stop_bot(self):
        if self.bot_worker:
            self.log("جاري إيقاف البوت...", "warning")
            self.bot_worker.stop()

    def on_bot_stopped(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.stat_ai_state.setText("⚪ متوقف")
        self.stat_ai_state.setStyleSheet("color: #AAAAAA;")
        self.status_timer.stop()
        self.status_bar.showMessage("⚪ البوت متوقف")
        self.log("تم إيقاف البوت", "warning")

    def update_status(self, status):
        self.lbl_char.setText(status.get("char_name", "—"))
        self.lbl_level.setText(str(status.get("level", "—")))
        hp = status.get("hp", 0)
        max_hp = status.get("max_hp", 100)
        mp = status.get("mp", 0)
        max_mp = status.get("max_mp", 100)
        self.hp_bar.setMaximum(max_hp)
        self.hp_bar.setValue(hp)
        self.hp_bar.setFormat(f"{hp}/{max_hp}")
        self.mp_bar.setMaximum(max_mp)
        self.mp_bar.setValue(mp)
        self.mp_bar.setFormat(f"{mp}/{max_mp}")
        self.lbl_pos.setText(f"X:{status.get('x',0):.0f} Y:{status.get('y',0):.0f}")
        self.lbl_target.setText(status.get("target", "لا يوجد"))
        self.lbl_monsters.setText(str(status.get("nearby_monsters", 0)))
        self.lbl_weapon.setText(status.get("weapon", "—"))
        in_combat = status.get("in_combat", False)
        self.lbl_combat.setText("⚔️ في قتال" if in_combat else "😴 هادئ")
        self.lbl_ai_action.setText(status.get("last_action", "—"))
        self.stat_commands.setText(str(status.get("total_commands", 0)))
        self.stat_dc_count.setText(str(status.get("dc_count", 0)))

    def update_uptime(self):
        if self.start_time:
            elapsed = int(time.time() - self.start_time)
            h, m, s = elapsed // 3600, (elapsed % 3600) // 60, elapsed % 60
            self.stat_uptime.setText(f"{h:02d}:{m:02d}:{s:02d}")

    def test_deepseek(self):
        key = self.deepseek_key.text().strip()
        if not key:
            QMessageBox.warning(self, "تحذير", "يرجى إدخال مفتاح DeepSeek API!")
            return
        self.log("جاري اختبار الاتصال بـ DeepSeek...", "info")
        def run_test():
            from deepseek_client import DeepSeekClient
            client = DeepSeekClient(key, self.deepseek_model.currentText())
            result = client.test_connection()
            if result:
                self.log("✅ الاتصال بـ DeepSeek يعمل بشكل صحيح!", "success")
            else:
                self.log("❌ فشل الاتصال بـ DeepSeek. تحقق من المفتاح.", "error")
        threading.Thread(target=run_test, daemon=True).start()

    def open_folder(self):
        import subprocess
        folder = os.path.dirname(os.path.abspath(__file__))
        if sys.platform == "win32":
            subprocess.Popen(f'explorer "{folder}"')
        else:
            subprocess.Popen(["xdg-open", folder])

    def build_exe(self):
        self.log("جاري تشغيل سكريبت البناء...", "info")
        import subprocess
        result = subprocess.Popen(
            ["pyinstaller", "--onefile", "--windowed",
             "--name", "SilkroadAIBot",
             "--icon", "icon.ico" if os.path.exists("icon.ico") else "",
             "main_gui.py"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        self.log("تم إطلاق عملية البناء. انتظر اكتمالها في نافذة CMD", "warning")

    def closeEvent(self, event):
        if self.bot_worker and self.bot_worker.isRunning():
            self.bot_worker.stop()
            self.bot_worker.wait(3000)
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Silkroad AI Bot")
    app.setFont(QFont("Arial", 10))
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
