"""
ai_core.py - النواة الذكية للبوت
يتولى: جمع البيانات، تحليل الموقف، إصدار الأوامر عبر DeepSeek
"""

import socket
import struct
import time
import threading
import random
import math
from deepseek_client import DeepSeekClient


SKILL_IDS = {
    "daredevil": 7650,
    "ground_impact": 7652,
    "stab": 7654,
    "turn_fresh": 7656,
    "iron_skin": 7910,
    "berserk": 7660,
    "charge": 7662,
}

WEAPON_SLOTS = {
    "two_hand_sword": 0,
    "one_hand_shield": 1,
}

PACKET_TYPES = {
    "LOGIN": 0x7001,
    "MOVEMENT": 0x7021,
    "SKILL_CAST": 0x7074,
    "WEAPON_SWITCH": 0x7034,
    "PICKUP": 0x7051,
}


class GameState:
    def __init__(self):
        self.char_name = ""
        self.hp = 100
        self.max_hp = 100
        self.mp = 100
        self.max_mp = 100
        self.level = 116
        self.x = 0.0
        self.y = 0.0
        self.target = ""
        self.target_hp = 0
        self.nearby_monsters = 0
        self.in_combat = False
        self.active_buffs = []
        self.weapon = "two_hand_sword"
        self.is_dead = False
        self.is_disconnected = False
        self.quest_list = []
        self.spot_empty_seconds = 0
        self.ks_detected = False
        self.last_kill_time = time.time()

    def hp_percent(self):
        if self.max_hp == 0:
            return 100
        return int((self.hp / self.max_hp) * 100)

    def to_dict(self):
        return {
            "char_name": self.char_name,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "hp_percent": self.hp_percent(),
            "mp": self.mp,
            "max_mp": self.max_mp,
            "level": self.level,
            "x": self.x,
            "y": self.y,
            "target": self.target,
            "target_hp": self.target_hp,
            "nearby_monsters": self.nearby_monsters,
            "in_combat": self.in_combat,
            "active_buffs": self.active_buffs,
            "weapon": self.weapon,
            "is_dead": self.is_dead,
            "is_disconnected": self.is_disconnected,
            "quest_list": self.quest_list,
            "spot_empty_seconds": self.spot_empty_seconds,
            "ks_detected": self.ks_detected,
        }


class PacketInjector:
    """حقن حزم الاتصال المباشر بالسيرفر"""

    def __init__(self, server_ip, server_port, logger):
        self.server_ip = server_ip
        self.server_port = server_port
        self.log = logger
        self.sock = None
        self.connected = False

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10)
            self.sock.connect((self.server_ip, self.server_port))
            self.connected = True
            self.log("تم الاتصال بالسيرفر", "success")
            return True
        except Exception as e:
            self.log(f"فشل الاتصال: {e}", "error")
            return False

    def disconnect(self):
        self.connected = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def build_packet(self, packet_type, data=b""):
        size = len(data) + 6
        packet = struct.pack("<HH", size, packet_type) + data
        checksum = sum(packet) & 0xFF
        return packet + struct.pack("B", checksum)

    def send_login_packet(self, username, password, pincode=""):
        try:
            user_bytes = username.encode("ascii") + b"\x00"
            pass_bytes = password.encode("ascii") + b"\x00"
            data = struct.pack("<H", len(user_bytes)) + user_bytes
            data += struct.pack("<H", len(pass_bytes)) + pass_bytes
            if pincode:
                pin_bytes = pincode.encode("ascii") + b"\x00"
                data += struct.pack("<H", len(pin_bytes)) + pin_bytes
            packet = self.build_packet(PACKET_TYPES["LOGIN"], data)
            self.sock.sendall(packet)
            self.log("تم إرسال حزمة تسجيل الدخول", "info")
            return True
        except Exception as e:
            self.log(f"خطأ في إرسال حزمة الدخول: {e}", "error")
            return False

    def spam_login(self, username, password, pincode="", attempts=10, delay=0.5):
        self.log(f"بدء محاولات الدخول المتكررة ({attempts} محاولة)...", "warning")
        for i in range(attempts):
            if not self.connected:
                if not self.connect():
                    time.sleep(delay)
                    continue
            success = self.send_login_packet(username, password, pincode)
            if success:
                self.log(f"محاولة الدخول {i+1}/{attempts}", "info")
            time.sleep(delay)

    def send_skill(self, skill_id, target_id=0):
        try:
            data = struct.pack("<IHI", skill_id, 2, target_id)
            packet = self.build_packet(PACKET_TYPES["SKILL_CAST"], data)
            self.sock.sendall(packet)
            return True
        except Exception as e:
            self.log(f"خطأ في إرسال مهارة: {e}", "error")
            return False

    def send_movement(self, x, y):
        try:
            data = struct.pack("<ff", x, y)
            packet = self.build_packet(PACKET_TYPES["MOVEMENT"], data)
            self.sock.sendall(packet)
            return True
        except Exception as e:
            self.log(f"خطأ في إرسال حركة: {e}", "error")
            return False


