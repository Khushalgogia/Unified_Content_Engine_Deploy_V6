"""
AI Caption Generator — Viral-Ready Metadata Engine
Uses Gemini to generate structured captions for Instagram/Twitter posts.
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

SYSTEM_PROMPT = """You are an expert Instagram Growth Manager.
I will give you a piece of news and a punchline.
You must generate the JSON output with these exact fields:

1. "caption_hook": A shocking or funny first sentence (under 10 words).
2. "caption_body": Two short sentences explaining the context (include keywords like 'Bengaluru', 'Tech', 'Money', 'Dating').
3. "call_to_action": A question to make people comment (e.g., "Tag a friend who needs to see this").
4. "hashtags": A string of exactly 15 hashtags mixed as follows:
   - 5 Broad Tags (e.g., #india, #news, #funny, #memes, #relatable)
   - 5 Niche Tags (e.g., #bangalorestartups, #corporatehumor, #engineering, #sharktankindia, #financenews)
   - 5 Specific Tags related to the news topic

Return ONLY valid JSON, no markdown fences, no extra text."""


def generate_caption(joke_text: str, topic: str = "") -> dict:
    """
    Generate viral-ready caption metadata from a joke/punchline.
    
    Returns dict with: caption_hook, caption_body, call_to_action, hashtags
    """
    user_prompt = f"""NEWS/TOPIC: {topic if topic else "General humor"}

PUNCHLINE/JOKE:
{joke_text}

Generate the viral caption JSON now."""

    config = types.GenerateContentConfig(
        temperature=0.8,
        max_output_tokens=1024,
        system_instruction=SYSTEM_PROMPT,
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
                data = {
                    "caption_hook": "🔥 You won't believe this!",
                    "caption_body": joke_text[:100],
                    "call_to_action": "Tag a friend who needs to see this 👇",
                    "hashtags": "#funny #memes #relatable #india #viral",
                }
        else:
            data = {
                "caption_hook": "🔥 You won't believe this!",
                "caption_body": joke_text[:100],
                "call_to_action": "Tag a friend who needs to see this 👇",
                "hashtags": "#funny #memes #relatable #india #viral",
            }

    return data


def format_caption(data: dict) -> str:
    """
    Format the structured caption data into a single ready-to-post caption string.
    """
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

    # Never return empty
    if not result:
        return f"🔥 Check this out!\n\n{data}"

    return result
