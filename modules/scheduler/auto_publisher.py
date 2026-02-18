"""
In-App Auto-Publisher — Background thread that runs inside the Streamlit app.
Checks Supabase every 60 seconds for due scheduled posts and publishes them.

Works wherever the Streamlit app runs:
    • Local (loads from .env)
    • Streamlit Cloud (loads from st.secrets → os.environ)

Uses the same credential flow as app.py — no separate secrets needed.
"""

import os
import time
import tempfile
import threading
import logging
from datetime import datetime, timezone

import requests as http_requests

# Set up logging
logger = logging.getLogger("auto_publisher")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [Publisher] %(message)s", "%H:%M:%S"))
    logger.addHandler(handler)


# ─── Configuration ───────────────────────────────────────────────────────────

CHECK_INTERVAL = 60  # seconds between checks

# Instagram Graph API
GRAPH_API_URL = "https://graph.facebook.com/v22.0"
RUPLOAD_URL = "https://rupload.facebook.com/ig-api-upload"

# Twitter API
TWITTER_API_BASE = "https://api.twitter.com/2"
TWITTER_MEDIA_UPLOAD_URL = "https://upload.twitter.com/1.1/media/upload.json"
CHUNK_SIZE = 4 * 1024 * 1024  # 4 MB

BUCKET_NAME = "ready_to_publish"
TABLE_NAME = "content_schedule"


# ─── Supabase Client ─────────────────────────────────────────────────────────

def _get_supabase():
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY not available")
    return create_client(url, key)


# ─── Download Helper ─────────────────────────────────────────────────────────

def _download_video(url, suffix=".mp4"):
    """Download a video from URL to a temporary file."""
    resp = http_requests.get(url, stream=True, timeout=120)
    resp.raise_for_status()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    for chunk in resp.iter_content(chunk_size=8192):
        tmp.write(chunk)
    tmp.close()
    return tmp.name


# ─── Instagram Publishing ────────────────────────────────────────────────────

def _get_ig_config(account="khushal_page"):
    """Get Instagram config from environment variables."""
    token = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "")
    accounts = {
        "khushal_page": os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID_1",
                                       os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")),
        "skin_nurture": os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID_2", ""),
    }
    account_id = accounts.get(account, "")
    return token, account_id


def _publish_instagram(video_path, caption, account="khushal_page"):
    """Full Instagram Reel upload pipeline."""
    token, account_id = _get_ig_config(account)
    if not token:
        raise ValueError("Instagram access token not configured")
    if not account_id:
        raise ValueError(f"Instagram Business ID not configured for '{account}'")

    file_size = os.path.getsize(video_path)

    # Step 1: Create container
    resp = http_requests.post(
        f"{GRAPH_API_URL}/{account_id}/media",
        params={
            "media_type": "REELS",
            "upload_type": "resumable",
            "caption": caption,
            "access_token": token,
        },
    )
    data = resp.json()
    if "id" not in data:
        raise Exception(f"Container creation failed: {data}")
    container_id = data["id"]

    # Step 2: Upload binary
    with open(video_path, "rb") as f:
        resp = http_requests.post(
            f"{RUPLOAD_URL}/{container_id}",
            headers={
                "Authorization": f"OAuth {token}",
                "offset": "0",
                "file_size": str(file_size),
                "Content-Type": "application/octet-stream",
            },
            data=f,
        )
    if resp.status_code != 200:
        raise Exception(f"Upload failed: {resp.json()}")

    # Step 3: Poll for processing
    for attempt in range(60):
        resp = http_requests.get(
            f"{GRAPH_API_URL}/{container_id}",
            params={"fields": "status_code,status", "access_token": token},
        )
        status = resp.json().get("status_code", "UNKNOWN")
        if status == "FINISHED":
            break
        if status in ("ERROR", "EXPIRED"):
            raise Exception(f"Processing failed: {resp.json()}")
        time.sleep(5)
    else:
        raise Exception("Processing timeout (300s)")

    # Step 4: Publish
    resp = http_requests.post(
        f"{GRAPH_API_URL}/{account_id}/media_publish",
        params={"creation_id": container_id, "access_token": token},
    )
    data = resp.json()
    if "id" not in data:
        raise Exception(f"Publish failed: {data}")

    return data["id"]


