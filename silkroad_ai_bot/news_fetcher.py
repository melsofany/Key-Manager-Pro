"""
news_fetcher.py - متابعة أخبار Silkroad Online
يجلب آخر أخبار السيرفرات والتحديثات تلقائياً
"""

import requests
import json
import time
import threading
from datetime import datetime
from html.parser import HTMLParser


NEWS_SOURCES = [
    {
        "name": "SilkroadR Official",
        "url": "https://silkroadr.com/en/news",
        "type": "html",
    },
    {
        "name": "JOYMAX iSRO",
        "url": "https://www.silkroad.com/en/news",
        "type": "html",
    },
    {
        "name": "RateMyServer SRO",
        "url": "https://ratemyserver.net/index.php?page=detailedlistserver&sname=&servertype=2&country=0&pserver=1&region=0&game=11",
        "type": "html",
    },
]

DEEPSEEK_NEWS_PROMPT = """
أنت محلل أخبار لعبة Silkroad Online. لخّص الأخبار التالية بالعربية بشكل مختصر وأضف توصياتك للاعبين من مستوى 116:
"""


class SimpleHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.in_relevant = False

    def handle_data(self, data):
        cleaned = data.strip()
        if len(cleaned) > 20:
            self.text_parts.append(cleaned)

    def get_text(self, limit=50):
        return "\n".join(self.text_parts[:limit])


class NewsItem:
    def __init__(self, title, summary, source, timestamp=None, url=""):
        self.title = title
        self.summary = summary
        self.source = source
        self.timestamp = timestamp or datetime.now().isoformat()
        self.url = url
        self.ai_analysis = ""

    def to_dict(self):
        return {
            "title": self.title,
            "summary": self.summary,
            "source": self.source,
            "timestamp": self.timestamp,
            "url": self.url,
            "ai_analysis": self.ai_analysis,
        }


class NewsFetcher:
    def __init__(self, deepseek_client, logger, on_news_callback=None):
        self.ai = deepseek_client
        self.log = logger
        self.on_news = on_news_callback
        self.news_cache = []
        self.running = False
        self.fetch_interval = 1800
        self.last_fetch = 0
        self._load_cache()

    def _load_cache(self):
        try:
            with open("news_cache.json", encoding="utf-8") as f:
                raw = json.load(f)
                self.news_cache = [
                    NewsItem(
                        n["title"], n["summary"], n["source"],
                        n.get("timestamp"), n.get("url", "")
                    )
                    for n in raw
                ]
        except Exception:
            self.news_cache = []

    def _save_cache(self):
        try:
            with open("news_cache.json", "w", encoding="utf-8") as f:
                json.dump([n.to_dict() for n in self.news_cache[-50:]], f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def start(self):
        self.running = True
        self.log("📰 بدء متابعة أخبار Silkroad...", "info")
        threading.Thread(target=self._fetch_loop, daemon=True).start()

    def stop(self):
        self.running = False

    def _fetch_loop(self):
        while self.running:
            elapsed = time.time() - self.last_fetch
            if elapsed >= self.fetch_interval:
                self.fetch_all()
                self.last_fetch = time.time()
            time.sleep(60)

    def fetch_all(self):
        self.log("🔄 جلب آخر أخبار Silkroad...", "info")
        fetched = []
        for source in NEWS_SOURCES:
            items = self._fetch_source(source)
            fetched.extend(items)
        if fetched:
            self._analyze_with_ai(fetched)
            self.news_cache = fetched + self.news_cache
            self.news_cache = self.news_cache[:50]
            self._save_cache()
            self.log(f"✅ تم جلب {len(fetched)} خبر جديد", "success")
        else:
            self.log("ℹ️ لا توجد أخبار جديدة الآن", "info")
        return fetched

    def _fetch_source(self, source: dict) -> list:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            resp = requests.get(source["url"], headers=headers, timeout=10)
            if resp.status_code != 200:
                return []
            parser = SimpleHTMLParser()
            parser.feed(resp.text)
            text_blocks = parser.text_parts[:20]
            items = []
            for i, block in enumerate(text_blocks[:5]):
                if len(block) > 30:
                    items.append(NewsItem(
                        title=block[:100],
                        summary=block[:300],
                        source=source["name"],
                        url=source["url"],
                    ))
            return items
        except Exception as e:
            self.log(f"⚠️ فشل جلب {source['name']}: {e}", "warning")
            return []

    def _analyze_with_ai(self, items: list):
        if not items or not self.ai.api_key:
            return
        try:
            text = "\n".join([f"- {item.title}: {item.summary[:200]}" for item in items[:5]])
            prompt = f"{DEEPSEEK_NEWS_PROMPT}\n\n{text}"
            messages = [{"role": "user", "content": prompt}]
            payload = {
                "model": self.ai.model,
                "messages": messages,
                "temperature": 0.5,
                "max_tokens": 400,
            }
            resp = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers=self.ai.headers,
                json=payload,
                timeout=20
            )
            if resp.status_code == 200:
                analysis = resp.json()["choices"][0]["message"]["content"]
                if items:
                    items[0].ai_analysis = analysis
                    self.log(f"🤖 تحليل AI للأخبار:\n{analysis}", "ai")
                if self.on_news:
                    self.on_news(items, analysis)
        except Exception as e:
            self.log(f"⚠️ خطأ في تحليل الأخبار: {e}", "warning")

    def get_cached_news(self) -> list:
        return self.news_cache

    def force_fetch(self):
        threading.Thread(target=self.fetch_all, daemon=True).start()

    def get_game_tips(self) -> str:
        """جلب نصائح من AI بناءً على أخبار اللعبة"""
        if not self.news_cache:
            return "لا توجد أخبار محفوظة للتحليل."
        recent = self.news_cache[:3]
        titles = [n.title for n in recent]
        try:
            prompt = (
                f"بناءً على أخبار Silkroad الأخيرة:\n"
                + "\n".join(f"- {t}" for t in titles)
                + "\n\nما هي أفضل نصيحة للاعب Warrior مستوى 116؟ (3 نصائح مختصرة)"
            )
            messages = [{"role": "user", "content": prompt}]
            payload = {
                "model": self.ai.model,
                "messages": messages,
                "temperature": 0.6,
                "max_tokens": 200,
            }
            resp = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers=self.ai.headers,
                json=payload,
                timeout=15
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
        except Exception:
            pass
        return "تعذّر جلب النصائح الآن."
