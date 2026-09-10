"""
backend/schemas.py — Typed Pydantic request models and input sanitizers for ReelsMob.

Enforces:
- Sane string limits (title <= 300 chars, description <= 5000 chars, url <= 2000 chars).
- Strict URL validation before triggering expensive yt-dlp processes.
- Safe filename / path sanitization to prevent path traversal attacks.
"""

import re
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from fastapi import HTTPException
from backend.utils import sanitize_url

# Regex to validate Instagram or YouTube URLs
VALID_VIDEO_URL_PATTERN = re.compile(
    r'^(https?:\/\/)?(www\.)?(instagram\.com\/(reel|p|tv)\/|youtube\.com\/(shorts\/|watch\?v=)|youtu\.be\/)[a-zA-Z0-9_\-\.\?&=%#]+'
)


def validate_video_url(url: str) -> str:
    """Validates and cleans input URL. Raises clean 400 HTTPException if invalid."""
    if not url or not isinstance(url, str):
        raise HTTPException(status_code=400, detail="URL cannot be empty or invalid.")
    
    clean = sanitize_url(url.strip())
    if not clean or len(clean) < 10:
        raise HTTPException(status_code=400, detail="URL is too short or malformed.")

    is_supported = (
        "instagram.com" in clean or 
        "youtube.com" in clean or 
        "youtu.be" in clean
    )
    if not is_supported:
        raise HTTPException(
            status_code=400, 
            detail="Invalid URL domain. Please provide a valid Instagram Reel or YouTube Shorts link."
        )
    return clean


def sanitize_filename_or_id(input_str: str) -> str:
    """Strips directory traversal sequences (../, \\) and dangerous characters."""
    if not input_str:
        return ""
    # Strip any path separators and null bytes
    sanitized = re.sub(r'[\/\\\0]', '', str(input_str))
    # Remove relative path tokens
    sanitized = sanitized.replace('..', '').strip()
    return sanitized


class URLRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2000, description="Instagram Reel or YouTube Shorts URL")


class DownloadRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2000, description="Video source URL")
    format_id: str = Field(..., min_length=1, max_length=150, description="yt-dlp format identifier")

    @field_validator('format_id')
    @classmethod
    def check_format_id(cls, v: str) -> str:
        clean = sanitize_filename_or_id(v)
        if not clean:
            raise ValueError("Invalid format_id")
        return clean



class AnalyzeRequest(BaseModel):
    title: Optional[str] = Field(default='', max_length=500)
    description: Optional[str] = Field(default='', max_length=10000)
    url: Optional[str] = Field(default='', max_length=2000)
    video_path: Optional[str] = Field(default='', max_length=1000)

    @field_validator('url')
    @classmethod
    def check_url(cls, v: Optional[str]) -> Optional[str]:
        if v and v.strip():
            return validate_video_url(v)
        return v or ''

    @field_validator('video_path')
    @classmethod
    def check_video_path(cls, v: Optional[str]) -> Optional[str]:
        if v and ('..' in v or '\0' in v):
            raise ValueError("Path traversal characters not allowed in video_path")
        return v or ''


class ConvertRequest(BaseModel):
    ratio: str = Field(..., description="Target aspect ratio: '9:16', '1:1', '4:5', or '16:9'")

    @field_validator('ratio')
    @classmethod
    def validate_ratio(cls, v: str) -> str:
        allowed = {"9:16", "1:1", "4:5", "16:9"}
        if v not in allowed:
            raise ValueError(f"Invalid ratio '{v}'. Must be one of {allowed}")
        return v



class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1, description="Page number, 1-indexed")
    limit: int = Field(default=20, ge=1, le=100, description="Number of items per page (max 100)")
    status: Optional[str] = Field(default=None, max_length=50)
    search: Optional[str] = Field(default=None, max_length=200)
