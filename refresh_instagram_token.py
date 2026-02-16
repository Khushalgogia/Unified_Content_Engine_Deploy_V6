"""
Instagram Token Auto-Refresh Script
=====================================
Refreshes the long-lived Instagram access token before it expires (60-day window).
Can be run locally or via GitHub Actions cron.

Usage:
    python refresh_instagram_token.py                    # just refresh & print
    python refresh_instagram_token.py --update-secret    # also update GitHub Secret
"""

import os
import sys
import json
import base64
import requests
from nacl import encoding, public


# ─── Configuration ───────────────────────────────────────────────────────────

CURRENT_TOKEN = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "Khushalgogia/Unified-Content-Engine-V4")
GH_PAT = os.environ.get("GH_PAT")  # Personal Access Token with 'repo' scope

REFRESH_URL = "https://graph.instagram.com/refresh_access_token"


# ─── Token Refresh ───────────────────────────────────────────────────────────

def refresh_token(current_token: str) -> dict:
    """
    Refresh Instagram long-lived user access token.

    The token must be at least 24 hours old and not yet expired.
    Returns a dict with 'access_token', 'token_type', and 'expires_in'.
    """
    print("🔄 Refreshing Instagram access token...")

    resp = requests.get(REFRESH_URL, params={
        "grant_type": "ig_refresh_token",
        "access_token": current_token,
    }, timeout=30)

    if resp.status_code != 200:
        raise Exception(
            f"Token refresh failed (HTTP {resp.status_code}): {resp.text}"
        )

    data = resp.json()

    if "access_token" not in data:
        raise Exception(f"Unexpected response: {data}")

    expires_days = data.get("expires_in", 0) // 86400
    print(f"✅ Token refreshed! Valid for {expires_days} days.")
    print(f"   New token: ...{data['access_token'][-10:]}")

    return data


# ─── GitHub Secret Update ────────────────────────────────────────────────────

def encrypt_secret(public_key: str, secret_value: str) -> str:
    """Encrypt a secret using the repo's public key (libsodium sealed box)."""
    pk = public.PublicKey(
        public_key.encode("utf-8"), encoding.Base64Encoder()
    )
    sealed_box = public.SealedBox(pk)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


def update_github_secret(repo: str, pat: str, secret_name: str, secret_value: str):
    """Update a GitHub repository secret via the API."""
    headers = {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # Get the repo's public key for encrypting secrets
    pk_resp = requests.get(
        f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
        headers=headers, timeout=30,
    )
    if pk_resp.status_code != 200:
        raise Exception(f"Failed to get public key: {pk_resp.text}")

    pk_data = pk_resp.json()
    encrypted_value = encrypt_secret(pk_data["key"], secret_value)

    # Update the secret
    resp = requests.put(
        f"https://api.github.com/repos/{repo}/actions/secrets/{secret_name}",
        headers=headers,
        json={
            "encrypted_value": encrypted_value,
            "key_id": pk_data["key_id"],
        },
        timeout=30,
    )

    if resp.status_code in (201, 204):
        print(f"✅ GitHub Secret '{secret_name}' updated in {repo}")
    else:
        raise Exception(
            f"Failed to update secret (HTTP {resp.status_code}): {resp.text}"
        )


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    if not CURRENT_TOKEN:
        print("❌ INSTAGRAM_ACCESS_TOKEN not set in environment.")
        sys.exit(1)

    # Step 1: Refresh the token
    try:
        result = refresh_token(CURRENT_TOKEN)
        new_token = result["access_token"]
    except Exception as e:
        print(f"❌ Refresh failed: {e}")
        sys.exit(1)

    # Step 2: Optionally update GitHub Secret
    update_secret = "--update-secret" in sys.argv

    if update_secret:
        if not GH_PAT:
            print("⚠️  GH_PAT not set — cannot update GitHub Secret.")
            print("   Set GH_PAT env var with a Personal Access Token (repo scope).")
            sys.exit(1)

        try:
            update_github_secret(
                GITHUB_REPO, GH_PAT,
                "INSTAGRAM_ACCESS_TOKEN", new_token,
            )
        except Exception as e:
            print(f"❌ GitHub Secret update failed: {e}")
            sys.exit(1)
    else:
        print()
        print("👉 To also update your GitHub Secret, run with --update-secret")
        print(f"   New token value:\n   {new_token}")

    print("\n🏁 Done.")


if __name__ == "__main__":
    main()
