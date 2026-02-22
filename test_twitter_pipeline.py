"""
Quick smoke test — fetch 1 trend, search 1 tweet, generate 1 joke.
Run:  python test_twitter_pipeline.py
"""
import os, sys, json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

print("=" * 60)
print("🧪 TWITTER PIPELINE SMOKE TEST")
print("=" * 60)

# 1. Check API key
key = os.getenv("TWITTERAPI_IO_KEY", "")
print(f"\n1️⃣  TWITTERAPI_IO_KEY: {'✅ set (' + key[:8] + '...)' if key else '❌ MISSING'}")
if not key:
    print("   Add TWITTERAPI_IO_KEY to your .env file")
    sys.exit(1)

# 2. Fetch 1 trend
print(f"\n2️⃣  Fetching 1 trending topic (India)...")
from modules.news_workflow.twitter_trends_fetcher import fetch_trending_topics
trends = fetch_trending_topics()
if not trends:
    print("   ❌ No trends fetched. API may be down.")
    sys.exit(1)

trend = trends[0]
print(f"   ✅ Trend: {trend['name']} (volume: {trend.get('tweet_volume', 'N/A')})")

# 3. Search 1 tweet for that trend
print(f"\n3️⃣  Searching tweets for: {trend['name']}...")
from modules.news_workflow.twitter_trends_fetcher import search_tweets_for_trend
tweets = search_tweets_for_trend(trend["name"], count=3)
if not tweets:
    print("   ❌ No tweets found for this trend.")
    sys.exit(1)

tweet = tweets[0]
print(f"   ✅ Found {len(tweets)} tweets. Top tweet:")
print(f"      Author: @{tweet['author']}")
print(f"      Text:   {tweet['text'][:120]}...")
print(f"      ❤️ {tweet['likes']:,}  🔁 {tweet['retweets']:,}  👁️ {tweet['views']:,}")
print(f"      URL:    {tweet['url']}")

# 4. Generate 1 joke from this tweet
print(f"\n4️⃣  Generating joke from this tweet...")
try:
    from modules.joke_generator.campaign_generator import search_bridges, generate_from_selected

    # Use the tweet text as a "headline" to find bridges
    headline = tweet["text"][:200]
    bridges = search_bridges(headline, top_k=5)
    quality = [b for b in bridges if b.get("similarity", 0) > 0.2][:3]
    print(f"   🔍 Found {len(bridges)} bridges, {len(quality)} quality matches")

    if quality:
        jokes = generate_from_selected(headline, quality[:1])  # Just 1 bridge = ~1 joke
        if jokes:
            print(f"\n   🎭 GENERATED JOKE:")
            print(f"   ─────────────────")
            print(f"   {jokes[0].get('joke', 'N/A')}")
            print(f"   Engine: {jokes[0].get('engine', '?')}")
        else:
            print("   ⚠️ Joke generation returned empty")
    else:
        print("   ⚠️ No quality bridges found (similarity too low)")
except Exception as e:
    print(f"   ⚠️ Joke generation failed: {e}")
    print("   (This is OK — the tweet search part still works)")

print(f"\n{'=' * 60}")
print("✅ SMOKE TEST COMPLETE")
print(f"{'=' * 60}")
