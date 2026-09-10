"""
cloud_auth.py  —  Credential loader for both local and cloud (GitHub Actions) environments.

Priority order:
  1. Environment variables (GitHub Actions secrets, or locally exported vars)
  2. Local file fallback (youtube_credentials.json + client_secrets.json)

Usage:
    from cloud.cloud_auth import get_youtube_creds, get_supabase_client
"""

import os
import json
import urllib.request
import urllib.parse
from pathlib import Path

try:
    from dotenv import load_dotenv
    # Load .env from the cloud folder if it exists
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

# ── Paths for local fallback ─────────────────────────────────────────────────
_BACKEND_DIR   = Path(__file__).parent.parent / "backend"
_SECRETS_FILE  = _BACKEND_DIR / "client_secrets.json"
_CREDS_FILE    = _BACKEND_DIR / "youtube_credentials.json"

# ── YouTube OAuth ─────────────────────────────────────────────────────────────

def get_youtube_creds() -> dict:
    """
    Returns a dict with: client_id, client_secret, refresh_token.
    Loads from env vars if present (GitHub Actions), otherwise from local files.
    """
    # 1. Environment variables (GitHub Actions secrets)
    client_id     = os.getenv("YT_CLIENT_ID")
    client_secret = os.getenv("YT_CLIENT_SECRET")
    refresh_token = os.getenv("YT_REFRESH_TOKEN")

    if client_id and client_secret and refresh_token:
        return {
            "client_id":     client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        }

    # 2. Local file fallback
    if _CREDS_FILE.exists() and _SECRETS_FILE.exists():
        with open(_SECRETS_FILE) as f:
            secrets_raw = json.load(f)
        secrets = secrets_raw.get("web") or secrets_raw.get("installed", {})

        with open(_CREDS_FILE) as f:
            creds = json.load(f)

        return {
            "client_id":     secrets.get("client_id",     creds.get("client_id")),
            "client_secret": secrets.get("client_secret", creds.get("client_secret")),
            "refresh_token": creds.get("refresh_token"),
        }

    raise EnvironmentError(
        "YouTube credentials not found. "
        "Set YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN as env vars, "
        "or place client_secrets.json + youtube_credentials.json in backend/."
    )


def get_fresh_access_token() -> str:
    """
    Uses the refresh token to get a fresh access token from Google.
    The refresh token never expires (unless revoked), so this is safe
    to call from GitHub Actions without any stored session.
    """
    creds = get_youtube_creds()

    data = urllib.parse.urlencode({
        "client_id":     creds["client_id"],
        "client_secret": creds["client_secret"],
        "refresh_token": creds["refresh_token"],
        "grant_type":    "refresh_token",
    }).encode()

    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as res:
        tokens = json.loads(res.read())

    access_token = tokens.get("access_token")
    if not access_token:
        raise RuntimeError(f"Failed to refresh token: {tokens}")

    return access_token


# ── Supabase client ───────────────────────────────────────────────────────────

def get_supabase_client():
    """
    Returns an initialised supabase-py client.
    Reads SUPABASE_URL and SUPABASE_SERVICE_KEY from env vars (never committed).
    """
    try:
        from supabase import create_client, Client
    except ImportError:
        raise ImportError("Run: pip install supabase")

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")   # service key (bypasses RLS)

    if not url or not key:
        raise EnvironmentError(
            "Set SUPABASE_URL and SUPABASE_SERVICE_KEY as env vars or GitHub Actions secrets."
        )

    return create_client(url, key)
