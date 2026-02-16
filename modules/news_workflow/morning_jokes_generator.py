"""
Morning Jokes Generator — Orchestrates the full daily pipeline.

Pipeline:
1. Fetch top 5 trending headlines (via news_fetcher)
2. For each headline, search 20 bridge structures and generate 20 jokes
3. Total: ~100 jokes
4. Send via Telegram + Email (via notifier)

This module can be imported by daily_jokes.py (GitHub Actions entry point)
or run standalone.
"""

import sys
import time
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = str(Path(__file__).parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def run_daily_pipeline():
    """
    Run the complete daily joke generation pipeline.
    Returns (headlines, jokes_by_headline) tuple.
    """
    print()
    print("=" * 60)
    print("🎭 MORNING JOKES GENERATOR")
    print("   5 Headlines × 20 Jokes = 100 Jokes")
    print("=" * 60)
    print()

    # Step 1: Fetch headlines
    print("📰 STEP 1: Fetching trending headlines...")
    from modules.news_workflow.news_fetcher import fetch_top_headlines
    headlines = fetch_top_headlines()

    if not headlines:
        print("❌ No headlines fetched. Aborting.")
        return [], {}

    print(f"\n✅ Got {len(headlines)} headlines")

    # Step 2: Generate jokes for each headline
    print("\n🔥 STEP 2: Generating jokes for each headline...")
    from modules.joke_generator.campaign_generator import search_bridges, generate_from_selected

    jokes_by_headline = {}

    for idx, headline in enumerate(headlines):
        print()
        print(f"{'─' * 50}")
        print(f"📰 [{idx+1}/{len(headlines)}] {headline}")
        print(f"{'─' * 50}")

        # Search bridges
        try:
            matches = search_bridges(headline, top_k=20)
            print(f"   🔍 Found {len(matches)} bridge matches")
        except Exception as e:
            print(f"   ❌ Bridge search failed: {e}")
            jokes_by_headline[headline] = []
            continue

        # Generate jokes from all matches (up to 20)
        try:
            jokes = generate_from_selected(headline, matches[:20])
            jokes_by_headline[headline] = jokes
            print(f"   ✅ Generated {len(jokes)} jokes")
        except Exception as e:
            print(f"   ❌ Joke generation failed: {e}")
            jokes_by_headline[headline] = []

    total = sum(len(j) for j in jokes_by_headline.values())
    print()
    print("=" * 60)
    print(f"🎯 STEP 2 COMPLETE: {total} jokes from {len(headlines)} headlines")
    print("=" * 60)

    # Step 3: Send notifications
    print("\n📨 STEP 3: Sending notifications...")
    try:
        from modules.news_workflow.notifier import notify_jokes
        notify_jokes(headlines, jokes_by_headline)
    except Exception as e:
        print(f"❌ Notification failed: {e}")

    print()
    print("=" * 60)
    print("🏁 DAILY PIPELINE COMPLETE")
    print(f"   Headlines: {len(headlines)}")
    print(f"   Total Jokes: {total}")
    print("=" * 60)

    return headlines, jokes_by_headline


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent / ".env")
    run_daily_pipeline()
