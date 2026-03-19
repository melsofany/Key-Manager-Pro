"""
phbot_plugin.py - إضافة phBot الرسمية
انسخ هذا الملف إلى مجلد plugins في phBot
"""

import requests
import json
import time

# عنوان الخادم المحلي (يجب تشغيل main_gui.py أولاً)
SERVER_URL = "http://127.0.0.1:9090"
SEND_INTERVAL = 1.0
_last_send = 0


def get_plugin_info():
    return {
        "name": "Silkroad AI Bot",
        "version": "1.0",
        "author": "AI Controller",
        "description": "نظام تحكم ذكي بـ DeepSeek AI",
    }


def on_start():
    """يُستدعى عند بدء البوت"""
    log("[AI Plugin] تم تفعيل إضافة الذكاء الاصطناعي")
    _send_telemetry({"event": "start"})


def on_stop():
    """يُستدعى عند إيقاف البوت"""
    log("[AI Plugin] تم إيقاف الإضافة")


def on_tick():
    """يُستدعى كل ثانية - نقل البيانات للذكاء الاصطناعي"""
    global _last_send
    now = time.time()
    if now - _last_send < SEND_INTERVAL:
        return
    _last_send = now
    try:
        telemetry = _gather_telemetry()
        command = _send_telemetry(telemetry)
        if command:
            _execute_command(command)
    except Exception as e:
        log(f"[AI Plugin] خطأ: {e}")


def on_killed():
    """يُستدعى عند موت الشخصية"""
    log("[AI Plugin] الشخصية ماتت - إرسال إشارة للذكاء الاصطناعي")
    _send_telemetry({"event": "death"})


def on_dc():
    """يُستدعى عند انقطاع الاتصال"""
    log("[AI Plugin] انقطاع الاتصال - الذكاء الاصطناعي سيعيد الاتصال")
    _send_telemetry({"event": "disconnect"})


def _gather_telemetry():
    """جمع البيانات من phBot API"""
    try:
        char = get_character_data()
        monsters = get_monsters()
        target = get_target()
        pos = get_position()
        return {
            "char_name": char.get("name", ""),
            "hp": char.get("hp", 100),
            "max_hp": char.get("max_hp", 100),
            "mp": char.get("mp", 100),
            "max_mp": char.get("max_mp", 100),
            "level": char.get("level", 116),
            "x": pos.get("x", 0),
            "y": pos.get("y", 0),
            "target": target.get("name", ""),
            "target_hp": target.get("hp", 0),
            "nearby_monsters": len(monsters),
            "is_in_combat": target.get("name", "") != "",
            "active_buffs": char.get("buffs", []),
            "current_weapon": char.get("weapon", "two_hand_sword"),
            "is_dead": char.get("is_dead", False),
            "is_disconnected": False,
            "quest_list": get_quests(),
            "spot_empty_seconds": 0,
            "ks_detected": False,
        }
    except Exception:
        return {}


def _send_telemetry(data):
    """إرسال البيانات للخادم المحلي واستقبال الأوامر"""
    try:
        resp = requests.post(f"{SERVER_URL}/api/telemetry", json=data, timeout=3)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


def _execute_command(command):
    """تنفيذ أوامر الذكاء الاصطناعي في phBot"""
    action = command.get("action", "idle")
    if action == "cast_skill":
        skill_id = command.get("skillId", 0)
        use_skill(skill_id)
        log(f"[AI] استخدام مهارة {skill_id}")
    elif action == "switch_weapon":
        slot = command.get("weaponSlot", 0)
        switch_weapon(slot)
        log(f"[AI] تغيير السلاح: slot {slot}")
    elif action == "move_to":
        x, y = command.get("targetX", 0), command.get("targetY", 0)
        move_to(x, y)
        log(f"[AI] الانتقال إلى {x}, {y}")
    elif action == "defend":
        switch_weapon(1)
        use_skill(7910)
        log("[AI] وضع الدفاع")
