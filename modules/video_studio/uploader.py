"""
Instagram Graph API Uploader — Resumable Upload Protocol
Refactored for Unified Content Engine — no changes to core logic,
credentials passed in as arguments.
"""

import os
import time
import requests


# ─── Constants ────────────────────────────────────────────────────────────────

GRAPH_API_URL = "https://graph.facebook.com/v22.0"
RUPLOAD_URL = "https://rupload.facebook.com/ig-api-upload"

STATUS_CHECK_INTERVAL = 5
STATUS_CHECK_MAX_RETRIES = 60


# ─── Custom Exception ────────────────────────────────────────────────────────

class UploadError(Exception):
    """Raised when an Instagram API call fails."""
    def __init__(self, message, api_response=None):
        super().__init__(message)
        self.api_response = api_response


# ─── Step 1: Initialize Upload Container ─────────────────────────────────────

def initialize_upload(access_token, ig_user_id, file_path, caption=""):
    """Create a media container for resumable upload."""
    file_size = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)

    url = f"{GRAPH_API_URL}/{ig_user_id}/media"
    params = {
        "media_type": "REELS",
        "upload_type": "resumable",
        "caption": caption,
        "access_token": access_token,
    }

    print(f"   📦 Initializing upload container...")
    print(f"      File: {file_name} ({file_size / (1024*1024):.1f} MB)")

    response = requests.post(url, params=params)
    data = response.json()

    if "id" not in data:
        error_msg = data.get("error", {}).get("message", "Unknown error")
        raise UploadError(
            f"Failed to create media container: {error_msg}",
            api_response=data
        )

    container_id = data["id"]
    print(f"   ✅ Container created: {container_id}")
    return container_id


# ─── Step 2: Upload Binary File ──────────────────────────────────────────────

def upload_file(access_token, container_id, file_path):
    """Upload the video file binary to Instagram's resumable upload endpoint."""
    file_size = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)

    upload_url = f"{RUPLOAD_URL}/{container_id}"

    headers = {
        "Authorization": f"OAuth {access_token}",
        "offset": "0",
        "file_size": str(file_size),
        "Content-Type": "application/octet-stream",
    }

    print(f"   📤 Uploading {file_name} ({file_size / (1024*1024):.1f} MB)...")

    with open(file_path, "rb") as f:
        response = requests.post(upload_url, headers=headers, data=f)

    data = response.json()

    if response.status_code != 200:
        error_msg = data.get("error", {}).get("message", f"HTTP {response.status_code}")
        raise UploadError(
            f"File upload failed: {error_msg}",
            api_response=data
        )

    print(f"   ✅ File uploaded successfully")
    return data


# ─── Step 3: Check Processing Status ─────────────────────────────────────────

def check_status(access_token, container_id):
    """Poll the container status until processing is FINISHED."""
    url = f"{GRAPH_API_URL}/{container_id}"
    params = {
        "fields": "status_code,status",
        "access_token": access_token,
    }

    print(f"   🔄 Waiting for Instagram to process video...")

    for attempt in range(1, STATUS_CHECK_MAX_RETRIES + 1):
        response = requests.get(url, params=params)
        data = response.json()

        status_code = data.get("status_code", "UNKNOWN")

        if status_code == "FINISHED":
            print(f"   ✅ Processing complete! (took ~{attempt * STATUS_CHECK_INTERVAL}s)")
            return status_code

        if status_code == "ERROR":
            error_detail = data.get("status", "No details provided")
            raise UploadError(
                f"Instagram processing failed: {error_detail}",
                api_response=data
            )

        if status_code == "EXPIRED":
            raise UploadError(
                "Upload container expired before processing completed",
                api_response=data
            )

        print(f"      ⏳ Status: {status_code} (attempt {attempt}/{STATUS_CHECK_MAX_RETRIES})")
        time.sleep(STATUS_CHECK_INTERVAL)

    raise UploadError(
        f"Timeout: processing did not complete within "
        f"{STATUS_CHECK_MAX_RETRIES * STATUS_CHECK_INTERVAL} seconds"
    )


# ─── Step 4: Publish ─────────────────────────────────────────────────────────

def publish(access_token, ig_user_id, container_id):
    """Publish the processed media container."""
    url = f"{GRAPH_API_URL}/{ig_user_id}/media_publish"
    params = {
        "creation_id": container_id,
        "access_token": access_token,
    }

    print(f"   📢 Publishing Reel...")

    response = requests.post(url, params=params)
    data = response.json()

    if "id" not in data:
        error_msg = data.get("error", {}).get("message", "Unknown error")
        raise UploadError(
            f"Publish failed: {error_msg}",
            api_response=data
        )

    media_id = data["id"]
    print(f"   ✅ Published! Media ID: {media_id}")
    return media_id


# ─── Bonus: Get Permalink ────────────────────────────────────────────────────

def get_permalink(access_token, media_id):
    """Fetch the public URL of a published Instagram post."""
    url = f"{GRAPH_API_URL}/{media_id}"
    params = {
        "fields": "permalink",
        "access_token": access_token,
    }

    response = requests.get(url, params=params)
    data = response.json()

    return data.get("permalink")


# ─── Orchestrator ─────────────────────────────────────────────────────────────

def upload_reel(access_token, ig_user_id, file_path, caption=""):
    """
    Full upload pipeline: init → upload → poll → publish → permalink.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Video file not found: {file_path}")

    if not file_path.lower().endswith(".mp4"):
        raise ValueError(f"Only .mp4 files are supported. Got: {file_path}")

    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    print(f"\n{'='*60}")
    print(f"📤 INSTAGRAM REEL UPLOAD")
    print(f"{'='*60}")
    print(f"   File: {os.path.basename(file_path)} ({file_size_mb:.1f} MB)")
    print(f"   Caption: {caption[:80]}{'...' if len(caption) > 80 else ''}")
    print()

    container_id = initialize_upload(access_token, ig_user_id, file_path, caption)
    upload_file(access_token, container_id, file_path)
    check_status(access_token, container_id)
    media_id = publish(access_token, ig_user_id, container_id)
    permalink = get_permalink(access_token, media_id)

    print()
    print(f"{'='*60}")
    if permalink:
        print(f"🎉 REEL POSTED SUCCESSFULLY!")
        print(f"   🔗 {permalink}")
    else:
        print(f"🎉 REEL POSTED! (Media ID: {media_id})")
        print(f"   ⚠️ Permalink not yet available (may take a moment)")
    print(f"{'='*60}")

    return {
        "media_id": media_id,
        "permalink": permalink,
        "container_id": container_id,
    }
