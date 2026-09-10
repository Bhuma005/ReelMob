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
_raw_cors = os.getenv("CORS_ORIGINS", "")
if _raw_cors:
    CORS_ORIGINS: List[str] = [origin.strip() for origin in _raw_cors.split(",") if origin.strip()]
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
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")


def mask_secret(secret: str, visible_chars: int = 4) -> str:
    """Returns a masked representation of a secret string (••••••••a1b2)."""
    if not secret:
        return "Not Set"
    if len(secret) <= visible_chars:
        return "••••••••"
    return "••••••••" + secret[-visible_chars:]


def validate_config(fail_fast: bool = False) -> dict:
    """
    Checks essential configuration.
    If fail_fast is True, raises RuntimeError when critical paths are invalid.
    """
    status = {
        "downloads_dir": os.path.exists(DOWNLOAD_DIR) and os.access(DOWNLOAD_DIR, os.W_OK),
        "supabase_configured": bool(SUPABASE_URL and SUPABASE_SERVICE_KEY),
        "gemini_configured": bool(GEMINI_API_KEY),
        "groq_configured": bool(GROQ_API_KEY),
        "youtube_api_configured": bool(YOUTUBE_API_KEY),
    }

    if fail_fast and not status["downloads_dir"]:
        raise RuntimeError(f"DOWNLOAD_DIR is not writable: {DOWNLOAD_DIR}")
        
    return status
