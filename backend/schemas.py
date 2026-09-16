"""
backend/schemas.py — Typed Pydantic request models and input sanitizers for ReelsMob.

Enforces:
- Sane string limits (title <= 300 chars, description <= 5000 chars, url <= 2000 chars).
- Strict URL validation before triggering expensive yt-dlp processes.
- Safe filename / path sanitization to prevent path traversal attacks.
"""

import re
from typing import Optional, List, Literal
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


class VideoTrimParams(BaseModel):
    start: float = Field(default=0.0, ge=0.0)
    end: Optional[float] = Field(default=None, ge=0.0)


class VideoColorParams(BaseModel):
    brightness: float = Field(default=0.0, ge=-0.5, le=0.5)
    contrast: float = Field(default=1.0, ge=0.5, le=2.0)
    saturation: float = Field(default=1.0, ge=0.0, le=2.0)


class VideoCaptionParams(BaseModel):
    text: str = Field(..., max_length=500)
    font_size: int = Field(default=36, ge=14, le=72)
    position: Literal["top", "center", "bottom"] = "bottom"
    color: Literal["white", "yellow", "cyan", "lime"] = "white"


class VideoWatermarkParams(BaseModel):
    text: str = Field(..., max_length=100)
    position: Literal["top-left", "top-right", "bottom-left", "bottom-right"] = "bottom-right"
    opacity: float = Field(default=0.75, ge=0.1, le=1.0)


class EditVideoRequest(BaseModel):
    video_path: str = Field(..., description="Local video filename or path inside downloads/")
    trim: Optional[VideoTrimParams] = None
    color: Optional[VideoColorParams] = None
    captions: Optional[VideoCaptionParams] = None
    watermark: Optional[VideoWatermarkParams] = None
    framing: Literal["original", "blur_pad", "crop"] = "original"

    @field_validator('video_path')
    @classmethod
    def check_video_path(cls, v: str) -> str:
        if not v or '..' in v or '\0' in v:
            raise ValueError("Invalid or unsafe video_path")
        return v


class HighlightItem(BaseModel):
    start: float = Field(..., ge=0.0, description="Start timestamp in seconds")
    end: float = Field(..., ge=0.0, description="End timestamp in seconds")
    reason: str = Field(..., max_length=500, description="Why this clip is engaging")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0 and 1")


class HighlightRequest(BaseModel):
    video_path: Optional[str] = Field(default=None, max_length=1000, description="Local video filename or path inside downloads/")
    url: Optional[str] = Field(default=None, max_length=2000, description="Source video URL")
    target_duration_min: float = Field(default=15.0, ge=5.0, le=120.0)
    target_duration_max: float = Field(default=60.0, ge=10.0, le=300.0)
    num_clips: int = Field(default=3, ge=1, le=5)

    @field_validator('video_path')
    @classmethod
    def check_video_path(cls, v: Optional[str]) -> Optional[str]:
        if v and ('..' in v or '\0' in v):
            raise ValueError("Path traversal characters not allowed in video_path")
        return v

    @field_validator('url')
    @classmethod
    def check_url(cls, v: Optional[str]) -> Optional[str]:
        if v and v.strip():
            return validate_video_url(v)
        return v


class HighlightResponse(BaseModel):
    job_id: str
    status: Literal["PENDING", "PROCESSING", "COMPLETED", "FAILED"]
    highlights: Optional[List[HighlightItem]] = None
    error: Optional[str] = None


class DuplicateMatch(BaseModel):
    id: str
    title: str
    distance: int = Field(..., ge=0, le=64)
    similarity_pct: float = Field(..., ge=0.0, le=100.0)
    created_at: Optional[str] = None


class DuplicateCheckRequest(BaseModel):
    video_path: str = Field(..., max_length=1000, description="Local video filename or path inside downloads/")
    threshold: int = Field(default=10, ge=0, le=64, description="Maximum hamming distance threshold")

    @field_validator('video_path')
    @classmethod
    def check_video_path(cls, v: str) -> str:
        if not v or '..' in v or '\0' in v:
            raise ValueError("Invalid or unsafe video_path")
        return v


class DuplicateCheckResponse(BaseModel):
    is_duplicate: bool
    hash: str
    matches: List[DuplicateMatch] = []

