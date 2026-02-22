"""
Twitter Trends Fetcher — Fetches trending tweets via twitterapi.io and
preprocesses them for the joke engine using Gemini 3 Flash.

Pipeline:
1. Fetch 8 India trends + 2 global English-only trends
2. Search top tweets for each trend
3. Filter by language + engagement
4. LLM preprocessor extracts factual one-liners for joke engine
5. Save results JSON for Streamlit to load later
"""

import os
import sys
import json
import time
import urllib.request
import urllib.parse
import ssl
from pathlib import Path
from datetime import datetime

# Ensure project root is on sys.path
PROJECT_ROOT = str(Path(__file__).parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ─── Config ───────────────────────────────────────────────────────────────────

TWITTERAPI_KEY = os.getenv("TWITTERAPI_IO_KEY", "")
TWITTERAPI_BASE = "https://api.twitterapi.io"
RATE_LIMIT_DELAY = 5  # seconds between API calls (free tier: 1 req/5sec)

INDIA_WOEID = "23424848"
GLOBAL_WOEID = "1"
INDIA_TREND_COUNT = 8
GLOBAL_TREND_COUNT = 2

# Hindi tweets need high engagement to be included (since reply is in English)
HINDI_MIN_LIKES = 500
HINDI_MIN_RETWEETS = 100

# Results storage
RESULTS_DIR = Path(PROJECT_ROOT) / "data" / "tweet_jokes"


# ─── twitterapi.io Client ────────────────────────────────────────────────────

def _api_get(endpoint, params=None):
    """Make GET request to twitterapi.io with rate limit handling."""
    url = f"{TWITTERAPI_BASE}{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(url)
    req.add_header("X-API-Key", TWITTERAPI_KEY)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)")

    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500]
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, body
    except Exception as e:
        return -1, str(e)


# ─── Trend Fetching ──────────────────────────────────────────────────────────

def _is_english_trend(name):
    """Check if a trend name is likely English (ASCII + basic punctuation)."""
    try:
        name.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def fetch_trending_topics():
    """
    Fetch 8 India + 2 Global (English-only) trending topics.
    Returns list of dicts: [{"name": "...", "query": "...", "source": "india|global", "rank": N}]
    """
    trends = []

    # 1. India trends
    print("   🇮🇳 Fetching India trends...")
    status, data = _api_get("/twitter/trends", {"woeid": INDIA_WOEID})
    if status == 200 and isinstance(data, dict):
        raw_trends = data.get("trends", [])
        for t in raw_trends[:INDIA_TREND_COUNT]:
            trend_data = t.get("trend", t)
            trends.append({
                "name": trend_data.get("name", ""),
                "query": trend_data.get("target", {}).get("query", trend_data.get("name", "")),
                "source": "india",
                "rank": trend_data.get("rank", len(trends) + 1),
            })
        print(f"   ✅ Got {len(trends)} India trends")
    else:
        print(f"   ❌ India trends failed (HTTP {status}): {str(data)[:200]}")

    time.sleep(RATE_LIMIT_DELAY)

    # 2. Global trends (English only)
    print("   🌍 Fetching Global trends (English only)...")
    status, data = _api_get("/twitter/trends", {"woeid": GLOBAL_WOEID})
    global_added = 0
    if status == 200 and isinstance(data, dict):
        raw_trends = data.get("trends", [])
        for t in raw_trends:
            if global_added >= GLOBAL_TREND_COUNT:
                break
            trend_data = t.get("trend", t)
            name = trend_data.get("name", "")
            if _is_english_trend(name):
                trends.append({
                    "name": name,
                    "query": trend_data.get("target", {}).get("query", name),
                    "source": "global",
                    "rank": trend_data.get("rank", 0),
                })
                global_added += 1
        print(f"   ✅ Got {global_added} global English trends")
    else:
        print(f"   ❌ Global trends failed (HTTP {status}): {str(data)[:200]}")

    return trends


# ─── Tweet Search ─────────────────────────────────────────────────────────────

