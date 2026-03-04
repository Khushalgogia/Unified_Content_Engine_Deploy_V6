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
RUPLOAD_URL = "https://rupload.facebook.com/ig-api-upload"

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

def publish_to_instagram(video_path, caption, account="khushal_page", video_url=None):
    """
    Full Instagram Reel upload pipeline using video_url method.
    If video_url is provided, it's passed directly to the Graph API (no binary upload).
    If only video_path is provided, we upload it to a temporary public URL first.
    Includes retry logic for transient processing errors.
    """
    if not IG_ACCESS_TOKEN:
        raise ValueError("Instagram access token not configured")

    acct = INSTAGRAM_ACCOUNTS.get(account)
    if not acct or not acct.get("id"):
        raise ValueError(f"Instagram Business ID not configured for '{account}'")
    ig_account_id = acct["id"]
    print(f"   📸 Posting to: {acct.get('label', account)}")

    # If no video_url provided but we have a local file, we need a public URL
    if not video_url and video_path:
        try:
            supabase = get_supabase()
            temp_name = f"temp_ig_upload_{os.path.basename(video_path)}"
            with open(video_path, "rb") as f:
                video_bytes = f.read()
            try:
                supabase.storage.from_(BUCKET_NAME).remove([temp_name])
            except Exception:
                pass
            supabase.storage.from_(BUCKET_NAME).upload(
                path=temp_name, file=video_bytes,
                file_options={"content-type": "video/mp4"},
            )
            video_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{temp_name}"
            print(f"   ☁️ Uploaded to temp storage: {temp_name}")
        except Exception as e:
            raise Exception(f"Cannot create public video URL for Instagram upload: {e}")

    if not video_url:
        raise ValueError("No video URL available for Instagram upload")

    import time
    last_error = None

    # Retry up to 2 times for transient processing errors (e.g. App ID mismatch)
    for attempt in range(1, 3):
        if attempt > 1:
            print(f"   🔄 Retry {attempt}/2 — creating fresh container...")
            time.sleep(10)

        # Step 1: Create container with video_url
        print(f"   📦 Creating Instagram container (video_url method)...")
        resp = http_requests.post(
            f"{GRAPH_API_URL}/{ig_account_id}/media",
            params={
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption,
                "access_token": IG_ACCESS_TOKEN,
            },
        )
        data = resp.json()
        if "id" not in data:
            raise Exception(f"Container creation failed: {data}")
        container_id = data["id"]
        print(f"   ✅ Container: {container_id}")

        # Step 2: Poll for processing
        print(f"   🔄 Waiting for processing...")
        processing_ok = False
        for poll in range(60):
            resp = http_requests.get(
                f"{GRAPH_API_URL}/{container_id}",
                params={"fields": "status_code,status", "access_token": IG_ACCESS_TOKEN},
            )
            status_data = resp.json()
            status = status_data.get("status_code", "UNKNOWN")
            if status == "FINISHED":
                print(f"   ✅ Processing complete ({poll * 5}s)")
                processing_ok = True
                break
            if status in ("ERROR", "EXPIRED"):
                last_error = f"Processing failed: {status_data}"
                print(f"   ⚠️ {last_error}")
                break
            time.sleep(5)
        else:
            last_error = "Processing timeout (300s)"
            print(f"   ⚠️ {last_error}")

        if not processing_ok:
            continue  # Retry with fresh container

        # Small delay before publish
        time.sleep(5)

        # Step 3: Publish (with publish retry)
        print(f"   📢 Publishing Reel...")
        for pub_attempt in range(1, 4):
            if pub_attempt > 1:
                print(f"      🔄 Publish retry {pub_attempt}/3 (waiting 10s)...")
                time.sleep(10)
            resp = http_requests.post(
                f"{GRAPH_API_URL}/{ig_account_id}/media_publish",
                params={"creation_id": container_id, "access_token": IG_ACCESS_TOKEN},
            )
            data = resp.json()
            if "id" in data:
                media_id = data["id"]
                print(f"   🎉 Published! Media ID: {media_id}")
                return media_id
            error_msg = data.get("error", {}).get("message", "")
            if "invalid" in error_msg.lower() or "not ready" in error_msg.lower():
                continue  # Retry publish
            last_error = f"Publish failed: {data}"
            break

    raise Exception(last_error or "Instagram upload failed after all retries")


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


