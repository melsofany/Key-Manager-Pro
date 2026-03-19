"""
deepseek_client.py - عميل DeepSeek AI
يتولى: أوامر القتال، شات الأوامر، تحليل الأخبار، التعلم من الأخطاء
"""

import json
import requests
import time
import os

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"


def _load_system_prompt():
    path = os.path.join(os.path.dirname(__file__), "system_prompt.txt")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    return ""


SYSTEM_PROMPT = _load_system_prompt()


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
        self.chat_history = []
        self.max_history = 20

    def _rate_limit(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()

    def _call_api(self, messages, temperature=0.3, max_tokens=400, json_mode=True):
        self._rate_limit()
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        try:
            resp = requests.post(
                DEEPSEEK_API_URL,
                headers=self.headers,
                json=payload,
                timeout=20
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            if json_mode:
                return json.loads(content)
            return content
        except requests.exceptions.HTTPError as e:
            code = e.response.status_code if e.response else "?"
            raise Exception(f"خطأ HTTP {code} من DeepSeek")
        except requests.exceptions.Timeout:
            raise Exception("انتهى وقت الاتصال بـ DeepSeek")
        except json.JSONDecodeError as e:
            raise Exception(f"استجابة JSON غير صالحة: {e}")
        except Exception as e:
            raise Exception(f"خطأ DeepSeek: {e}")

    # ─── أوامر القتال ──────────────────────────────────────────────────────
    def get_combat_command(self, game_state: dict, lessons: str = "") -> dict:
        prompt = self._build_combat_prompt(game_state, lessons)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT or self._default_system_prompt()},
            {"role": "user", "content": prompt},
        ]
        result = self._call_api(messages)
        return self._validate_command(result)

    def _build_combat_prompt(self, state: dict, lessons: str = "") -> str:
        hp_pct = state.get("hp_percent", 100)
        lines = [
            "حالة الشخصية:",
            f"HP: {state.get('hp',0)}/{state.get('max_hp',100)} ({hp_pct}%)",
            f"MP: {state.get('mp',0)}/{state.get('max_mp',100)}",
            f"الوحوش القريبة: {state.get('nearby_monsters',0)}",
            f"الهدف: {state.get('target','لا يوجد')} (HP {state.get('target_hp',0)}%)",
            f"السلاح: {state.get('weapon','two_hand_sword')}",
            f"في قتال: {'نعم' if state.get('in_combat') else 'لا'}",
            f"Buffs: {', '.join(state.get('active_buffs',[]) or ['لا يوجد'])}",
            f"المنطقة فارغة منذ: {state.get('spot_empty_seconds',0)}ث",
            f"KS: {'نعم' if state.get('ks_detected') else 'لا'}",
            f"حد HP: {state.get('hp_threshold',45)}%",
            f"حد الوحوش: {state.get('monster_threshold',5)}",
        ]
        if lessons:
            lines.append(f"\n--- دروس مستفادة ---\n{lessons}")
        lines.append("\nأصدر الأمر المناسب الآن.")
        return "\n".join(lines)

    def _default_system_prompt(self):
        return (
            "أنت نظام تحكم ذكي بشخصية Warrior مستوى 116 في Silkroad Online. "
            "رد دائماً بـ JSON فقط:\n"
            '{"action":"cast_skill|switch_weapon|move_to|defend|login_inject|idle",'
            '"skillId":0,"weaponSlot":0,"targetX":0,"targetY":0,'
            '"reason":"السبب","priority":1}\n'
            "القواعد: دفاع إذا HP<45% أو وحوش>5. روتين: 7650→7652→7654→7656."
        )

    def _validate_command(self, data: dict) -> dict:
        valid = {"cast_skill","switch_weapon","move_to","defend","login_inject","idle","use_potion"}
        action = data.get("action", "idle")
        if action not in valid:
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

    # ─── شات الأوامر ──────────────────────────────────────────────────────
    def chat_command(self, user_message: str, bot_state: dict = None) -> dict:
        """
        يستقبل أمر نصي من المستخدم بالعربية ويحوله لإجراء قابل للتنفيذ.
        مثال: "وقف القتال", "انتقل لمنطقة أخرى", "فعّل الدفاع", "أخبرني عن حالتي"
        """
        system = (
            "أنت مساعد Bot للعبة Silkroad Online، تفهم الأوامر العربية وتحولها لإجراءات.\n"
            "رد بـ JSON دائماً:\n"
            "{\n"
            '  "bot_action": "start|stop|defend|attack|move|idle|info|quest|report",\n'
            '  "game_command": {"action":"...","skillId":0,"targetX":0,"targetY":0},\n'
            '  "reply": "رد بالعربية للمستخدم",\n'
            '  "requires_confirmation": false\n'
            "}\n"
            "أمثلة تحويل:\n"
            "- 'وقف' → bot_action=stop\n"
            "- 'اشتغل' أو 'شغّل' → bot_action=start\n"
            "- 'دافع عني' أو 'تحوّل للدرع' → bot_action=defend\n"
            "- 'انتقل لمنطقة أخرى' → bot_action=move\n"
            "- 'حالتي' أو 'أخبرني' → bot_action=info\n"
            "- 'اقبل المهام' → bot_action=quest\n"
            "- 'تقرير' أو 'إحصائيات' → bot_action=report\n"
        )
        state_context = ""
        if bot_state:
            state_context = (
                f"\n\nحالة البوت الحالية:\n"
                f"HP: {bot_state.get('hp',0)}/{bot_state.get('max_hp',100)}\n"
                f"الوحوش: {bot_state.get('nearby_monsters',0)}\n"
                f"في قتال: {'نعم' if bot_state.get('in_combat') else 'لا'}\n"
                f"أوامر نُفّذت: {bot_state.get('total_commands',0)}"
            )
        self.chat_history.append({"role": "user", "content": user_message + state_context})
        if len(self.chat_history) > self.max_history:
            self.chat_history = self.chat_history[-self.max_history:]
        messages = [{"role": "system", "content": system}] + self.chat_history
        try:
            result = self._call_api(messages, temperature=0.5, max_tokens=300)
            reply = result.get("reply", "تم تنفيذ الأمر")
            self.chat_history.append({"role": "assistant", "content": reply})
            return result
        except Exception as e:
            self.chat_history.append({"role": "assistant", "content": f"خطأ: {e}"})
            return {
                "bot_action": "idle",
                "reply": f"حدث خطأ: {e}",
                "requires_confirmation": False,
            }

    def free_chat(self, user_message: str) -> str:
        """محادثة حرة بدون تنفيذ أوامر - للأسئلة والاستفسارات"""
        system = (
            "أنت مساعد متخصص في لعبة Silkroad Online، تُجيب بالعربية."
            " تعرف كل شيء عن المهارات، الشخصيات، السيرفرات، والاستراتيجيات."
        )
        msgs = [{"role": "system", "content": system}]
        msgs += self.chat_history[-6:]
        msgs.append({"role": "user", "content": user_message})
        try:
            reply = self._call_api(msgs, temperature=0.7, max_tokens=500, json_mode=False)
            self.chat_history.append({"role": "user", "content": user_message})
            self.chat_history.append({"role": "assistant", "content": reply})
            return reply
        except Exception as e:
            return f"خطأ في الاتصال: {e}"

    def clear_history(self):
        self.chat_history = []

    # ─── اختبار الاتصال ───────────────────────────────────────────────────
    def test_connection(self) -> bool:
        try:
            msgs = [{"role": "user", "content": 'رد بـ JSON: {"status": "ok"}'}]
            result = self._call_api(msgs, max_tokens=50)
            return result.get("status") == "ok"
        except Exception:
            return False
