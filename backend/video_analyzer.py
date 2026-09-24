# video_analyzer.py
import os
import re
import json
import base64
import logging
import urllib.request
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

VIDEO_ANALYSIS_CACHE: Dict[str, dict] = {}

def get_installed_vision_model() -> Optional[str]:
    """Check if Cloud AI vision (Google Gemini Flash) is configured."""
    try:
        from backend.services.cloud_ai import get_gemini_api_key, get_gemini_model
        if get_gemini_api_key():
            return get_gemini_model()
    except Exception as e:
        logger.debug(f'Cloud vision model check error: {e}')
    return None

def find_video_file_for_request(url: str = '', raw_title: str = '', video_path: str = '') -> Optional[str]:
    if video_path and os.path.exists(video_path) and video_path.lower().endswith(('.mp4', '.mov', '.mkv', '.webm')) and os.path.getsize(video_path) > 1000:
        return video_path

    downloads_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'downloads')
    os.makedirs(downloads_dir, exist_ok=True)

    if url:
        shortcode_match = re.search(r'/(?:reel|p|shorts)/([A-Za-z0-9_-]+)', url)
        if shortcode_match:
            code = shortcode_match.group(1)
            candidate = os.path.join(downloads_dir, f'{code}.mp4')
            if os.path.exists(candidate) and os.path.getsize(candidate) > 1000:
                return candidate
            for f in os.listdir(downloads_dir):
                if f.startswith(code) and f.endswith('.mp4') and os.path.getsize(os.path.join(downloads_dir, f)) > 1000:
                    return os.path.join(downloads_dir, f)

    return None

def extract_video_frames(
    video_path: str,
    num_frames: int = 5,
    max_dim: int = 480,
    progress_callback = None
) -> List[str]:
    """
    Extracts 5 well-spaced keyframes downscaled to 480p using fast seek.
    Tuned for 0.1 vCPU environments without heavy memory/cpu pressure.
    """
    frames_b64: List[str] = []
    if not os.path.exists(video_path):
        return frames_b64

    # 1. Fast OpenCV keyframe extraction
    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        try:
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total_frames > 0:
                positions = [0.08, 0.28, 0.50, 0.72, 0.92][:num_frames]
                for i, pos in enumerate(positions):
                    frame_idx = int(total_frames * pos)
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        h, w = frame.shape[:2]
                        if max(h, w) > max_dim:
                            scale = max_dim / max(h, w)
                            frame = cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
                        ret_enc, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                        if ret_enc:
                            frames_b64.append(base64.b64encode(buf).decode('utf-8'))
                    if progress_callback:
                        pct = 30 + int(((i + 1) / len(positions)) * 20)
                        progress_callback(pct, f'Extracting frame {i + 1} of {len(positions)}...')
        finally:
            cap.release()
        if frames_b64:
            return frames_b64
    except Exception as e:
        logger.debug(f'cv2 frame extraction skipped: {e}')

    # 2. Ultrafast ffmpeg fallback with single-thread clamp
    from backend.fit_to_canvas import resolve_ffmpeg_binary
    ffmpeg_exe = resolve_ffmpeg_binary()
    if ffmpeg_exe:
        try:
            import subprocess, tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                cmd = [
                    ffmpeg_exe, '-y',
                    '-threads', '1',
                    '-i', video_path,
                    '-vf', f'fps=1,scale={max_dim}:-2',
                    '-vframes', str(num_frames),
                    '-preset', 'ultrafast',
                    '-q:v', '4',
                    os.path.join(tmpdir, 'frame_%02d.jpg')
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False, timeout=30)
                extracted_files = sorted(f for f in os.listdir(tmpdir) if f.endswith('.jpg'))
                for i, f in enumerate(extracted_files):
                    with open(os.path.join(tmpdir, f), 'rb') as img_f:
                        frames_b64.append(base64.b64encode(img_f.read()).decode('utf-8'))
                    if progress_callback:
                        pct = 30 + int(((i + 1) / max(1, len(extracted_files))) * 20)
                        progress_callback(pct, f'Extracting frame {i + 1} of {len(extracted_files)}...')
        except Exception as e:
            logger.debug(f'ffmpeg frame extraction skipped: {e}')

    return frames_b64

