"""
V12 Database Manager
Refactored for Unified Content Engine — reads credentials from .env
"""

import os
from supabase import create_client


def get_supabase_client():
    """Get Supabase client."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment")

    return create_client(url, key)


def get_embedding(text: str) -> list:
    """
    Generate embedding for text using OpenAI.
    Uses text-embedding-3-small model.
    """
    from openai import OpenAI

    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        raise ValueError("OPENAI_API_KEY not found in environment. Check your .env file.")

    client = OpenAI(api_key=openai_key)

    text = text.replace("\n", " ").strip()
    if not text:
        return None

    response = client.embeddings.create(
        input=[text],
        model="text-embedding-3-small"
    )

    return response.data[0].embedding


def get_all_jokes(limit: int = None):
    """Get all jokes from the database."""
    supabase = get_supabase_client()

    query = supabase.table("comic_segments").select("*")
    if limit:
        query = query.limit(limit)

    result = query.execute()
    return result.data


def update_joke_bridge(joke_id: int, bridge_content: str, bridge_embedding: list):
    """Update a joke with its bridge content and embedding."""
    supabase = get_supabase_client()

    result = supabase.table("comic_segments").update({
        "bridge_content": bridge_content,
        "bridge_embedding": bridge_embedding
    }).eq("id", joke_id).execute()

    return result


def search_by_bridge(query_embedding: list, match_count: int = 10):
    """Search jokes by bridge embedding similarity."""
    supabase = get_supabase_client()

    result = supabase.rpc(
        'match_joke_bridges',
        {
            'query_embedding': query_embedding,
            'match_count': match_count
        }
    ).execute()

    return result.data


def check_bridge_column_exists():
    """Check if bridge columns exist in the database."""
    supabase = get_supabase_client()

    try:
        result = supabase.table("comic_segments").select("bridge_content, bridge_embedding").limit(1).execute()
        return True
    except Exception as e:
        if "column" in str(e).lower():
            return False
        raise
