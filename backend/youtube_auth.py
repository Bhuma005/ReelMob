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

# ── helpers ──────────────────────────────────────────────────────────────────

def _load_secrets():
    with open(CLIENT_SECRETS_FILE) as f:
        data = json.load(f)
    # supports both "web" and "installed" credential types
    return data.get("web") or data.get("installed")

def _save_credentials(token_data: dict):
    with open(CREDENTIALS_FILE, "w") as f:
        json.dump(token_data, f, indent=2)

def _load_credentials():
    if not os.path.exists(CREDENTIALS_FILE):
        return None
    with open(CREDENTIALS_FILE) as f:
        return json.load(f)

def _fetch_channel_name(access_token: str) -> str:
    try:
        req = urllib.request.Request(
            "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(res.read())
            items = data.get("items", [])
            if items:
                return items[0]["snippet"]["title"]
    except Exception as e:
        print("Channel name fetch error:", e)
    return "YouTube Channel"

# ── routes ───────────────────────────────────────────────────────────────────

@router.get("/auth/status")
async def get_auth_status():
    has_secrets = os.path.exists(CLIENT_SECRETS_FILE)
    creds = _load_credentials()
    is_authenticated = creds is not None and "access_token" in creds
    channel_name = creds.get("channel_name", "Connected") if is_authenticated else None
    return {
        "has_client_secrets": has_secrets,
        "is_authenticated": is_authenticated,
        "channel_name": channel_name
    }

@router.get("/auth/login")
async def login_youtube():
    if not os.path.exists(CLIENT_SECRETS_FILE):
        return {"error": "client_secrets.json not found in the backend folder."}

    try:
        secrets = _load_secrets()
        client_id = secrets["client_id"]
        scope = "%20".join(SCOPES)
        redirect_uri = "http://localhost:8000/auth/callback"
        # NOTE: Add http://localhost:8000/auth/callback to your
        # Google Cloud Console → OAuth 2.0 Client ID → Authorized redirect URIs
        auth_url = (
            f"https://accounts.google.com/o/oauth2/auth"
            f"?client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&response_type=code"
            f"&scope={scope}"
            f"&access_type=offline"
            f"&prompt=consent"
        )
        return {"auth_url": auth_url}
    except Exception as e:
        return {"error": str(e)}


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
        redirect_uri = "http://localhost:8000/auth/callback"

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
            <a href="http://127.0.0.1:9090">← Back to ReelGrab</a>
          </div>
        </body>
        </html>
        """)

    except Exception as e:
        print("Callback error:", e)
        return HTMLResponse(f"<h2 style='color:red'>Error: {e}</h2><a href='http://127.0.0.1:9090'>Go back</a>")


@router.get("/auth/logout")
async def logout():
    if os.path.exists(CREDENTIALS_FILE):
        os.remove(CREDENTIALS_FILE)
    return {"status": "logged_out"}