def transcribe_audio_dialogue(video_path: str) -> Optional[str]:
    """
    Transcribes spoken dialogue via faster-whisper.
    Skipped by default on Free-tier CPU (0.1 vCPU) to prevent 2-4 minute hangs and OOM crashes.
    """
    if not video_path or not os.path.exists(video_path):
        return None

    # Only run local whisper if explicitly enabled via environment variable.
    if not os.getenv('ENABLE_LOCAL_WHISPER', '').lower() in ('true', '1'):
        return None

    try:
        from faster_whisper import WhisperModel
        model = WhisperModel('tiny', device='cpu', compute_type='int8')
        segments, info = model.transcribe(video_path, beam_size=1)
        transcript_parts = [seg.text.strip() for seg in segments if seg.text.strip()]
        full_transcript = ' '.join(transcript_parts).strip()
        if full_transcript:
            logger.info(f'Audio transcription succeeded: {full_transcript[:100]}...')
            return full_transcript
    except Exception as e:
        logger.debug(f'Audio transcription skipped: {e}')

    return None

def analyze_frames_with_vision(frames_b64: List[str], vision_model: Optional[str] = None) -> Optional[str]:
    """Delegates video keyframe analysis to Gemini Flash."""
    if not frames_b64:
        return None
    try:
        from backend.services.cloud_ai import analyze_frames_with_gemini
        res = analyze_frames_with_gemini(frames_b64)
        if res.get("success"):
            return res.get("visual_summary")
    except Exception as e:
        logger.warning(f"Cloud vision analysis error: {e}")
    return None

