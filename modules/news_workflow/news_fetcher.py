"""
News Fetcher — Adapted from News_extractor/trends_fetcher.py
Fetches trending news from India and curates top 5 comedy-worthy headlines.
Uses OPENAI_API_KEY env var (no file-based key dependency).
NOW WITH HISTORY: Tracks last 7 days to ensure daily variety.
"""

import os
import time
import json
from pathlib import Path
from datetime import datetime, timedelta
from gnews import GNews
from openai import OpenAI


# ─── History Management ──────────────────────────────────────────────────────

HISTORY_FILE = Path(__file__).parent / "news_history.json"

class HistoryManager:
    def __init__(self, retention_days=7):
        self.retention_days = retention_days
        self.history = self._load()

    def _load(self):
        if not HISTORY_FILE.exists():
            return {}
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save(self):
        with open(HISTORY_FILE, "w") as f:
            json.dump(self.history, f, indent=2)

    def add_headlines(self, headlines):
        today = datetime.now().strftime("%Y-%m-%d")
        if today not in self.history:
            self.history[today] = []
        self.history[today].extend(headlines)
        self._cleanup()
        self._save()

    def get_recent_headlines(self):
        """Returns a list of all headlines from the last N days."""
        cutoff_date = (datetime.now() - timedelta(days=self.retention_days)).strftime("%Y-%m-%d")
        recent = []
        for date_str, items in self.history.items():
            if date_str >= cutoff_date:
                recent.extend(items)
        return recent

    def _cleanup(self):
        cutoff_date = (datetime.now() - timedelta(days=self.retention_days)).strftime("%Y-%m-%d")
        self.history = {k: v for k, v in self.history.items() if k >= cutoff_date}


# ─── OpenAI Client ──────────────────────────────────────────────────────────

def _get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment.")
    return OpenAI(api_key=api_key)


# ─── Fetchers ───────────────────────────────────────────────────────────────

def fetch_pain_news():
    """Fetches news about daily frustrations from India."""
    google_news = GNews(language='en', country='IN', period='24h', max_results=10)

    keywords = [
        "Bangalore Traffic",
        "Mumbai Local Train",
        "Delhi Pollution",
        "Heatwave India",
        "Rent increase",
        "Salary hike",
        "Indian Wedding",
        "Startup Layoffs",
        "Food Delivery",
        "IPL",
    ]

    raw_articles = []
    print(f"   Searching {len(keywords)} keywords...")
    for key in keywords:
        try:
            # GNews sometimes returns empty for niche queries, so we try/except
            news = google_news.get_news(key)
            if news:
                for article in news:
                    raw_articles.append(f"{key}: {article['title']}")
        except Exception as e:
            print(f"⚠️ Error fetching '{key}': {e}")

    return list(set(raw_articles))


def fetch_viral_trends():
    """Fetches Google Trends for India (optional, fails gracefully)."""
    try:
        from pytrends.request import TrendReq
        # pytrends can be flaky, so we use a generous timeout/retry logic internally if needed
        # but here we just wrap in try/except for safety
        pytrends = TrendReq(hl='en-US', tz=330)
        trending = pytrends.trending_searches(pn='india')
        return trending[0].tolist()[:10]
    except Exception as e:
        print(f"⚠️ Could not fetch trends: {e}")
        return []


def llm_curator(raw_data_list, history_list=None):
    """
    Uses OpenAI GPT-4o-mini to filter and find the top 5 distinct comedy topics.
    Args:
        raw_data_list: List of raw news strings
        history_list: List of headlines from the last 7 days to avoid repeating
    """
    client = _get_openai_client()
    history_str = json.dumps(history_list[-20:]) if history_list else "[]"  # Show last 20

    prompt = f"""
    You are the Head Writer for a Daily Comedy Show in India.
    
    INPUT DATA:
    1. Raw News/Trends: {json.dumps(raw_data_list[:60])}
    2. RECENTLY USED TOPICS (AVOID THESE): {history_str}

    TASK:
    1. Filter out tragedy (death/accidents) and boring politics.
    2. Select exactly 5 distinct topics with high "Comedic Potential" (Irony, Frustration, Absurdity).
    3. **CRITICAL**: Summarize the REAL news story in one simple sentence.
       GOOD: "Zomato raises delivery fee in Bangalore to ₹50"
       GOOD: "IPL team pays 24 crore for a player who scored 12 runs last season"
       BAD: "Bangalore CEO Stuck at Silk Board for 3 Days" (this is made up)
       BAD: "Zomato Agent Delivers Pizza on Horseback" (this is made up)
       Do NOT invent or exaggerate — the joke generator will handle the comedy.
    4. LANGUAGE: Use simple, everyday English. Write like you're telling a friend what happened.
       No fancy words, no dramatic phrasing.
    5. Ensure variety from the 'Recent Topics' list.

    OUTPUT JSON:
    {{
      "topics": [
        "Simple real news summary 1",
        "Simple real news summary 2",
        "Simple real news summary 3",
        "Simple real news summary 4",
        "Simple real news summary 5"
      ]
    }}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a comedy writer. Output valid JSON with 'topics' array containing exactly 5 specific headline strings."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.8
        )

        result = json.loads(response.choices[0].message.content)

        if isinstance(result, list):
            return result[:5]
        elif isinstance(result, dict):
            topics = result.get('topics', [])
            if topics:
                return topics[:5]

        print(f"⚠️ Unexpected response format: {result}")
        return []
    except Exception as e:
        print(f"❌ LLM Curation failed: {e}")
        return []


def fetch_top_headlines():
    """
    Master function: Fetch news + trends → LLM curate (with history check) → return 5 headlines.
    """
    print("=" * 60)
    print("📰 NEWS FETCHER — Top 5 Comedy Headlines (with 7-day History)")
    print("=" * 60)

    # Load history
    history_mgr = HistoryManager()
    recent = history_mgr.get_recent_headlines()
    print(f"\n📚 Found {len(recent)} recent headlines (will avoid repeating them).")

    print("\n🎣 Fetching news articles...")
    pain_news = fetch_pain_news()
    print(f"   Found {len(pain_news)} articles")

    print("\n🎣 Fetching viral trends...")
    viral_trends = fetch_viral_trends()
    print(f"   Found {len(viral_trends)} trends")

    combined_feed = pain_news + viral_trends

    # Fallback if news fetch fails completely
    if not combined_feed:
        print("❌ No news found. Using fallback topics.")
        fallback = [
            "Bangalore Techie Marries Laptop",
            "Delhi Fog Hires PR Agency",
            "Mumbai Local Train stops for Tea",
            "Startups Now Paying Salaries in Equity Only",
            "IPL Team Buys Player for 50 Crores to Sit on Bench"
        ]
        return fallback

    print(f"\n📦 {len(combined_feed)} raw items → Sending to LLM curator...")
    
    # Pass history to curator
    headlines = llm_curator(combined_feed, history_list=recent)

    if not headlines:
        print("⚠️ LLM returned no headlines. Using raw feed fallback.")
        headlines = combined_feed[:5]

    print(f"\n✨ TOP 5 HEADLINES:")
    for i, h in enumerate(headlines, 1):
        print(f"   {i}. {h}")

    # Save to history
    history_mgr.add_headlines(headlines)
    print(f"\n💾 Saved to history (retention: 7 days)")

    return headlines


if __name__ == "__main__":
    from dotenv import load_dotenv
    from pathlib import Path
    load_dotenv(Path(__file__).parent.parent.parent / ".env")
    headlines = fetch_top_headlines()
    print(f"\nResult: {headlines}")

