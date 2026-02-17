"""
AI Caption Generator — Viral-Ready Metadata Engine
Uses Gemini to generate structured captions for Instagram/Twitter posts.
Supports platform-specific prompts and dynamic topic adaptation.
"""

import os
import json
import re
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load .env from project root so GEMINI_API_KEY is always available
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


# Lazy-init Gemini client (env vars may not be set at module import time)
_client = None
MODEL = "gemini-3-flash-preview"


def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment. Check your .env file.")
        _client = genai.Client(api_key=api_key)
    return _client


# ─── Platform-Specific System Prompts ────────────────────────────────────────

INSTAGRAM_SYSTEM_PROMPT = """You are an expert Social Media Growth Manager specializing in Instagram Reels and posts.
I will give you a piece of content (joke, news, punchline) and its topic.
You must generate the JSON output with these exact fields:

1. "caption_hook": A shocking, funny, or curiosity-driven first sentence (under 10 words). This is the first thing people see — make it scroll-stopping.
2. "caption_body": Two short sentences that add context or a relatable spin on the topic. Reference the actual topic naturally — don't force unrelated keywords.
3. "call_to_action": A question or prompt that makes people comment, share, or tag someone. Make it specific to the content, not generic.
4. "hashtags": A string of exactly 15 hashtags mixed as follows:
   - 5 Broad/Trending Tags relevant to the content's category (e.g., #funny, #relatable, #trending, #viral, #explore)
   - 5 Niche Tags specific to the topic's industry or community (derive these from the topic itself)
   - 5 Ultra-Specific Tags directly about the content's subject matter

RULES:
- Adapt ALL keywords, references, and hashtags to the actual topic provided. Do NOT default to any specific city or region unless the topic is about that place.
- Write in a casual, Gen-Z friendly tone — like texting a friend.
- Keep the caption body under 40 words total.

Return ONLY valid JSON, no markdown fences, no extra text."""


TWITTER_SYSTEM_PROMPT = """You are an expert Social Media Growth Manager specializing in Twitter/X.
I will give you a piece of content (joke, news, punchline) and its topic.
You must generate the JSON output with these exact fields:

1. "tweet_text": The main tweet text. MUST be under 280 characters total (including hashtags). Make it punchy, witty, and shareable. Can include the joke itself or a fresh take on it.
2. "alt_tweet": An alternative version of the tweet with a different angle or tone. Also under 280 characters.
3. "thread_hook": If the content deserves a thread, write a compelling first tweet that makes people want to read more (under 280 chars). If not needed, set to empty string "".
4. "hashtags": A string of 3-5 relevant hashtags (Twitter works best with fewer hashtags). Keep total under 60 characters.

RULES:
- Keep it SHORT and PUNCHY — Twitter rewards brevity.
- Use conversational, witty tone. No corporate speak.
- Adapt hashtags and references to the actual topic. Do NOT default to any specific city or region unless the topic mentions it.
- Emojis are welcome but don't overdo it (max 2-3).

Return ONLY valid JSON, no markdown fences, no extra text."""


def generate_caption(joke_text: str, topic: str = "", platform: str = "instagram") -> dict:
    """
    Generate viral-ready caption metadata from a joke/punchline.

    Args:
        joke_text: The joke or content text
        topic: Optional topic/context for better hashtags
        platform: "instagram" or "twitter" — determines prompt style

    Returns dict with platform-specific fields:
        Instagram: caption_hook, caption_body, call_to_action, hashtags
        Twitter: tweet_text, alt_tweet, thread_hook, hashtags
    """
    platform = platform.lower().strip()
    is_twitter = platform in ("twitter", "x")

    system_prompt = TWITTER_SYSTEM_PROMPT if is_twitter else INSTAGRAM_SYSTEM_PROMPT

    user_prompt = f"""TOPIC: {topic if topic else "General humor"}

CONTENT/JOKE:
{joke_text}

Generate the {"tweet" if is_twitter else "viral caption"} JSON now."""

    config = types.GenerateContentConfig(
        temperature=0.8,
        max_output_tokens=1024,
        system_instruction=system_prompt,
        response_mime_type="application/json",
    )

    response = _get_client().models.generate_content(
        model=MODEL,
        contents=user_prompt,
        config=config,
    )

    result_text = response.text

    # Parse JSON response
    try:
        data = json.loads(result_text)
    except json.JSONDecodeError:
        # Try to extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', result_text)
        if json_match:
            try:
                data = json.loads(json_match.group())
            except json.JSONDecodeError:
                data = _fallback_response(joke_text, is_twitter)
        else:
            data = _fallback_response(joke_text, is_twitter)

    return data


def _fallback_response(joke_text: str, is_twitter: bool) -> dict:
    """Return a safe fallback if Gemini fails to produce valid JSON."""
    if is_twitter:
        return {
            "tweet_text": joke_text[:270] + "…" if len(joke_text) > 270 else joke_text,
            "alt_tweet": "",
            "thread_hook": "",
            "hashtags": "#funny #trending",
        }
    return {
        "caption_hook": "🔥 You won't believe this!",
        "caption_body": joke_text[:100],
        "call_to_action": "Tag a friend who needs to see this 👇",
        "hashtags": "#funny #memes #relatable #viral #trending",
    }


def format_caption(data: dict, platform: str = "instagram") -> str:
    """
    Format the structured caption data into a single ready-to-post string.
    Adapts formatting based on platform.
    """
    platform = platform.lower().strip()
    is_twitter = platform in ("twitter", "x")

    if is_twitter:
        return _format_twitter(data)
    return _format_instagram(data)


def _format_instagram(data: dict) -> str:
    """Format Instagram caption: hook + body + CTA + hashtags."""
    hook = data.get("caption_hook", "")
    body = data.get("caption_body", "")
    cta = data.get("call_to_action", "")
    hashtags = data.get("hashtags", "")

    # Handle case where hashtags is returned as a list
    if isinstance(hashtags, list):
        hashtags = " ".join(hashtags)

    parts = []
    if hook:
        parts.append(str(hook))
    if body:
        parts.append(f"\n{str(body)}")
    if cta:
        parts.append(f"\n{str(cta)}")
    if hashtags:
        parts.append(f"\n\n{str(hashtags)}")

    result = "\n".join(parts).strip()

    if not result:
        return f"🔥 Check this out!\n\n{data}"
    return result


def _format_twitter(data: dict) -> str:
    """Format Twitter output: primary tweet + alt + thread hook."""
    tweet = data.get("tweet_text", "")
    alt = data.get("alt_tweet", "")
    thread = data.get("thread_hook", "")
    hashtags = data.get("hashtags", "")

    if isinstance(hashtags, list):
        hashtags = " ".join(hashtags)

    parts = []
    if tweet:
        parts.append(f"📝 Tweet:\n{tweet}")
    if hashtags:
        parts.append(f"\n{hashtags}")
    if alt:
        parts.append(f"\n\n🔄 Alternative:\n{alt}")
    if thread:
        parts.append(f"\n\n🧵 Thread opener:\n{thread}")

    result = "\n".join(parts).strip()

    if not result:
        return str(data)
    return result
