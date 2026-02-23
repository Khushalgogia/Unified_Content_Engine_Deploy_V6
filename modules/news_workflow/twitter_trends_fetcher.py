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
from datetime import datetime, timedelta, timezone

# Ensure project root is on sys.path
PROJECT_ROOT = str(Path(__file__).parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ─── Config ───────────────────────────────────────────────────────────────────

TWITTERAPI_KEY = os.getenv("TWITTERAPI_IO_KEY", "")
TWITTERAPI_BASE = "https://api.twitterapi.io"
RATE_LIMIT_DELAY = 6  # seconds between API calls (free tier: 1 req/5sec, buffer)

INDIA_WOEID = "23424848"
US_WOEID = "23424977"     # United States (English trends)
UK_WOEID = "23424975"     # United Kingdom (English trends)
INDIA_TREND_COUNT = 15
US_TREND_COUNT = 3
UK_TREND_COUNT = 2

# Minimum engagement for any tweet to be worth including
MIN_LIKES = 5

# Results storage
RESULTS_DIR = Path(PROJECT_ROOT) / "data" / "tweet_jokes"
TWEET_JOKES_BUCKET = "tweet_jokes"


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
    Fetch 15 India + 3 US + 2 UK trending topics.
    Returns list of dicts: [{"name": "...", "query": "...", "source": "india|us|uk", "rank": N}]
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

    # 2. US trends (English-speaking)
    print("   🇺🇸 Fetching US trends...")
    status, data = _api_get("/twitter/trends", {"woeid": US_WOEID})
    us_added = 0
    if status == 200 and isinstance(data, dict):
        raw_trends = data.get("trends", [])
        for t in raw_trends:
            if us_added >= US_TREND_COUNT:
                break
            trend_data = t.get("trend", t)
            name = trend_data.get("name", "")
            trends.append({
                "name": name,
                "query": trend_data.get("target", {}).get("query", name),
                "source": "us",
                "rank": trend_data.get("rank", 0),
            })
            us_added += 1
        print(f"   ✅ Got {us_added} US trends")
    else:
        print(f"   ❌ US trends failed (HTTP {status}): {str(data)[:200]}")

    time.sleep(RATE_LIMIT_DELAY)

    # 3. UK trends (English-speaking)
    print("   🇬🇧 Fetching UK trends...")
    status, data = _api_get("/twitter/trends", {"woeid": UK_WOEID})
    uk_added = 0
    if status == 200 and isinstance(data, dict):
        raw_trends = data.get("trends", [])
        for t in raw_trends:
            if uk_added >= UK_TREND_COUNT:
                break
            trend_data = t.get("trend", t)
            name = trend_data.get("name", "")
            trends.append({
                "name": name,
                "query": trend_data.get("target", {}).get("query", name),
                "source": "uk",
                "rank": trend_data.get("rank", 0),
            })
            uk_added += 1
        print(f"   ✅ Got {uk_added} UK trends")
    else:
        print(f"   ❌ UK trends failed (HTTP {status}): {str(data)[:200]}")

    return trends


# ─── Tweet Search ─────────────────────────────────────────────────────────────

def _parse_tweet_time(created_at_str):
    """Parse tweet timestamp and return (datetime_obj, human_readable_age)."""
    if not created_at_str:
        return None, ""
    try:
        # Twitter format: "Mon Feb 22 10:30:00 +0000 2026"
        dt = datetime.strptime(created_at_str, "%a %b %d %H:%M:%S %z %Y")
        now = datetime.now(timezone.utc)
        diff = now - dt
        secs = int(diff.total_seconds())
        if secs < 0:
            return dt, "just now"
        elif secs < 60:
            return dt, f"{secs}s ago"
        elif secs < 3600:
            return dt, f"{secs // 60}m ago"
        elif secs < 86400:
            return dt, f"{secs // 3600}h ago"
        else:
            days = secs // 86400
            return dt, f"{days}d ago"
    except Exception:
        return None, ""


def search_tweets_for_trend(query, count=10, max_age_hours=None, _retries=3):
    """
    Search for top tweets about a trending topic.
    Returns list of tweet dicts with id, text, author, likes, retweets, url.
    Retries automatically on 429 (rate limit) with exponential backoff.

    Args:
        max_age_hours: If set, only return tweets newer than this many hours.
    """
    time.sleep(RATE_LIMIT_DELAY)

    status, data = _api_get("/twitter/tweet/advanced_search", {
        "query": f"{query} lang:en",
        "queryType": "Top",
    })

    # Retry on rate limit (429)
    if status == 429 and _retries > 0:
        wait = RATE_LIMIT_DELAY * (4 - _retries)  # 6s, 12s, 18s backoff
        print(f"   ⏳ Rate limited (429), waiting {wait}s before retry ({_retries} left)...")
        time.sleep(wait)
        return search_tweets_for_trend(query, count=count, max_age_hours=max_age_hours, _retries=_retries - 1)

    # Credits exhausted (402) — return special sentinel
    if status == 402:
        print(f"   💳 Credits exhausted (HTTP 402) — stopping further searches")
        return "CREDITS_EXHAUSTED"

    if status != 200 or not isinstance(data, dict):
        print(f"   ❌ Search failed for '{query[:60]}' (HTTP {status})")
        return []

    raw_tweets = data.get("tweets", [])
    cutoff = None
    if max_age_hours:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

    tweets = []

    for t in raw_tweets[:count * 2]:  # fetch extra to compensate for filtering
        author = t.get("author", {})
        username = author.get("userName", "unknown") if isinstance(author, dict) else "unknown"
        tweet_id = t.get("id", "")
        created_at = t.get("createdAt", "")

        # Parse and compute age
        tweet_dt, tweet_age = _parse_tweet_time(created_at)

        # Filter by recency if cutoff is set
        if cutoff and tweet_dt and tweet_dt < cutoff:
            continue

        tweets.append({
            "id": str(tweet_id),
            "text": t.get("text", ""),
            "author": username,
            "author_name": author.get("name", username) if isinstance(author, dict) else username,
            "likes": t.get("likeCount", 0),
            "retweets": t.get("retweetCount", 0),
            "views": t.get("viewCount", 0),
            "lang": t.get("lang", ""),
            "url": f"https://x.com/{username}/status/{tweet_id}",
            "created_at": created_at,
            "tweet_age": tweet_age,  # human-readable, e.g. "2h ago"
        })

        if len(tweets) >= count:
            break

    return tweets


def _pick_best_tweet(tweets):
    """
    Pick the best English tweet from search results.
    Since we use lang:en in the search query, most tweets should be English.
    We still do a safety check using the lang field and a basic text check.
    """
    if not tweets:
        return None

    for tweet in sorted(tweets, key=lambda t: t.get("likes", 0) + t.get("retweets", 0) * 3, reverse=True):
        # Skip very low engagement tweets
        if tweet.get("likes", 0) < MIN_LIKES:
            continue

        # Safety: skip if API explicitly says not English
        lang = tweet.get("lang", "")
        if lang and lang not in ("en", "und", ""):  # "und" = undetermined = OK
            continue

        return tweet

    # No tweet met the criteria
    return None


# ─── LLM Preprocessor ────────────────────────────────────────────────────────

TWEET_PREPROCESSOR_PROMPT = """
INPUT: A list of tweets from Twitter/X trending topics.

YOUR JOB: For each tweet, decide if it has COMEDY POTENTIAL, and if yes,
extract a SHORT FACTUAL ONE-LINER that a joke engine can use.

RULES:
1. SKIP tweets about: death, tragedy, natural disasters, prayers/condolences,
   boring corporate earnings.
   Mark these as "SKIP" with a reason.

2. KEEP (high priority) tweets about: irony, frustration, absurdity, relatable situations,
   viral drama, sports fails, price hikes, government decisions, celebrity gossip,
   tech fails, corporate greed, funny incidents.

3. KEEP (lower priority) tweets about: religious events (if there's an ironic angle),
   motivational/inspirational content (if the situation itself is funny or contradictory),
   spiritual trends (only if the context is absurd or relatable).

4. For KEPT tweets, extract a FACTUAL one-sentence summary:
   - Write like you're telling a friend what happened
   - Use simple everyday English a 15-year-old would understand
   - If tweet is in Hindi/Hinglish, TRANSLATE to simple English
   - Remove hashtags, mentions, emojis, URLs, thread markers
   - Do NOT add jokes, exaggeration, or opinion — just facts
   - Max 20 words

5. GOOD:
   ✅ "Strickland just got knocked out cold in R1 😭 #UFCHouston"
      → "Sean Strickland lost by first-round knockout at UFC Houston"
   ✅ "Bhai Mumbai Police ne 2160 bacche dhundh liye 🔥🔥"
      → "Mumbai police found 2,160 out of 2,182 missing children"
   ✅ "This guru's ashram is trending because they filed a court case against a meme page"
      → "A spiritual guru's ashram sued a meme page for making fun of them"

6. BAD:
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
    print("   15 India + 3 US + 2 UK trends → lang:en search → LLM preprocessing → Jokes")
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
        flags = {"india": "🇮🇳", "us": "🇺🇸", "uk": "🇬🇧"}
        flag = flags.get(t["source"], "🌍")
        print(f"   {flag} #{t['rank']}: {t['name']}")

    # Step 2: Search tweets for each trend
    print("\n🔍 STEP 2: Searching top tweets for each trend...")
    tweets_with_trends = []

    for t in trends:
        print(f"\n   Searching: {t['name']}...")
        tweets = search_tweets_for_trend(t["query"], count=5, max_age_hours=48)

        # Stop early if credits exhausted
        if tweets == "CREDITS_EXHAUSTED":
            print(f"   ⚠️ Stopping searches — API credits exhausted")
            break

        if tweets:
            best = _pick_best_tweet(tweets)
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
    """Save pipeline results locally AND to Supabase Storage."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"tweet_jokes_{today}.json"
    filepath = RESULTS_DIR / filename

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

    # Save locally
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Results saved locally: {filepath}")

    # Upload to Supabase Storage so Streamlit Cloud can access it
    try:
        _upload_to_supabase_storage(filename, data)
    except Exception as e:
        print(f"   ⚠️ Supabase Storage upload failed: {e}")
        print(f"   (Local file still saved — Streamlit local dev will work)")

    return filepath


def _upload_to_supabase_storage(filename, data):
    """Upload tweet jokes JSON to Supabase Storage bucket."""
    from supabase import create_client

    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY", "")
    if not url or not key:
        print("   ⚠️ SUPABASE_URL/KEY not set — skipping storage upload")
        return

    client = create_client(url, key)
    json_bytes = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")

    # Try to remove old file first (upsert)
    try:
        client.storage.from_(TWEET_JOKES_BUCKET).remove([filename])
    except Exception:
        pass  # File may not exist yet

    # Also upload as "latest.json" for easy loading
    try:
        client.storage.from_(TWEET_JOKES_BUCKET).remove(["latest.json"])
    except Exception:
        pass

    client.storage.from_(TWEET_JOKES_BUCKET).upload(
        path=filename,
        file=json_bytes,
        file_options={"content-type": "application/json"},
    )
    client.storage.from_(TWEET_JOKES_BUCKET).upload(
        path="latest.json",
        file=json_bytes,
        file_options={"content-type": "application/json"},
    )
    print(f"   ☁️ Uploaded to Supabase Storage: {filename} + latest.json")


def load_latest_results():
    """
    Load the most recent tweet jokes.
    Priority: Supabase Storage → local file.
    """
    # Try Supabase Storage first (works on Streamlit Cloud)
    try:
        data = _download_from_supabase_storage()
        if data:
            return data
    except Exception as e:
        print(f"   ⚠️ Supabase Storage download failed: {e}")

    # Fallback to local file (works in local dev)
    if not RESULTS_DIR.exists():
        return None

    json_files = sorted(RESULTS_DIR.glob("tweet_jokes_*.json"), reverse=True)
    if not json_files:
        return None

    with open(json_files[0], "r", encoding="utf-8") as f:
        return json.load(f)


def _download_from_supabase_storage():
    """Download latest.json from Supabase Storage."""
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY", "")
    if not url or not key:
        return None

    # Use public URL to download (no auth needed for public bucket)
    public_url = f"{url}/storage/v1/object/public/{TWEET_JOKES_BUCKET}/latest.json"

    req = urllib.request.Request(public_url)
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode())
    except Exception:
        pass

    return None


def search_tweets_manual(query, count=10):
    """
    Manual search for Streamlit Tab 2. Returns top tweets sorted by engagement.
    Limited to last 7 days to ensure relevance.
    """
    tweets = search_tweets_for_trend(query, count=count, max_age_hours=168)  # 7 days
    if tweets == "CREDITS_EXHAUSTED":
        return []  # Return empty list, not sentinel
    return sorted(tweets, key=lambda t: t.get("likes", 0) + t.get("retweets", 0) * 3, reverse=True)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent / ".env")
    run_twitter_pipeline()
