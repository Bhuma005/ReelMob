"""
video_download.py — Reusable video downloader using yt-dlp.
Provides on-demand video downloading for automation, highlight detection,
content moderation, and duplicate check flows.
"""

import os
import uuid
import asyncio
import logging
from pathlib import Path
from typing import Optional
import yt_dlp

from backend.config import DOWNLOAD_DIR

logger = logging.getLogger("reelsmob.download_service")

STANDARD_DOWNLOAD_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


def ensure_video_downloaded(
    url: str,
    target_dir: Optional[str] = None,
    format_id: Optional[str] = None,
    prefix: str = "auto_",
    timeout_seconds: int = 30
) -> str:
    """
    Downloads a video from a URL to target_dir using yt-dlp with primary and secondary format fallback.
    Returns the absolute/resolved path to the downloaded file.
    Raises RuntimeError if download fails or file is empty.
    """
    if not url or not url.strip():
        raise ValueError("Cannot download video: URL is empty or missing.")

    out_dir = Path(target_dir) if target_dir else Path(DOWNLOAD_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    temp_id = uuid.uuid4().hex[:12]
    temp_filepath = str(out_dir / f"{prefix}{temp_id}.mp4")

    logger.info(f"⬇️ Downloading video on-demand to: {temp_filepath} from {url}")

    is_instagram = "instagram.com" in url.lower()
    is_youtube = "youtube.com" in url.lower() or "youtu.be" in url.lower()

    if is_instagram:
        format_selector = format_id or 'best'
    else:
        format_selector = format_id or 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'

    ydl_opts = {
        'format': format_selector,
        'outtmpl': temp_filepath,
        'quiet': False,
        'no_warnings': True,
        'socket_timeout': timeout_seconds,
        'http_headers': {
            'User-Agent': STANDARD_DOWNLOAD_UA,
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
        },
        'nocheckcertificate': True,
    }
    if is_youtube:
        ydl_opts['extractor_args'] = {
            'youtube': {
                'player_client': ['ios', 'android', 'web']
            }
        }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        logger.warning(f"Primary format download failed for {url}: {e}. Trying secondary format fallback...")
        try:
            fallback_opts = {
                'format': 'best',
                'outtmpl': temp_filepath,
                'quiet': True,
                'no_warnings': True,
                'socket_timeout': timeout_seconds,
                'nocheckcertificate': True,
            }
            with yt_dlp.YoutubeDL(fallback_opts) as ydl:
                ydl.download([url])
        except Exception as e2:
            logger.error(f"Download failed completely for {url}: {e2}")
            if os.path.exists(temp_filepath):
                try:
                    os.remove(temp_filepath)
                except Exception:
                    pass
            raise RuntimeError(f"Download failed: {str(e2)}") from e2

    if not os.path.exists(temp_filepath) or os.path.getsize(temp_filepath) == 0:
        if os.path.exists(temp_filepath):
            try:
                os.remove(temp_filepath)
            except Exception:
                pass
        raise RuntimeError("Downloaded video file is missing or empty.")

    return temp_filepath


async def async_ensure_video_downloaded(
    url: str,
    target_dir: Optional[str] = None,
    format_id: Optional[str] = None,
    prefix: str = "auto_",
    timeout_seconds: int = 30
) -> str:
    """Asynchronous wrapper for ensure_video_downloaded running on a background thread."""
    return await asyncio.to_thread(
        ensure_video_downloaded,
        url=url,
        target_dir=target_dir,
        format_id=format_id,
        prefix=prefix,
        timeout_seconds=timeout_seconds
    )
