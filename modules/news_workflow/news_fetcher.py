"""
News Fetcher — Fetches trending news from India and curates top 5 headlines.
Uses GNews top stories + broad category searches for diverse, real-time coverage.
LLM curator picks stories with comedy potential and outputs FACTUAL, simple summaries.
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

def fetch_top_stories():
    """
    Fetches TODAY's actual news from India using two tiers:
    1. Top Stories — whatever is actually trending right now
    2. Category searches — broad topics for diversity (entertainment, sports, business, tech)
    """
    raw_articles = []

    # ── Tier 1: Top News from India (what's actually trending today) ──
    print("   📡 Fetching top stories from India...")
    try:
        google_news_top = GNews(language='en', country='IN', period='24h', max_results=30)
        top_news = google_news_top.get_top_news()
        if top_news:
            for article in top_news:
                raw_articles.append(f"TOP: {article['title']}")
            print(f"   Found {len(top_news)} top stories")
        else:
            print("   ⚠️ No top stories returned")
    except Exception as e:
        print(f"   ⚠️ Top stories fetch failed: {e}")

    # ── Tier 2: Broad category searches for diversity ──
    category_keywords = [
        "India trending today",
        "Bollywood news",
        "IPL cricket",
        "India startup",
        "India viral",
    ]

    print(f"   🔍 Searching {len(category_keywords)} broad categories...")
    google_news_search = GNews(language='en', country='IN', period='24h', max_results=10)
    for key in category_keywords:
        try:
            news = google_news_search.get_news(key)
            if news:
                for article in news:
                    raw_articles.append(f"{key}: {article['title']}")
        except Exception as e:
            print(f"   ⚠️ Error fetching '{key}': {e}")

    # Deduplicate
    raw_articles = list(set(raw_articles))
    print(f"   📦 Total: {len(raw_articles)} unique articles")
    return raw_articles


def fetch_viral_trends():
    """Fetches Google Trends for India (optional, fails gracefully)."""
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl='en-US', tz=330)
        trending = pytrends.trending_searches(pn='india')
        return trending[0].tolist()[:10]
    except Exception as e:
        print(f"   ⚠️ Could not fetch trends: {e}")
        return []


def llm_curator(raw_data_list, history_list=None):
    """
    Uses OpenAI GPT-4o-mini to pick 5 stories with comedy potential.
    Outputs FACTUAL, simple-language summaries — NOT jokes.
    """
    client = _get_openai_client()
    history_str = json.dumps(history_list[-20:]) if history_list else "[]"

    prompt = f"""
    INPUT DATA:
    1. Today's News Headlines: {json.dumps(raw_data_list[:80])}
    2. RECENTLY USED TOPICS (AVOID THESE): {history_str}

    TASK:
    Pick exactly 5 news stories that have comedy potential (irony, frustration, absurdity, relatable situations).
    
    RULES:
    1. Filter out tragedy (death, accidents, natural disasters) and boring politics.
    2. Pick from DIFFERENT categories — don't pick 3 cricket stories.
    3. Output a FACTUAL one-sentence summary of what actually happened. You are a news editor, NOT a comedian.
    
    WHAT A GOOD HEADLINE LOOKS LIKE:
    ✅ "Zomato increased delivery fee to ₹50 in Bangalore"
    ✅ "An IPL team bought a player for 24 crore who scored only 12 runs last season"
    ✅ "Government wants companies to have a 4-day work week"
    ✅ "A man in Delhi got fined ₹500 for honking unnecessarily"
    
    WHAT A BAD HEADLINE LOOKS LIKE — DO NOT DO THIS:
    ❌ "Bangalore traffic is so bad that even GPS gave up" (this is a joke, not news)
    ❌ "Zomato Agent Delivers Pizza on Horseback" (this is made up)
    ❌ "The fiscal deficit has widened amid macroeconomic headwinds" (too complex)
    ❌ "Amidst allegations of impropriety, the incumbent administration..." (too formal)
    
    4. LANGUAGE: Write like you're telling a friend what happened.
       Use simple, everyday English that a 15-year-old would understand.
       NO journalist words like "amidst", "allegedly", "fiscal", "unprecedented", "incumbent".
       SIMPLIFY complex terms: "GDP growth slows" → "India's economy is growing slower than expected"
    
    5. Avoid topics from the 'Recently Used' list.

    OUTPUT (valid JSON):
    {{
      "topics": [
        "Simple factual news summary 1",
        "Simple factual news summary 2",
        "Simple factual news summary 3",
        "Simple factual news summary 4",
        "Simple factual news summary 5"
      ]
    }}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a news editor. Your job is to pick interesting stories and summarize them in plain, simple, factual language. You are NOT a comedian — do not add jokes, exaggeration, or dramatic flair. Output valid JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3
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
    Master function: Fetch top stories + trends → LLM curate (with history check) → return 5 headlines.
    """
    print("=" * 60)
    print("📰 NEWS FETCHER — Top 5 Headlines (with 7-day History)")
    print("=" * 60)

    # Load history
    history_mgr = HistoryManager()
    recent = history_mgr.get_recent_headlines()
    print(f"\n📚 Found {len(recent)} recent headlines (will avoid repeating them).")

    print("\n🎣 Fetching today's news...")
    top_stories = fetch_top_stories()

    print("\n🎣 Fetching viral trends...")
    viral_trends = fetch_viral_trends()

    combined_feed = top_stories + viral_trends

    # Fallback if news fetch fails completely
    if not combined_feed:
        print("❌ No news found. Using fallback topics.")
        fallback = [
            "India vs Australia cricket match results",
            "Petrol and diesel prices updated today",
            "New Bollywood movie released this Friday",
            "Swiggy and Zomato increase platform fees",
            "Stock market hits new high this week"
        ]
        return fallback

    print(f"\n📦 {len(combined_feed)} items → Sending to LLM curator...")
    
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
