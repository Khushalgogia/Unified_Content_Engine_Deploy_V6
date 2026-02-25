"""
Social Media Publisher — Standalone script for scheduled post execution.
Checks Supabase for due scheduled posts and publishes them.

Works in ALL environments:
    • Local    — loads credentials from .env
    • Streamlit Cloud — loads from st.secrets (auto-injected as env vars)
    • GitHub Actions  — loads from repo secrets (injected as env vars)
"""

import os
import sys
import tempfile
import requests as http_requests
from datetime import datetime, timezone
from supabase import create_client
from requests_oauthlib import OAuth1

# ─── Load .env for local development ─────────────────────────────────────────
try:
    from dotenv import load_dotenv
    from pathlib import Path
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass  # dotenv not installed (e.g. on GitHub Actions) — that's fine


# ─── Credential Helper ───────────────────────────────────────────────────────

def _env(key, default=""):
    """
    Get a credential from the best available source:
      1. os.environ  (GitHub Actions secrets, .env via dotenv, Streamlit Cloud)
      2. st.secrets  (Streamlit Cloud fallback — some keys only live there)
    """
    val = os.environ.get(key, "")
    if not val:
        try:
            import streamlit as st
            val = st.secrets.get(key, "")
        except Exception:
            pass
    return val or default


# ─── Configuration ───────────────────────────────────────────────────────────

SUPABASE_URL = _env("SUPABASE_URL")
SUPABASE_KEY = _env("SUPABASE_KEY")

# Instagram — shared access token, per-account business IDs
IG_ACCESS_TOKEN = _env("INSTAGRAM_ACCESS_TOKEN")

INSTAGRAM_ACCOUNTS = {
    "khushal_page": {
        "id": _env("INSTAGRAM_BUSINESS_ACCOUNT_ID_1") or _env("INSTAGRAM_BUSINESS_ACCOUNT_ID"),
        "label": "Khushal Page",
    },
    "skin_nurture": {
        "id": _env("INSTAGRAM_BUSINESS_ACCOUNT_ID_2"),
        "label": "Skin Nurture",
    },
}

# Twitter OAuth 1.0a — shared app credentials
TW_CONSUMER_KEY = _env("TWITTER_CONSUMER_KEY")
TW_CONSUMER_SECRET = _env("TWITTER_CONSUMER_SECRET")

# Per-account access tokens (looked up by account name)
TWITTER_ACCOUNTS = {
    "account_1": {
        "access_token": _env("TWITTER_ACCESS_TOKEN_ACCOUNT_1"),
        "access_token_secret": _env("TWITTER_ACCESS_TOKEN_SECRET_ACCOUNT_1"),
    },
    "account_2": {
        "access_token": _env("TWITTER_ACCESS_TOKEN_ACCOUNT_2"),
        "access_token_secret": _env("TWITTER_ACCESS_TOKEN_SECRET_ACCOUNT_2"),
    },
    "account_3": {
        "access_token": _env("TWITTER_ACCESS_TOKEN_ACCOUNT_3"),
        "access_token_secret": _env("TWITTER_ACCESS_TOKEN_SECRET_ACCOUNT_3"),
    },
}

BUCKET_NAME = "ready_to_publish"
TABLE_NAME = "content_schedule"

# Instagram Graph API
GRAPH_API_URL = "https://graph.facebook.com/v22.0"
RUPLOAD_URL = "https://rupload.facebook.com/ig-api-upload/v22.0"

# Twitter API
TWITTER_API_BASE = "https://api.twitter.com/2"
TWITTER_MEDIA_UPLOAD_URL = "https://upload.twitter.com/1.1/media/upload.json"
CHUNK_SIZE = 4 * 1024 * 1024  # 4 MB


# ─── Supabase Client ─────────────────────────────────────────────────────────

def get_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY env vars are required")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# ─── Download Helper ─────────────────────────────────────────────────────────

def download_video(url, suffix=".mp4"):
    """Download a video from URL to a temporary file. Returns file path."""
    print(f"   📥 Downloading video...")
    resp = http_requests.get(url, stream=True)
    resp.raise_for_status()

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    for chunk in resp.iter_content(chunk_size=8192):
        tmp.write(chunk)
    tmp.close()
    print(f"   ✅ Downloaded to {tmp.name}")
    return tmp.name


# ─── Instagram Publishing ────────────────────────────────────────────────────