def publish_tweet_text(text, account="account_1", reply_to_tweet_id=None):
    """Post a text-only tweet from the specified account.
    Retries with timestamp suffix on 403 (duplicate content).
    If reply_to_tweet_id is set, posts as a reply to that tweet.
    """
    auth = _get_twitter_oauth1(account)
    payload = {"text": text}
    if reply_to_tweet_id:
        payload["reply"] = {"in_reply_to_tweet_id": str(reply_to_tweet_id)}
    resp = http_requests.post(
        f"{TWITTER_API_BASE}/tweets",
        json=payload,
        auth=auth,
    )
    if resp.status_code == 201:
        tweet_data = resp.json().get("data", {})
        print(f"   🐦 Tweeted! ID: {tweet_data.get('id')}")
        return tweet_data.get("id")

    # Handle 403 — often means duplicate content
    if resp.status_code == 403:
        print(f"   ⚠️ Got 403 (likely duplicate). Retrying with timestamp...")
        suffix = f" [{datetime.now(timezone.utc).strftime('%H:%M')}]"
        modified_text = text[:280 - len(suffix)] + suffix
        payload2 = {"text": modified_text}
        if reply_to_tweet_id:
            payload2["reply"] = {"in_reply_to_tweet_id": str(reply_to_tweet_id)}
        resp2 = http_requests.post(
            f"{TWITTER_API_BASE}/tweets",
            json=payload2,
            auth=auth,
        )
        if resp2.status_code == 201:
            tweet_data = resp2.json().get("data", {})
            print(f"   🐦 Tweeted (with timestamp)! ID: {tweet_data.get('id')}")
            return tweet_data.get("id")
        raise Exception(f"Tweet failed after retry (HTTP {resp2.status_code}): {resp2.text}")

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
    if resp.status_code not in (200, 201, 202):
        raise Exception(f"Media INIT failed (HTTP {resp.status_code}): {resp.text}")
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


def publish_tweet_with_video(text, video_path, account="account_1", reply_to_tweet_id=None):
    """Upload video and post tweet from the specified account.
    Retries with timestamp suffix on 403 (duplicate content).
    If reply_to_tweet_id is set, posts as a reply to that tweet.
    """
    media_id = upload_twitter_media(video_path, account)
    auth = _get_twitter_oauth1(account)
    payload = {"text": text, "media": {"media_ids": [media_id]}}
    if reply_to_tweet_id:
        payload["reply"] = {"in_reply_to_tweet_id": str(reply_to_tweet_id)}
    resp = http_requests.post(
        f"{TWITTER_API_BASE}/tweets",
        json=payload,
        auth=auth,
    )
    if resp.status_code == 201:
        tweet_data = resp.json().get("data", {})
        print(f"   🐦 Tweeted with video! ID: {tweet_data.get('id')}")
        return tweet_data.get("id")

    # Handle 403 — often means duplicate content
    if resp.status_code == 403:
        print(f"   ⚠️ Got 403 (likely duplicate). Retrying with timestamp...")
        suffix = f" [{datetime.now(timezone.utc).strftime('%H:%M')}]"
        modified_text = text[:280 - len(suffix)] + suffix
        payload2 = {"text": modified_text, "media": {"media_ids": [media_id]}}
        if reply_to_tweet_id:
            payload2["reply"] = {"in_reply_to_tweet_id": str(reply_to_tweet_id)}
        resp2 = http_requests.post(
            f"{TWITTER_API_BASE}/tweets",
            json=payload2,
            auth=auth,
        )
        if resp2.status_code == 201:
            tweet_data = resp2.json().get("data", {})
            print(f"   🐦 Tweeted with video (with timestamp)! ID: {tweet_data.get('id')}")
            return tweet_data.get("id")
        raise Exception(f"Tweet+video failed after retry (HTTP {resp2.status_code}): {resp2.text}")

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
        reply_to_tweet_id = post.get("reply_to_tweet_id")

        # ── Atomic claim: prevent double-posting ──────────────────────────
        # Set posted_at to now ONLY if still 'pending' with no posted_at.
        # If another scheduler already claimed it, this update affects 0 rows.
        claim_time = datetime.now(timezone.utc).isoformat()
        claim = supabase.table(TABLE_NAME).update({
            "posted_at": claim_time,
        }).eq("id", post_id).eq("status", "pending").is_("posted_at", "null").execute()

        if not claim.data:
            print(f"   ⏭  Post #{post_id} already claimed by another scheduler, skipping.")
            continue

        print(f"{'='*50}")
        print(f"📋 Post #{post_id} — {platform}")
        print(f"   Caption: {caption[:80]}{'...' if len(caption) > 80 else ''}")
        print(f"   Scheduled: {post['scheduled_time']}")
        if reply_to_tweet_id:
            print(f"   ↩️ Reply to tweet: {reply_to_tweet_id}")

        video_path = None

        try:
            # Download video if needed
            if video_url:
                video_path = download_video(video_url)

            # Publish based on platform
            if platform == "instagram":
                if not video_url and not video_path:
                    raise ValueError("Instagram post requires a video")
                publish_to_instagram(video_path, caption, account=instagram_account, video_url=video_url)

            elif platform == "twitter_text":
                print(f"   🐦 Posting from: {twitter_account}")
                publish_tweet_text(caption, account=twitter_account, reply_to_tweet_id=reply_to_tweet_id)

            elif platform == "twitter_video":
                if not video_path:
                    raise ValueError("Twitter video post requires a video")
                print(f"   🐦 Posting from: {twitter_account}")
                publish_tweet_with_video(caption, video_path, account=twitter_account, reply_to_tweet_id=reply_to_tweet_id)

            else:
                raise ValueError(f"Unknown platform: {platform}")

            # Mark as posted (posted_at already set by claim)
            supabase.table(TABLE_NAME).update({
                "status": "posted",
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
                "posted_at": None,
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