# ─── Twitter Publishing ─────────────────────────────────────────────────────

def _get_twitter_oauth1(account="account_1"):
    """Build OAuth1 auth object for a specific Twitter account."""
    from requests_oauthlib import OAuth1

    consumer_key = os.environ.get("TWITTER_CONSUMER_KEY", "")
    consumer_secret = os.environ.get("TWITTER_CONSUMER_SECRET", "")

    if not consumer_key or not consumer_secret:
        raise ValueError("Twitter consumer key/secret not configured in environment")

    account_tokens = {
        "account_1": {
            "token": os.environ.get("TWITTER_ACCESS_TOKEN_ACCOUNT_1", ""),
            "secret": os.environ.get("TWITTER_ACCESS_TOKEN_SECRET_ACCOUNT_1", ""),
        },
        "account_2": {
            "token": os.environ.get("TWITTER_ACCESS_TOKEN_ACCOUNT_2", ""),
            "secret": os.environ.get("TWITTER_ACCESS_TOKEN_SECRET_ACCOUNT_2", ""),
        },
        "account_3": {
            "token": os.environ.get("TWITTER_ACCESS_TOKEN_ACCOUNT_3", ""),
            "secret": os.environ.get("TWITTER_ACCESS_TOKEN_SECRET_ACCOUNT_3", ""),
        },
    }

    acct = account_tokens.get(account, {})
    if not acct.get("token") or not acct.get("secret"):
        raise ValueError(f"Twitter credentials not configured for '{account}'")

    return OAuth1(consumer_key, consumer_secret, acct["token"], acct["secret"])


def _publish_tweet_text(text, account="account_1"):
    """Post a text-only tweet."""
    auth = _get_twitter_oauth1(account)
    resp = http_requests.post(
        f"{TWITTER_API_BASE}/tweets",
        json={"text": text},
        auth=auth,
        timeout=30,
    )
    if resp.status_code == 201:
        return resp.json().get("data", {}).get("id")
    raise Exception(f"Tweet failed (HTTP {resp.status_code}): {resp.text}")