def publish_to_instagram(video_path, caption, account="khushal_page"):
    """Full Instagram Reel upload pipeline: init → upload → poll → publish."""
    if not IG_ACCESS_TOKEN:
        raise ValueError("Instagram access token not configured")

    acct = INSTAGRAM_ACCOUNTS.get(account)
    if not acct or not acct.get("id"):
        raise ValueError(f"Instagram Business ID not configured for '{account}'")
    ig_account_id = acct["id"]
    print(f"   📸 Posting to: {acct.get('label', account)}")

    file_size = os.path.getsize(video_path)

    # Step 1: Initialize container
    print(f"   📦 Creating Instagram container...")
    resp = http_requests.post(
        f"{GRAPH_API_URL}/{ig_account_id}/media",
        params={
            "media_type": "REELS",
            "upload_type": "resumable",
            "caption": caption,
            "access_token": IG_ACCESS_TOKEN,
        },
    )
    data = resp.json()
    if "id" not in data:
        raise Exception(f"Container creation failed: {data}")
    container_id = data["id"]
    print(f"   ✅ Container: {container_id}")

    # Step 2: Upload binary
    print(f"   📤 Uploading video ({file_size / (1024*1024):.1f} MB)...")
    with open(video_path, "rb") as f:
        resp = http_requests.post(
            f"{RUPLOAD_URL}/{container_id}",
            headers={
                "Authorization": f"OAuth {IG_ACCESS_TOKEN}",
                "offset": "0",
                "file_size": str(file_size),
                "Content-Type": "application/octet-stream",
            },
            data=f,
        )
    if resp.status_code != 200:
        raise Exception(f"Upload failed: {resp.json()}")
    print(f"   ✅ Upload complete")

    # Step 3: Poll for processing
    print(f"   🔄 Waiting for processing...")
    import time
    for attempt in range(60):
        resp = http_requests.get(
            f"{GRAPH_API_URL}/{container_id}",
            params={"fields": "status_code,status", "access_token": IG_ACCESS_TOKEN},
        )
        status = resp.json().get("status_code", "UNKNOWN")
        if status == "FINISHED":
            print(f"   ✅ Processing complete ({attempt * 5}s)")
            break
        if status in ("ERROR", "EXPIRED"):
            raise Exception(f"Processing failed: {resp.json()}")
        time.sleep(5)
    else:
        raise Exception("Processing timeout (300s)")

    # Step 4: Publish
    print(f"   📢 Publishing Reel...")
    resp = http_requests.post(
        f"{GRAPH_API_URL}/{ig_account_id}/media_publish",
        params={"creation_id": container_id, "access_token": IG_ACCESS_TOKEN},
    )
    data = resp.json()
    if "id" not in data:
        raise Exception(f"Publish failed: {data}")

    media_id = data["id"]
    print(f"   🎉 Published! Media ID: {media_id}")
    return media_id


# ─── Twitter Publishing ─────────────────────────────────────────────────────

def _get_twitter_oauth1(account="account_1"):
    """Build OAuth1 auth object for a specific Twitter account."""
    if not TW_CONSUMER_KEY or not TW_CONSUMER_SECRET:
        raise ValueError("Twitter consumer key/secret not configured")

    acct = TWITTER_ACCOUNTS.get(account)
    if not acct or not acct.get("access_token") or not acct.get("access_token_secret"):
        raise ValueError(f"Twitter credentials not configured for '{account}'")

    return OAuth1(
        TW_CONSUMER_KEY, TW_CONSUMER_SECRET,
        acct["access_token"], acct["access_token_secret"],
    )


def publish_tweet_text(text, account="account_1"):
    """Post a text-only tweet from the specified account."""
    auth = _get_twitter_oauth1(account)
    resp = http_requests.post(
        f"{TWITTER_API_BASE}/tweets",
        json={"text": text},
        auth=auth,
    )
    if resp.status_code == 201:
        tweet_data = resp.json().get("data", {})
        print(f"   🐦 Tweeted! ID: {tweet_data.get('id')}")
        return tweet_data.get("id")
    raise Exception(f"Tweet failed (HTTP {resp.status_code}): {resp.text}")


def upload_twitter_media(video_path, account="account_1"):
    """Upload video via Twitter v1.1 chunked media upload. Returns media_id."""
    import time
    auth = _get_twitter_oauth1(account)
    file_size = os.path.getsize(video_path)

    # INIT
    resp = http_requests.post(
        TWITTER_MEDIA_UPLOAD_URL,
        data={
            "command": "INIT",
            "media_type": "video/mp4",
            "total_bytes": str(file_size),
            "media_category": "tweet_video",
        },
        auth=auth,
    )
    if resp.status_code != 202:
        raise Exception(f"Media INIT failed: {resp.text}")
    media_id = resp.json()["media_id_string"]
    print(f"   📦 Media INIT: {media_id}")

    # APPEND
    with open(video_path, "rb") as f:
        segment = 0
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            resp = http_requests.post(
                TWITTER_MEDIA_UPLOAD_URL,
                data={"command": "APPEND", "media_id": media_id, "segment_index": segment},
                files={"media": chunk},
                auth=auth,
            )
            if resp.status_code not in (200, 204):
                raise Exception(f"Media APPEND failed: {resp.text}")
            segment += 1
    print(f"   📤 Uploaded {segment} chunk(s)")

    # FINALIZE
    resp = http_requests.post(
        TWITTER_MEDIA_UPLOAD_URL,
        data={"command": "FINALIZE", "media_id": media_id},
        auth=auth,
    )
    if resp.status_code not in (200, 201):
        raise Exception(f"Media FINALIZE failed: {resp.text}")

    # Wait for processing
    processing = resp.json().get("processing_info")
    while processing:
        wait = processing.get("check_after_secs", 5)
        print(f"   ⏳ Processing... (waiting {wait}s)")
        time.sleep(wait)
        resp = http_requests.get(
            TWITTER_MEDIA_UPLOAD_URL,
            params={"command": "STATUS", "media_id": media_id},
            auth=auth,
        )
        processing = resp.json().get("processing_info")
        state = processing.get("state", "") if processing else "succeeded"
        if state == "failed":
            raise Exception(f"Media processing failed: {processing}")
        if state == "succeeded" or not processing:
            break

    print(f"   ✅ Media ready: {media_id}")
    return media_id


