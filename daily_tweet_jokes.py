"""
Daily Tweet Jokes — Standalone GitHub Actions entry point.
Runs ONLY the Twitter trending jokes pipeline independently.

Usage:
    python daily_tweet_jokes.py
"""

import os
import sys
from pathlib import Path

# ─── Bootstrap ───────────────────────────────────────────────────────────────
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

    print(f"🐦 Daily Tweet Jokes Pipeline (Standalone)")
    print(f"   Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

    # Quick env check
    twitterapi_key = os.getenv("TWITTERAPI_IO_KEY", "")
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = os.getenv("SUPABASE_KEY", "")

    print(f"   TWITTERAPI_IO_KEY: {'✅' if twitterapi_key else '❌ MISSING'}")
    print(f"   GEMINI_API_KEY: {'✅' if gemini_key else '❌ MISSING'}")
    print(f"   SUPABASE_URL: {'✅' if supabase_url.startswith('https://') else '❌ MISSING'}")
    print(f"   SUPABASE_KEY: {'✅' if len(supabase_key) > 20 else '❌ MISSING'}")
    print()

    if not twitterapi_key:
        print("❌ TWITTERAPI_IO_KEY is required. Aborting.")
        sys.exit(1)
    if not gemini_key:
        print("❌ GEMINI_API_KEY is required. Aborting.")
        sys.exit(1)

    # Run the Twitter pipeline
    from modules.news_workflow.twitter_trends_fetcher import run_twitter_pipeline
    topics, jokes_by_topic = run_twitter_pipeline()

    total = sum(len(v.get("jokes", [])) for v in jokes_by_topic.values())
    print(f"\n📊 Final stats: {total} tweet jokes from {len(topics)} topics")

    # Send notifications (tweet jokes only, no news jokes)
    if total > 0:
        print("\n📨 Sending notifications...")
        try:
            from modules.news_workflow.notifier import notify_jokes
            notify_jokes(
                headlines=[],
                jokes_by_headline={},
                tweet_jokes=jokes_by_topic,
            )
        except Exception as e:
            print(f"   ⚠️ Notification failed: {e}")
    else:
        print("\n📭 No tweet jokes generated — skipping notifications.")

    print(f"\n✅ Pipeline complete!")
