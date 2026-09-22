"""
backend/config.py — Centralized configuration and fail-fast environment validation for ReelsMob.
"""

import os
from pathlib import Path
from typing import List

# Load environment variables from root .env and cloud/.env
ROOT_DIR = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv
    # 1. Root .env
    load_dotenv(ROOT_DIR / ".env")
    # 2. cloud/.env
    load_dotenv(ROOT_DIR / "cloud" / ".env")
except ImportError:
    pass

# Application Settings
APP_NAME = "ReelsMob"
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.getenv("LOG_FORMAT", "console").lower()

# Downloads and file system
DOWNLOAD_DIR = os.path.join(ROOT_DIR, "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Rate Limiting
RATE_LIMIT_BURST = int(os.getenv("RATE_LIMIT_BURST", "10"))
RATE_LIMIT_SECONDS = float(os.getenv("RATE_LIMIT_SECONDS", "1.0"))

# Request Timeouts
HTTP_TIMEOUT_SECONDS = float(os.getenv("HTTP_TIMEOUT_SECONDS", "30.0"))
YTDL_TIMEOUT_SECONDS = float(os.getenv("YTDL_TIMEOUT_SECONDS", "45.0"))

# CORS Configuration
_raw_cors = os.getenv("CORS_ORIGINS", "").strip()
_render_url = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")

if ENVIRONMENT == "production":
    if not _raw_cors and not _render_url:
        raise RuntimeError("CORS_ORIGINS must be set in production")
    origins = [origin.strip() for origin in _raw_cors.split(",") if origin.strip()] if _raw_cors else []
    if _render_url and _render_url not in origins:
        origins.append(_render_url)
    CORS_ORIGINS: List[str] = origins
else:
    if _raw_cors:
        CORS_ORIGINS: List[str] = [origin.strip() for origin in _raw_cors.split(",") if origin.strip()]
    elif _render_url:
        CORS_ORIGINS = [_render_url]
    else:
        # Standard local frontend origins for dev / staging
        CORS_ORIGINS = [
            "http://localhost:9090",
            "http://127.0.0.1:9090",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ]
        if ENVIRONMENT == "development":
            CORS_ORIGINS.append("*")

# Cloud Credentials
def _clean_supabase_url(url: str) -> str:
    if not url:
        return ""
    clean = url.strip().strip("'\"").rstrip("/")
    if clean.endswith("/rest/v1"):
        clean = clean[:-len("/rest/v1")].rstrip("/")
    elif clean.endswith("/rest"):
        clean = clean[:-len("/rest")].rstrip("/")
    return clean

SUPABASE_URL = _clean_supabase_url(os.getenv("SUPABASE_URL", ""))
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "").strip().strip("'\"")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "").strip().strip("'\"")
GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_KEY") or "").strip().strip("'\"")
GROQ_API_KEY = (os.getenv("GROQ_API_KEY") or os.getenv("GROQ_KEY") or "").strip().strip("'\"")

# AI Model Configuration (allows environment overrides when providers deprecate models)
DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"
GEMINI_MODEL = (os.getenv("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL).strip().strip("'\"")
GROQ_MODEL = (os.getenv("GROQ_MODEL") or DEFAULT_GROQ_MODEL).strip().strip("'\"")

# GitHub Actions Video Analysis Offloading
ANALYSIS_OFFLOAD_MODE = os.getenv("ANALYSIS_OFFLOAD_MODE", "local").strip().lower()
GITHUB_DISPATCH_TOKEN = os.getenv("GITHUB_DISPATCH_TOKEN", "").strip()
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY", "Bhuma005/ReelMob").strip()


def mask_secret(secret: str, visible_chars: int = 4) -> str:
    """Returns a masked representation of a secret string (••••••••a1b2)."""
    if not secret:
        return "Not Set"
    if len(secret) <= visible_chars:
        return "••••••••"
    return "••••••••" + secret[-visible_chars:]


def validate_offload_config():
    """Fails fast if ANALYSIS_OFFLOAD_MODE is 'github_actions' but GITHUB_DISPATCH_TOKEN is missing."""
    mode = os.getenv("ANALYSIS_OFFLOAD_MODE", "local").strip().lower()
    if mode == "github_actions":
        token = os.getenv("GITHUB_DISPATCH_TOKEN", "").strip()
        if not token:
            raise EnvironmentError(
                "ANALYSIS_OFFLOAD_MODE is set to 'github_actions' but GITHUB_DISPATCH_TOKEN is missing or empty. "
                "Please set GITHUB_DISPATCH_TOKEN in your environment with Actions/Contents read-write permissions."
            )


def validate_config(fail_fast: bool = False) -> dict:
    """
    Checks essential configuration.
    If fail_fast is True, raises RuntimeError/EnvironmentError when critical paths are invalid.
    """
    offload_mode = os.getenv("ANALYSIS_OFFLOAD_MODE", "local").strip().lower()
    github_token = os.getenv("GITHUB_DISPATCH_TOKEN", "").strip()

    status = {
        "downloads_dir": os.path.exists(DOWNLOAD_DIR) and os.access(DOWNLOAD_DIR, os.W_OK),
        "supabase_configured": bool(SUPABASE_URL and SUPABASE_SERVICE_KEY),
        "gemini_configured": bool(GEMINI_API_KEY),
        "groq_configured": bool(GROQ_API_KEY),
        "youtube_api_configured": bool(YOUTUBE_API_KEY),
        "analysis_offload_mode": offload_mode,
        "github_dispatch_configured": bool(github_token),
    }

    if offload_mode == "github_actions" and not github_token:
        err_msg = (
            "ANALYSIS_OFFLOAD_MODE is set to 'github_actions' but GITHUB_DISPATCH_TOKEN is missing or empty."
        )
        if fail_fast:
            raise EnvironmentError(err_msg)

    if fail_fast and not status["downloads_dir"]:
        raise RuntimeError(f"DOWNLOAD_DIR is not writable: {DOWNLOAD_DIR}")
        
    return status

