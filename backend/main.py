import os
import time
import asyncio
import logging
import uuid
import glob
import re
import urllib.request
import tempfile
import shutil
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import yt_dlp

from backend.logging_config import setup_logging, request_id_ctx_var
from backend.config import (
    APP_NAME,
    ENVIRONMENT,
    CORS_ORIGINS,
    DOWNLOAD_DIR,
    RATE_LIMIT_BURST,
    RATE_LIMIT_SECONDS,
    YTDL_TIMEOUT_SECONDS,
    validate_config,
)
from backend.retry import async_retry, is_transient_error
from backend.schemas import (
    URLRequest,
    DownloadRequest,
    AnalyzeRequest,
    ConvertRequest,
    EditVideoRequest,
    HighlightRequest,
    HighlightResponse,
    HighlightItem,
    DuplicateCheckRequest,
    DuplicateCheckResponse,
    AnalyticsTrendsResponse,
    UpdateVideoTagsRequest,
    TagPerformanceResponse,
    validate_video_url,
    sanitize_filename_or_id,
)
from backend.automate import router as automate_router
from backend.youtube_auth import router as yt_auth_router

# Initialize Structured Redacting Logger
setup_logging()
logger = logging.getLogger("reelsmob.main")

# Fail-safe config sanity check at startup
validate_config(fail_fast=False)

APP_START_TIME = time.time()
app = FastAPI(title=APP_NAME, version="2.0.0")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if "*" not in CORS_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(automate_router)
app.include_router(yt_auth_router)

RATE_LIMIT_STORE: Dict[str, list] = {}


# Middleware 1: Request ID context and execution timing
@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    token = request_id_ctx_var.set(req_id)
    t0 = time.perf_counter()
    try:
        response = await call_next(request)
        duration_ms = (time.perf_counter() - t0) * 1000.0
        response.headers["X-Request-ID"] = req_id
        # Log request lifecycle
        logger.info(
            f"{request.method} {request.url.path} - {response.status_code} ({duration_ms:.1f}ms)"
        )
        return response
    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000.0
        logger.error(
            f"{request.method} {request.url.path} failed after {duration_ms:.1f}ms: {exc}"
        )
        raise exc
    finally:
        request_id_ctx_var.reset(token)


# Middleware 2: IP-based sliding-window Rate Limiting
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()

    history = RATE_LIMIT_STORE.get(client_ip, [])
    history = [t for t in history if now - t < RATE_LIMIT_SECONDS]

    if len(history) >= RATE_LIMIT_BURST:
        req_id = request_id_ctx_var.get()
        logger.warning(f"Rate limit exceeded for IP {client_ip} on {request.url.path}")
        return JSONResponse(
            status_code=429,
            content={
                "detail": "Too many requests. Please slow down.",
                "error": {
                    "code": 429,
                    "message": "Too many requests. Please slow down.",
                    "request_id": req_id
                }
            },
            headers={"X-Request-ID": req_id or ""}
        )

    history.append(now)
    RATE_LIMIT_STORE[client_ip] = history
    return await call_next(request)


# Global Exception Handler: HTTPException
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    req_id = request_id_ctx_var.get()
    if exc.status_code >= 500:
        logger.error(f"HTTPException {exc.status_code} on {request.url.path}: {exc.detail}")
    else:
        logger.warning(f"HTTPException {exc.status_code} on {request.url.path}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "error": {
                "code": exc.status_code,
                "message": str(exc.detail),
                "request_id": req_id
            }
        },
        headers={"X-Request-ID": req_id or ""}
    )


# Global Exception Handler: RequestValidationError
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    req_id = request_id_ctx_var.get()
    raw_errors = exc.errors()
    logger.warning(f"Validation error on {request.url.path}: {raw_errors}")
    from fastapi.encoders import jsonable_encoder
    safe_errors = jsonable_encoder(raw_errors)
    return JSONResponse(
        status_code=422,
        content={
            "detail": safe_errors,
            "error": {
                "code": 422,
                "message": "Validation error",
                "details": safe_errors,
                "request_id": req_id
            }
        },
        headers={"X-Request-ID": req_id or ""}
    )



# Global Exception Handler: Unhandled Exception
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    req_id = request_id_ctx_var.get()
    logger.exception(f"Unhandled internal server error on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error.",
            "error": {
                "code": 500,
                "message": "Internal server error",
                "request_id": req_id
            }
        },
        headers={"X-Request-ID": req_id or ""}
    )


def validate_url(url: str):
    """Backward compatibility wrapper around validate_video_url."""
    return validate_video_url(url)


@app.post("/formats", summary="Get Video Formats", description="Returns a list of available video formats for a valid URL.")
async def get_formats(req: URLRequest, request: Request):
    clean_url = validate_video_url(req.url)

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'socket_timeout': 30,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info(f"Fetching info for {clean_url}")
            info = await asyncio.wait_for(
                asyncio.to_thread(ydl.extract_info, clean_url, download=False),
                timeout=YTDL_TIMEOUT_SECONDS
            )

            if not info:
                raise HTTPException(status_code=400, detail="Could not extract info. Video might be private or unavailable.")

            import math
            def get_aspect_ratio(w, h):
                if not w or not h: return "Unknown"
                if w == 1080 and h == 1920: return "9:16"
                if w == 1920 and h == 1080: return "16:9"
                if w == 1080 and h == 1350: return "4:5"
                if w == 1080 and h == 1080: return "1:1"
                g = math.gcd(w, h)
                return f"{w//g}:{h//g}"

            formats = info.get('formats', [])
            resolutions = []

            for f in formats:
                if f.get('vcodec') != 'none':
                    w = f.get('width', 0)
                    h = f.get('height', 0)
                    fps = f.get('fps', 0)
                    vcodec = f.get('vcodec', 'unknown')
                    acodec = f.get('acodec', 'none')

                    has_audio = acodec != 'none'
                    fmt_id = f.get('format_id')
                    if not has_audio:
                        fmt_id = f"{fmt_id}+bestaudio"

                    resolutions.append({
                        "format_id": fmt_id,
                        "resolution": f"{w}x{h}" if w and h else f.get('format_note', 'Unknown'),
                        "width": w,
                        "height": h,
                        "aspect_ratio": get_aspect_ratio(w, h),
                        "fps": fps,
                        "ext": f.get('ext', 'mp4'),
                        "vcodec": vcodec,
                        "has_audio": has_audio,
                        "filesize": f.get('filesize') or f.get('filesize_approx', 0),
                        "is_original": False
                    })

            resolutions.sort(key=lambda x: (x['width'] * x['height']), reverse=True)

            unique_resolutions = []
            seen = set()
            for r in resolutions:
                key = f"{r['width']}x{r['height']}_{r['fps']}"
                if key not in seen and r['width'] > 0:
                    seen.add(key)
                    unique_resolutions.append(r)

            best_w = info.get('width') or (unique_resolutions[0]['width'] if unique_resolutions else 0)
            best_h = info.get('height') or (unique_resolutions[0]['height'] if unique_resolutions else 0)
            best_fps = info.get('fps') or (unique_resolutions[0]['fps'] if unique_resolutions else 0)

            original_format = {
                "format_id": "bestvideo+bestaudio/best",
                "resolution": f"{best_w}x{best_h}" if best_w else "Best",
                "width": best_w,
                "height": best_h,
                "aspect_ratio": get_aspect_ratio(best_w, best_h),
                "fps": best_fps,
                "ext": "mp4",
                "has_audio": True,
                "is_original": True
            }

            return [original_format] + unique_resolutions

    except asyncio.TimeoutError:
        logger.error(f"Timeout extracting formats for {clean_url}")
        raise HTTPException(status_code=504, detail="Timeout while fetching video formats from upstream.")
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"yt-dlp error: {e}")
        raise HTTPException(status_code=400, detail=f"Download error: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error fetching formats for {clean_url}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching formats.")