class SilkroadAICore:
    """النواة الرئيسية للبوت"""

    def __init__(self, config, logger):
        self.config = config
        self.log = logger
        self.state = GameState()
        self.running = False
        self.ai_client = DeepSeekClient(
            config.get("deepseek_api_key", ""),
            config.get("deepseek_model", "deepseek-chat")
        )
        self.injector = PacketInjector(
            config.get("server_ip", ""),
            config.get("server_port", 15779),
            logger
        )
        self.total_commands = 0
        self.dc_count = 0
        self.last_action = "—"
        self.last_spot_check = time.time()
        self.combat_lock = threading.Lock()
        self.state.char_name = config.get("char_name", "Warrior")

    def start(self):
        self.running = True
        self.log("🚀 بدء تشغيل نظام AI...", "success")
        if not self.config.get("use_phbot", False):
            self.log("وضع مستقل (بدون phBot)", "info")
            if self.config.get("auto_login"):
                threading.Thread(target=self._auto_login_loop, daemon=True).start()
        else:
            self.log("وضع phBot - الاتصال بـ phBot...", "info")
        threading.Thread(target=self._simulation_loop, daemon=True).start()

    def stop(self):
        self.running = False
        self.injector.disconnect()
        self.log("تم إيقاف البوت", "warning")

    def _auto_login_loop(self):
        self.log("بدء محرك تسجيل الدخول التلقائي...", "info")
        while self.running:
            if self.state.is_disconnected:
                self.log("⚠️ انقطاع الاتصال - محاولة إعادة الدخول...", "warning")
                self.dc_count += 1
                self.injector.spam_login(
                    self.config.get("login_id", ""),
                    self.config.get("login_password", ""),
                    self.config.get("login_pincode", ""),
                    attempts=5, delay=0.3
                )
                time.sleep(5)
            time.sleep(2)

    def _simulation_loop(self):
        """حلقة المحاكاة للاختبار وعرض البيانات"""
        tick = 0
        while self.running:
            tick += 1
            self._simulate_game_state(tick)
            if tick % 5 == 0:
                self._ai_decision_cycle()
            if self.config.get("auto_quest") and tick % 30 == 0:
                self._check_quests()
            self._check_spot(tick)
            time.sleep(1)

    def _simulate_game_state(self, tick):
        """محاكاة تغيير حالة اللعبة - يستبدل بالبيانات الحقيقية من phBot"""
        self.state.hp = max(30, min(self.state.max_hp, self.state.hp + random.randint(-15, 20)))
        self.state.mp = max(10, min(self.state.max_mp, self.state.mp + random.randint(-5, 15)))
        self.state.nearby_monsters = random.randint(0, 8)
        self.state.in_combat = self.state.nearby_monsters > 0
        if self.state.in_combat:
            self.state.target = random.choice(["Tiger King", "Stone Golem", "Giant Spider"])
            self.state.target_hp = random.randint(20, 100)
        else:
            self.state.target = ""
            self.state.spot_empty_seconds += 1
        if self.state.in_combat:
            self.state.spot_empty_seconds = 0
            self.state.last_kill_time = time.time()

    def _ai_decision_cycle(self):
        """دورة القرار الذكي - تسأل DeepSeek عن أفضل أمر"""
        with self.combat_lock:
            state_data = self.state.to_dict()
            state_data.update({
                "hp_threshold": self.config.get("hp_threshold", 45),
                "monster_threshold": self.config.get("monster_threshold", 5),
            })
            try:
                command = self.ai_client.get_combat_command(state_data)
                if command:
                    self._execute_command(command)
            except Exception as e:
                self.log(f"خطأ في AI: {e}", "error")
                self._fallback_logic()

    def _execute_command(self, command):
        action = command.get("action", "idle")
        reason = command.get("reason", "")
        self.total_commands += 1
        self.last_action = action

        if action == "cast_skill":
            skill_id = command.get("skillId", 0)
            skill_name = self._get_skill_name(skill_id)
            self.log(f"🤖 AI: استخدام مهارة {skill_name} - {reason}", "ai")
            self._cast_skill(skill_id)

        elif action == "switch_weapon":
            slot = command.get("weaponSlot", 0)
            wname = "درع ودرع" if slot == 1 else "سيف ثقيل"
            self.log(f"🤖 AI: تغيير السلاح إلى {wname} - {reason}", "ai")
            self._switch_weapon(slot)

        elif action == "move_to":
            x, y = command.get("targetX", 0), command.get("targetY", 0)
            self.log(f"🤖 AI: الانتقال إلى X:{x} Y:{y} - {reason}", "ai")
            self.injector.send_movement(x, y)

        elif action == "defend":
            self.log(f"🛡️ AI: وضع الدفاع - {reason}", "ai")
            self._switch_weapon(WEAPON_SLOTS["one_hand_shield"])
            self._cast_skill(SKILL_IDS["iron_skin"])

        elif action == "login_inject":
            self.log("🔐 AI: محاولة إعادة الدخول...", "warning")
            self.injector.spam_login(
                self.config.get("login_id", ""),
                self.config.get("login_password", ""),
                self.config.get("login_pincode", ""),
                attempts=3, delay=0.5
            )

    def _fallback_logic(self):
        """منطق احتياطي عند عدم توفر AI"""
        hp_pct = self.state.hp_percent()
        monsters = self.state.nearby_monsters
        threshold_hp = self.config.get("hp_threshold", 45)
        threshold_mon = self.config.get("monster_threshold", 5)

        if hp_pct < threshold_hp or monsters > threshold_mon:
            self.log(f"⚠️ إجراء دفاعي: HP={hp_pct}% وحوش={monsters}", "warning")
            self._switch_weapon(WEAPON_SLOTS["one_hand_shield"])
            self._cast_skill(SKILL_IDS["iron_skin"])
            time.sleep(1)
            self._switch_weapon(WEAPON_SLOTS["two_hand_sword"])
        elif self.state.in_combat:
            rotation = [
                SKILL_IDS["daredevil"],
                SKILL_IDS["ground_impact"],
                SKILL_IDS["stab"],
                SKILL_IDS["turn_fresh"],
            ]
            skill = rotation[self.total_commands % len(rotation)]
            self._cast_skill(skill)
            self.log(f"🗡️ احتياطي: {self._get_skill_name(skill)}", "info")

    def _cast_skill(self, skill_id):
        self.injector.send_skill(skill_id)

    def _switch_weapon(self, slot):
        wname = "one_hand_shield" if slot == 1 else "two_hand_sword"
        self.state.weapon = wname

    def _check_quests(self):
        if self.state.quest_list:
            self.log(f"📜 فحص المهام: {len(self.state.quest_list)} مهمة متاحة", "info")

    def _check_spot(self, tick):
        empty_limit = self.config.get("spot_empty_minutes", 2) * 60
        if self.state.spot_empty_seconds > empty_limit:
            self.log("📍 المنطقة فارغة - البحث عن موقع جديد...", "warning")
            new_x = self.state.x + random.uniform(-50, 50)
            new_y = self.state.y + random.uniform(-50, 50)
            self.injector.send_movement(new_x, new_y)
            self.state.spot_empty_seconds = 0
            self.last_action = f"انتقل إلى {new_x:.0f},{new_y:.0f}"

        if self.state.ks_detected:
            self.log("⚔️ KS مكتشف - الانتقال لمكان آمن...", "warning")
            angle = random.uniform(0, 2 * math.pi)
            dist = random.uniform(30, 80)
            new_x = self.state.x + math.cos(angle) * dist
            new_y = self.state.y + math.sin(angle) * dist
            self.injector.send_movement(new_x, new_y)
            self.state.ks_detected = False

    def _get_skill_name(self, skill_id):
        names = {v: k for k, v in SKILL_IDS.items()}
        arabic = {
            "daredevil": "داريديفل",
            "ground_impact": "ضربة أرضية",
            "stab": "طعنة",
            "turn_fresh": "هجوم جماعي",
            "iron_skin": "جلد حديدي",
            "berserk": "برسيرك",
            "charge": "돌진",
        }
        eng = names.get(skill_id, str(skill_id))
        return arabic.get(eng, eng)

    def get_status(self):
        return {
            "char_name": self.state.char_name,
            "hp": self.state.hp,
            "max_hp": self.state.max_hp,
            "mp": self.state.mp,
            "max_mp": self.state.max_mp,
            "level": self.state.level,
            "x": self.state.x,
            "y": self.state.y,
            "target": self.state.target,
            "nearby_monsters": self.state.nearby_monsters,
            "in_combat": self.state.in_combat,
            "weapon": self.state.weapon,
            "last_action": self.last_action,
            "total_commands": self.total_commands,
            "dc_count": self.dc_count,
        }
