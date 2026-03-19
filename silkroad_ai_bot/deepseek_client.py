"""
deepseek_client.py - عميل DeepSeek AI
يتولى الاتصال بـ DeepSeek API وإصدار الأوامر الذكية
"""

import json
import requests
import time


SYSTEM_PROMPT = open("system_prompt.txt", encoding="utf-8").read() if __import__("os").path.exists("system_prompt.txt") else ""

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"


class DeepSeekClient:
    def __init__(self, api_key, model="deepseek-chat"):
        self.api_key = api_key
        self.model = model
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self.last_request_time = 0
        self.min_request_interval = 2.0

    def _rate_limit(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()

    def _call_api(self, messages, temperature=0.3, max_tokens=300):
        self._rate_limit()
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        try:
            resp = requests.post(
                DEEPSEEK_API_URL,
                headers=self.headers,
                json=payload,
                timeout=15
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
        except requests.exceptions.HTTPError as e:
            raise Exception(f"خطأ HTTP من DeepSeek: {e.response.status_code}")
        except requests.exceptions.Timeout:
            raise Exception("انتهى وقت الاتصال بـ DeepSeek")
        except json.JSONDecodeError:
            raise Exception("استجابة غير صالحة من DeepSeek")
        except Exception as e:
            raise Exception(f"خطأ في DeepSeek: {e}")

    def get_combat_command(self, game_state: dict) -> dict:
        prompt = self._build_combat_prompt(game_state)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT or self._default_system_prompt()},
            {"role": "user", "content": prompt},
        ]
        result = self._call_api(messages)
        return self._validate_command(result)

    def _build_combat_prompt(self, state: dict) -> str:
        hp_pct = state.get("hp_percent", 100)
        return f"""
حالة الشخصية الحالية:
- HP: {state.get('hp', 0)}/{state.get('max_hp', 100)} ({hp_pct}%)
- MP: {state.get('mp', 0)}/{state.get('max_mp', 100)}
- المستوى: {state.get('level', 116)}
- الموقع: X={state.get('x', 0):.0f} Y={state.get('y', 0):.0f}
- الهدف: {state.get('target', 'لا يوجد')}
- HP الهدف: {state.get('target_hp', 0)}%
- عدد الوحوش القريبة: {state.get('nearby_monsters', 0)}
- في قتال: {'نعم' if state.get('in_combat') else 'لا'}
- السلاح الحالي: {state.get('weapon', 'two_hand_sword')}
- الـ Buffs النشطة: {', '.join(state.get('active_buffs', [])) or 'لا يوجد'}
- المنطقة فارغة منذ: {state.get('spot_empty_seconds', 0)} ثانية
- KS مكتشف: {'نعم' if state.get('ks_detected') else 'لا'}
- حد HP للدفاع: {state.get('hp_threshold', 45)}%
- حد عدد الوحوش: {state.get('monster_threshold', 5)}

قدّم الأمر المناسب الآن بصيغة JSON.
""".strip()

    def _default_system_prompt(self):
        return """أنت مسؤول تحكم ذكي بشخصية Warrior مستوى 116 في لعبة Silkroad Online.
يجب أن ترد دائماً بـ JSON فقط وفق هذا الشكل:
{
  "action": "cast_skill|switch_weapon|move_to|defend|login_inject|idle",
  "skillId": 7650,
  "weaponSlot": 0,
  "targetX": 0,
  "targetY": 0,
  "reason": "سبب القرار بالعربية",
  "priority": 1
}

قواعد القرار:
1. إذا HP < حد_HP أو عدد_الوحوش > حد_الوحوش: action=defend (تفعيل Iron Skin وتغيير السلاح)
2. في القتال العادي: دورة المهارات: daredevil(7650) → ground_impact(7652) → stab(7654) → turn_fresh(7656)
3. إذا target_hp < 30 واستخدم stab(7654) لمضاعفة الضرر
4. إذا ks_detected أو spot_empty: action=move_to مع إحداثيات جديدة
5. إذا is_disconnected: action=login_inject
6. إذا لا يوجد هدف: action=idle"""

    def _validate_command(self, data: dict) -> dict:
        valid_actions = {"cast_skill", "switch_weapon", "move_to", "defend", "login_inject", "idle", "use_potion"}
        action = data.get("action", "idle")
        if action not in valid_actions:
            action = "idle"
        return {
            "action": action,
            "skillId": int(data.get("skillId", 0)),
            "weaponSlot": int(data.get("weaponSlot", 0)),
            "targetX": float(data.get("targetX", 0)),
            "targetY": float(data.get("targetY", 0)),
            "reason": str(data.get("reason", "—")),
            "priority": int(data.get("priority", 1)),
        }

    def test_connection(self) -> bool:
        try:
            messages = [
                {"role": "user", "content": 'رد بـ JSON: {"status": "ok", "message": "يعمل"}'}
            ]
            result = self._call_api(messages, max_tokens=50)
            return result.get("status") == "ok"
        except Exception:
            return False
