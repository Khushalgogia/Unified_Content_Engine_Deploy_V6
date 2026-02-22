"""
Scheduler DB — Supabase CRUD for content_schedule table & Storage.
Handles queuing, status updates, and file storage for scheduled posts.
"""

import os
import uuid
from datetime import datetime, timezone
from supabase import create_client


# ─── Supabase Client ─────────────────────────────────────────────────────────

def _get_client():
    """Get Supabase client from environment variables."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment")
    return create_client(url, key)


BUCKET_NAME = "ready_to_publish"
TABLE_NAME = "content_schedule"


# ─── Storage Operations ─────────────────────────────────────────────────────

def upload_to_storage(file_path):
    """
    Upload a video file to Supabase Storage bucket.

    Args:
        file_path: Local path to the .mp4 file.

    Returns:
        str: Public URL of the uploaded file.
    """
    client = _get_client()
    file_name = f"{uuid.uuid4().hex}_{os.path.basename(file_path)}"

    with open(file_path, "rb") as f:
        client.storage.from_(BUCKET_NAME).upload(
            path=file_name,
            file=f,
            file_options={"content-type": "video/mp4"},
        )

    public_url = client.storage.from_(BUCKET_NAME).get_public_url(file_name)
    print(f"   ☁️  Uploaded to Storage: {file_name}")
    return public_url


def delete_from_storage(video_url):
    """
    Delete a file from Supabase Storage using its public URL.

    Args:
        video_url: Public URL of the file in Storage.
    """
    if not video_url:
        return

    client = _get_client()

    # Extract filename from public URL
    # URL format: https://<project>.supabase.co/storage/v1/object/public/ready_to_publish/<filename>
    try:
        file_name = video_url.split(f"/{BUCKET_NAME}/")[-1]
        if file_name:
            client.storage.from_(BUCKET_NAME).remove([file_name])
            print(f"   🗑️  Removed from Storage: {file_name}")
    except Exception as e:
        print(f"   ⚠️  Storage cleanup failed: {e}")


# ─── Database Operations ─────────────────────────────────────────────────────

def insert_schedule(platform, video_url, caption, scheduled_time, twitter_account=None, instagram_account=None, reply_to_tweet_id=None):
    """
    Insert a new scheduled post into the database.

    Args:
        platform: "instagram", "twitter_text", or "twitter_video"
        video_url: Public URL from Storage (None for text-only tweets)
        caption: The text/caption to post
        scheduled_time: datetime (timezone-aware) when to post
        twitter_account: Twitter account name (None for Instagram)
        instagram_account: Instagram account name (None for Twitter)
        reply_to_tweet_id: Tweet ID to reply to (None for original posts)

    Returns:
        dict: The inserted row data.
    """
    client = _get_client()

    data = {
        "platform": platform,
        "video_url": video_url,
        "caption": caption,
        "scheduled_time": scheduled_time.isoformat(),
        "status": "pending",
        "twitter_account": twitter_account,
        "instagram_account": instagram_account,
    }

    # Only include reply_to_tweet_id if it has a value
    if reply_to_tweet_id:
        data["reply_to_tweet_id"] = reply_to_tweet_id

    try:
        result = client.table(TABLE_NAME).insert(data).execute()
    except Exception as e:
        # If the column doesn't exist yet, retry without it
        if "reply_to_tweet_id" in str(e) and reply_to_tweet_id:
            print(f"   ⚠️ reply_to_tweet_id column missing — scheduling without reply chain")
            data.pop("reply_to_tweet_id", None)
            result = client.table(TABLE_NAME).insert(data).execute()
        else:
            raise

    reply_tag = f" (reply to {reply_to_tweet_id})" if reply_to_tweet_id else ""
    print(f"   📋 Scheduled: {platform} at {scheduled_time.strftime('%Y-%m-%d %H:%M')}{reply_tag}")
    return result.data[0] if result.data else {}


def get_pending_posts():
    """
    Fetch all pending posts where scheduled_time <= now.

    Returns:
        list[dict]: List of due pending posts.
    """
    client = _get_client()
    now = datetime.now(timezone.utc).isoformat()

    result = (
        client.table(TABLE_NAME)
        .select("*")
        .eq("status", "pending")
        .lte("scheduled_time", now)
        .order("scheduled_time", desc=False)
        .execute()
    )
    return result.data or []


def get_all_scheduled(status=None):
    """
    List all scheduled posts, optionally filtered by status.

    Args:
        status: "pending", "posted", "failed", or None for all.

    Returns:
        list[dict]: List of scheduled posts.
    """
    client = _get_client()

    query = client.table(TABLE_NAME).select("*")
    if status:
        query = query.eq("status", status)

    result = query.order("scheduled_time", desc=True).execute()
    return result.data or []


def get_last_scheduled_time(platform=None, twitter_account=None):
    """
    Get the scheduled_time of the most recent pending post,
    optionally filtered by platform and twitter_account.

    Different accounts are independent — scheduling for account_2
    should NOT consume a slot that belongs to account_1.

    Args:
        platform: Filter by platform (e.g. "instagram", "twitter_text")
        twitter_account: Filter by Twitter account name

    Returns:
        datetime or None: The latest pending scheduled time, or None.
    """
    client = _get_client()

    query = (
        client.table(TABLE_NAME)
        .select("scheduled_time")
        .eq("status", "pending")
    )

    if platform:
        query = query.eq("platform", platform)
    if twitter_account:
        query = query.eq("twitter_account", twitter_account)

    result = (
        query
        .order("scheduled_time", desc=True)
        .limit(1)
        .execute()
    )

    if result.data:
        from dateutil.parser import parse as parse_dt
        return parse_dt(result.data[0]["scheduled_time"])

    return None


def mark_posted(post_id):
    """
    Mark a scheduled post as successfully posted.

    Args:
        post_id: The ID of the post in content_schedule.
    """
    client = _get_client()
    client.table(TABLE_NAME).update({
        "status": "posted",
        "posted_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", post_id).execute()
    print(f"   ✅ Marked as posted: #{post_id}")


def mark_failed(post_id, error_message):
    """
    Mark a scheduled post as failed with error details.

    Args:
        post_id: The ID of the post.
        error_message: Description of what went wrong.
    """
    client = _get_client()
    client.table(TABLE_NAME).update({
        "status": "failed",
        "error_message": str(error_message)[:500],
    }).eq("id", post_id).execute()
    print(f"   ❌ Marked as failed: #{post_id} — {error_message}")


def delete_schedule(post_id):
    """
    Delete a scheduled post and its associated storage file.

    Args:
        post_id: The ID of the post to delete.
    """
    client = _get_client()

    # First get the video_url so we can clean up storage
    result = (
        client.table(TABLE_NAME)
        .select("video_url")
        .eq("id", post_id)
        .execute()
    )

    if result.data and result.data[0].get("video_url"):
        delete_from_storage(result.data[0]["video_url"])

    # Delete the DB row
    client.table(TABLE_NAME).delete().eq("id", post_id).execute()
    print(f"   🗑️  Deleted schedule #{post_id}")


def update_schedule_time(post_id, new_time):
    """
    Update the scheduled_time of a pending post.

    Args:
        post_id: The ID of the post to update.
        new_time: datetime (timezone-aware) — the new scheduled time.
    """
    client = _get_client()
    client.table(TABLE_NAME).update({
        "scheduled_time": new_time.isoformat(),
    }).eq("id", post_id).eq("status", "pending").execute()
    print(f"   ⏰ Rescheduled #{post_id} → {new_time.strftime('%Y-%m-%d %H:%M')}")


def format_time_ist(iso_string):
    """
    Convert an ISO timestamp string to a readable IST format.

    Args:
        iso_string: ISO 8601 timestamp string (e.g. from Supabase).

    Returns:
        str: e.g. "Sat, Feb 15 at 09:00 AM IST"
    """
    if not iso_string or iso_string == "N/A":
        return "N/A"

    try:
        from dateutil.parser import parse as parse_dt
        import pytz

        dt = parse_dt(iso_string)
        ist = pytz.timezone("Asia/Kolkata")

        if dt.tzinfo is None:
            dt = pytz.utc.localize(dt)

        dt_ist = dt.astimezone(ist)
        return dt_ist.strftime("%a, %b %d at %I:%M %p IST")
    except Exception:
        return str(iso_string)[:16]


def retry_failed(post_id, new_time=None):
    """
    Reset a failed post back to 'pending' so it will be retried.

    Args:
        post_id: The ID of the failed post.
        new_time: Optional new scheduled_time (datetime, tz-aware).
                  If None, schedules for 2 minutes from now.
    """
    client = _get_client()
    if new_time is None:
        from datetime import timedelta
        new_time = datetime.now(timezone.utc) + timedelta(minutes=2)

    client.table(TABLE_NAME).update({
        "status": "pending",
        "error_message": None,
        "scheduled_time": new_time.isoformat(),
    }).eq("id", post_id).execute()
    print(f"   🔄 Retrying #{post_id} → {new_time.strftime('%Y-%m-%d %H:%M')}")


def retry_all_failed():
    """
    Reset ALL failed posts back to 'pending' for retry.
    Each post is scheduled 2 minutes apart starting from now.

    Returns:
        int: Number of posts reset.
    """
    client = _get_client()
    from datetime import timedelta

    result = (
        client.table(TABLE_NAME)
        .select("id")
        .eq("status", "failed")
        .order("scheduled_time", desc=False)
        .execute()
    )
    failed_posts = result.data or []

    now = datetime.now(timezone.utc)
    for i, post in enumerate(failed_posts):
        new_time = now + timedelta(minutes=2 * (i + 1))
        client.table(TABLE_NAME).update({
            "status": "pending",
            "error_message": None,
            "scheduled_time": new_time.isoformat(),
        }).eq("id", post["id"]).execute()

    if failed_posts:
        print(f"   🔄 Reset {len(failed_posts)} failed post(s) to pending")
    return len(failed_posts)