def cleanup_partial_downloads(temp_id: str):
    """Deletes any partial files for a given id"""
    for file in glob.glob(os.path.join(DOWNLOAD_DIR, f"{temp_id}*")):
        try:
            os.remove(file)
            logger.info(f"Cleaned up partial download {file}")
        except Exception as e:
            logger.warning(f"Failed to clean up {file}: {e}")


@app.post("/download", summary="Download specific video format", description="Downloads the video from the provided URL using the requested format ID.")
async def download_video(req: DownloadRequest, request: Request):
    clean_url = validate_video_url(req.url)
    clean_fmt = sanitize_filename_or_id(req.format_id)
    if not clean_fmt:
        raise HTTPException(status_code=400, detail="Invalid format_id provided.")

    temp_id = str(uuid.uuid4())
    ydl_opts = {
        'format': clean_fmt,
        'outtmpl': os.path.join(DOWNLOAD_DIR, f"{temp_id}.%(ext)s"),
        'quiet': False,
        'socket_timeout': 30,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info(f"Downloading format {clean_fmt} for {clean_url}")
            info = await asyncio.wait_for(
                asyncio.to_thread(ydl.extract_info, clean_url, download=True),
                timeout=YTDL_TIMEOUT_SECONDS * 3
            )

            ext = info.get('ext', 'mp4') if info else 'mp4'
            filepath = os.path.join(DOWNLOAD_DIR, f"{temp_id}.{ext}")

            if not os.path.exists(filepath):
                downloaded_files = glob.glob(os.path.join(DOWNLOAD_DIR, f"{temp_id}*"))
                if downloaded_files:
                    filepath = downloaded_files[0]
                else:
                    raise FileNotFoundError("Download failed, file not found.")

            raw_id = info.get('id', temp_id) if info else temp_id
            video_id = sanitize_filename_or_id(raw_id) or temp_id
            final_filename = f"{video_id}.{filepath.split('.')[-1]}"
            final_filepath = os.path.join(DOWNLOAD_DIR, final_filename)

            if os.path.exists(final_filepath):
                try:
                    os.remove(final_filepath)
                except Exception:
                    final_filepath = os.path.join(DOWNLOAD_DIR, f"{video_id}_{temp_id}.{filepath.split('.')[-1]}")

            os.rename(filepath, final_filepath)

            # Run FFprobe verification for audit logs
            import subprocess
            import json
            try:
                cmd = [
                    "backend/ffprobe.exe" if os.path.exists("backend/ffprobe.exe") else "ffprobe",
                    "-v", "error", "-select_streams", "v:0",
                    "-show_entries", "stream=width,height,display_aspect_ratio",
                    "-of", "json", final_filepath
                ]
                probe_res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if probe_res.returncode == 0:
                    probe_data = json.loads(probe_res.stdout)
                    streams = probe_data.get('streams', [])
                    if streams:
                        v_stream = streams[0]
                        out_w = v_stream.get('width', 0)
                        out_h = v_stream.get('height', 0)
                        dar = v_stream.get('display_aspect_ratio', 'Unknown')
                        from datetime import datetime
                        with open("reelgrab_audit.log", "a", encoding='utf-8') as log_file:
                            log_file.write(f"[{datetime.now().isoformat()}] DOWNLOAD VERIFIED | OUTPUT: {out_w}x{out_h} | DAR: {dar} | MODE: original | FILE: {final_filename}\n")
            except Exception as e:
                logger.error(f"FFprobe verification failed: {e}")

            return FileResponse(
                path=final_filepath,
                media_type=f"video/{final_filepath.split('.')[-1]}",
                filename=final_filename
            )

    except asyncio.TimeoutError:
        cleanup_partial_downloads(temp_id)
        logger.error(f"Timeout downloading {clean_url}")
        raise HTTPException(status_code=504, detail="Timeout while downloading video from upstream.")
    except yt_dlp.utils.DownloadError as e:
        cleanup_partial_downloads(temp_id)
        logger.error(f"yt-dlp error: {e}")
        raise HTTPException(status_code=400, detail=f"Download error: {str(e)}")
    except HTTPException:
        cleanup_partial_downloads(temp_id)
        raise
    except Exception as e:
        cleanup_partial_downloads(temp_id)
        logger.exception(f"Error downloading video {clean_url}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during download.")


@app.post("/metadata", summary="Fetch Video Metadata", description="Extracts basic title, description, and hashtags from a video URL.")
async def get_metadata(req: URLRequest, request: Request):
    # validate_url handles invalid urls with HTTPException 400, but for metadata we want 200 with nulls on failure.
    try:
        clean_url = validate_video_url(req.url)
    except HTTPException:
        return {"title": None, "description": None, "description_clean": None, "hashtags": [], "thumbnail_url": None}

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'socket_timeout': 30,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.wait_for(
                asyncio.to_thread(ydl.extract_info, clean_url, download=False),
                timeout=30.0
            )
            if not info:
                return {"title": None, "description": None, "description_clean": None, "hashtags": [], "thumbnail_url": None}
            title = info.get('title')
            description = info.get('description') or ''
            thumbnail_url = info.get('thumbnail')

            hashtags = []
            seen = set()
            for match in re.finditer(r'#\w+', description):
                tag = match.group()
                if tag not in seen:
                    seen.add(tag)
                    hashtags.append(tag)

            description_clean = re.sub(r'#\w+', '', description)
            description_clean = re.sub(r'[ \t]+', ' ', description_clean)
            description_clean = re.sub(r'\n\s*\n', '\n', description_clean).strip()

            return {
                "title": title,
                "description": description,
                "description_clean": description_clean,
                "hashtags": hashtags,
                "thumbnail_url": thumbnail_url,
                "view_count": info.get('view_count'),
                "like_count": info.get('like_count'),
                "comment_count": info.get('comment_count')
            }
    except Exception as e:
        logger.warning(f"Metadata extraction error: {e}")
        return {"title": None, "description": None, "description_clean": None, "hashtags": [], "thumbnail_url": None}


@app.post("/metadata/comments", summary="Extract Comments Hashtags", description="Pulls comment sections and parses the author's own hashtags for deep viral tagging.")
async def get_metadata_comments(req: URLRequest, request: Request):
    try:
        clean_url = validate_video_url(req.url)
    except HTTPException:
        return {"hashtags": [], "available": False}

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'getcomments': True,
        'socket_timeout': 30,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.wait_for(
                asyncio.to_thread(ydl.extract_info, clean_url, download=False),
                timeout=30.0
            )
            if not info:
                return {"hashtags": [], "available": False}

            uploader = info.get('uploader') or info.get('uploader_id')
            comments = info.get('comments', [])

            hashtags = []
            seen = set()
            for comment in comments:
                author = comment.get('author') or comment.get('author_id')
                if author and uploader and author == uploader:
                    text = comment.get('text', '')
                    for match in re.finditer(r'#\w+', text):
                        tag = match.group()
                        if tag not in seen:
                            seen.add(tag)
                            hashtags.append(tag)

            return {"hashtags": hashtags, "available": True}
    except Exception as e:
        logger.warning(f"Comments metadata error: {e}")
        return {"hashtags": [], "available": False}


@app.post("/download-thumbnail", summary="Download Best Thumbnail", description="Retrieves and proxies the max resolution thumbnail for a video URL.")
async def download_thumbnail(req: URLRequest, request: Request):
    clean_url = validate_video_url(req.url)

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'socket_timeout': 30,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.wait_for(
                asyncio.to_thread(ydl.extract_info, clean_url, download=False),
                timeout=30.0
            )
            if not info:
                raise HTTPException(status_code=400, detail="Could not extract info.")
            thumbnail_url = info.get('thumbnail')
            if not thumbnail_url:
                raise HTTPException(status_code=404, detail="Thumbnail not found.")

            temp_id = str(uuid.uuid4())
            ext = thumbnail_url.split('?')[0].split('.')[-1]
            if not ext or len(ext) > 4:
                ext = 'jpg'

            filepath = os.path.join(DOWNLOAD_DIR, f"{temp_id}_thumb.{ext}")
            urllib.request.urlretrieve(thumbnail_url, filepath)

            raw_id = info.get('id', temp_id)
            safe_id = sanitize_filename_or_id(raw_id) or temp_id

            return FileResponse(
                path=filepath,
                media_type=f"image/{ext if ext != 'jpg' else 'jpeg'}",
                filename=f"thumbnail_{safe_id}.{ext}"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Thumbnail error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error fetching thumbnail.")

        
import hashlib
from datetime import datetime

AI_JOBS_STORE: Dict[str, dict] = {}
AI_CACHE_STORE: Dict[str, dict] = {}

def get_content_hash(url: str, title: str, description: str) -> str:
    combined = f"url:{url or ''}|title:{title or ''}|desc:{description or ''}".strip()
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()

async def execute_ai_analysis_job(job_id: str, title: str, description: str, url: str, video_path: str = ""):
    if job_id not in AI_JOBS_STORE:
        return
    
    job = AI_JOBS_STORE[job_id]
    content_hash = job.get("content_hash")
    
    try:
        if job.get("status") == "CANCELLED":
            return
            
        from backend.video_analyzer import analyze_video_content

        job["status"] = "ANALYZING_FRAMES"
        job["progress"] = 25
        job["current_step"] = "Inspecting video footage & extracting key frames..."
        job["started_at"] = datetime.now().isoformat()
        
        # Run real local video frame & audio analyzer
        video_analysis = await asyncio.to_thread(
            analyze_video_content,
            video_path=video_path,
            url=url,
            raw_title=title,
            raw_description=description
        )
        
        if job.get("status") == "CANCELLED":
            return
            
        job["status"] = "ANALYZING"
        job["progress"] = 55
        if video_analysis.get("vision_success"):
            job["current_step"] = f"Visual frames analyzed via local vision model ({video_analysis.get('vision_model_used')})..."
        elif video_analysis.get("audio_success"):
            job["current_step"] = "Spoken dialogue transcribed via local Whisper..."
        else:
            job["current_step"] = "Analyzing context & emotional retention hooks..."
        await asyncio.sleep(0.4)
        
        if job.get("status") == "CANCELLED":
            return
            
        job["status"] = "GENERATING_METADATA"
        job["progress"] = 75
        job["current_step"] = "Writing algorithm-grounded viral title, description & tags..."
        
        # ── 1. Priority: ReelsMob Cloud AI (Gemini + Groq) ──────────────────────
        cloud_meta = None
        try:
            from backend.services.cloud_ai import is_cloud_ai_available, generate_metadata_with_groq
            if is_cloud_ai_available():
                logger.info("⚡ Using ReelsMob Cloud AI (Groq + Gemini) for instant metadata generation...")
                cloud_meta = await asyncio.to_thread(
                    generate_metadata_with_groq,
                    visual_summary=video_analysis.get("visual_description", "") or description or title,
                    caption=description
                )
        except Exception as e:
            logger.warning(f"Cloud AI metadata generation attempt error: {e}")

        if cloud_meta and cloud_meta.get("success"):
            best_title = cloud_meta.get("title") or title or "Must Watch Viral Scene 🔥"
            desc = cloud_meta.get("description") or description or ""
            youtube_tags = cloud_meta.get("youtube_hashtags", ["#Shorts", "#ShortsFeed", "#Viral"])
            instagram_tags = cloud_meta.get("instagram_hashtags", ["#Reels", "#Viral"])
            
            source_label = video_analysis.get("source_label") or "Based on video analysis"
            analysis_source = video_analysis.get("analysis_source") or "video_visual"
            video_analyzed = video_analysis.get("video_analyzed", True)

            raw_result = {
                "title": best_title,
                "description": desc,
                "youtube_hashtags": youtube_tags,
                "instagram_hashtags": instagram_tags,
                "title_candidates": [{"title": best_title, "strategy": "Cloud AI Viral Hook", "score": 98}],
                "viewer_appeal_score": 96,
                "title_reason": ["Video-grounded visual hook", "High CTR algorithm match"],
                "posting_recommendation": {
                    "human_readable_time": "07:30 PM",
                    "reason": "Peak engagement slot for short-form video audience."
                },
                "ai_failed": False,
                "source_label": source_label,
                "analysis_source": analysis_source,
                "video_analyzed": video_analyzed,
                "visual_description": video_analysis.get("visual_description", ""),
                "audio_transcript": video_analysis.get("audio_transcript", ""),
                "provider": "ReelsMob Cloud AI (Gemini 3.6 + Groq)"
            }
            
            result_payload = {
                "viral_title": best_title,
                "optimized_description": desc,
                "youtube": youtube_tags,
                "instagram": instagram_tags,
                "analysis": "Generated via ReelsMob Cloud AI using Gemini 3.6 video visual inspection and Groq viral synthesis.",
                "confidence_notes": "VERY HIGH (Cloud AI)",
                "scheduled_time": "07:30 PM",
                "raw_result": raw_result,
                "ai_failed": False,
                "source_label": source_label,
                "analysis_source": analysis_source,
                "video_analyzed": video_analyzed
            }
            
            job["status"] = "COMPLETED"
            job["progress"] = 100
            job["current_step"] = "AI optimization complete (Cloud AI)"
            job["completed_at"] = datetime.now().isoformat()
            job["result"] = result_payload
            
            if content_hash:
                ANALYSIS_CACHE[content_hash] = result_payload
            return

        # ── 2. Fallback: Ollama Check ──────────────────────────────────────────
        # Pre-flight check: is Ollama alive?
        ollama_alive = False
        try:
            import urllib.request
            req = urllib.request.Request("http://127.0.0.1:11434/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                if resp.status == 200:
                    ollama_alive = True
        except Exception:
            ollama_alive = False
            
        if not ollama_alive:
            logger.warning(f"Ollama server not reachable for job {job_id}. Using deterministic fallback metadata.")
            fallback_title = title or "Trending Reel"
            fallback_desc = description or "Watch this trending video! #Shorts #Viral"
            fallback_tags = ["#Shorts", "#Viral", "#Trending", "#Reel"]
            
            raw_result = {
                "title": fallback_title,
                "description": fallback_desc,
                "youtube_hashtags": fallback_tags,
                "instagram_hashtags": fallback_tags,
                "title_candidates": [{"strategy": "Original", "title": fallback_title}],
                "viewer_appeal_score": 75,
                "title_reason": ["Deterministic fallback (Ollama unavailable)"],
                "posting_recommendation": {
                    "human_readable_time": "07:30 PM",
                    "reason": "Standard peak evening engagement slot."
                },
                "ai_failed": True,
                "fallback": True,
                "source_label": "From caption — video analysis unavailable",
                "analysis_source": "caption_fallback",
                "video_analyzed": False
            }
            
            result_payload = {
                "viral_title": fallback_title,
                "optimized_description": fallback_desc,
                "youtube": fallback_tags,
                "instagram": fallback_tags,
                "analysis": "Generated using deterministic fallback (Ollama model server is offline).",
                "confidence_notes": "FALLBACK",
                "scheduled_time": "07:30 PM",
                "raw_result": raw_result,
                "ai_failed": True,
                "source_label": "From caption — video analysis unavailable",
                "analysis_source": "caption_fallback",
                "video_analyzed": False
            }
            
            job["status"] = "COMPLETED"
            job["progress"] = 100
            job["current_step"] = "AI completed with fallback metadata"
            job["completed_at"] = datetime.now().isoformat()
            job["result"] = result_payload
            return

        from backend.agents.master_agent import MasterAgent, backfill_hashtags
        from backend.agents.base import AgentState

        agent = MasterAgent()
        initial_state = AgentState({
            "raw_title": title or "",
            "raw_description": description or "",
            "transcript_text": video_analysis.get("audio_transcript") or description or "",
            "audio_transcript": video_analysis.get("audio_transcript") or "",
            "visual_description": video_analysis.get("visual_description") or "",
            "analysis_source": video_analysis.get("analysis_source") or "caption_fallback",
            "source_label": video_analysis.get("source_label") or "From caption — video analysis unavailable",
            "video_analyzed": video_analysis.get("video_analyzed", False),
            "url": url or ""
        })
        
        try:
            final_state = await asyncio.wait_for(
                asyncio.to_thread(agent.run, initial_state),
                timeout=120.0
            )
        except Exception as e:
            logger.warning(f"AI job {job_id} fallback due to: {e}")
            desc_clean = re.sub(r'#\w+', '', description or '').strip()
            desc_clean = re.split(r'Film Details:|Cast:|Director:|Release Year:|Copyright', desc_clean, flags=re.IGNORECASE)[0].strip()
            lines = [l.strip() for l in desc_clean.split('\n') if l.strip()]
            hook_text = lines[1] if len(lines) > 1 and len(lines[0]) < 12 else (lines[0] if lines else '')
            clean_subject = re.sub(r'[^\w\s]', '', hook_text)[:40].strip()
            fallback_title = f"Why {clean_subject}... 💔" if clean_subject else "A Moment You Will Never Forget 🥺"
            guaranteed_fallback_tags = backfill_hashtags([], fallback_title, desc_clean, min_count=7)
            final_state = AgentState({
                "metadata": {
                    "status": "success",
                    "best_title": fallback_title,
                    "title_candidates": [{"title": fallback_title, "strategy": "Emotional Retention", "score": 92}],
                    "viewer_appeal_score": 90,
                    "title_reason": ["High emotional curiosity hook", "Strong mobile viewer retention"],
                    "description": f"{hook_text or 'Watch this powerful scene!'}\n\nWhat do you think? Let us know below! 👇\n\n👉 Subscribe for daily shorts!\n#Shorts #Viral",
                    "youtube_hashtags": guaranteed_fallback_tags,
                    "instagram_hashtags": guaranteed_fallback_tags,
                    "ai_failed": True,
                    "source_label": "From caption — video analysis unavailable",
                    "analysis_source": "caption_fallback",
                    "video_analyzed": False
                },
                "posting": {"scheduled_time": "19:30", "score": 95, "reason": "Standard peak evening engagement slot."}
            })

        if job.get("status") == "CANCELLED":
            return
            
        metadata = final_state.get("metadata", {})
        posting = final_state.get("posting", {})
        analytics = final_state.get("analytics", {})
        
        best_title = metadata.get("best_title") or title or "Untitled Reel"
        desc = metadata.get("description") or description or ""
        raw_yt = metadata.get("youtube_hashtags", [])
        raw_ig = metadata.get("instagram_hashtags", [])
        youtube_tags = backfill_hashtags(raw_yt, best_title, desc, min_count=7)
        instagram_tags = backfill_hashtags(raw_ig, best_title, desc, min_count=7)
        ai_failed = metadata.get("ai_failed", False) or metadata.get("status") == "failed"
        
        source_label = metadata.get("source_label") or video_analysis.get("source_label") or "From caption — video analysis unavailable"
        analysis_source = metadata.get("analysis_source") or video_analysis.get("analysis_source") or "caption_fallback"
        video_analyzed = metadata.get("video_analyzed", False) or video_analysis.get("video_analyzed", False)
        
        raw_result = {
            "title": best_title,
            "description": desc,
            "youtube_hashtags": youtube_tags,
            "instagram_hashtags": instagram_tags,
            "title_candidates": metadata.get("title_candidates", [{"title": best_title, "strategy": "High-CTR Algorithm Hook", "score": 95}]),
            "viewer_appeal_score": metadata.get("viewer_appeal_score", 90),
            "title_reason": metadata.get("title_reason", ["High viral hook potential", "Optimized search query"]),
            "posting_recommendation": posting,
            "ai_failed": ai_failed,
            "source_label": source_label,
            "analysis_source": analysis_source,
            "video_analyzed": video_analyzed,
            "visual_description": video_analysis.get("visual_description", ""),
            "audio_transcript": video_analysis.get("audio_transcript", ""),
            "vision_hint": video_analysis.get("vision_hint"),
            "agent_workflow_state": final_state.data if hasattr(final_state, "data") else final_state
        }
        
        result_payload = {
            "viral_title": best_title,
            "optimized_description": desc,
            "youtube": youtube_tags,
            "instagram": instagram_tags,
            "analysis": analytics.get("reasoning", posting.get("reason", "Optimized based on audience peak activity.")),
            "confidence_notes": posting.get("confidence", "HIGH"),
            "scheduled_time": posting.get("human_readable_time", "07:30 PM"),
            "raw_result": raw_result,
            "ai_failed": ai_failed,
            "source_label": source_label,
            "analysis_source": analysis_source,
            "video_analyzed": video_analyzed,
            "vision_hint": video_analysis.get("vision_hint")
        }
        
        job["status"] = "COMPLETED"
        job["progress"] = 100
        job["current_step"] = "AI optimization complete"
        job["completed_at"] = datetime.now().isoformat()
        job["result"] = result_payload
        
        if content_hash:
            AI_CACHE_STORE[content_hash] = result_payload
            
    except Exception as e:
        logger.warning(f"AI job {job_id} error: {e}. Falling back to instant metadata.")
        fallback_title = title or "Trending Reel"
        fallback_desc = description or "Watch this trending video! #Shorts #Viral"
        fallback_tags = backfill_hashtags([], fallback_title, fallback_desc, min_count=7)
        
        raw_result = {
            "title": fallback_title,
            "description": fallback_desc,
            "youtube_hashtags": fallback_tags,
            "instagram_hashtags": fallback_tags,
            "title_candidates": [{"strategy": "Original", "title": fallback_title}],
            "viewer_appeal_score": 85,
            "title_reason": ["Fast fallback metadata"],
            "posting_recommendation": {"human_readable_time": "07:30 PM", "reason": "Peak evening engagement."},
            "ai_failed": True,
            "fallback": True
        }
        
        result_payload = {
            "viral_title": fallback_title,
            "optimized_description": fallback_desc,
            "youtube": fallback_tags,
            "instagram": fallback_tags,
            "analysis": "Instant optimized metadata.",
            "confidence_notes": "READY",
            "scheduled_time": "07:30 PM",
            "raw_result": raw_result,
            "ai_failed": True
        }
        
        job["status"] = "COMPLETED"
        job["progress"] = 100
        job["current_step"] = "AI optimization complete"
        job["completed_at"] = datetime.now().isoformat()
        job["result"] = result_payload

@app.post("/metadata/analyze", summary="Analyze via Local GenAI (Async Job)")
@app.post("/api/analyze", summary="Analyze via Local GenAI (Async Job)")
async def start_ai_analysis(req: AnalyzeRequest, background_tasks: BackgroundTasks):
    text = f"{req.title or ''}\n{req.description or ''}".strip()
    if not text and not req.url:
        return {
            "job_id": None,
            "status": "COMPLETED",
            "progress": 100,
            "current_step": "Empty input provided",
            "result": {
                "viral_title": "",
                "optimized_description": "",
                "youtube": [],
                "instagram": [],
                "analysis": ""
            }
        }
        
    content_hash = get_content_hash(req.url, req.title, req.description)
    
    # 1. Check in-memory cache
    if content_hash in AI_CACHE_STORE:
        logger.info(f"⚡ Returning cached AI analysis for hash {content_hash[:8]}")
        return {
            "job_id": f"cached_{content_hash[:8]}",
            "status": "COMPLETED",
            "progress": 100,
            "current_step": "Retrieved from cache",
            "result": AI_CACHE_STORE[content_hash],
            "cached": True
        }

    # 2. Create new Async Job
    job_id = str(uuid.uuid4())
    AI_JOBS_STORE[job_id] = {
        "job_id": job_id,
        "content_hash": content_hash,
        "status": "QUEUED",
        "progress": 10,
        "current_step": "Queued for AI analysis",
        "created_at": datetime.now().isoformat(),
        "result": None,
        "error": None
    }
    
    background_tasks.add_task(execute_ai_analysis_job, job_id, req.title, req.description, req.url, req.video_path or "")
    
    return {
        "job_id": job_id,
        "status": "QUEUED",
        "progress": 10,
        "current_step": "Queued for processing"
    }

@app.get("/api/analyze/status/{job_id}", summary="Get AI Analysis Job Status")
async def get_ai_job_status(job_id: str):
    clean_job_id = sanitize_filename_or_id(job_id)
    job = AI_JOBS_STORE.get(clean_job_id)
    if not job:
        if clean_job_id.startswith("cached_"):
            return {"job_id": clean_job_id, "status": "COMPLETED", "progress": 100, "current_step": "Complete", "result": None}
        raise HTTPException(status_code=404, detail="AI job not found")

    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "progress": job["progress"],
        "current_step": job["current_step"],
        "result": job.get("result"),
        "error": job.get("error")
    }

@app.post("/api/analyze/cancel/{job_id}", summary="Cancel AI Analysis Job")
async def cancel_ai_job(job_id: str):
    clean_job_id = sanitize_filename_or_id(job_id)
    job = AI_JOBS_STORE.get(clean_job_id)
    if not job:
        return {"success": False, "message": "Job not found"}
    job["status"] = "CANCELLED"
    job["progress"] = 0
    job["current_step"] = "Cancelled by user"
    return {"success": True, "job_id": clean_job_id, "status": "CANCELLED"}

@app.get("/api/scheduling/recommendation", summary="Get Posting Intelligence Recommendation")
async def get_scheduling_recommendation(topic: str = None, category: str = None):
    from backend.posting_engine import get_best_posting_time
    try:
        intel = get_best_posting_time(topic=topic, category=category)
        return intel
    except Exception as e:
        logger.error(f"Scheduling recommendation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate scheduling recommendation.")

@app.get("/api/dashboard/stats", summary="Get Dashboard Stats", description="Fetch cloud DB statistics for connections and saved/uploaded videos.")
async def get_dashboard_stats():
    from cloud.cloud_auth import get_supabase_client
    try:
        sb = get_supabase_client()
        # Query permanent video_library counts
        res_total = sb.table("video_library").select("id", count="exact").execute()
        res_scheduled = sb.table("video_library").select("id", count="exact").eq("status", "scheduled").execute()
        res_processing = sb.table("video_library").select("id", count="exact").in_("status", ["created", "downloading", "downloaded", "processing", "uploading"]).execute()
        res_published = sb.table("video_library").select("id", count="exact").eq("status", "published").execute()
        res_cleaned = sb.table("video_library").select("id", count="exact").eq("status", "cleaned").execute()
        res_failed = sb.table("video_library").select("id", count="exact").eq("status", "failed").execute()

        def get_count(res):
            return res.count if getattr(res, "count", None) is not None else len(res.data)

        return {
            "total": get_count(res_total),
            "scheduled": get_count(res_scheduled),
            "processing": get_count(res_processing),
            "published": get_count(res_published),
            "cleaned": get_count(res_cleaned),
            "failed": get_count(res_failed),
            # Backward compatibility aliases
            "pending": get_count(res_scheduled),
            "uploaded": get_count(res_published)
        }
    except Exception as e:
        logger.error(f"Dashboard Stats error: {e}")
        return {"total": 0, "scheduled": 0, "processing": 0, "published": 0, "cleaned": 0, "failed": 0, "pending": 0, "uploaded": 0, "error": str(e)}

@app.get("/api/dashboard/videos", summary="Get Video Queue", description="Fetch videos for the library with optional pagination, status filter, and search.")
async def get_dashboard_videos(
    page: int = 1,
    limit: int = 20,
    status: Optional[str] = None,
    search: Optional[str] = None
):
    from cloud.cloud_auth import get_supabase_client
    # Enforce safe parameter bounds
    page = max(1, page)
    limit = max(1, min(limit, 100))
    if search:
        search = search.strip()[:200]
    if status:
        status = status.strip()[:50]
    try:
        sb = get_supabase_client()
        query = sb.table("video_library").select("*", count="exact")

        if status and status.lower() != 'all':
            query = query.eq("status", status.lower())

        if search and search.strip():
            query = query.ilike("title", f"%{search.strip()}%")

        start = max(0, (page - 1) * limit)
        end = start + limit - 1

        res = query.order("created_at", desc=True).range(start, end).execute()
        videos = res.data or []
        total_count = res.count if getattr(res, "count", None) is not None else len(videos)

        for v in videos:
            if v.get("storage_path") and v.get("status") not in ['cleaned', 'published']:
                try:
                    signed = sb.storage.from_("reelgrab-videos").create_signed_url(v["storage_path"], 3600*24)
                    v["public_url"] = signed.get("signedURL") or signed.get("signedUrl") or signed
                except Exception as e:
                    logger.error(f"Failed to generate signed url: {e}")
            v["storage_exists"] = bool(v.get("storage_path"))

        return {
            "videos": videos,
            "total": total_count,
            "page": page,
            "limit": limit,
            "total_pages": max(1, (total_count + limit - 1) // limit) if total_count > 0 else 1
        }
    except Exception as e:
        logger.error(f"Dashboard Videos error: {e}")
        return {"videos": [], "total": 0, "page": page, "limit": limit, "total_pages": 1, "error": str(e)}


@app.delete("/api/dashboard/videos/{video_id}", summary="Delete a video", description="Deletes video from Supabase Storage and DB.")
async def delete_dashboard_video(video_id: str):
    from cloud.cloud_auth import get_supabase_client
    from datetime import datetime
    clean_video_id = sanitize_filename_or_id(video_id)
    if not clean_video_id:
        return {"status": "error", "message": "Invalid video_id"}
    try:
        sb = get_supabase_client()
        res = sb.table("video_library").select("storage_path, title").eq("id", clean_video_id).execute()
        if not res.data:
            return {"status": "error", "message": "Video not found"}

        storage_path = res.data[0].get("storage_path")
        title = res.data[0].get("title")

        if storage_path:
            try:
                sb.storage.from_("reelgrab-videos").remove([storage_path])
            except Exception as e:
                logger.error(f"Failed to delete from storage: {e}")

        sb.table("scheduled_videos").delete().eq("library_video_id", clean_video_id).execute()
        sb.table("video_library").delete().eq("id", clean_video_id).execute()

        with open("reelgrab_audit.log", "a", encoding='utf-8') as log_file:
            log_file.write(f"[{datetime.now().isoformat()}] DELETED VIDEO | ID: {clean_video_id} | Title: {title} | Storage: {storage_path}\n")

        return {"status": "success", "message": "Video deleted successfully"}
    except Exception as e:
        logger.error(f"Failed to delete video: {e}")
        import traceback
        err = traceback.format_exc()
        logger.error(f"Convert error trace: {err}")
        return {"status": "error", "message": repr(e)}


@app.post("/api/dashboard/videos/{video_id}/convert", summary="Convert Aspect Ratio")
async def convert_dashboard_video(video_id: str, req: ConvertRequest):
    from cloud.cloud_auth import get_supabase_client
    import os
    import subprocess
    import uuid
    import asyncio

    clean_video_id = sanitize_filename_or_id(video_id)
    if not clean_video_id:
        return {"status": "error", "message": "Invalid video_id"}

    ratio_map = {
        "9:16": (1080, 1920),
        "1:1": (1080, 1080),
        "4:5": (1080, 1350),
        "16:9": (1920, 1080)
    }
    if req.ratio not in ratio_map:
        return {"status": "error", "message": "Invalid ratio"}
    W, H = ratio_map[req.ratio]

    try:
        sb = get_supabase_client()
        res = sb.table("video_library").select("storage_path").eq("id", clean_video_id).execute()
        if not res.data:
            return {"status": "error", "message": "Video not found"}

        storage_path = res.data[0].get("storage_path")

        # 1. Download the original video completely to memory or disk
        temp_in = f"downloads/conv_in_{uuid.uuid4().hex}.mp4"
        temp_out = f"downloads/conv_out_{uuid.uuid4().hex}.mp4"
        os.makedirs("downloads", exist_ok=True)

        with open(temp_in, "wb") as f:
            res_down = sb.storage.from_("reelgrab-videos").download(storage_path)
            f.write(res_down)

        # 2. Run FFmpeg (blur background padding technique)
        filter_complex = f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,boxblur=20:20,crop={W}:{H}[bg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,setdar={W}/{H}"
        cmd = [
            "backend/ffmpeg.exe" if os.path.exists("backend/ffmpeg.exe") else "ffmpeg",
            "-y", "-i", temp_in,
            "-lavfi", filter_complex,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            "-c:a", "copy",
            temp_out
        ]

        def run_ffmpeg():
            return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        process = await asyncio.to_thread(run_ffmpeg)

        if process.returncode != 0:
            logger.error(f"FFmpeg error: {process.stderr.decode()}")
            return {"status": "error", "message": "FFmpeg conversion failed: " + process.stderr.decode()[:200]}

        # 3. Upload overwritten video back to Supabase
        sb.storage.from_("reelgrab-videos").remove([storage_path])
        with open(temp_out, "rb") as f:
            sb.storage.from_("reelgrab-videos").upload(storage_path, f, file_options={"content-type": "video/mp4"})

        # Cleanup
        if os.path.exists(temp_in): os.remove(temp_in)
        if os.path.exists(temp_out): os.remove(temp_out)

        return {"status": "success", "message": "Converted"}
    except Exception as e:
        logger.error(f"Convert error: {e}")
        import traceback
        err = traceback.format_exc()
        logger.error(f"Convert error trace: {err}")
        return {"status": "error", "message": repr(e)}


@app.post("/api/video/edit", summary="In-App Video Editor (Trim, Color, Captions, Watermark, Framing)")
async def edit_video_endpoint(req: EditVideoRequest):
    """
    Processes video edits using FFmpeg in a single optimized pass:
    - trim (start/end in seconds)
    - color filters (brightness, contrast, saturation)
    - captions burn-in with customizable position and font
    - corner watermark text
    - aspect framing (original, blur_pad, crop)
    """
    from backend.services.video_editor import process_video_edit

    clean_path = sanitize_filename_or_id(req.video_path)
    candidate_paths = [
        os.path.join("downloads", clean_path),
        clean_path,
        os.path.join("downloads", os.path.basename(clean_path)),
    ]
    input_file = None
    for p in candidate_paths:
        if os.path.exists(p) and os.path.isfile(p):
            input_file = p
            break

    if not input_file:
        raise HTTPException(
            status_code=404,
            detail=f"Source video file not found for path: {clean_path}"
        )

    out_name = f"edited_{uuid.uuid4().hex[:10]}.mp4"
    output_path = os.path.join("downloads", out_name)

    trim_dict = req.trim.model_dump() if req.trim else None
    color_dict = req.color.model_dump() if req.color else None
    captions_dict = req.captions.model_dump() if req.captions else None
    watermark_dict = req.watermark.model_dump() if req.watermark else None

    try:
        result = await asyncio.to_thread(
            process_video_edit,
            input_path=input_file,
            output_path=output_path,
            trim=trim_dict,
            color=color_dict,
            captions=captions_dict,
            watermark=watermark_dict,
            framing=req.framing,
        )

        return {
            "status": "success",
            "message": "Video edited successfully",
            "video_path": out_name,
            "full_path": output_path,
            "download_url": f"/download/{out_name}",
            "metadata": {
                "width": result.get("width"),
                "height": result.get("height"),
                "duration": result.get("duration"),
                "size_bytes": result.get("size_bytes"),
            }
        }
    except Exception as exc:
        logger.error(f"Video edit processing failed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Video processing failed: {str(exc)}"
        )


# In-memory store for async highlight detection jobs
HIGHLIGHT_JOBS: Dict[str, Dict[str, Any]] = {}

def execute_highlight_job(
    job_id: str,
    video_path: Optional[str],
    target_duration_min: float,
    target_duration_max: float,
    num_clips: int,
    url: Optional[str]
):
    from backend.services.highlight_detector import detect_highlights

    job = HIGHLIGHT_JOBS.get(job_id)
    if not job:
        return

    job["status"] = "PROCESSING"
    try:
        path_to_use = video_path
        if not path_to_use:
            downloads_dir = "downloads"
            if os.path.exists(downloads_dir):
                files = [
                    os.path.join(downloads_dir, f)
                    for f in os.listdir(downloads_dir)
                    if f.lower().endswith(('.mp4', '.mkv', '.webm', '.mov'))
                ]
                if files:
                    files.sort(key=os.path.getmtime, reverse=True)
                    path_to_use = files[0]

        if not path_to_use:
            raise ValueError("No video file specified or found in downloads.")

        clips = detect_highlights(
            video_path=path_to_use,
            target_duration_min=target_duration_min,
            target_duration_max=target_duration_max,
            num_clips=num_clips,
            url=url
        )
        job["status"] = "COMPLETED"
        job["highlights"] = clips
    except Exception as exc:
        logger.error(f"Highlight job {job_id} failed: {exc}", exc_info=True)
        job["status"] = "FAILED"
        job["error"] = str(exc)


@app.post("/api/video/highlights", summary="Multi-Clip Highlight Detection (Async Job)")
async def create_highlights_job(req: HighlightRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    HIGHLIGHT_JOBS[job_id] = {
        "job_id": job_id,
        "status": "PENDING",
        "highlights": None,
        "error": None,
        "created_at": datetime.now().isoformat()
    }
    background_tasks.add_task(
        execute_highlight_job,
        job_id=job_id,
        video_path=req.video_path,
        target_duration_min=req.target_duration_min,
        target_duration_max=req.target_duration_max,
        num_clips=req.num_clips,
        url=req.url
    )
    return {"job_id": job_id, "status": "PENDING"}


@app.get("/api/video/highlights/status/{job_id}", summary="Get Highlight Job Status", response_model=HighlightResponse)
async def get_highlight_job_status(job_id: str):
    clean_id = sanitize_filename_or_id(job_id)
    job = HIGHLIGHT_JOBS.get(clean_id)
    if not job:
        raise HTTPException(status_code=404, detail="Highlight job not found")
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "highlights": job.get("highlights"),
        "error": job.get("error")
    }


@app.post("/api/video/check-duplicate", summary="Check for Duplicate / Near-Duplicate Videos", response_model=DuplicateCheckResponse)
async def check_duplicate_video_endpoint(req: DuplicateCheckRequest):
    """
    Computes perceptual difference hash (dHash) for the target video
    and compares against the creator's video library using Hamming distance.
    Flags duplicates if distance <= threshold (default 10 / 64 bits).
    """
    from backend.services.duplicate_detector import check_video_duplicate

    clean_path = sanitize_filename_or_id(req.video_path)
    candidate_paths = [
        os.path.join("downloads", clean_path),
        clean_path,
        os.path.join("downloads", os.path.basename(clean_path)),
    ]
    input_file = None
    for p in candidate_paths:
        if os.path.exists(p) and os.path.isfile(p):
            input_file = p
            break

    if not input_file:
        raise HTTPException(
            status_code=404,
            detail=f"Video file not found for path: {clean_path}"
        )

    try:
        result = await asyncio.to_thread(
            check_video_duplicate,
            video_path=input_file,
            threshold=req.threshold
        )
        return result
    except Exception as exc:
        logger.error(f"Duplicate check failed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Duplicate check failed: {str(exc)}"
        )


@app.get("/api/dashboard/analytics/trends", summary="Channel Historical Trend Comparison & Rolling Averages", response_model=AnalyticsTrendsResponse)
async def get_channel_trends_endpoint(days: int = 30):
    """
    Computes 30-day channel rolling averages vs individual video metrics.
    Flags each video as overperforming, average, or underperforming.
    """
    from backend.services.analytics_trends import calculate_channel_trends
    days_bounded = max(7, min(days, 90))
    return await asyncio.to_thread(calculate_channel_trends, days=days_bounded)


# In-memory tag cache for offline/test mode
LOCAL_VIDEO_TAGS: Dict[str, List[str]] = {}

@app.patch("/api/dashboard/videos/{video_id}/tags", summary="Update Video Tags")
async def update_video_tags_endpoint(video_id: str, req: UpdateVideoTagsRequest):
    """
    Updates custom tags for a video in the creator's library.
    Validates tag naming, length, and cardinality.
    """
    clean_id = sanitize_filename_or_id(video_id)
    if not clean_id:
        raise HTTPException(status_code=400, detail="Invalid video_id")

    LOCAL_VIDEO_TAGS[clean_id] = req.tags

    # Attempt Supabase update
    try:
        from cloud.cloud_auth import get_supabase_client
        sb = get_supabase_client()
        sb.table("video_library").update({"tags": req.tags}).eq("id", clean_id).execute()
    except Exception as exc:
        logger.debug(f"Supabase tag update skipped or failed: {exc}")

    return {
        "status": "success",
        "id": clean_id,
        "tags": req.tags
    }


@app.get("/api/dashboard/analytics/tags", summary="Tag Performance Analytics", response_model=TagPerformanceResponse)
async def get_tag_performance_endpoint(days: int = 30):
    """
    Computes performance by tag (average views, likes, engagement rate, benchmark status).
    """
    from backend.services.analytics_trends import calculate_performance_by_tag
    days_bounded = max(7, min(days, 90))
    return await asyncio.to_thread(calculate_performance_by_tag, days=days_bounded)


@app.post("/api/dashboard/videos/{video_id}/publish", summary="Force Publish to YouTube immediately")
async def publish_dashboard_video(video_id: str):
    from cloud.cloud_auth import get_supabase_client
    import os
    import tempfile
    from datetime import datetime, timezone, timedelta

    clean_video_id = sanitize_filename_or_id(video_id)
    if not clean_video_id:
        return {"status": "error", "message": "Invalid video_id"}

    try:
        try:
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
            from google.oauth2.credentials import Credentials
        except ImportError:
            return {"status": "error", "message": "Google API packages missing (pip install google-api-python-client google-auth-oauthlib)"}

        sb = get_supabase_client()
        res = sb.table("video_library").select("*").eq("id", clean_video_id).execute()
        if not res.data:
            return {"status": "error", "message": "Video not found in library"}

        video = res.data[0]
        if video.get("status") in ["published", "delete_pending", "cleaned"] or video.get("youtube_video_id"):
            return {"status": "error", "message": "Already published!"}

        if not video.get("storage_path"):
            return {"status": "error", "message": "Video file is missing from cloud storage"}

        sb.table("video_activity_log").insert({
            "video_id": clean_video_id,
            "event_type": "UPLOAD_STARTED",
            "message": "Manual publish triggered from dashboard"
        }).execute()

        logger.info(f"Downloading video for publish: {video.get('storage_path')}")
        file_bytes = sb.storage.from_("reelgrab-videos").download(video.get("storage_path"))

        from cloud.cloud_auth import get_youtube_creds
        try:
            creds_data = get_youtube_creds()
        except Exception:
            return {"status": "error", "message": "YouTube Credentials not configured in .env"}

        creds = Credentials(
            token=None,
            refresh_token=creds_data["refresh_token"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=creds_data["client_id"],
            client_secret=creds_data["client_secret"]
        )
        yt_service = build("youtube", "v3", credentials=creds)

        tags = video.get("hashtags", [])
        if isinstance(tags, str): tags = tags.replace("#", "").split()
        else: tags = [t.replace("#", "") for t in tags]

        tag_str = " ".join([f"#{t}" for t in tags])
        full_desc = f"{video.get('description', '')}\n\n{tag_str}".strip()

        body = {
            "snippet": {
                "title": video.get("title", "ReelGrab Upload"),
                "description": full_desc,
                "tags": tags,
                "categoryId": "22"
            },
            "status": {
                "privacyStatus": "public",
                "madeForKids": False,
                "selfDeclaredMadeForKids": False
            }
        }

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            media = MediaFileUpload(tmp_path, mimetype="video/mp4", resumable=True)
            request = yt_service.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media
            )
            response = None
            while response is None:
                status, response = request.next_chunk()

            yt_id = response.get("id")
            yt_url = f"https://youtube.com/shorts/{yt_id}"
            now = datetime.now(timezone.utc).isoformat()

            sb.table("video_library").update({
                "status": "published",
                "upload_status": "uploaded",
                "youtube_video_id": yt_id,
                "youtube_url": yt_url,
                "uploaded_at": now
            }).eq("id", clean_video_id).execute()

            sb.table("video_activity_log").insert({
                "video_id": clean_video_id,
                "event_type": "YOUTUBE_UPLOAD_SUCCESS",
                "message": f"Successfully published via dashboard. ID: {yt_id}"
            }).execute()

            now_dt = datetime.now(timezone.utc)
            delete_after = (now_dt + timedelta(days=3)).isoformat()
            sb.table("scheduled_videos").update({
                "upload_status": "uploaded",
                "delete_after": delete_after,
                "youtube_video_id": yt_id,
                "uploaded_at": now
            }).eq("library_video_id", clean_video_id).execute()

            return {"status": "success", "message": "Published"}
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    except Exception as e:
        import traceback
        logger.error(f"Publish error: {e}")
        return {"status": "error", "message": str(e) + " - " + traceback.format_exc()[:200]}


@app.get("/api/dashboard/logs", summary="Get audit logs", description="Returns structured Supabase activity events and audit log history.")
async def get_dashboard_logs(limit: int = 50):
    from cloud.cloud_auth import get_supabase_client
    import os

    limit = max(1, min(limit, 100))

    # 1. Fetch structured activity events from video_activity_log
    activity_events = []
    try:
        sb = get_supabase_client()
        res = sb.table("video_activity_log").select("*, video_library(title, status, youtube_url)").order("created_at", desc=True).limit(limit).execute()
        activity_events = res.data or []
    except Exception as e:
        logger.debug(f"Activity log fetch skipped: {e}")

    # 2. Fetch local audit file lines
    local_logs = []
    log_path = "reelgrab_audit.log"
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    local_logs.append(line)
        local_logs.reverse()

    return {
        "activity_events": activity_events,
        "logs": local_logs[:limit]
    }


HEALTH_CACHE = {
    "data": None,
    "last_check": 0
}

@app.get("/api/health", summary="System Health Audit", description="Reports health of Backend, Supabase Database, Storage, Ollama GenAI, and YouTube Auth.")
async def health_check():
    import time
    global HEALTH_CACHE

    now = time.time()
    if HEALTH_CACHE["data"] and (now - HEALTH_CACHE["last_check"] < 20):
        return HEALTH_CACHE["data"]

    def _do_check():
        import urllib.request
        from cloud.cloud_auth import get_supabase_client
        health = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "backend": {"status": "ok", "message": "FastAPI running"},
                "database": {"status": "ok", "message": "Connected to Supabase DB"},
                "storage": {"status": "ok", "message": "Storage bucket accessible"},
                "ollama": {"status": "unknown", "message": ""},
                "youtube": {"status": "unknown", "message": ""},
                "disk": {"status": "ok", "message": "Storage disk healthy"},
                "ffmpeg": {"status": "ok", "message": "FFmpeg available"}
            }
        }

        # 1. Supabase Database check
        try:
            sb = get_supabase_client()
            sb.table("video_library").select("id").limit(1).execute()
        except Exception as e:
            health["services"]["database"] = {"status": "warning", "message": f"DB check: {str(e)[:60]}"}

        # 2. Ollama / Cloud AI check
        try:
            from backend.services.cloud_ai import is_cloud_ai_available
            if is_cloud_ai_available():
                health["services"]["ollama"] = {"status": "ok", "message": "ReelsMob Cloud AI active"}
            else:
                req = urllib.request.Request("http://127.0.0.1:11434/api/tags", method="GET")
                with urllib.request.urlopen(req, timeout=2.0) as resp:
                    if resp.status == 200:
                        health["services"]["ollama"] = {"status": "ok", "message": "Ollama active"}
        except Exception:
            health["services"]["ollama"] = {"status": "info", "message": "Ollama offline (fallback active)"}

        # 3. YouTube OAuth check
        yt_creds_path = os.path.join(os.path.dirname(__file__), "youtube_credentials.json")
        if os.path.exists(yt_creds_path) and os.path.getsize(yt_creds_path) > 10:
            health["services"]["youtube"] = {"status": "ok", "message": "YouTube OAuth token present"}
        else:
            health["services"]["youtube"] = {"status": "info", "message": "YouTube account not linked yet"}

        # 4. Disk check
        try:
            usage = shutil.disk_usage(DOWNLOAD_DIR)
            free_gb = usage.free / (1024 ** 3)
            health["services"]["disk"] = {"status": "ok", "message": f"{free_gb:.1f} GB available"}
        except Exception as e:
            health["services"]["disk"] = {"status": "warning", "message": str(e)}

        # 5. FFmpeg check
        ffmpeg_bin = "backend/ffmpeg.exe" if os.path.exists("backend/ffmpeg.exe") else shutil.which("ffmpeg")
        if not ffmpeg_bin:
            health["services"]["ffmpeg"] = {"status": "warning", "message": "FFmpeg not detected"}

        return health

    result = await asyncio.to_thread(_do_check)
    HEALTH_CACHE["data"] = result
    HEALTH_CACHE["last_check"] = now
    return result


@app.get("/api/health/detailed", summary="Detailed Health and Latency Audit", description="Reports latency in milliseconds for each external dependency.")
async def health_check_detailed():
    """Returns granular latency timings and operational status for all dependencies."""
    from cloud.cloud_auth import get_supabase_client
    import time
    from datetime import datetime, timezone

    t_start = time.perf_counter()
    dependencies: Dict[str, dict] = {}
    overall_healthy = True

    # 1. Supabase Database check with latency
    t0 = time.perf_counter()
    try:
        sb = get_supabase_client()
        sb.table("video_library").select("id").limit(1).execute()
        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        dependencies["database"] = {"status": "ok", "latency_ms": latency_ms, "message": "Supabase DB reachable"}
    except Exception as e:
        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        dependencies["database"] = {"status": "error", "latency_ms": latency_ms, "message": str(e)[:120]}
        overall_healthy = False

    # 2. Supabase Storage bucket access
    t0 = time.perf_counter()
    try:
        sb = get_supabase_client()
        sb.storage.from_("reelgrab-videos").list()
        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        dependencies["storage"] = {"status": "ok", "latency_ms": latency_ms, "message": "Storage bucket accessible"}
    except Exception as e:
        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        dependencies["storage"] = {"status": "warning", "latency_ms": latency_ms, "message": str(e)[:120]}

    # 3. AI Service status & latency
    t0 = time.perf_counter()
    try:
        from backend.services.cloud_ai import is_cloud_ai_available
        if is_cloud_ai_available():
            latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            dependencies["ai"] = {"status": "ok", "latency_ms": latency_ms, "provider": "ReelsMob Cloud AI"}
        else:
            req = urllib.request.Request("http://127.0.0.1:11434/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
                if resp.status == 200:
                    dependencies["ai"] = {"status": "ok", "latency_ms": latency_ms, "provider": "Ollama (local)"}
                else:
                    dependencies["ai"] = {"status": "offline", "latency_ms": latency_ms, "provider": "fallback"}
    except Exception:
        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        dependencies["ai"] = {"status": "offline", "latency_ms": latency_ms, "provider": "deterministic_fallback"}

    # 4. YouTube OAuth status
    yt_creds_path = os.path.join(os.path.dirname(__file__), "youtube_credentials.json")
    if os.path.exists(yt_creds_path) and os.path.getsize(yt_creds_path) > 10:
        dependencies["youtube"] = {"status": "configured", "message": "OAuth token file present"}
    else:
        dependencies["youtube"] = {"status": "unlinked", "message": "OAuth token file missing or empty"}

    # 5. Disk storage
    try:
        usage = shutil.disk_usage(DOWNLOAD_DIR)
        dependencies["disk"] = {
            "status": "ok" if usage.free > (500 * 1024 * 1024) else "warning",
            "free_gb": round(usage.free / (1024 ** 3), 2),
            "total_gb": round(usage.total / (1024 ** 3), 2)
        }
    except Exception as e:
        dependencies["disk"] = {"status": "error", "message": str(e)}

    # 6. FFmpeg availability
    ffmpeg_bin = "backend/ffmpeg.exe" if os.path.exists("backend/ffmpeg.exe") else shutil.which("ffmpeg")
    dependencies["ffmpeg"] = {
        "status": "ok" if ffmpeg_bin else "missing",
        "path": ffmpeg_bin or "Not Found"
    }

    total_latency_ms = round((time.perf_counter() - t_start) * 1000.0, 2)
    uptime_seconds = round(time.time() - APP_START_TIME, 1)

    return {
        "status": "healthy" if overall_healthy else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": uptime_seconds,
        "total_audit_latency_ms": total_latency_ms,
        "environment": ENVIRONMENT,
        "dependencies": dependencies
    }



@app.get("/api/health/ai", summary="AI Health Check")
async def health_check_ai():
    try:
        from backend.services.cloud_ai import is_cloud_ai_available
        if is_cloud_ai_available():
            return {
                "available": True,
                "provider": "ReelsMob Cloud AI",
                "models": ["gemini-3.6-flash (vision)", "groq/compound-mini (metadata)"],
                "status": "active"
            }
    except Exception:
        pass

    import urllib.request
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            if resp.status == 200:
                return {
                    "available": True,
                    "provider": "ollama",
                    "model": "qwen2.5:7b",
                    "endpoint": "http://127.0.0.1:11434"
                }
    except Exception as e:
        return {
            "available": False,
            "provider": "ollama",
            "error": "Ollama server not responding on port 11434",
            "fallback_enabled": True
        }


# ── Mount Frontend Single-Page App (SPA) for 24/7 Cloud Deployment ─────────
dist_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend-react", "dist")
if not os.path.exists(dist_dir):
    dist_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dist")

if os.path.exists(dist_dir):
    from fastapi.staticfiles import StaticFiles
    from starlette.responses import FileResponse

    assets_dir = os.path.join(dist_dir, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Don't intercept API or metadata routes
        if full_path.startswith("api/") or full_path.startswith("metadata/"):
            raise HTTPException(status_code=404, detail="Not Found")
        file_path = os.path.join(dist_dir, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(dist_dir, "index.html"))


