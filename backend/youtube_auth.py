from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, HTMLResponse
import os
import json
import urllib.request
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

from backend.retry import sync_retry

router = APIRouter()

CLIENT_SECRETS_FILE = os.path.join(os.path.dirname(__file__), "client_secrets.json")

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly"
]

logger = logging.getLogger("reelsmob.youtube_auth")


def _get_supabase_client():
    """Returns the cached Supabase client singleton, or None if unavailable/unconfigured."""
    try:
        from cloud.cloud_auth import get_supabase_client
        return get_supabase_client()
    except Exception as e:
        logger.warning(f"Supabase client unavailable for YouTube OAuth: {e}")
        return None


def _load_secrets() -> Optional[Dict[str, str]]:
    # 1. Environment variables (best for Render / Cloud deployment)
    client_id = os.getenv("GOOGLE_CLIENT_ID") or os.getenv("YOUTUBE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET") or os.getenv("YOUTUBE_CLIENT_SECRET")
    if client_id and client_secret:
        return {"client_id": client_id.strip(), "client_secret": client_secret.strip()}

    # 2. Local client_secrets.json file fallback
    if not os.path.exists(CLIENT_SECRETS_FILE):
        return None
    try:
        with open(CLIENT_SECRETS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("web") or data.get("installed")
    except Exception as e:
        logger.error(f"Failed to read client_secrets.json: {e}")
        return None


def _save_credentials(token_data: dict):
    """
    Persists YouTube OAuth credentials to the 'oauth_tokens' table in Supabase.
    Preserves existing refresh_token if new payload does not include one.
    """
    client = _get_supabase_client()
    if not client:
        logger.error("Cannot save YouTube credentials: Supabase client is unreachable or unconfigured")
        return

    expires_at = token_data.get("expires_at")
    if not expires_at and token_data.get("expires_in"):
        try:
            exp = datetime.now(timezone.utc) + timedelta(seconds=int(token_data["expires_in"]))
            expires_at = exp.isoformat()
        except Exception:
            expires_at = None

    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        # Preserve existing refresh token from database if present
        existing = _load_credentials()
        if existing and existing.get("refresh_token"):
            refresh_token = existing["refresh_token"]

    record = {
        "provider": "youtube",
        "access_token": token_data.get("access_token", ""),
        "refresh_token": refresh_token,
        "token_type": token_data.get("token_type", "Bearer"),
        "expires_at": expires_at,
        "channel_name": token_data.get("channel_name"),
        "scope": token_data.get("scope"),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

    def _do_upsert():
        return client.table("oauth_tokens").upsert(record, on_conflict="provider").execute()

    try:
        sync_retry(_do_upsert, max_retries=2, operation_name="save_youtube_oauth_token")
        logger.info("YouTube OAuth credentials persisted to Supabase (oauth_tokens table)")
    except Exception as e:
        logger.error(f"Failed to save YouTube credentials to Supabase: {e}")


def _load_credentials() -> Optional[Dict[str, Any]]:
    """
    Loads YouTube OAuth credentials from the 'oauth_tokens' table in Supabase.
    Returns None if no token row exists or if Supabase is unreachable.
    """
    client = _get_supabase_client()
    if not client:
        logger.warning("Supabase unavailable: unable to load YouTube credentials")
        return None

    def _do_select():
        return client.table("oauth_tokens").select("*").eq("provider", "youtube").execute()

    try:
        res = sync_retry(_do_select, max_retries=2, operation_name="load_youtube_oauth_token")
        data = getattr(res, "data", None) or []
        if not data:
            return None
        row = data[0]
        return {
            "provider": row.get("provider", "youtube"),
            "access_token": row.get("access_token"),
            "refresh_token": row.get("refresh_token"),
            "token_type": row.get("token_type", "Bearer"),
            "expires_at": row.get("expires_at"),
            "channel_name": row.get("channel_name"),
            "scope": row.get("scope"),
            "updated_at": row.get("updated_at")
        }
    except Exception as e:
        logger.warning(f"Failed to load YouTube credentials from Supabase: {e}")
        return None

def _fetch_channel_name(access_token: str) -> str:
    if not access_token:
        return "YouTube Channel"
    req = urllib.request.Request(
        "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    def _do_fetch():
        with urllib.request.urlopen(req, timeout=8) as res:
            return json.loads(res.read())

    try:
        data = sync_retry(_do_fetch, max_retries=2, operation_name="fetch_channel_name")
        items = data.get("items", [])
        if items:
            return items[0]["snippet"]["title"]
    except Exception as e:
        logger.warning(f"Channel name fetch error (token may be expired): {e}")
    return "YouTube Channel"

import re

DEFAULT_ALLOWED_REDIRECT_PATTERNS = [
    r"^https?://localhost(:\d+)?(/.*)?$",
    r"^https?://127\.0\.0\.1(:\d+)?(/.*)?$",
    r"^https://([a-zA-Z0-9-]+\.)?onrender\.com(/.*)?$",
    r"^https://([a-zA-Z0-9-]+\.)?reelmob\.app(/.*)?$",
]

def is_allowed_redirect_uri(uri: str) -> bool:
    """Validates whether a redirect URI matches configured production allowlists."""
    if not uri or not isinstance(uri, str):
        return False
    uri = uri.strip()

    custom_allowlist = os.getenv("ALLOWED_OAUTH_REDIRECT_URIS", "")
    if custom_allowlist:
        allowed_items = [item.strip() for item in custom_allowlist.split(",") if item.strip()]
        for allowed in allowed_items:
            if uri == allowed:
                return True
            try:
                if re.match(allowed, uri):
                    return True
            except re.error:
                pass

    for pattern in DEFAULT_ALLOWED_REDIRECT_PATTERNS:
        if re.match(pattern, uri):
            return True

    return False

def _get_public_base_url(request: Request = None) -> str:
    env_redirect = os.getenv("GOOGLE_REDIRECT_URI") or os.getenv("REDIRECT_URI")
    if env_redirect:
        return env_redirect.rsplit("/auth/callback", 1)[0].rstrip("/")

    render_url = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
    if render_url:
        return render_url

    if request:
        proto = request.headers.get("x-forwarded-proto") or request.url.scheme or "https"
        host = request.headers.get("x-forwarded-host") or request.headers.get("host")
        if host:
            clean_host = host.split(":")[0].lower()
            allowed_hosts = {"localhost", "127.0.0.1"}
            custom_hosts = os.getenv("ALLOWED_HOSTS", "")
            if custom_hosts:
                allowed_hosts.update([h.strip().lower() for h in custom_hosts.split(",") if h.strip()])

            if clean_host in allowed_hosts or clean_host.endswith(".onrender.com") or clean_host.endswith(".reelmob.app"):
                return f"{proto}://{host}".rstrip("/")
            else:
                logger.warning(f"Untrusted Host header rejected in _get_public_base_url: {host}")

    return os.getenv("PUBLIC_BASE_URL", "https://reelmob.onrender.com").rstrip("/")

def _get_redirect_uri(request: Request = None, override_uri: str = None) -> str:
    canonical_env = os.getenv("GOOGLE_REDIRECT_URI") or os.getenv("REDIRECT_URI")

    if override_uri and override_uri.startswith(("http://", "https://")):
        cleaned_override = override_uri.strip()
        if is_allowed_redirect_uri(cleaned_override):
            return cleaned_override
        logger.warning(
            f"Blocked unauthorized OAuth redirect_uri override: '{cleaned_override}'. "
            f"Falling back to canonical redirect URI."
        )

    if canonical_env:
        return canonical_env.strip()
    return f"{_get_public_base_url(request)}/auth/callback"

# ── routes ───────────────────────────────────────────────────────────────────

@router.get("/auth/status")
async def get_auth_status(request: Request, redirect_uri: str = None):
    secrets = _load_secrets()
    has_secrets = secrets is not None
    creds = _load_credentials()
    is_authenticated = creds is not None and "access_token" in creds
    channel_name = creds.get("channel_name", "Connected") if is_authenticated else None
    resolved_uri = _get_redirect_uri(request, override_uri=redirect_uri)
    return {
        "has_client_secrets": has_secrets,
        "is_authenticated": is_authenticated,
        "channel_name": channel_name,
        "redirect_uri": resolved_uri
    }

@router.get("/auth/login")
async def login_youtube(request: Request, redirect_uri: str = None):
    secrets = _load_secrets()
    resolved_redirect_uri = _get_redirect_uri(request, override_uri=redirect_uri)
    if not secrets:
        return {
            "error": "Google OAuth credentials not configured. Set GOOGLE_CLIENT_ID & GOOGLE_CLIENT_SECRET in environment variables (or place client_secrets.json in backend folder).",
            "redirect_uri": resolved_redirect_uri,
            "has_client_secrets": False
        }

    try:
        client_id = secrets["client_id"]
        scope = "%20".join(SCOPES)
        auth_url = (
            f"https://accounts.google.com/o/oauth2/auth"
            f"?client_id={client_id}"
            f"&redirect_uri={resolved_redirect_uri}"
            f"&response_type=code"
            f"&scope={scope}"
            f"&access_type=offline"
            f"&prompt=consent"
        )
        return {"auth_url": auth_url, "redirect_uri": resolved_redirect_uri, "has_client_secrets": True}
    except Exception as e:
        return {"error": str(e), "redirect_uri": resolved_redirect_uri}


@router.get("/auth/callback")
async def auth_callback(request: Request):
    """Google redirects here after user grants permission."""
    code = request.query_params.get("code")
    error = request.query_params.get("error")

    if error:
        return HTMLResponse(f"<h2>Auth failed: {error}</h2>")
    if not code:
        return HTMLResponse("<h2>No authorization code received.</h2>")

    try:
        secrets = _load_secrets()
        client_id = secrets["client_id"]
        client_secret = secrets["client_secret"]
        redirect_uri = _get_redirect_uri(request)

        # Exchange code for tokens
        token_data = json.dumps({
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code"
        }).encode()

        req = urllib.request.Request(
            "https://oauth2.googleapis.com/token",
            data=token_data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as res:
            tokens = json.loads(res.read())

        # Fetch channel name and save everything
        channel_name = _fetch_channel_name(tokens.get("access_token", ""))
        tokens["channel_name"] = channel_name
        _save_credentials(tokens)

        return HTMLResponse(f"""
        <html>
        <head>
          <style>
            body {{ background:#131313; color:#e5e2e1; font-family:Inter,sans-serif;
                    display:flex; align-items:center; justify-content:center; height:100vh; margin:0; }}
            .card {{ background:rgba(26,26,26,0.9); border:1px solid #E0115F;
                     border-radius:12px; padding:40px; text-align:center; max-width:400px; }}
            h2 {{ color:#4CAF50; margin-bottom:8px; }}
            p {{ color:#ab888d; margin-bottom:24px; }}
            a {{ display:inline-block; padding:12px 24px; background:linear-gradient(135deg,#E0115F,#800a36);
                 color:white; text-decoration:none; border-radius:8px; font-weight:bold; }}
          </style>
        </head>
        <body>
          <div class="card">
            <h2>✅ Connected Successfully!</h2>
            <p>Channel: <strong style="color:white">{channel_name}</strong></p>
            <a href="/">← Back to ReelsMob</a>
          </div>
        </body>
        </html>
        """)

    except Exception as e:
        logger.error(f"Callback error: {e}")
        return HTMLResponse(f"<h2 style='color:red'>Error: {e}</h2><a href='/'>Go back</a>")


@router.get("/auth/logout")
async def logout():
    client = _get_supabase_client()
    if client:
        try:
            def _do_delete():
                return client.table("oauth_tokens").delete().eq("provider", "youtube").execute()

            sync_retry(_do_delete, max_retries=2, operation_name="delete_youtube_oauth_token")
            logger.info("YouTube OAuth credentials deleted from Supabase (logged out)")
        except Exception as e:
            logger.warning(f"Failed to delete YouTube credentials from Supabase: {e}")
    return {"status": "logged_out"}

