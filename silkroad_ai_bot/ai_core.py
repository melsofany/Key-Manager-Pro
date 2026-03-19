"""
ai_core.py - النواة الذكية للبوت
يتولى: جمع البيانات، التعلم من الأخطاء، تنفيذ أوامر القتال
"""

import socket
import struct
import time
import threading
import random
import math
from deepseek_client import DeepSeekClient
from memory import BotMemory


SKILL_IDS = {
    "daredevil":    7650,
    "ground_impact":7652,
    "stab":         7654,
    "turn_fresh":   7656,
    "iron_skin":    7910,
    "berserk":      7660,
    "charge":       7662,
}

SKILL_NAMES_AR = {
    7650: "داريديفل",
    7652: "ضربة أرضية",
    7654: "طعنة",
    7656: "هجوم جماعي",
    7910: "جلد حديدي",
    7660: "برسيرك",
    7662: "돌진",
}

WEAPON_SLOTS = {"two_hand_sword": 0, "one_hand_shield": 1}
PACKET_LOGIN    = 0x7001
PACKET_MOVEMENT = 0x7021
PACKET_SKILL    = 0x7074
PACKET_POTION   = 0x7080


class GameState:
    def __init__(self):
        self.char_name = ""
        self.hp = 100; self.max_hp = 100
        self.mp = 100; self.max_mp = 100
        self.level = 116
        self.x = 0.0; self.y = 0.0
        self.target = ""; self.target_hp = 0
        self.nearby_monsters = 0
        self.in_combat = False
        self.active_buffs = []
        self.buff_timers = {}
        self.weapon = "two_hand_sword"
        self.is_dead = False
        self.is_disconnected = False
        self.quest_list = []
        self.spot_empty_seconds = 0
        self.ks_detected = False
        self.gold = 0
        self.kills_this_session = 0

    def hp_percent(self):
        return int((self.hp / max(self.max_hp, 1)) * 100)

    def mp_percent(self):
        return int((self.mp / max(self.max_mp, 1)) * 100)

    def to_dict(self):
        return {
            "char_name":          self.char_name,
            "hp":                 self.hp, "max_hp": self.max_hp,
            "hp_percent":         self.hp_percent(),
            "mp":                 self.mp, "max_mp": self.max_mp,
            "mp_percent":         self.mp_percent(),
            "level":              self.level,
            "x": self.x, "y":    self.y,
            "target":             self.target,
            "target_hp":          self.target_hp,
            "nearby_monsters":    self.nearby_monsters,
            "in_combat":          self.in_combat,
            "active_buffs":       self.active_buffs,
            "weapon":             self.weapon,
            "is_dead":            self.is_dead,
            "is_disconnected":    self.is_disconnected,
            "quest_list":         self.quest_list,
            "spot_empty_seconds": self.spot_empty_seconds,
            "ks_detected":        self.ks_detected,
            "gold":               self.gold,
            "kills_this_session": self.kills_this_session,
        }


class PacketInjector:
    def __init__(self, server_ip, server_port, logger):
        self.server_ip   = server_ip
        self.server_port = server_port
        self.log         = logger
        self.sock        = None
        self.connected   = False

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
            try: self.sock.close()
            except: pass
            self.sock = None

    def _build(self, ptype, data=b""):
        size = len(data) + 6
        pkt = struct.pack("<HH", size, ptype) + data
        return pkt + struct.pack("B", sum(pkt) & 0xFF)

    def spam_login(self, username, password, pincode="",
                   attempts=8, delay=0.4, shard_id=0):
        shard_txt = f" → Shard {shard_id}" if shard_id else ""
        self.log(f"بدء محاولات الدخول{shard_txt} ({attempts} محاولة)...", "warning")
        for i in range(attempts):
            if not self.connected:
                if not self.connect():
                    time.sleep(delay); continue
            try:
                u = username.encode("ascii") + b"\x00"
                p = password.encode("ascii") + b"\x00"
                data = struct.pack("<H", len(u)) + u + struct.pack("<H", len(p)) + p
                if pincode:
                    pin = pincode.encode("ascii") + b"\x00"
                    data += struct.pack("<H", len(pin)) + pin
                # إضافة Shard ID لاختيار السيرفر داخل اللعبة
                if shard_id:
                    data += struct.pack("<H", shard_id)
                self.sock.sendall(self._build(PACKET_LOGIN, data))
                self.log(f"محاولة دخول {i+1}/{attempts}{shard_txt}", "info")
            except Exception as e:
                self.log(f"خطأ في الإرسال: {e}", "error")
                self.connected = False
            time.sleep(delay)

    def send_skill(self, skill_id, target_id=0):
        if not self.connected:
            return False
        try:
            data = struct.pack("<IHI", skill_id, 2, target_id)
            self.sock.sendall(self._build(PACKET_SKILL, data))
            return True
        except:
            self.connected = False
            return False

    def send_movement(self, x, y):
        if not self.connected:
            return False
        try:
            self.sock.sendall(self._build(PACKET_MOVEMENT, struct.pack("<ff", x, y)))
            return True
        except:
            self.connected = False
            return False

    def send_potion(self, potion_type: str = "hp"):
        """إرسال حزمة استخدام بوشن (HP أو MP)"""
        if not self.connected:
            return False
        try:
            ptype_byte = 0x01 if potion_type == "hp" else 0x02
            data = struct.pack("<B", ptype_byte)
            self.sock.sendall(self._build(PACKET_POTION, data))
            return True
        except:
            self.connected = False
            return False


