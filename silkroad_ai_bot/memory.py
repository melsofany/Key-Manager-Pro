"""
memory.py - نظام الذاكرة والتعلم من الأخطاء
يحفظ القرارات ونتائجها ويُراكم الخبرة لتحسين الأداء مستقبلاً
"""

import json
import os
import time
import threading
from datetime import datetime
from collections import defaultdict

MEMORY_FILE = "bot_memory.json"
MAX_MEMORIES = 500


class BotMemory:
    def __init__(self):
        self.memories       = []
        self.skill_stats    = defaultdict(lambda: {"used": 0, "success": 0, "fail": 0})
        self.error_patterns = defaultdict(int)
        self.session_lessons = []
        # Session stats
        self.session_start  = time.time()
        self.session_kills  = 0
        self.session_xp     = 0
        self.session_gold   = 0
        self.session_deaths = 0
        self.load()
        self._start_autosave()

    # ─── Persistence ──────────────────────────────────────────────────────
    def load(self):
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                self.memories = data.get("memories", [])
                self.skill_stats = defaultdict(
                    lambda: {"used": 0, "success": 0, "fail": 0},
                    data.get("skill_stats", {})
                )
                self.error_patterns = defaultdict(int, data.get("error_patterns", {}))
                self.session_lessons = data.get("session_lessons", [])
            except Exception:
                pass

    def save(self):
        data = {
            "memories":       self.memories[-MAX_MEMORIES:],
            "skill_stats":    dict(self.skill_stats),
            "error_patterns": dict(self.error_patterns),
            "session_lessons": self.session_lessons[-100:],
            "last_updated":   datetime.now().isoformat(),
        }
        try:
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _start_autosave(self):
        """حفظ تلقائي كل 60 ثانية في خلفية"""
        def _loop():
            while True:
                time.sleep(60)
                self.save()
        t = threading.Thread(target=_loop, daemon=True)
        t.start()

    # ─── Recording ────────────────────────────────────────────────────────
    def record_decision(self, state: dict, command: dict, result: str):
        """تسجيل قرار وما نتج عنه"""
        hp_before = state.get("hp_percent", 100)
        memory = {
            "timestamp": datetime.now().isoformat(),
            "hp_before": hp_before,
            "monsters":  state.get("nearby_monsters", 0),
            "action":    command.get("action"),
            "skill_id":  command.get("skillId", 0),
            "result":    result,
            "was_smart": result == "success",
        }
        self.memories.append(memory)
        skill_id = str(command.get("skillId", 0))
        if skill_id != "0":
            self.skill_stats[skill_id]["used"] += 1
            if result == "success":
                self.skill_stats[skill_id]["success"] += 1
            else:
                self.skill_stats[skill_id]["fail"] += 1
        if len(self.memories) % 50 == 0:
            self.save()

    def record_error(self, error_type: str, context: str = ""):
        """تسجيل خطأ وسياقه"""
        key = f"{error_type}:{context[:50]}"
        self.error_patterns[key] += 1
        lesson = {
            "time":    datetime.now().isoformat(),
            "error":   error_type,
            "context": context,
            "count":   self.error_patterns[key],
        }
        self.session_lessons.append(lesson)

    def record_death(self, state: dict):
        """تسجيل الموت لتجنب نفس الأخطاء"""
        self.session_deaths += 1
        lesson = (
            f"مات عند HP={state.get('hp_percent', 0)}% "
            f"و{state.get('nearby_monsters', 0)} وحوش. "
            f"السلاح: {state.get('weapon', '؟')}"
        )
        self.session_lessons.append({
            "time":   datetime.now().isoformat(),
            "type":   "death",
            "lesson": lesson,
            "state":  state,
        })
        self.save()

    def record_kill(self, count: int = 1, xp: int = 0, gold: int = 0):
        """تسجيل عدد القتلى في الجلسة"""
        self.session_kills += count
        self.session_xp    += xp
        self.session_gold  += gold

    # ─── Analytics ────────────────────────────────────────────────────────
    def get_skill_success_rate(self, skill_id: int) -> float:
        stats = self.skill_stats.get(str(skill_id), {"used": 1, "success": 0})
        used  = max(stats["used"], 1)
        return (stats["success"] / used) * 100

    def get_lessons_summary(self) -> str:
        """ملخص الدروس المستفادة لإرسالها لـ DeepSeek"""
        if not self.session_lessons:
            return "لا توجد دروس مسجّلة بعد."
        recent = self.session_lessons[-10:]
        lines  = ["=== دروس مستفادة من الجلسات السابقة ==="]
        for lesson in recent:
            if lesson.get("type") == "death":
                lines.append(f"• وفاة: {lesson.get('lesson', '')}")
            else:
                err = lesson.get("error", "")
                ctx = lesson.get("context", "")
                cnt = lesson.get("count", 1)
                lines.append(f"• خطأ متكرر ({cnt}x): {err} - {ctx}")
        skill_lines = []
        for sid, stats in self.skill_stats.items():
            if stats["used"] > 5:
                rate = (stats["success"] / max(stats["used"], 1)) * 100
                if rate < 50:
                    skill_lines.append(f"  - مهارة {sid}: نجاح {rate:.0f}% من {stats['used']} استخدام")
        if skill_lines:
            lines.append("=== مهارات بأداء ضعيف ===")
            lines.extend(skill_lines)
        return "\n".join(lines)

    def get_best_rotation(self) -> list:
        """استخراج أفضل تسلسل مهارات بناءً على التجربة"""
        default = [7650, 7652, 7654, 7656]
        if not self.skill_stats:
            return default
        ranked = sorted(
            [(int(sid), (s["success"] / max(s["used"], 1)))
             for sid, s in self.skill_stats.items() if s["used"] > 3],
            key=lambda x: x[1], reverse=True
        )
        if len(ranked) >= 3:
            return [sid for sid, _ in ranked[:4]]
        return default

    def get_session_summary(self) -> dict:
        """ملخص الجلسة الحالية"""
        elapsed = int(time.time() - self.session_start)
        return {
            "kills":   self.session_kills,
            "xp":      self.session_xp,
            "gold":    self.session_gold,
            "deaths":  self.session_deaths,
            "elapsed_sec": elapsed,
            "kills_per_hour": int(self.session_kills / max(elapsed / 3600, 0.01)),
        }

    def get_stats(self) -> dict:
        total    = len(self.memories)
        deaths   = sum(1 for m in self.memories if m.get("result") == "death")
        successes= sum(1 for m in self.memories if m.get("was_smart"))
        return {
            "total_decisions":  total,
            "deaths_recorded":  deaths + self.session_deaths,
            "success_rate":     f"{(successes / max(total, 1) * 100):.1f}%",
            "lessons_learned":  len(self.session_lessons),
            "error_patterns":   len(self.error_patterns),
        }

    def export_session_report(self) -> str:
        """تصدير تقرير الجلسة كنص"""
        s = self.get_session_summary()
        stats = self.get_stats()
        elapsed = s["elapsed_sec"]
        h, m = elapsed // 3600, (elapsed % 3600) // 60
        return (
            f"=== تقرير جلسة {datetime.now().strftime('%Y-%m-%d %H:%M')} ===\n"
            f"مدة الجلسة:     {h:02d}:{m:02d}\n"
            f"وحوش منتهية:   {s['kills']}\n"
            f"قتل/ساعة:      {s['kills_per_hour']}\n"
            f"XP مكتسب:      {s['xp']:,}\n"
            f"Gold مكتسب:    {s['gold']:,}\n"
            f"وفيات:         {s['deaths']}\n"
            f"قرارات AI:     {stats['total_decisions']}\n"
            f"معدل نجاح AI:  {stats['success_rate']}\n"
            f"دروس مستفادة:  {stats['lessons_learned']}\n"
        )
