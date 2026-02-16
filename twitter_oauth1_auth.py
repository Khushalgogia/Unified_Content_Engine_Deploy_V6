"""
OAuth 1.0a — 3-legged Authorization for Twitter/X
==================================================
Authorizes any Twitter account to use the app with OAuth 1.0a,
enabling full API access including media uploads.

Uses the same app API Key & Secret from account_1 (the developer app owner).

Usage:
    python twitter_oauth1_auth.py account_2
    python twitter_oauth1_auth.py account_3
"""

import json
import sys
import webbrowser
from pathlib import Path

try:
    from requests_oauthlib import OAuth1Session
except ImportError:
    print("❌ Missing dependency: pip install requests-oauthlib")
    sys.exit(1)

# ─── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
CREDS_DIR = SCRIPT_DIR / "modules" / "twitter" / "credentials"

# Twitter OAuth 1.0a endpoints
REQUEST_TOKEN_URL = "https://api.twitter.com/oauth/request_token"
AUTHORIZATION_URL = "https://api.twitter.com/oauth/authorize"
ACCESS_TOKEN_URL = "https://api.twitter.com/oauth/access_token"
USER_INFO_URL = "https://api.twitter.com/2/users/me"


def get_app_credentials() -> tuple[str, str]:
    """
    Get the app's API Key and Secret from account_1.json (the app owner account).
    These are the same for all accounts — they identify the Twitter Developer App.
    """
    account_1_path = CREDS_DIR / "account_1.json"
    if not account_1_path.exists():
        print("❌ No account_1.json found. The app owner account must be set up first.")
        sys.exit(1)

    with open(account_1_path, "r") as f:
        data = json.load(f)

    api_key = data.get("api_key")
    api_secret = data.get("api_secret")

    if not api_key or not api_secret:
        print("❌ account_1.json is missing api_key or api_secret.")
        sys.exit(1)

    return api_key, api_secret


def authorize_account(account_name: str):
    """Run the 3-legged OAuth 1.0a flow to authorize an account."""

    print(f"\n{'='*60}")
    print(f"  OAuth 1.0a Authorization for: {account_name}")
    print(f"{'='*60}\n")

    api_key, api_secret = get_app_credentials()
    print(f"✅ App credentials loaded from account_1.json")

    # Step 1: Get a request token
    print("\n🔄 Step 1: Fetching request token...")
    oauth = OAuth1Session(
        api_key,
        client_secret=api_secret,
        callback_uri="oob",  # PIN-based (out-of-band) flow
    )

    try:
        response = oauth.fetch_request_token(REQUEST_TOKEN_URL)
    except Exception as e:
        print(f"❌ Failed to get request token: {e}")
        print("\n💡 Make sure your Twitter Developer App has:")
        print("   • OAuth 1.0a enabled")
        print("   • 'Read and Write' permissions (or 'Read, Write and DM')")
        print("   • Callback URL set to something (even 'https://example.com')")
        sys.exit(1)

    resource_owner_key = response.get("oauth_token")
    resource_owner_secret = response.get("oauth_token_secret")

    # Step 2: Direct user to authorization URL
    authorization_url = oauth.authorization_url(AUTHORIZATION_URL)

    print(f"\n🌐 Step 2: Open this URL in your browser and authorize the app:\n")
    print(f"   {authorization_url}\n")

    # Try to open automatically
    try:
        webbrowser.open(authorization_url)
        print("   (Browser should have opened automatically)")
    except Exception:
        print("   (Please copy and paste the URL into your browser)")

    # Step 3: Get the PIN from user
    print(f"\n📌 Step 3: After authorizing, Twitter will show you a PIN.")
    pin = input("   Enter the PIN here: ").strip()

    if not pin:
        print("❌ No PIN entered. Aborting.")
        sys.exit(1)

    # Step 4: Exchange for access token
    print("\n🔄 Step 4: Exchanging PIN for access token...")
    oauth = OAuth1Session(
        api_key,
        client_secret=api_secret,
        resource_owner_key=resource_owner_key,
        resource_owner_secret=resource_owner_secret,
        verifier=pin,
    )

    try:
        tokens = oauth.fetch_access_token(ACCESS_TOKEN_URL)
    except Exception as e:
        print(f"❌ Failed to get access token: {e}")
        sys.exit(1)

    access_token = tokens["oauth_token"]
    access_token_secret = tokens["oauth_token_secret"]

    # Step 5: Verify by fetching user info
    print("\n🔍 Step 5: Verifying credentials...")
    verify_oauth = OAuth1Session(
        api_key,
        client_secret=api_secret,
        resource_owner_key=access_token,
        resource_owner_secret=access_token_secret,
    )

    resp = verify_oauth.get(USER_INFO_URL)
    if resp.status_code == 200:
        user_data = resp.json().get("data", {})
        username = user_data.get("username", "???")
        user_id = user_data.get("id", "???")
        print(f"   ✅ Authorized as: @{username} (ID: {user_id})")
    else:
        print(f"   ⚠️ Could not verify (HTTP {resp.status_code}), but tokens were obtained.")
        username = "unknown"

    # Step 6: Save credentials
    creds = {
        "auth_type": "oauth1",
        "api_key": api_key,
        "api_secret": api_secret,
        "access_token": access_token,
        "access_token_secret": access_token_secret,
        "username": username,
    }

    creds_path = CREDS_DIR / f"{account_name}.json"

    # Back up existing file if present
    if creds_path.exists():
        backup_path = CREDS_DIR / f"{account_name}.oauth2_backup.json"
        import shutil
        shutil.copy2(creds_path, backup_path)
        print(f"\n   📦 Backed up existing credentials to {backup_path.name}")

    with open(creds_path, "w") as f:
        json.dump(creds, f, indent=2)

    print(f"\n   💾 Credentials saved to: {creds_path.name}")

    print(f"\n{'='*60}")
    print(f"  ✅ {account_name} is now authorized with OAuth 1.0a!")
    print(f"  🎬 Media uploads (video tweets) are now enabled.")
    print(f"  🐦 Account: @{username}")
    print(f"{'='*60}\n")


def main():
    if len(sys.argv) < 2:
        print("Usage: python twitter_oauth1_auth.py <account_name>")
        print()
        print("Examples:")
        print("  python twitter_oauth1_auth.py account_2")
        print("  python twitter_oauth1_auth.py account_3")
        print()

        # Show current accounts and their auth types
        if CREDS_DIR.exists():
            print("Current accounts:")
            for f in sorted(CREDS_DIR.glob("*.json")):
                if f.name.startswith(".") or "backup" in f.name:
                    continue
                with open(f, "r") as fh:
                    d = json.load(fh)
                auth = d.get("auth_type", "oauth2")
                media = "✅ Media uploads" if auth == "oauth1" else "❌ No media uploads"
                print(f"  {f.stem}: {auth} — {media}")
        sys.exit(0)

    account_name = sys.argv[1]
    authorize_account(account_name)


if __name__ == "__main__":
    main()
