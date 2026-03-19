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
    QListWidgetItem, QSplitter, QScrollArea
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt5.QtGui import QFont, QTextCursor, QColor, QIcon

from ai_core import SilkroadAICore
from news_fetcher import NewsFetcher

CONFIG_FILE = "bot_config.json"


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
        self._setup_ui()
        self._apply_theme()
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
        self.tabs.addTab(self._build_settings_tab(), "⚙️ الإعدادات")
        self.tabs.addTab(self._build_bot_tab(),      "🤖 البوت")
        self.tabs.addTab(self._build_chat_tab(),     "💬 الشات")
        self.tabs.addTab(self._build_news_tab(),     "📰 الأخبار")
        self.tabs.addTab(self._build_memory_tab(),   "🧠 الذاكرة")
        self.tabs.addTab(self._build_logs_tab(),     "📋 السجل")
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
        self.e_srv  = QLineEdit(self.config.get("server_name",""))
        self.e_ip   = QLineEdit(self.config.get("server_ip",""))
        self.e_port = QSpinBox(); self.e_port.setRange(1,65535)
        self.e_port.setValue(self.config.get("server_port",15779))
        self.e_uid  = QLineEdit(self.config.get("login_id",""))
        self.e_pwd  = QLineEdit(self.config.get("login_password",""))
        self.e_pwd.setEchoMode(QLineEdit.Password)
        self.e_pin  = QLineEdit(self.config.get("login_pincode",""))
        self.e_pin.setEchoMode(QLineEdit.Password)
        self.e_pin.setPlaceholderText("اختياري")
        self.e_char = QLineEdit(self.config.get("char_name",""))
        for lbl, w_ in [("السيرفر:",self.e_srv),("IP:",self.e_ip),
                        ("البورت:",self.e_port),("المستخدم:",self.e_uid),
                        ("كلمة المرور:",self.e_pwd),("PIN:",self.e_pin),
                        ("اسم الشخصية:",self.e_char)]:
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
        self.chk_login = QCheckBox("تسجيل دخول تلقائي عند الانقطاع")
        self.chk_login.setChecked(self.config.get("auto_login",True))
        self.chk_quest = QCheckBox("قبول وتسليم المهام تلقائياً")
        self.chk_quest.setChecked(self.config.get("auto_quest",True))
        self.chk_news  = QCheckBox("متابعة أخبار اللعبة تلقائياً")
        self.chk_news.setChecked(self.config.get("auto_news",True))
        for lbl, w_ in [("حد HP:",self.e_hp),("حد الوحوش:",self.e_mon),
                        ("وقت المنطقة الفارغة:",self.e_spot),("منطقة الزراعة:",self.e_zone)]:
            f3.addRow(lbl, w_)
        for chk in [self.chk_login, self.chk_quest, self.chk_news]:
            f3.addRow("", chk)
        g3.setLayout(f3)

        btn = QPushButton("💾 حفظ الإعدادات")
        btn.setMinimumHeight(40)
        btn.setStyleSheet("background:#1B5E20; font-size:14px; font-weight:bold;")
        btn.clicked.connect(self._save_config)

        row1 = QHBoxLayout(); row1.addWidget(g1); row1.addWidget(g2)
        lay.addLayout(row1); lay.addWidget(g3); lay.addWidget(btn)
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

        g_ctrl = QGroupBox("🎮 التحكم"); h = QHBoxLayout()
        self.btn_start = QPushButton("▶️ تشغيل")
        self.btn_stop  = QPushButton("⏹️ إيقاف")
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

        lay.addWidget(g_status); lay.addWidget(g_ctrl); lay.addWidget(g_stats)
        self._uptime_timer = QTimer(); self._uptime_timer.timeout.connect(self._tick_uptime)
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
        ctrl.addWidget(btn_refresh); ctrl.addWidget(btn_clear); ctrl.addStretch()

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

    # ─── Config ───────────────────────────────────────────────────────────
    def _save_config(self):
        self.config = {
            "deepseek_api_key": self.e_key.text().strip(),
            "deepseek_model":   self.e_model.currentText(),
            "server_name":      self.e_srv.text().strip(),
            "server_ip":        self.e_ip.text().strip(),
            "server_port":      self.e_port.value(),
            "login_id":         self.e_uid.text().strip(),
            "login_password":   self.e_pwd.text(),
            "login_pincode":    self.e_pin.text(),
            "char_name":        self.e_char.text().strip(),
            "hp_threshold":     self.e_hp.value(),
            "monster_threshold":self.e_mon.value(),
            "spot_empty_minutes":self.e_spot.value(),
            "farming_zone":     self.e_zone.text().strip(),
            "auto_login":       self.chk_login.isChecked(),
            "auto_quest":       self.chk_quest.isChecked(),
            "auto_news":        self.chk_news.isChecked(),
        }
        with open(CONFIG_FILE,"w",encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)
        self._log("تم حفظ الإعدادات", "success")
        QMessageBox.information(self, "حفظ", "تم حفظ الإعدادات بنجاح!")

    def _load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, encoding="utf-8") as f:
                    return json.load(f)
            except: pass
        return {}

    # ─── Bot Control ──────────────────────────────────────────────────────
    def _start_bot(self):
        if not self.config.get("deepseek_api_key"):
            QMessageBox.warning(self, "تحذير", "يرجى إدخال مفتاح DeepSeek API أولاً!")
            return
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
            QMessageBox.warning(self, "تحذير", "أدخل مفتاح API أولاً!"); return
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
        self.st["cmds"].setText(str(s.get("total_commands",0)))
        self.st["dc"].setText(str(s.get("dc_count",0)))
        if self.bot_worker:
            mem = self.bot_worker.get_memory()
            stats = mem.get_stats()
            self.st["decisions"].setText(stats["total_decisions"])
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
        mem = self.bot_worker.get_memory()
        stats = mem.get_stats()
        self.mem_lbl["decisions"].setText(str(stats["total_decisions"]))
        self.mem_lbl["deaths"].setText(str(stats["deaths_recorded"]))
        self.mem_lbl["success"].setText(stats["success_rate"])
        self.mem_lbl["lessons"].setText(str(stats["lessons_learned"]))
        self.mem_lbl["errors"].setText(str(stats["error_patterns"]))
        best = mem.get_best_rotation()
        from ai_core import SKILL_NAMES_AR
        rotation_str = " → ".join(SKILL_NAMES_AR.get(s, str(s)) for s in best)
        self.mem_lbl["rotation"].setText(rotation_str)
        self.lessons_text.setPlainText(mem.get_lessons_summary())
        skill_lines = []
        for sid, st in mem.skill_stats.items():
            rate = (st["success"] / max(st["used"], 1)) * 100
            from ai_core import SKILL_NAMES_AR
            name = SKILL_NAMES_AR.get(int(sid), sid)
            skill_lines.append(f"{name}: {st['used']} استخدام | نجاح {rate:.0f}%")
        self.skills_text.setPlainText("\n".join(skill_lines) or "لا توجد بيانات مهارات بعد")

    def _clear_memory(self):
        r = QMessageBox.question(self, "تأكيد", "هل تريد مسح الذاكرة المحفوظة؟",
                                  QMessageBox.Yes | QMessageBox.No)
        if r == QMessageBox.Yes:
            import os
            for f in ["bot_memory.json", "news_cache.json"]:
                if os.path.exists(f): os.remove(f)
            self._log("تم مسح الذاكرة", "warning")

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
