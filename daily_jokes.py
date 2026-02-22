"""
Daily Jokes — GitHub Actions entry point.
Runs the full news-to-jokes pipeline and sends notifications.
Does NOT depend on Streamlit.

Usage:
    python daily_jokes.py
"""

import os
import sys
from pathlib import Path

# ─── Bootstrap ───────────────────────────────────────────────────────────────
# Ensure project root is on sys.path
PROJECT_ROOT = str(Path(__file__).parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# For local dev, load .env
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass  # dotenv not required on GitHub Actions


# ─── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from datetime import datetime, timezone

    print(f"🚀 Daily Jokes Pipeline")
    print(f"   Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

    # Quick env check
    import os
    supa_url = os.getenv("SUPABASE_URL", "")
    supa_key = os.getenv("SUPABASE_KEY", "")
    print(f"   SUPABASE_URL: {'✅' if supa_url.startswith('https://') else '❌ MISSING/INVALID'} (len={len(supa_url)})")
    print(f"   SUPABASE_KEY: {'✅' if len(supa_key) > 20 else '❌ MISSING/SHORT'} (len={len(supa_key)})")
    print(f"   OPENAI_API_KEY: {'✅' if os.getenv('OPENAI_API_KEY') else '❌ MISSING'}")
    print()

    from modules.news_workflow.morning_jokes_generator import run_daily_pipeline
    headlines, jokes, tweet_jokes = run_daily_pipeline()

    total = sum(len(j) for j in jokes.values())
    print(f"\n📊 Final stats: {total} jokes from {len(headlines)} headlines")