def search_tweets_for_trend(query, count=10):
    """
    Search for top tweets about a trending topic.
    Returns list of tweet dicts with id, text, author, likes, retweets, url.
    """
    time.sleep(RATE_LIMIT_DELAY)

    status, data = _api_get("/twitter/tweet/advanced_search", {
        "query": query,
        "queryType": "Top",
    })

    if status != 200 or not isinstance(data, dict):
        print(f"   ❌ Search failed for '{query}' (HTTP {status})")
        return []

    raw_tweets = data.get("tweets", [])
    tweets = []

    for t in raw_tweets[:count]:
        author = t.get("author", {})
        username = author.get("userName", "unknown") if isinstance(author, dict) else "unknown"
        tweet_id = t.get("id", "")

        tweets.append({
            "id": str(tweet_id),
            "text": t.get("text", ""),
            "author": username,
            "author_name": author.get("name", username) if isinstance(author, dict) else username,
            "likes": t.get("likeCount", 0),
            "retweets": t.get("retweetCount", 0),
            "views": t.get("viewCount", 0),
            "url": f"https://x.com/{username}/status/{tweet_id}",
            "created_at": t.get("createdAt", ""),
        })

    return tweets


def _is_high_engagement_hindi(tweet):
    """Check if a Hindi tweet has enough engagement to be worth including."""
    return tweet.get("likes", 0) >= HINDI_MIN_LIKES or tweet.get("retweets", 0) >= HINDI_MIN_RETWEETS


def _pick_best_tweet(tweets, source):
    """
    Pick the best tweet from search results based on language + engagement rules.
    Global: English only. India: English preferred, Hindi OK if high engagement.
    """
    if not tweets:
        return None

    for tweet in sorted(tweets, key=lambda t: t.get("likes", 0) + t.get("retweets", 0) * 3, reverse=True):
        text = tweet.get("text", "")
        try:
            text.encode("ascii")
            is_english = True
        except UnicodeEncodeError:
            is_english = False

        if source == "global":
            if is_english:
                return tweet
        else:  # india
            if is_english:
                return tweet
            elif _is_high_engagement_hindi(tweet):
                return tweet

    # Fallback: return highest engagement regardless of language
    return tweets[0] if tweets else None


# ─── LLM Preprocessor ────────────────────────────────────────────────────────

TWEET_PREPROCESSOR_PROMPT = """
INPUT: A list of tweets from Twitter/X trending topics.

YOUR JOB: For each tweet, decide if it has COMEDY POTENTIAL, and if yes,
extract a SHORT FACTUAL ONE-LINER that a joke engine can use.

RULES:
1. SKIP tweets about: death, tragedy, natural disasters, prayers/condolences,
   boring corporate earnings, generic motivational quotes.
   Mark these as "SKIP" with a reason.

2. KEEP tweets about: irony, frustration, absurdity, relatable situations,
   viral drama, sports fails, price hikes, government decisions, celebrity gossip,
   tech fails, corporate greed, funny incidents.

3. For KEPT tweets, extract a FACTUAL one-sentence summary:
   - Write like you're telling a friend what happened
   - Use simple everyday English a 15-year-old would understand
   - If tweet is in Hindi/Hinglish, TRANSLATE to simple English
   - Remove hashtags, mentions, emojis, URLs, thread markers
   - Do NOT add jokes, exaggeration, or opinion — just facts
   - Max 20 words

4. GOOD:
   ✅ "Bhai Mumbai Police ne 2160 bacche dhundh liye 🔥🔥 #MumbaiPolice"
      → "Mumbai police found 2,160 out of 2,182 missing children"
   ✅ "Strickland just got knocked out cold in R1 😭 #UFCHouston"
      → "Sean Strickland lost by first-round knockout at UFC Houston"

5. BAD:
   ❌ "The situation is dire and unprecedented" (too formal)
   ❌ "Mumbai police are absolute legends!" (opinion, not fact)

OUTPUT (valid JSON):
{
  "results": [
    {"tweet_index": 0, "action": "KEEP", "topic": "factual one-liner here"},
    {"tweet_index": 1, "action": "SKIP", "reason": "tragedy"},
    {"tweet_index": 2, "action": "KEEP", "topic": "factual one-liner here"}
  ]
}
"""