def _upload_twitter_media(video_path, account="account_1"):
    """Upload video via Twitter v1.1 chunked media upload."""
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
        timeout=30,
    )
    if resp.status_code not in (200, 201, 202):
        raise Exception(f"Media INIT failed: {resp.text}")
    media_id = resp.json()["media_id_string"]

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
                timeout=60,
            )
            if resp.status_code not in (200, 204):
                raise Exception(f"Media APPEND failed: {resp.text}")
            segment += 1

    # FINALIZE
    resp = http_requests.post(
        TWITTER_MEDIA_UPLOAD_URL,
        data={"command": "FINALIZE", "media_id": media_id},
        auth=auth,
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        raise Exception(f"Media FINALIZE failed: {resp.text}")

    # Wait for processing
    processing = resp.json().get("processing_info")
    while processing:
        wait = processing.get("check_after_secs", 5)
        time.sleep(wait)
        resp = http_requests.get(
            TWITTER_MEDIA_UPLOAD_URL,
            params={"command": "STATUS", "media_id": media_id},
            auth=auth,
            timeout=30,
        )
        processing = resp.json().get("processing_info")
        state = processing.get("state", "") if processing else "succeeded"
        if state == "failed":
            raise Exception(f"Media processing failed: {processing}")
        if state == "succeeded" or not processing:
            break

    return media_id


def _publish_tweet_with_video(text, video_path, account="account_1"):
    """Upload video and post tweet."""
    media_id = _upload_twitter_media(video_path, account)
    auth = _get_twitter_oauth1(account)
    resp = http_requests.post(
        f"{TWITTER_API_BASE}/tweets",
        json={"text": text, "media": {"media_ids": [media_id]}},
        auth=auth,
        timeout=30,
    )
    if resp.status_code == 201:
        return resp.json().get("data", {}).get("id")
    raise Exception(f"Tweet+video failed (HTTP {resp.status_code}): {resp.text}")


# ─── Storage Cleanup ─────────────────────────────────────────────────────────

def _cleanup_storage(supabase, video_url):
    """Delete video from Supabase Storage after posting."""
    if not video_url:
        return
    try:
        file_name = video_url.split(f"/{BUCKET_NAME}/")[-1]
        if file_name:
            supabase.storage.from_(BUCKET_NAME).remove([file_name])
    except Exception as e:
        logger.warning(f"Storage cleanup failed: {e}")


# ─── Core Publisher Logic ────────────────────────────────────────────────────

def publish_due_posts():
    """
    Check Supabase for due pending posts and publish them.
    Returns (published_count, failed_count).
    """
    try:
        supabase = _get_supabase()
    except Exception as e:
        logger.error(f"Cannot connect to Supabase: {e}")
        return 0, 0

    now = datetime.now(timezone.utc).isoformat()

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
        return 0, 0

    logger.info(f"Found {len(posts)} due post(s)")

    published = 0
    failed = 0

    for post in posts:
        post_id = post["id"]
        platform = post["platform"]
        caption = post["caption"]
        video_url = post.get("video_url")
        twitter_account = post.get("twitter_account", "account_1")
        instagram_account = post.get("instagram_account", "khushal_page")

        video_path = None

        try:
            # Download video if needed
            if video_url:
                video_path = _download_video(video_url)

            # Publish based on platform
            if platform == "instagram":
                if not video_path:
                    raise ValueError("Instagram post requires a video")
                _publish_instagram(video_path, caption, account=instagram_account)

            elif platform == "twitter_text":
                _publish_tweet_text(caption, account=twitter_account)

            elif platform == "twitter_video":
                if not video_path:
                    raise ValueError("Twitter video post requires a video")
                _publish_tweet_with_video(caption, video_path, account=twitter_account)

            else:
                raise ValueError(f"Unknown platform: {platform}")

            # Mark as posted
            supabase.table(TABLE_NAME).update({
                "status": "posted",
                "posted_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", post_id).execute()

            logger.info(f"✅ Published #{post_id} ({platform})")
            published += 1

            # Clean up storage
            if video_url:
                _cleanup_storage(supabase, video_url)

        except Exception as e:
            logger.error(f"❌ Failed #{post_id} ({platform}): {e}")
            supabase.table(TABLE_NAME).update({
                "status": "failed",
                "error_message": str(e)[:500],
            }).eq("id", post_id).execute()
            failed += 1

        finally:
            if video_path and os.path.exists(video_path):
                os.unlink(video_path)

    return published, failed


# ─── Background Thread ──────────────────────────────────────────────────────

_publisher_thread = None
_publisher_running = False


def _publisher_loop():
    """Background loop that checks for due posts every CHECK_INTERVAL seconds."""
    global _publisher_running
    logger.info(f"🚀 Auto-publisher started (checking every {CHECK_INTERVAL}s)")

    while _publisher_running:
        try:
            published, failed = publish_due_posts()
            if published or failed:
                logger.info(f"Run complete: {published} published, {failed} failed")
        except Exception as e:
            logger.error(f"Publisher error: {e}")

        # Sleep in small increments so we can stop quickly
        for _ in range(CHECK_INTERVAL):
            if not _publisher_running:
                break
            time.sleep(1)

    logger.info("Auto-publisher stopped")


def start_publisher():
    """Start the background auto-publisher thread (idempotent)."""
    global _publisher_thread, _publisher_running

    if _publisher_running and _publisher_thread and _publisher_thread.is_alive():
        return  # Already running

    _publisher_running = True
    _publisher_thread = threading.Thread(target=_publisher_loop, daemon=True)
    _publisher_thread.start()


def stop_publisher():
    """Stop the background auto-publisher thread."""
    global _publisher_running
    _publisher_running = False