def extract_frames_from_url(
    url: str,
    num_frames: int = 5,
    max_dim: int = 480,
    progress_callback = None
) -> List[str]:
    """
    Extracts preview/thumbnail frame(s) directly from a video URL without downloading the full video.
    This enables Gemini visual analysis even before the video is stored locally.
    """
    if not url:
        return []

    frames_b64: List[str] = []

    try:
        import yt_dlp
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'extract_flat': False,
            'socket_timeout': 10,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        candidate_urls: List[str] = []
        if info:
            thumbs = info.get('thumbnails') or []
            if isinstance(thumbs, list):
                for t in thumbs:
                    if isinstance(t, dict) and t.get('url'):
                        candidate_urls.append(t['url'])
            if info.get('thumbnail') and info['thumbnail'] not in candidate_urls:
                candidate_urls.insert(0, info['thumbnail'])

            selected_urls = []
            if candidate_urls:
                if len(candidate_urls) <= num_frames:
                    selected_urls = candidate_urls
                else:
                    selected_urls = [candidate_urls[-1]]
                    if len(candidate_urls) > 2:
                        selected_urls.append(candidate_urls[0])
                        selected_urls.append(candidate_urls[len(candidate_urls) // 2])

            for idx, thumb_url in enumerate(selected_urls[:num_frames]):
                try:
                    req = urllib.request.Request(
                        thumb_url,
                        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                    )
                    with urllib.request.urlopen(req, timeout=6) as resp:
                        img_bytes = resp.read()
                    if img_bytes and len(img_bytes) > 200:
                        try:
                            import cv2
                            import numpy as np
                            nparr = np.frombuffer(img_bytes, np.uint8)
                            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                            if img is not None:
                                h, w = img.shape[:2]
                                if max(h, w) > max_dim:
                                    scale = max_dim / max(h, w)
                                    img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
                                ret_enc, buf = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                                if ret_enc:
                                    frames_b64.append(base64.b64encode(buf).decode('utf-8'))
                                    if progress_callback:
                                        pct = 30 + int(((idx + 1) / max(1, len(selected_urls[:num_frames]))) * 20)
                                        progress_callback(pct, f'Extracting preview frame {idx + 1} of {len(selected_urls[:num_frames])}...')
                                    continue
                        except Exception:
                            pass
                        frames_b64.append(base64.b64encode(img_bytes).decode('utf-8'))
                        if progress_callback:
                            pct = 30 + int(((idx + 1) / max(1, len(selected_urls[:num_frames]))) * 20)
                            progress_callback(pct, f'Extracting preview frame {idx + 1} of {len(selected_urls[:num_frames])}...')
                except Exception as e:
                    logger.debug(f'Thumbnail frame download skipped for {thumb_url}: {e}')

        if frames_b64:
            logger.info(f'Extracted {len(frames_b64)} preview frame(s) from URL metadata: {url}')
            return frames_b64
    except Exception as e:
        logger.debug(f'URL thumbnail extraction skipped: {e}')

    return frames_b64


def analyze_video_content(
    video_path: Optional[str] = None,
    url: str = '',
    raw_title: str = '',
    raw_description: str = '',
    progress_callback = None,
    skip_audio: bool = True
) -> dict:
    resolved_path = video_path or find_video_file_for_request(url, raw_title)
    cache_key = resolved_path or (url if url else raw_title)
    
    if cache_key in VIDEO_ANALYSIS_CACHE:
        logger.info(f'⚡ Returning cached video analysis for: {cache_key}')
        return VIDEO_ANALYSIS_CACHE[cache_key]

    vision_model = get_installed_vision_model()
    visual_description = None
    audio_transcript = None
    vision_success = False
    audio_success = False
    vision_error = None
    frames = []

    if resolved_path and os.path.exists(resolved_path):
        logger.info(f'Analyzing actual video file: {resolved_path}')
        if progress_callback:
            progress_callback(30, 'Extracting video frames for visual analysis...')
        frames = extract_video_frames(resolved_path, num_frames=5, max_dim=480, progress_callback=progress_callback)
    elif url:
        logger.info(f'No local video file found; extracting preview frames from URL: {url}')
        if progress_callback:
            progress_callback(30, 'Extracting preview frame from video URL...')
        frames = extract_frames_from_url(url, num_frames=5, max_dim=480, progress_callback=progress_callback)

    if frames:
        # Cloud AI (Google Gemini Flash)
        try:
            from backend.services.cloud_ai import is_cloud_ai_available, analyze_frames_with_gemini
            if is_cloud_ai_available():
                if progress_callback:
                    progress_callback(52, f'Analyzing visual frames with Google Gemini ({vision_model or "Flash"})...')
                cloud_vision = analyze_frames_with_gemini(frames, caption=raw_description)
                if cloud_vision.get('success'):
                    visual_description = cloud_vision['visual_summary']
                    vision_success = True
                    vision_model = cloud_vision.get('model') or get_installed_vision_model() or 'gemini-2.0-flash'
                    logger.info(f'Gemini Cloud Vision analysis completed: {visual_description[:100]}...')
                else:
                    vision_error = cloud_vision.get('error')
                    logger.warning(f'Gemini vision unsuccessful: {vision_error}')
        except Exception as e:
            vision_error = str(e)
            logger.warning(f'Cloud vision attempt error: {e}')

    # Only run audio transcription if explicitly requested and visual analysis did not succeed
    if not skip_audio and not vision_success and resolved_path and os.path.exists(resolved_path):
        if progress_callback:
            progress_callback(60, 'Extracting audio and dialogue cues...')
        audio_transcript = transcribe_audio_dialogue(resolved_path)
        if audio_transcript:
            audio_success = True

    if vision_success:
        is_full_video = bool(resolved_path and os.path.exists(resolved_path))
        analysis_source = 'video_visual' if is_full_video else 'video_preview'
        source_label = 'Based on video analysis' if is_full_video else 'Based on video preview frame'
    elif audio_success:
        analysis_source = 'video_audio'
        source_label = 'Based on video dialogue analysis'
    else:
        analysis_source = 'caption_fallback'
        source_label = 'From caption context & hashtags'

    result = {
        'video_analyzed': vision_success or audio_success,
        'vision_success': vision_success,
        'audio_success': audio_success,
        'vision_model_used': vision_model if vision_success else None,
        'visual_description': visual_description or '',
        'audio_transcript': audio_transcript or '',
        'analysis_source': analysis_source,
        'source_label': source_label,
        'video_path': resolved_path,
        'vision_hint': 'Configure GEMINI_API_KEY in environment to enable visual frame understanding.' if not vision_success else None,
        'vision_error': vision_error if not vision_success else None
    }

    if len(VIDEO_ANALYSIS_CACHE) >= 100:
        VIDEO_ANALYSIS_CACHE.pop(next(iter(VIDEO_ANALYSIS_CACHE)), None)
    VIDEO_ANALYSIS_CACHE[cache_key] = result
    return result

def check_anti_copy_paste(generated_text: str, raw_caption: str, threshold: float = 0.65) -> bool:
    if not generated_text or not raw_caption:
        return False

    gen_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', generated_text.lower()))
    cap_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', raw_caption.lower()))
    
    if not gen_words or not cap_words:
        return False

    overlap = gen_words.intersection(cap_words)
    similarity = len(overlap) / max(len(gen_words), 1)
    
    return similarity >= threshold