def preprocess_tweets(tweets_with_trends):
    """
    Run tweets through Gemini 3 Flash to extract factual topics for the joke engine.

    Args:
        tweets_with_trends: list of dicts, each with {"trend": {...}, "tweet": {...}}

    Returns:
        list of dicts with extracted topics:
        [{"trend": {...}, "tweet": {...}, "topic": "factual one-liner", "action": "KEEP|SKIP"}]
    """
    if not tweets_with_trends:
        return []

    # Build tweet list for the LLM
    tweet_texts = []
    for i, item in enumerate(tweets_with_trends):
        tweet = item["tweet"]
        tweet_texts.append(f"Tweet {i}: [{item['trend']['name']}] @{tweet['author']}: {tweet['text']}")

    user_prompt = "Here are the tweets to classify:\n\n" + "\n\n".join(tweet_texts)

    # Call Gemini 3 Flash
    print("   🤖 Running LLM preprocessor (gemini-3-flash-preview)...")
    try:
        from google import genai
        from google.genai import types

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("   ❌ GEMINI_API_KEY not found")
            return []

        gemini_client = genai.Client(api_key=api_key)

        config = types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=4096,
            system_instruction=TWEET_PREPROCESSOR_PROMPT,
            response_mime_type="application/json",
        )

        response = gemini_client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=user_prompt,
            config=config,
        )

        result = json.loads(response.text)
        results = result.get("results", [])

        # Merge LLM results back into our data
        processed = []
        for r in results:
            idx = r.get("tweet_index", -1)
            if 0 <= idx < len(tweets_with_trends):
                item = tweets_with_trends[idx].copy()
                item["action"] = r.get("action", "SKIP")
                item["topic"] = r.get("topic", "")
                item["skip_reason"] = r.get("reason", "")
                processed.append(item)

        kept = sum(1 for p in processed if p["action"] == "KEEP")
        skipped = sum(1 for p in processed if p["action"] == "SKIP")
        print(f"   ✅ LLM: {kept} joke-worthy, {skipped} skipped")

        return processed

    except Exception as e:
        print(f"   ❌ LLM preprocessor failed: {e}")
        # Fallback: keep all tweets with raw text as topic
        return [
            {**item, "action": "KEEP", "topic": item["tweet"]["text"][:100]}
            for item in tweets_with_trends
        ]


# ─── Full Pipeline ────────────────────────────────────────────────────────────

