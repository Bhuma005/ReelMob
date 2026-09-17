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
    # Load root .env first, then cloud/.env overrides if present
    load_dotenv(Path(__file__).parent.parent / ".env")
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

_SUPABASE_CLIENT = None


def normalize_supabase_url(url: str) -> str:
    """
    Normalizes Supabase URL by stripping whitespace, quotes, trailing slashes,
    and accidental '/rest/v1' or '/rest' subpaths (which PostgREST appends automatically and causes PGRST125).
    """
    if not url:
        return ""
    clean = url.strip().strip("'\"").rstrip("/")
    if clean.endswith("/rest/v1"):
        clean = clean[:-len("/rest/v1")].rstrip("/")
    elif clean.endswith("/rest"):
        clean = clean[:-len("/rest")].rstrip("/")
    return clean


def normalize_supabase_key(key: str) -> str:
    """Strips whitespace and surrounding quotes from the service key."""
    if not key:
        return ""
    return key.strip().strip("'\"")


def validate_supabase_config(fail_fast: bool = False) -> dict:
    """
    Validates that SUPABASE_URL and SUPABASE_SERVICE_KEY are properly defined.
    If fail_fast is True, raises ValueError or EnvironmentError.
    """
    url = normalize_supabase_url(os.getenv("SUPABASE_URL", ""))
    key = normalize_supabase_key(os.getenv("SUPABASE_SERVICE_KEY", ""))

    errors = []
    if not url:
        errors.append("SUPABASE_URL environment variable is missing or empty.")
    elif not (url.startswith("https://") or url.startswith("http://")):
        errors.append(f"SUPABASE_URL is malformed: must start with https:// or http:// (got '{url[:15]}...')")

    if not key:
        errors.append("SUPABASE_SERVICE_KEY environment variable is missing or empty.")
    elif len(key) < 20:
        errors.append("SUPABASE_SERVICE_KEY is suspiciously short (expected valid JWT service key).")

    is_valid = len(errors) == 0

    if fail_fast and not is_valid:
        raise EnvironmentError(" ; ".join(errors))

    return {
        "valid": is_valid,
        "url_set": bool(url),
        "key_set": bool(key),
        "errors": errors
    }


def get_supabase_client(force_refresh: bool = False):
    """
    Returns an initialised, cached supabase-py Client instance.
    Reads SUPABASE_URL and SUPABASE_SERVICE_KEY from environment variables only (never committed or logged).
    Reuses connection pool across calls unless force_refresh=True.
    Automatically normalizes URLs to avoid PostgREST PGRST125 path duplication errors.
    """
    global _SUPABASE_CLIENT

    if _SUPABASE_CLIENT is not None and not force_refresh:
        return _SUPABASE_CLIENT

    try:
        from supabase import create_client, Client
    except ImportError:
        raise ImportError("Run: pip install supabase")

    validation = validate_supabase_config(fail_fast=True)

    url = normalize_supabase_url(os.getenv("SUPABASE_URL", ""))
    key = normalize_supabase_key(os.getenv("SUPABASE_SERVICE_KEY", ""))

    try:
        _SUPABASE_CLIENT = create_client(url, key)
        return _SUPABASE_CLIENT
    except Exception as exc:
        raise ConnectionError(f"Failed to initialize Supabase client: {exc}") from exc

