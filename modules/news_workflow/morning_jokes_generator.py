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
    Returns (headlines, jokes_by_headline, tweet_topics, tweet_jokes) tuple.
    """
    print()
    print("=" * 60)
    print("🎭 MORNING JOKES GENERATOR")
    print("   10 Headlines × ~10 Best Bridges = ~100 Quality Jokes")
    print("   + Twitter Trending Jokes")
    print("=" * 60)
    print()

    # Step 1: Fetch headlines
    print("📰 STEP 1: Fetching trending headlines...")
    from modules.news_workflow.news_fetcher import fetch_top_headlines
    headlines = fetch_top_headlines()

    if not headlines:
        print("❌ No headlines fetched. Aborting.")
        return [], {}, [], {}

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
            matches = search_bridges(headline, top_k=15)
            # Filter: keep only bridges with decent similarity, cap at 10
            quality_matches = [m for m in matches if m.get('similarity', 0) > 0.25][:10]
            print(f"   🔍 Found {len(matches)} bridges → {len(quality_matches)} quality matches (similarity > 0.25)")
        except Exception as e:
            print(f"   ❌ Bridge search failed: {e}")
            jokes_by_headline[headline] = []
            continue

        # Generate jokes from quality matches
        try:
            jokes = generate_from_selected(headline, quality_matches)
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

    # Step 3: Twitter Trending Jokes
    tweet_topics = []
    tweet_jokes = {}
    try:
        print("\n🐦 STEP 3: Running Twitter Trending Jokes Pipeline...")
        from modules.news_workflow.twitter_trends_fetcher import run_twitter_pipeline
        tweet_topics, tweet_jokes = run_twitter_pipeline()
        tweet_total = sum(len(v.get("jokes", [])) for v in tweet_jokes.values())
        print(f"✅ Twitter pipeline: {tweet_total} jokes from {len(tweet_topics)} tweet topics")
    except Exception as e:
        print(f"⚠️ Twitter pipeline failed (non-fatal): {e}")

    # Step 4: Send notifications
    print("\n📨 STEP 4: Sending notifications...")
    try:
        from modules.news_workflow.notifier import notify_jokes
        notify_jokes(headlines, jokes_by_headline, tweet_jokes=tweet_jokes)
    except Exception as e:
        print(f"❌ Notification failed: {e}")

    print()
    print("=" * 60)
    print("🏁 DAILY PIPELINE COMPLETE")
    print(f"   Headlines: {len(headlines)}")
    print(f"   News Jokes: {total}")
    tweet_total = sum(len(v.get("jokes", [])) for v in tweet_jokes.values())
    print(f"   Tweet Jokes: {tweet_total}")
    print(f"   Total: {total + tweet_total}")
    print("=" * 60)

    return headlines, jokes_by_headline, tweet_topics, tweet_jokes


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent / ".env")
    run_daily_pipeline()
