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

VISION_MODEL_CANDIDATES = [
    'moondream:latest',
    'moondream',
    'llava:latest',
    'llava:7b',
    'llava',
    'qwen2.5vl:7b',
    'qwen2.5vl:3b',
    'qwen2.5vl',
    'llama3.2-vision:11b',
    'llama3.2-vision',
    'minicpm-v',
    'bakllava'
]

def get_installed_vision_model() -> Optional[str]:
    try:
        req = urllib.request.Request('http://127.0.0.1:11434/api/tags', method='GET')
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            installed_names = [m.get('name', '') for m in data.get('models', [])]
            for candidate in VISION_MODEL_CANDIDATES:
                for installed in installed_names:
                    if candidate in installed or installed.startswith(candidate):
                        return installed
    except Exception as e:
        logger.debug(f'Vision model check error: {e}')
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

    # If video is not downloaded yet, auto-download it with yt_dlp so vision model has the actual footage!
    if url and any(domain in url for domain in ['instagram.com', 'youtube.com', 'youtu.be', 'tiktok.com']):
        try:
            logger.info(f"Auto-downloading video for vision frame analysis: {url}")
            import yt_dlp
            ydl_opts = {
                'outtmpl': os.path.join(downloads_dir, '%(id)s.%(ext)s'),
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'quiet': True,
                'no_warnings': True,
                'noplaylist': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info:
                    vid_id = info.get('id')
                    expected = os.path.join(downloads_dir, f"{vid_id}.mp4")
                    if os.path.exists(expected) and os.path.getsize(expected) > 1000:
                        return expected
                    for f in os.listdir(downloads_dir):
                        if f.startswith(str(vid_id)) and f.endswith('.mp4') and os.path.getsize(os.path.join(downloads_dir, f)) > 1000:
                            return os.path.join(downloads_dir, f)
        except Exception as e:
            logger.warning(f"Could not auto-download video for vision analysis: {e}")

    return None

def extract_video_frames(video_path: str, num_frames: int = 5, max_dim: int = 512) -> List[str]:
    frames_b64: List[str] = []
    if not os.path.exists(video_path):
        return frames_b64

    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames > 0:
            positions = [0.05, 0.25, 0.50, 0.75, 0.95][:num_frames]
            for pos in positions:
                frame_idx = int(total_frames * pos)
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()
                if ret and frame is not None:
                    h, w = frame.shape[:2]
                    if max(h, w) > max_dim:
                        scale = max_dim / max(h, w)
                        frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
                    ret_enc, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                    if ret_enc:
                        frames_b64.append(base64.b64encode(buf).decode('utf-8'))
            cap.release()
            if frames_b64:
                return frames_b64
    except Exception as e:
        logger.debug(f'cv2 frame extraction skipped: {e}')

    ffmpeg_exe = os.path.join(os.path.dirname(__file__), 'ffmpeg.exe')
    if os.path.exists(ffmpeg_exe):
        try:
            import subprocess, tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                cmd = [
                    ffmpeg_exe, '-y', '-i', video_path,
                    '-vf', f'fps=1,scale={max_dim}:-1',
                    '-vframes', str(num_frames),
                    os.path.join(tmpdir, 'frame_%02d.jpg')
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                for f in sorted(os.listdir(tmpdir)):
                    if f.endswith('.jpg'):
                        with open(os.path.join(tmpdir, f), 'rb') as img_f:
                            frames_b64.append(base64.b64encode(img_f.read()).decode('utf-8'))
        except Exception as e:
            logger.debug(f'ffmpeg frame extraction skipped: {e}')

    return frames_b64

def transcribe_audio_dialogue(video_path: str) -> Optional[str]:
    if not video_path or not os.path.exists(video_path):
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

def analyze_frames_with_vision(frames_b64: List[str], vision_model: str) -> Optional[str]:
    if not frames_b64 or not vision_model:
        return None

    prompt = (
        'You are an expert video content analyst. These are sequential frames from a video clip.\n'
        'Describe what is ACTUALLY happening in the footage:\n'
        '- Who and what is on screen (actors, people, setting, objects)\n'
        '- Actions, physical gestures, and emotional expressions\n'
        '- Any visible text overlays or subtitles\n'
        '- The core story moment, twist, or mood (e.g. romance, heartbreak, comedy, suspense)\n'
        'Provide a concise, factual 2-3 sentence visual summary.'
    )

    payload = {
        'model': vision_model,
        'prompt': prompt,
        'images': [frames_b64[min(1, len(frames_b64)-1)]],  # 1 key frame for optimal CPU inference speed
        'stream': False,
        'options': {
            'temperature': 0.2,
            'num_predict': 90,
            'num_thread': 8,
        }
    }

    try:
        req = urllib.request.Request(
            'http://127.0.0.1:11434/api/generate',
            data=json.dumps(payload).encode('utf-8'),
            method='POST',
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=120.0) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data.get('response', '').strip()
    except Exception as e:
        logger.warning(f'Vision model error with {vision_model}: {e}')
        return None

def analyze_video_content(
    video_path: Optional[str] = None,
    url: str = '',
    raw_title: str = '',
    raw_description: str = '',
    progress_callback = None
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

    if resolved_path and os.path.exists(resolved_path):
        logger.info(f'Analyzing actual video file: {resolved_path}')
        
        if progress_callback:
            progress_callback(30, 'Extracting video frames for visual analysis...')
        frames = extract_video_frames(resolved_path, num_frames=5)
        
        # 1. First priority: High-speed Cloud AI (Gemini 3.6 Flash)
        try:
            from backend.services.cloud_ai import is_cloud_ai_available, analyze_frames_with_gemini
            if is_cloud_ai_available() and frames:
                if progress_callback:
                    progress_callback(45, 'Analyzing visual frames with Google Gemini 3.6 Flash...')
                cloud_vision = analyze_frames_with_gemini(frames, caption=raw_description)
                if cloud_vision.get('success'):
                    visual_description = cloud_vision['visual_summary']
                    vision_success = True
                    vision_model = 'gemini-3.6-flash'
                    logger.info(f'Gemini Cloud Vision analysis completed: {visual_description[:100]}...')
        except Exception as e:
            logger.warning(f'Cloud vision attempt error: {e}')

        # 2. Local vision model fallback if cloud not available
        if not vision_success and frames and vision_model:
            if progress_callback:
                progress_callback(45, f'Analyzing visual frames with local vision model ({vision_model})...')
            visual_description = analyze_frames_with_vision(frames, vision_model)
            if visual_description:
                vision_success = True
                logger.info(f'Local vision analysis completed: {visual_description[:100]}...')
        elif not vision_success and not vision_model:
            logger.info('No local vision model found in Ollama.')

        if progress_callback:
            progress_callback(60, 'Extracting audio and dialogue cues...')
        audio_transcript = transcribe_audio_dialogue(resolved_path)
        if audio_transcript:
            audio_success = True

    if vision_success:
        analysis_source = 'video_visual'
        source_label = 'Based on video analysis'
    elif audio_success:
        analysis_source = 'video_audio'
        source_label = 'Based on video dialogue analysis'
    else:
        analysis_source = 'caption_fallback'
        source_label = 'From caption — video analysis unavailable'

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
        'vision_hint': 'To enable visual frame understanding, run: ollama pull qwen2.5vl:7b or ollama pull llava' if not vision_model else None
    }

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
