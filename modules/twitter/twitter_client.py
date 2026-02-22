"""
Twitter / X API v2 Client
Supports:
    • OAuth 1.0a   — developer app-owner account (tokens never expire)
    • OAuth 2.0    — browser-authorized accounts (with auto-refresh)
    • Media uploads via Twitter v1.1 chunked upload API (OAuth 1.0a only)

Usage:
    from modules.twitter.twitter_client import TwitterClient, list_accounts, list_sample_videos
    client = TwitterClient("account_1")
    result = client.post_tweet("Hello from the engine!")
"""

import json
import math
import os
import time

import requests
from dotenv import load_dotenv
from pathlib import Path

# ─── Paths ────────────────────────────────────────────────────────────────────
# Resolve relative to THIS file's parent (modules/twitter/)
MODULE_DIR = Path(__file__).resolve().parent
CREDS_DIR = MODULE_DIR / "credentials"
VIDEOS_DIR = MODULE_DIR / "videos"

# Load env from project root
PROJECT_ROOT = MODULE_DIR.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# ─── Twitter API Config ──────────────────────────────────────────────────────
CLIENT_ID = os.getenv("TWITTER_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("TWITTER_CLIENT_SECRET", "")

API_BASE = "https://api.twitter.com/2"
TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
MEDIA_UPLOAD_URL = "https://upload.twitter.com/1.1/media/upload.json"
CHUNK_SIZE = 4 * 1024 * 1024  # 4 MB


# ─── Exceptions ───────────────────────────────────────────────────────────────

class TwitterClientError(Exception):
    """General API error."""

class TokenExpiredError(TwitterClientError):
    """Access token expired and could not be refreshed."""


# ─── Helper Functions ─────────────────────────────────────────────────────────

def list_accounts() -> list[str]:
    """Return names of all credential files (without .json extension)."""
    if not CREDS_DIR.exists():
        return []
    return sorted([
        f.stem for f in CREDS_DIR.glob("*.json")
        if not f.name.startswith(".")
    ])

# Alias for UI imports
get_available_accounts = list_accounts


def list_sample_videos() -> list[str]:
    """Return list of .mp4 filenames in the videos directory."""
    if not VIDEOS_DIR.exists():
        return []
    return sorted([
        f.name for f in VIDEOS_DIR.iterdir()
        if f.suffix.lower() in (".mp4", ".mov") and not f.name.startswith(".")
    ])




# ─── Client ──────────────────────────────────────────────────────────────────

class TwitterClient:
    """Lightweight Twitter API v2 client."""

    def __init__(self, account_name: str):
        self.account_name = account_name
        self.creds_path = CREDS_DIR / f"{account_name}.json"

        if not self.creds_path.exists():
            raise FileNotFoundError(
                f"Credentials not found: {self.creds_path}\n"
                f"Available accounts: {list_accounts()}"
            )

        self._load_creds()

    # ── Credentials ───────────────────────────────────────────────────────

    def _load_creds(self):
        """Load credentials from JSON file and detect auth type."""
        with open(self.creds_path, "r") as f:
            data = json.load(f)

        self.auth_type = data.get("auth_type", "oauth2")

        if self.auth_type == "oauth1":
            # OAuth 1.0a — owner account (tokens never expire)
            self.api_key = data["api_key"]
            self.api_secret = data["api_secret"]
            self.access_token = data["access_token"]
            self.access_token_secret = data["access_token_secret"]
        else:
            # OAuth 2.0 — browser-authorized accounts
            self.access_token = data["access_token"]
            self.refresh_token = data.get("refresh_token")
            self.expires_in = data.get("expires_in", 7200)
            self.created_at = data.get("created_at", 0)

    def _save_creds(self):
        """Persist updated tokens back to disk."""
        with open(self.creds_path, "r") as f:
            data = json.load(f)

        data["access_token"] = self.access_token
        if self.auth_type == "oauth2":
            data["refresh_token"] = self.refresh_token
            data["expires_in"] = self.expires_in
            data["created_at"] = self.created_at

        with open(self.creds_path, "w") as f:
            json.dump(data, f, indent=2)

    def _refresh_access_token(self):
        """Use the refresh token to get a new access token (OAuth 2.0 only)."""
        if self.auth_type == "oauth1":
            return  # Nothing to refresh

        if not self.refresh_token:
            raise TokenExpiredError(
                f"No refresh token for '{self.account_name}'. "
                f"Re-run: python twitter_auth.py --name {self.account_name}"
            )

        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
            },
            auth=(CLIENT_ID, CLIENT_SECRET),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )

        if resp.status_code != 200:
            raise TokenExpiredError(
                f"Token refresh failed (HTTP {resp.status_code}): {resp.text}\n"
                f"Re-run: python twitter_auth.py --name {self.account_name}"
            )

        token_data = resp.json()
        self.access_token = token_data["access_token"]
        self.refresh_token = token_data.get("refresh_token", self.refresh_token)
        self.expires_in = token_data.get("expires_in", 7200)
        self.created_at = time.time()
        self._save_creds()

    @property
    def supports_media_upload(self) -> bool:
        """Whether this account supports media uploads (OAuth 1.0a only)."""
        return self.auth_type == "oauth1"

    # ── HTTP Helpers ──────────────────────────────────────────────────────

    def _get_oauth1(self):
        """Build OAuth1 auth object for requests."""
        from requests_oauthlib import OAuth1
        return OAuth1(
            self.api_key,
            client_secret=self.api_secret,
            resource_owner_key=self.access_token,
            resource_owner_secret=self.access_token_secret,
        )

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Make an authenticated API request."""
        if self.auth_type == "oauth1":
            kwargs["auth"] = self._get_oauth1()
        else:
            kwargs.setdefault("headers", {})
            kwargs["headers"]["Authorization"] = f"Bearer {self.access_token}"

        kwargs.setdefault("timeout", 30)
        return requests.request(method, url, **kwargs)

    # ── API Methods ───────────────────────────────────────────────────────

    def get_me(self) -> dict:
        """
        Return authenticated user info.
        Returns dict with 'id', 'name', 'username'.
        """
        resp = self._request("GET", f"{API_BASE}/users/me")

        if resp.status_code == 200:
            return resp.json().get("data", {})
        elif resp.status_code == 401 and self.auth_type == "oauth2":
            self._refresh_access_token()
            resp = self._request("GET", f"{API_BASE}/users/me")
            if resp.status_code == 200:
                return resp.json().get("data", {})

        raise TwitterClientError(
            f"Failed to get user info (HTTP {resp.status_code}): {resp.text}"
        )

    def post_tweet(self, text: str, reply_to_tweet_id: str = None) -> dict:
        """
        Post a tweet. Returns the tweet data dict with 'id' and 'text'.
        If reply_to_tweet_id is provided, posts as a reply to that tweet.
        """
        if not text or not text.strip():
            raise ValueError("Tweet text cannot be empty")
        if len(text) > 280:
            raise ValueError(f"Tweet too long ({len(text)} chars, max 280)")

        payload = {"text": text}
        if reply_to_tweet_id:
            payload["reply"] = {"in_reply_to_tweet_id": str(reply_to_tweet_id)}

        resp = self._request("POST", f"{API_BASE}/tweets", json=payload)

        if resp.status_code == 201:
            return resp.json().get("data", {})
        elif resp.status_code == 401 and self.auth_type == "oauth2":
            self._refresh_access_token()
            resp = self._request("POST", f"{API_BASE}/tweets", json=payload)
            if resp.status_code == 201:
                return resp.json().get("data", {})
        elif resp.status_code == 429:
            raise TwitterClientError(
                "Rate limit exceeded. Free tier allows 500 posts/month. "
                "Try again later or upgrade your API plan."
            )

        raise TwitterClientError(
            f"Failed to post tweet (HTTP {resp.status_code}): {resp.text}"
        )

    # ── Media Upload (v1.1 chunked) ──────────────────────────────────────

    def upload_media(self, file_path: str) -> str:
        """
        Upload a video file via Twitter v1.1 chunked media upload.
        Returns the media_id_string to use in post_tweet_with_media().

        Requires OAuth 1.0a. Run 'python twitter_oauth1_auth.py <account>'
        to authorize an account with OAuth 1.0a.
        """
        if self.auth_type != "oauth1":
            raise TwitterClientError(
                f"Account '{self.account_name}' uses OAuth 2.0 which doesn't support media uploads.\n"
                f"Fix: Run 'python twitter_oauth1_auth.py {self.account_name}' to upgrade to OAuth 1.0a."
            )

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Video file not found: {file_path}")

        file_size = os.path.getsize(file_path)
        file_name = os.path.basename(file_path)

        # Determine media type
        ext = os.path.splitext(file_path)[1].lower()
        media_type_map = {
            ".mp4": "video/mp4",
            ".mov": "video/quicktime",
            ".gif": "image/gif",
        }
        media_type = media_type_map.get(ext, "video/mp4")
        media_category = "tweet_video" if "video" in media_type else "tweet_image"

        auth = self._get_oauth1()

        # ── INIT ──
        init_data = {
            "command": "INIT",
            "total_bytes": file_size,
            "media_type": media_type,
            "media_category": media_category,
        }
        resp = requests.post(MEDIA_UPLOAD_URL, data=init_data, auth=auth, timeout=30)
        if resp.status_code not in (200, 201, 202):
            raise TwitterClientError(
                f"Media upload INIT failed (HTTP {resp.status_code}): {resp.text}"
            )
        media_id = resp.json()["media_id_string"]

        # ── APPEND (chunked) ──
        total_chunks = math.ceil(file_size / CHUNK_SIZE)
        with open(file_path, "rb") as f:
            for segment_index in range(total_chunks):
                chunk = f.read(CHUNK_SIZE)
                append_data = {
                    "command": "APPEND",
                    "media_id": media_id,
                    "segment_index": segment_index,
                }
                files = {"media": (file_name, chunk, media_type)}
                resp = requests.post(
                    MEDIA_UPLOAD_URL, data=append_data, files=files,
                    auth=auth, timeout=60
                )
                if resp.status_code not in (200, 204):
                    raise TwitterClientError(
                        f"Media upload APPEND failed at chunk {segment_index} "
                        f"(HTTP {resp.status_code}): {resp.text}"
                    )

        # ── FINALIZE ──
        finalize_data = {
            "command": "FINALIZE",
            "media_id": media_id,
        }
        resp = requests.post(MEDIA_UPLOAD_URL, data=finalize_data, auth=auth, timeout=30)
        if resp.status_code not in (200, 201):
            raise TwitterClientError(
                f"Media upload FINALIZE failed (HTTP {resp.status_code}): {resp.text}"
            )

        result = resp.json()

        # ── Poll processing_info if present (async video processing) ──
        if "processing_info" in result:
            self._wait_for_media_processing(media_id, auth)

        return media_id

    def _wait_for_media_processing(self, media_id: str, auth):
        """Poll until Twitter finishes processing an uploaded video."""
        max_wait = 120  # seconds
        waited = 0

        while waited < max_wait:
            resp = requests.get(
                MEDIA_UPLOAD_URL,
                params={"command": "STATUS", "media_id": media_id},
                auth=auth,
                timeout=30,
            )
            if resp.status_code != 200:
                raise TwitterClientError(
                    f"Media STATUS check failed (HTTP {resp.status_code}): {resp.text}"
                )

            info = resp.json().get("processing_info", {})
            state = info.get("state", "succeeded")

            if state == "succeeded":
                return
            elif state == "failed":
                error = info.get("error", {}).get("message", "Unknown error")
                raise TwitterClientError(f"Media processing failed: {error}")

            wait_secs = info.get("check_after_secs", 5)
            time.sleep(wait_secs)
            waited += wait_secs

        raise TwitterClientError(
            f"Media processing timed out after {max_wait}s for media_id={media_id}"
        )

    def post_tweet_with_media(self, text: str, media_id: str) -> dict:
        """
        Post a tweet with an attached media (video/image).
        media_id must be obtained from upload_media() first.
        """
        if not text or not text.strip():
            raise ValueError("Tweet text cannot be empty")
        if len(text) > 280:
            raise ValueError(f"Tweet too long ({len(text)} chars, max 280)")

        payload = {
            "text": text,
            "media": {"media_ids": [media_id]},
        }

        resp = self._request("POST", f"{API_BASE}/tweets", json=payload)

        if resp.status_code == 201:
            return resp.json().get("data", {})
        elif resp.status_code == 401 and self.auth_type == "oauth2":
            self._refresh_access_token()
            resp = self._request("POST", f"{API_BASE}/tweets", json=payload)
            if resp.status_code == 201:
                return resp.json().get("data", {})
        elif resp.status_code == 429:
            raise TwitterClientError(
                "Rate limit exceeded. Free tier allows 500 posts/month."
            )

        raise TwitterClientError(
            f"Failed to post tweet with media (HTTP {resp.status_code}): {resp.text}"
        )

    def post_tweet_with_video(self, text: str, video_path: str) -> dict:
        """
        Convenience method: upload a video and post a tweet in one call.
        Uploads the video, waits for processing, then posts the tweet
        — all from THIS account's credentials.

        Returns dict with 'id' and 'text'.
        """
        media_id = self.upload_media(video_path)
        return self.post_tweet_with_media(text, media_id)