def publish_tweet_with_video(text, video_path, account="account_1"):
    """Upload video and post tweet from the specified account."""
    media_id = upload_twitter_media(video_path, account)
    auth = _get_twitter_oauth1(account)
    resp = http_requests.post(
        f"{TWITTER_API_BASE}/tweets",
        json={"text": text, "media": {"media_ids": [media_id]}},
        auth=auth,
    )
    if resp.status_code == 201:
        tweet_data = resp.json().get("data", {})
        print(f"   🐦 Tweeted with video! ID: {tweet_data.get('id')}")
        return tweet_data.get("id")
    raise Exception(f"Tweet+video failed (HTTP {resp.status_code}): {resp.text}")


# ─── Storage Cleanup ─────────────────────────────────────────────────────────

def cleanup_storage(supabase, video_url):
    """Delete video from Supabase Storage after posting."""
    if not video_url:
        return
    try:
        file_name = video_url.split(f"/{BUCKET_NAME}/")[-1]
        if file_name:
            supabase.storage.from_(BUCKET_NAME).remove([file_name])
            print(f"   🗑️  Cleaned up: {file_name}")
    except Exception as e:
        print(f"   ⚠️  Storage cleanup failed: {e}")


# ─── Main Publisher ──────────────────────────────────────────────────────────

def publish_pending_posts():
    """Main function: find due posts and publish them."""
    supabase = get_supabase()
    now = datetime.now(timezone.utc).isoformat()

    # Fetch due pending posts
    result = (
        supabase.table(TABLE_NAME)
        .select("*")
        .eq("status", "pending")
        .lte("scheduled_time", now)
        .order("scheduled_time", desc=False)
        .execute()
    )

    posts = result.data or []

    if not posts:
        print("📭 No pending posts due. Nothing to do.")
        return

    print(f"📬 Found {len(posts)} post(s) due for publishing.\n")

    for post in posts:
        post_id = post["id"]
        platform = post["platform"]
        caption = post["caption"]
        video_url = post.get("video_url")
        twitter_account = post.get("twitter_account", "account_1")
        instagram_account = post.get("instagram_account", "khushal_page")

        # Note: double-publish prevention is handled by .eq("status", "pending")
        # on the final status update below

        print(f"{'='*50}")
        print(f"📋 Post #{post_id} — {platform}")
        print(f"   Caption: {caption[:80]}{'...' if len(caption) > 80 else ''}")
        print(f"   Scheduled: {post['scheduled_time']}")

        video_path = None

        try:
            # Download video if needed
            if video_url:
                video_path = download_video(video_url)

            # Publish based on platform
            if platform == "instagram":
                if not video_path:
                    raise ValueError("Instagram post requires a video")
                publish_to_instagram(video_path, caption, account=instagram_account)

            elif platform == "twitter_text":
                print(f"   🐦 Posting from: {twitter_account}")
                publish_tweet_text(caption, account=twitter_account)

            elif platform == "twitter_video":
                if not video_path:
                    raise ValueError("Twitter video post requires a video")
                print(f"   🐦 Posting from: {twitter_account}")
                publish_tweet_with_video(caption, video_path, account=twitter_account)

            else:
                raise ValueError(f"Unknown platform: {platform}")

            # Mark as posted (atomic: only if still pending — prevents double-publish)
            supabase.table(TABLE_NAME).update({
                "status": "posted",
                "posted_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", post_id).eq("status", "pending").execute()
            print(f"   ✅ Marked as posted")

            # Clean up storage
            if video_url:
                cleanup_storage(supabase, video_url)

        except Exception as e:
            print(f"   ❌ FAILED: {e}")
            supabase.table(TABLE_NAME).update({
                "status": "failed",
                "error_message": str(e)[:500],
            }).eq("id", post_id).eq("status", "pending").execute()

        finally:
            # Clean up temp file
            if video_path and os.path.exists(video_path):
                os.unlink(video_path)

        print()

    print("🏁 Publisher run complete.")


# ─── Entry Point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"🚀 Social Media Publisher")
    print(f"   Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print()
    publish_pending_posts()