class SilkroadAICore:
    def __init__(self, config, logger):
        self.config = config
        self.log    = logger
        self.state  = GameState()
        self.state.char_name = config.get("char_name", "Warrior")
        self.running = False
        self.ai = DeepSeekClient(
            config.get("deepseek_api_key", ""),
            config.get("deepseek_model", "deepseek-chat")
        )
        self.injector = PacketInjector(
            config.get("server_ip", ""),
            config.get("server_port", 15779),
            logger
        )
        self.memory = BotMemory()
        self.total_commands  = 0
        self.dc_count        = 0
        self.potion_count    = 0
        self.last_action     = "—"
        self._rotation_idx   = 0
        self._iron_skin_at   = 0
        self._berserk_at     = 0
        self._last_potion_at = 0
        self._paused         = False
        self._prev_kill_count = 0

    # ─── التشغيل والإيقاف ─────────────────────────────────────────────────
    def start(self):
        self.running = True
        self.log("🚀 بدء تشغيل نظام AI...", "success")
        stats = self.memory.get_stats()
        self.log(
            f"📚 الذاكرة: {stats['total_decisions']} قرار محفوظ، "
            f"{stats['lessons_learned']} درس، معدل نجاح {stats['success_rate']}",
            "info"
        )
        if self.config.get("use_phbot", False):
            self.log("وضع phBot مفعّل", "info")
        else:
            self.log("وضع مستقل (بدون phBot)", "info")
        if self.config.get("auto_login"):
            threading.Thread(target=self._dc_watchdog, daemon=True).start()
        threading.Thread(target=self._main_loop, daemon=True).start()

    def stop(self):
        self.running = False
        self.injector.disconnect()
        self.memory.save()
        self.log("تم إيقاف البوت وحفظ الذاكرة", "warning")

    def pause(self):
        self._paused = True
        self.log("⏸️ البوت موقوف مؤقتاً", "warning")

    def resume(self):
        self._paused = False
        self.log("▶️ استئناف البوت", "success")

    # ─── الحلقات الرئيسية ─────────────────────────────────────────────────
    def _dc_watchdog(self):
        repeated_dc = 0
        while self.running:
            if self.state.is_disconnected:
                repeated_dc += 1
                self.log("⚠️ انقطاع مكتشف - إعادة الدخول...", "warning")
                self.memory.record_error("disconnect", "انقطاع الاتصال")
                self.dc_count += 1
                if self.config.get("pause_on_repeated_dc") and repeated_dc >= 3:
                    self.log("🔴 انقطاع متكرر — إيقاف مؤقت 5 دقائق", "error")
                    self.pause()
                    time.sleep(300)
                    self.resume()
                    repeated_dc = 0
                else:
                    self.injector.spam_login(
                        self.config.get("login_id", ""),
                        self.config.get("login_password", ""),
                        self.config.get("login_pincode", ""),
                        shard_id=self.config.get("shard_id", 0),
                    )
                time.sleep(5)
            else:
                repeated_dc = max(0, repeated_dc - 1)
            time.sleep(2)

    def _main_loop(self):
        tick = 0
        while self.running:
            tick += 1
            if self._paused:
                time.sleep(1)
                continue
            self._simulate_state(tick)
            # Auto-potion
            if self.config.get("use_auto_potion", True):
                self._auto_potion()
            # Check for kill
            if self.state.kills_this_session > self._prev_kill_count:
                kills_new = self.state.kills_this_session - self._prev_kill_count
                xp_gain = kills_new * random.randint(4200, 8800)
                gold_gain = kills_new * random.randint(200, 900)
                self.memory.record_kill(kills_new, xp_gain, gold_gain)
                self._prev_kill_count = self.state.kills_this_session
            if self.state.is_dead:
                self.memory.record_death(self.state.to_dict())
                self.log("💀 الشخصية ماتت - انتظار إعادة الإحياء...", "error")
                time.sleep(5)
                continue
            if tick % 4 == 0:
                self._ai_cycle()
            if self.config.get("auto_quest") and tick % 30 == 0:
                self._handle_quests()
            # Check buffs
            if tick % self.config.get("buff_interval_sec", 30) == 0:
                self._refresh_buffs()
            self._check_spot()
            time.sleep(1)

    def _simulate_state(self, tick):
        """محاكاة حالة اللعبة - يُستبدل ببيانات حقيقية من phBot"""
        hp_regen = 30 if not self.state.in_combat else -random.randint(5, 20)
        self.state.hp = max(15, min(self.state.max_hp, self.state.hp + hp_regen))
        self.state.mp = max(10, min(self.state.max_mp, self.state.mp + random.randint(-8, 18)))

        prev_monsters = self.state.nearby_monsters
        self.state.nearby_monsters = random.randint(0, 8)
        self.state.in_combat = self.state.nearby_monsters > 0
        if self.state.in_combat:
            self.state.target    = random.choice(["Tiger King", "Stone Golem", "Giant Spider", "Roc", "Dark Hunter"])
            self.state.target_hp = random.randint(10, 100)
            self.state.spot_empty_seconds = 0
        else:
            self.state.target = ""
            self.state.spot_empty_seconds += 1
            # Kill counted when monsters disappear (combat ended)
            if prev_monsters > 0:
                self.state.kills_this_session += prev_monsters
                self.state.gold += prev_monsters * random.randint(200, 900)

    def _auto_potion(self):
        """استخدام بوشن HP/MP تلقائياً"""
        now = time.time()
        pot_delay = self.config.get("potion_delay_ms", 1500) / 1000.0
        if now - self._last_potion_at < pot_delay:
            return
        hp_threshold = self.config.get("hp_potion_threshold", 60)
        mp_threshold = self.config.get("mp_potion_threshold", 40)
        if self.state.hp_percent() < hp_threshold:
            self.injector.send_potion("hp")
            self.log(f"💊 HP بوشن! ({self.state.hp_percent()}%)", "warning")
            self.potion_count += 1
            self._last_potion_at = now
        elif self.state.mp_percent() < mp_threshold:
            combat_only = self.config.get("mp_potion_combat_only", False)
            if not combat_only or self.state.in_combat:
                self.injector.send_potion("mp")
                self.log(f"💊 MP بوشن! ({self.state.mp_percent()}%)", "info")
                self.potion_count += 1
                self._last_potion_at = now

    def _refresh_buffs(self):
        """تجديد بافات الدفاع"""
        if self.state.in_combat and time.time() - self._iron_skin_at > self.config.get("buff_interval_sec", 30):
            self.injector.send_skill(SKILL_IDS["iron_skin"])
            self._iron_skin_at = time.time()
            if "iron_skin" not in self.state.active_buffs:
                self.state.active_buffs.append("iron_skin")
            self.log("🛡️ تجديد Iron Skin", "info")

    # ─── دورة القرار الذكي ────────────────────────────────────────────────
    def _ai_cycle(self):
        state = self.state.to_dict()
        state.update({
            "hp_threshold":    self.config.get("hp_threshold", 45),
            "monster_threshold": self.config.get("monster_threshold", 5),
            "berserk_hp_min":  self.config.get("berserk_hp_min", 70),
        })
        lessons = self.memory.get_lessons_summary()
        try:
            cmd = self.ai.get_combat_command(state, lessons)
            result = self._execute(cmd, state)
            self.memory.record_decision(state, cmd, result)
        except Exception as e:
            self.memory.record_error("ai_error", str(e))
            self.log(f"⚠️ AI غير متاح، تفعيل الوضع الاحتياطي: {e}", "warning")
            self._fallback()

    def _execute(self, cmd: dict, state: dict) -> str:
        action = cmd.get("action", "idle")
        reason = cmd.get("reason", "")
        self.total_commands += 1
        self.last_action = action

        if action == "cast_skill":
            sid  = cmd.get("skillId", 0)
            # Skip disabled skills
            if not self.config.get(f"skill_{sid}_enabled", True):
                return "skipped"
            name = SKILL_NAMES_AR.get(sid, str(sid))
            self.log(f"🤖 [{reason}] → {name}", "ai")
            self.injector.send_skill(sid)
            return "success"

        elif action == "switch_weapon":
            slot  = cmd.get("weaponSlot", 0)
            wname = "درع ودرع" if slot == 1 else "سيف ثقيل"
            self.log(f"🤖 [{reason}] → تغيير: {wname}", "ai")
            self.state.weapon = "one_hand_shield" if slot == 1 else "two_hand_sword"
            return "success"

        elif action == "defend":
            self.log(f"🛡️ [{reason}] → وضع الدفاع", "ai")
            self.state.weapon = "one_hand_shield"
            if time.time() - self._iron_skin_at > 30:
                self.injector.send_skill(SKILL_IDS["iron_skin"])
                self._iron_skin_at = time.time()
            return "success"

        elif action == "use_potion":
            ptype = cmd.get("potion_type", "hp")
            self.injector.send_potion(ptype)
            self.log(f"💊 [{reason}] → بوشن {ptype.upper()}", "warning")
            self.potion_count += 1
            self._last_potion_at = time.time()
            return "success"

        elif action == "move_to":
            x, y = cmd.get("targetX", 0), cmd.get("targetY", 0)
            self.log(f"🤖 [{reason}] → انتقال {x:.0f},{y:.0f}", "ai")
            self.injector.send_movement(x, y)
            return "success"

        elif action == "login_inject":
            self.log(f"🔐 [{reason}] → إعادة تسجيل الدخول", "warning")
            threading.Thread(
                target=self.injector.spam_login,
                args=(
                    self.config.get("login_id", ""),
                    self.config.get("login_password", ""),
                    self.config.get("login_pincode", ""),
                ),
                kwargs={"shard_id": self.config.get("shard_id", 0)},
                daemon=True
            ).start()
            return "success"

        elif action == "idle":
            return "idle"

        return "unknown"

    def _fallback(self):
        hp_pct       = self.state.hp_percent()
        monsters     = self.state.nearby_monsters
        threshold_hp = self.config.get("hp_threshold", 45)
        threshold_mon= self.config.get("monster_threshold", 5)
        if hp_pct < threshold_hp or monsters > threshold_mon:
            self.log(f"⚠️ دفاع احتياطي HP={hp_pct}%", "warning")
            self.state.weapon = "one_hand_shield"
            if time.time() - self._iron_skin_at > 30:
                self.injector.send_skill(SKILL_IDS["iron_skin"])
                self._iron_skin_at = time.time()
        elif self.state.in_combat:
            rot_str = self.config.get("skill_rotation", "7650,7652,7654,7656")
            try:
                rotation = [int(x.strip()) for x in rot_str.split(",") if x.strip()]
            except ValueError:
                rotation = [7650, 7652, 7654, 7656]
            # Filter to enabled skills
            rotation = [sid for sid in rotation if self.config.get(f"skill_{sid}_enabled", True)]
            if not rotation:
                rotation = [7650]
            # Berserk logic
            berserk_min_hp = self.config.get("berserk_hp_min", 70)
            if hp_pct >= berserk_min_hp and self.config.get("skill_7660_enabled", False):
                if time.time() - self._berserk_at > 60:
                    self.injector.send_skill(SKILL_IDS["berserk"])
                    self._berserk_at = time.time()
                    self.log("⚡ برسيرك!", "ai")
                    return
            sid = rotation[self._rotation_idx % len(rotation)]
            self.injector.send_skill(sid)
            self.log(f"🗡️ احتياطي: {SKILL_NAMES_AR.get(sid, sid)}", "info")
            self._rotation_idx += 1
            self.total_commands += 1

    def _handle_quests(self):
        if self.state.quest_list:
            self.log(f"📜 مهام متاحة: {len(self.state.quest_list)}", "info")

    def _check_spot(self):
        empty_limit = self.config.get("spot_empty_minutes", 2) * 60
        if self.state.spot_empty_seconds > empty_limit:
            angle = random.uniform(0, 2 * math.pi)
            d = random.uniform(40, 100)
            nx = self.state.x + math.cos(angle) * d
            ny = self.state.y + math.sin(angle) * d
            self.log(f"📍 منطقة فارغة → انتقال {nx:.0f},{ny:.0f}", "warning")
            self.injector.send_movement(nx, ny)
            self.state.spot_empty_seconds = 0
            self.last_action = f"انتقل {nx:.0f},{ny:.0f}"
        if self.state.ks_detected and self.config.get("ks_auto_escape", True):
            angle = random.uniform(0, 2 * math.pi)
            d = random.uniform(50, 80)
            nx = self.state.x + math.cos(angle) * d
            ny = self.state.y + math.sin(angle) * d
            self.log(f"⚔️ KS → هروب {nx:.0f},{ny:.0f}", "warning")
            self.injector.send_movement(nx, ny)
            self.state.ks_detected = False

    # ─── تنفيذ أوامر الشات ────────────────────────────────────────────────
    def handle_chat_action(self, chat_result: dict) -> str:
        bot_action = chat_result.get("bot_action", "idle")
        if bot_action == "stop":
            self.pause()
            return "تم إيقاف البوت مؤقتاً"
        elif bot_action == "start":
            self.resume()
            return "تم استئناف البوت"
        elif bot_action == "defend":
            self.state.weapon = "one_hand_shield"
            self.injector.send_skill(SKILL_IDS["iron_skin"])
            return "تم تفعيل وضع الدفاع"
        elif bot_action == "move":
            gc = chat_result.get("game_command", {})
            x  = gc.get("targetX", self.state.x + 50)
            y  = gc.get("targetY", self.state.y + 50)
            self.injector.send_movement(x, y)
            return f"جارٍ الانتقال إلى {x:.0f}, {y:.0f}"
        elif bot_action == "attack":
            if self.state.in_combat:
                self.injector.send_skill(SKILL_IDS["daredevil"])
                return "تم تفعيل الهجوم"
            return "لا يوجد هدف للهجوم"
        elif bot_action == "info":
            s = self.state
            return (
                f"الشخصية: {s.char_name} | HP: {s.hp_percent()}% | "
                f"MP: {s.mp_percent()}% | وحوش: {s.nearby_monsters} | "
                f"سلاح: {s.weapon} | قتل: {s.kills_this_session}"
            )
        elif bot_action == "report":
            stats = self.memory.get_stats()
            session = self.memory.get_session_summary()
            return (
                f"📊 تقرير الجلسة:\n"
                f"• وحوش منتهية: {session.get('kills', 0)}\n"
                f"• XP مكتسب: {session.get('xp', 0):,}\n"
                f"• Gold مكتسب: {session.get('gold', 0):,}\n"
                f"• بوشن مستخدمة: {self.potion_count}\n"
                f"• انقطاعات: {self.dc_count}\n"
                f"• قرارات AI: {stats['total_decisions']}\n"
                f"• معدل النجاح: {stats['success_rate']}"
            )
        return chat_result.get("reply", "تم")

    def get_status(self) -> dict:
        return {
            "char_name":       self.state.char_name,
            "hp":              self.state.hp, "max_hp": self.state.max_hp,
            "mp":              self.state.mp, "max_mp": self.state.max_mp,
            "level":           self.state.level,
            "x":               self.state.x, "y": self.state.y,
            "target":          self.state.target,
            "nearby_monsters": self.state.nearby_monsters,
            "in_combat":       self.state.in_combat,
            "weapon":          self.state.weapon,
            "last_action":     self.last_action,
            "total_commands":  self.total_commands,
            "dc_count":        self.dc_count,
            "session_kills":   self.state.kills_this_session,
            "session_xp":      self.memory.session_xp,
            "session_gold":    self.state.gold,
            "potion_count":    self.potion_count,
        }
