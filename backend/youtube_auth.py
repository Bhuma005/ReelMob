from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, HTMLResponse
import os
import json
import urllib.request

router = APIRouter()

CLIENT_SECRETS_FILE = os.path.join(os.path.dirname(__file__), "client_secrets.json")
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "youtube_credentials.json")

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.readonly"]

import logging
from backend.retry import sync_retry

logger = logging.getLogger("reelsmob.youtube_auth")

def _load_secrets():
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
    try:
        with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
            json.dump(token_data, f, indent=2)
        logger.info("YouTube OAuth credentials saved safely")
    except Exception as e:
        logger.error(f"Failed to save credentials: {e}")

def _load_credentials():
    if not os.path.exists(CREDENTIALS_FILE):
        return None
    try:
        with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to parse credentials file: {e}")
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
            return f"{proto}://{host}".rstrip("/")

    return os.getenv("PUBLIC_BASE_URL", "https://reelmob.onrender.com").rstrip("/")

def _get_redirect_uri(request: Request = None, override_uri: str = None) -> str:
    if override_uri and override_uri.startswith(("http://", "https://")):
        return override_uri.strip()
    env_redirect = os.getenv("GOOGLE_REDIRECT_URI") or os.getenv("REDIRECT_URI")
    if env_redirect:
        return env_redirect.strip()
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
    if os.path.exists(CREDENTIALS_FILE):
        os.remove(CREDENTIALS_FILE)
    return {"status": "logged_out"}