def run_twitter_pipeline():
    """
    Full pipeline: trends → tweets → preprocess → joke generation → save.
    Returns (topics_with_metadata, jokes_by_topic) tuple.
    """
    print()
    print("=" * 60)
    print("🐦 TWITTER TRENDING JOKES PIPELINE")
    print("   8 India + 2 Global trends → LLM preprocessing → Jokes")
    print("=" * 60)
    print()

    # Step 1: Fetch trends
    print("🔥 STEP 1: Fetching trending topics...")
    trends = fetch_trending_topics()

    if not trends:
        print("❌ No trends fetched. Aborting.")
        return [], {}

    print(f"\n✅ Got {len(trends)} trends total")
    for t in trends:
        flag = "🇮🇳" if t["source"] == "india" else "🌍"
        print(f"   {flag} #{t['rank']}: {t['name']}")

    # Step 2: Search tweets for each trend
    print("\n🔍 STEP 2: Searching top tweets for each trend...")
    tweets_with_trends = []

    for t in trends:
        print(f"\n   Searching: {t['name']}...")
        tweets = search_tweets_for_trend(t["query"], count=5)
        if tweets:
            best = _pick_best_tweet(tweets, t["source"])
            if best:
                tweets_with_trends.append({"trend": t, "tweet": best})
                print(f"   ✅ Best: @{best['author']} ({best['likes']}❤️ {best['retweets']}🔁) — {best['text'][:80]}")
            else:
                print(f"   ⚠️ No suitable tweet found")
        else:
            print(f"   ⚠️ No tweets found")

    print(f"\n✅ Found {len(tweets_with_trends)} tweets to process")

    # Step 3: LLM preprocessing
    print("\n🤖 STEP 3: LLM preprocessor — extracting joke topics...")
    processed = preprocess_tweets(tweets_with_trends)

    # Filter to kept topics only
    kept_topics = [p for p in processed if p["action"] == "KEEP"]
    print(f"\n✅ {len(kept_topics)} topics ready for joke engine")

    # Step 4: Generate jokes for each topic
    print("\n🔥 STEP 4: Generating jokes for each topic...")
    from modules.joke_generator.campaign_generator import search_bridges, generate_from_selected

    jokes_by_topic = {}

    for idx, item in enumerate(kept_topics):
        topic = item["topic"]
        print(f"\n   {'─' * 50}")
        print(f"   🐦 [{idx+1}/{len(kept_topics)}] {topic}")
        print(f"      (from @{item['tweet']['author']}: {item['tweet']['text'][:60]}...)")
        print(f"   {'─' * 50}")

        try:
            matches = search_bridges(topic, top_k=15)
            quality_matches = [m for m in matches if m.get("similarity", 0) > 0.25][:10]
            print(f"   🔍 {len(matches)} bridges → {len(quality_matches)} quality")
        except Exception as e:
            print(f"   ❌ Bridge search failed: {e}")
            jokes_by_topic[topic] = {"tweet": item["tweet"], "trend": item["trend"], "jokes": []}
            continue

        try:
            jokes = generate_from_selected(topic, quality_matches)
            jokes_by_topic[topic] = {
                "tweet": item["tweet"],
                "trend": item["trend"],
                "jokes": jokes,
            }
            print(f"   ✅ Generated {len(jokes)} jokes")
        except Exception as e:
            print(f"   ❌ Joke generation failed: {e}")
            jokes_by_topic[topic] = {"tweet": item["tweet"], "trend": item["trend"], "jokes": []}

    total = sum(len(v["jokes"]) for v in jokes_by_topic.values())
    print()
    print("=" * 60)
    print(f"🎯 STEP 4 COMPLETE: {total} jokes from {len(kept_topics)} tweet topics")
    print("=" * 60)

    # Step 5: Save results for Streamlit
    _save_results(kept_topics, jokes_by_topic)

    return kept_topics, jokes_by_topic


def _save_results(topics, jokes_by_topic):
    """Save pipeline results as JSON for Streamlit to load."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    filepath = RESULTS_DIR / f"tweet_jokes_{today}.json"

    data = {
        "generated_at": datetime.now().isoformat(),
        "topics": [],
    }

    for item in topics:
        topic = item["topic"]
        entry = jokes_by_topic.get(topic, {})
        data["topics"].append({
            "topic": topic,
            "trend_name": item["trend"]["name"],
            "trend_source": item["trend"]["source"],
            "tweet": item["tweet"],
            "jokes": entry.get("jokes", []),
        })

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Results saved to {filepath}")
    return filepath


def load_latest_results():
    """Load the most recent tweet jokes JSON for Streamlit."""
    if not RESULTS_DIR.exists():
        return None

    json_files = sorted(RESULTS_DIR.glob("tweet_jokes_*.json"), reverse=True)
    if not json_files:
        return None

    with open(json_files[0], "r", encoding="utf-8") as f:
        return json.load(f)


def search_tweets_manual(query, count=10):
    """
    Manual search for Streamlit Tab 2. Returns top tweets sorted by engagement.
    """
    tweets = search_tweets_for_trend(query, count=count)
    return sorted(tweets, key=lambda t: t.get("likes", 0) + t.get("retweets", 0) * 3, reverse=True)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent / ".env")
    run_twitter_pipeline()
