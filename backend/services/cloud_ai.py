"""
cloud_ai.py — High-performance Cloud AI Pipeline for ReelsMob.
Uses:
- Google Gemini 3.6 Flash: Deep video/keyframe visual analysis ($0, zero GPU).
- Groq Qwen 3.6 27B: Sub-second viral title, description & hashtag synthesis.
"""

import os
import re
import json
import base64
import logging
import urllib.request
import urllib.error
from typing import List, Dict, Any

logger = logging.getLogger('reelsmob.cloud_ai')

try:
    from dotenv import load_dotenv
    load_dotenv()
    _cloud_env = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'cloud', '.env')
    if os.path.exists(_cloud_env):
        load_dotenv(_cloud_env)
except Exception:
    pass

def get_gemini_api_key() -> str:
    """Dynamically resolves Gemini/Google API key from environment."""
    return (os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_KEY') or '').strip().strip("'\"")


def get_groq_api_key() -> str:
    """Dynamically resolves Groq API key from environment."""
    return (os.getenv('GROQ_API_KEY') or os.getenv('GROQ_KEY') or '').strip().strip("'\"")


def get_gemini_model() -> str:
    """Returns valid Gemini model ID, normalizing non-existent/legacy identifiers."""
    raw = (os.getenv('GEMINI_MODEL') or '').strip().strip("'\"")
    if not raw or raw in ('gemini-3.6-flash', 'gemini-flash', 'gemini'):
        return 'gemini-2.0-flash'
    return raw


def get_groq_model() -> str:
    """Returns valid Groq model ID, normalizing OpenRouter slugs and legacy identifiers."""
    raw = (os.getenv('GROQ_MODEL') or '').strip().strip("'\"")
    if not raw or raw in ('groq/compound-mini', 'compound-mini', 'groq-compound'):
        return 'llama-3.3-70b-versatile'
    return raw


# Module-level references for backwards compatibility
GEMINI_API_KEY = get_gemini_api_key()
GROQ_API_KEY = get_groq_api_key()
GEMINI_MODEL = get_gemini_model()
GROQ_MODEL = get_groq_model()
STANDARD_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'


def is_cloud_ai_available() -> bool:
    """Returns True if both Gemini and Groq keys are configured."""
    return bool(get_gemini_api_key() and get_groq_api_key())


def get_cloud_ai_status() -> Dict[str, Any]:
    """Returns structured status of cloud AI providers for health checks and diagnostics."""
    gemini_key = get_gemini_api_key()
    groq_key = get_groq_api_key()
    return {
        'gemini_configured': bool(gemini_key),
        'groq_configured': bool(groq_key),
        'gemini_model': get_gemini_model(),
        'groq_model': get_groq_model(),
        'is_available': bool(gemini_key and groq_key)
    }


logger.info(
    f"Cloud AI initialized: Gemini={'CONFIGURED' if get_gemini_api_key() else 'MISSING'} "
    f"({get_gemini_model()}), Groq={'CONFIGURED' if get_groq_api_key() else 'MISSING'} "
    f"({get_groq_model()})"
)


def analyze_frames_with_gemini(frame_paths: List[str], caption: str = '') -> Dict[str, Any]:
    """
    Sends keyframe images to Google Gemini for visual & emotional analysis.
    """
    gemini_key = get_gemini_api_key()
    if not gemini_key:
        logger.warning('Gemini vision skipped: GEMINI_API_KEY not configured.')
        return {
            'visual_summary': caption or 'A short video scene',
            'success': False,
            'error': 'GEMINI_API_KEY not configured'
        }

    gemini_model = get_gemini_model()
    parts = []
    prompt = (
        'You are an expert video analyst for short-form content (YouTube Shorts & Instagram Reels).\n'
        'Carefully inspect these video frames to understand what is ACTUALLY happening in this video.\n'
        'Describe:\n'
        '1. VISUAL_SUMMARY: What is physically happening on screen? (Characters, clothing, expressions, gestures, setting, actions)\n'
        '2. VISUAL_HOOK: What is the most eye-catching or unexpected visual moment?\n'
        '3. MOOD_EMOTION: The emotional tone (e.g., romantic, hilarious, shocking, heartbreak, inspirational, suspenseful).\n'
    )
    if caption:
        prompt += f'\n(Original caption context for reference: {caption[:200]})\n'

    prompt += '\nProvide a concise analysis focusing on what the viewer SEES.'
    parts.append({'text': prompt})

    # Encode up to 3 frames as base64 JPEG
    for item in frame_paths[:3]:
        try:
            if os.path.exists(item):
                with open(item, 'rb') as f:
                    data = base64.b64encode(f.read()).decode('utf-8')
            elif len(item) > 100:
                # Already base64 encoded
                data = item
            else:
                continue

            parts.append({
                'inline_data': {
                    'mime_type': 'image/jpeg',
                    'data': data
                }
            })
        except Exception as e:
            logger.warning(f'Failed to process frame: {e}')

    url = f'https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={gemini_key}'
    payload = json.dumps({'contents': [{'parts': parts}]}).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json', 'User-Agent': STANDARD_USER_AGENT})

    from backend.retry import sync_retry

    def _execute():
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as he:
            try:
                err_text = he.read().decode('utf-8', errors='ignore')
            except Exception:
                err_text = str(he)
            raise RuntimeError(f"Gemini API error ({he.code}): {err_text}") from he

    try:
        data = sync_retry(_execute, max_retries=3, operation_name="gemini_vision")
        raw_text = data['candidates'][0]['content']['parts'][0]['text']
        logger.info(f'Gemini visual analysis completed using {gemini_model} ({len(raw_text)} chars)')
        return {
            'visual_summary': raw_text.strip(),
            'model': gemini_model,
            'success': True
        }
    except Exception as e:
        logger.error(f'Gemini vision request failed ({gemini_model}): {e}')
        return {
            'visual_summary': caption or 'A short video scene',
            'model': gemini_model,
            'success': False,
            'error': str(e)
        }


def generate_metadata_with_gemini(visual_summary: str, caption: str = '') -> Dict[str, Any]:
    """Fallback generator using Gemini if Groq is unavailable."""
    gemini_key = get_gemini_api_key()
    if not gemini_key:
        return {'success': False, 'error': 'GEMINI_API_KEY not configured'}

    gemini_model = get_gemini_model()
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={gemini_key}'
    prompt = (
        'You are an expert YouTube Shorts and Reels growth strategist.\n'
        'Based on this visual video footage, generate viral metadata:\n'
        f'Visual analysis: {visual_summary}\n'
        f'Caption context: {caption}\n\n'
        'Return ONLY valid JSON with exactly these keys:\n'
        '{\n'
        '  "title": "A single punchy viral title with 1-2 relevant emojis (under 60 chars)",\n'
        '  "description": "2-3 engaging sentences describing the scene, emotional hook, and a natural call to action",\n'
        '  "youtube_hashtags": ["#Shorts", "#ShortsFeed", "#Viral", ... 8 to 15 relevant tags],\n'
        '  "instagram_hashtags": ["#reels", "#viral", ... 15 to 25 relevant tags]\n'
        '}'
    )
    payload = json.dumps({
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {'responseMimeType': 'application/json'}
    }).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json', 'User-Agent': STANDARD_USER_AGENT})
    from backend.retry import sync_retry

    def _call_gemini_meta():
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as he:
            try:
                err_text = he.read().decode('utf-8', errors='ignore')
            except Exception:
                err_text = str(he)
            raise RuntimeError(f"Gemini metadata API error ({he.code}): {err_text}") from he

    try:
        data = sync_retry(_call_gemini_meta, max_retries=3, operation_name="gemini_metadata")
        raw = data['candidates'][0]['content']['parts'][0]['text']
        parsed = json.loads(raw)
        yt_tags = parsed.get('youtube_hashtags', ['#Shorts', '#ShortsFeed', '#Viral'])
        ig_tags = parsed.get('instagram_hashtags', ['#Reels', '#ExplorePage'])
        return {
            'title': parsed.get('title', 'Must Watch Scene 🔥'),
            'description': parsed.get('description', visual_summary[:200]),
            'youtube_hashtags': yt_tags[:15],
            'instagram_hashtags': ig_tags[:30],
            'hashtags': list(dict.fromkeys(yt_tags + ig_tags))[:25],
            'model': gemini_model,
            'success': True
        }
    except Exception as e:
        logger.error(f'Gemini metadata fallback failed ({gemini_model}): {e}')
        return {'success': False, 'error': str(e)}


def generate_metadata_with_groq(visual_summary: str, caption: str = '') -> Dict[str, Any]:
    """
    Calls Groq to synthesize a single winning viral title,
    compelling description, and high-CTR hashtags based on visual evidence.
    """
    groq_key = get_groq_api_key()
    if not groq_key:
        logger.warning('Groq metadata skipped: GROQ_API_KEY not configured. Trying Gemini fallback...')
        gemini_fallback = generate_metadata_with_gemini(visual_summary, caption=caption)
        if gemini_fallback.get('success'):
            gemini_fallback['fallback_reason'] = 'groq_unconfigured_used_gemini'
            return gemini_fallback
        return {
            'title': 'Must Watch Viral Scene 🔥',
            'description': visual_summary[:200] if visual_summary else 'Watch this incredible scene unfold.',
            'youtube_hashtags': ['#Shorts', '#ShortsFeed', '#Viral'],
            'instagram_hashtags': ['#Reels', '#ExplorePage'],
            'hashtags': ['#Shorts', '#ShortsFeed', '#Viral', '#Reels'],
            'success': False,
            'error': 'GROQ_API_KEY not configured',
            'fallback_reason': 'GROQ_API_KEY not configured'
        }

    groq_model = get_groq_model()
    system_prompt = (
        'You are the world top YouTube Shorts and Instagram Reels growth strategist.\n'
        'You produce viral metadata directly grounded in visual video footage.\n'
        'Return ONLY a valid JSON object with EXACTLY these keys:\n'
        '{\n'
        '  "title": "A single punchy viral title with 1-2 relevant emojis (under 60 chars)",\n'
        '  "description": "2-3 engaging sentences describing the scene, emotional hook, and a natural call to action",\n'
        '  "youtube_hashtags": ["#Shorts", "#ShortsFeed", "#Viral", ... 8 to 15 relevant tags],\n'
        '  "instagram_hashtags": ["#reels", "#viral", ... 15 to 25 relevant tags]\n'
        '}\n'
        'Rules:\n'
        '- Base the title and hook strictly on what is happening in the visual summary.\n'
        '- Output RAW JSON only with no markdown fences.'
    )

    user_prompt = f'Visual footage analysis from Gemini:\n{visual_summary}\n\n'
    if caption:
        user_prompt += f'Caption context: {caption}\n\n'
    user_prompt += 'Generate the viral JSON metadata now.'

    payload = json.dumps({
        'model': groq_model,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt}
        ],
        'response_format': {'type': 'json_object'},
        'temperature': 0.6,
        'max_tokens': 500
    }).encode('utf-8')

    req = urllib.request.Request(
        'https://api.groq.com/openai/v1/chat/completions',
        data=payload,
        headers={
            'Authorization': f'Bearer {groq_key}',
            'Content-Type': 'application/json',
            'User-Agent': STANDARD_USER_AGENT
        }
    )

    from backend.retry import sync_retry

    def _call_groq():
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as he:
            try:
                err_text = he.read().decode('utf-8', errors='ignore')
            except Exception:
                err_text = str(he)
            raise RuntimeError(f"Groq API error ({he.code}): {err_text}") from he

    try:
        data = sync_retry(_call_groq, max_retries=3, operation_name="groq_metadata")
        content = data['choices'][0]['message']['content'].strip()
        
        # Extract JSON block
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            content = match.group(0)

        parsed = json.loads(content)
        
        yt_tags = parsed.get('youtube_hashtags', [])
        if not isinstance(yt_tags, list):
            yt_tags = [str(yt_tags)]
        if '#Shorts' not in yt_tags and '#shorts' not in [t.lower() for t in yt_tags]:
            yt_tags.insert(0, '#Shorts')
            yt_tags.insert(1, '#ShortsFeed')

        ig_tags = parsed.get('instagram_hashtags', [])
        if not isinstance(ig_tags, list):
            ig_tags = [str(ig_tags)]

        all_tags = list(dict.fromkeys(yt_tags + ig_tags))

        return {
            'title': parsed.get('title', 'Must Watch Viral Scene 🔥'),
            'description': parsed.get('description', visual_summary[:200]),
            'youtube_hashtags': yt_tags[:15],
            'instagram_hashtags': ig_tags[:30],
            'hashtags': all_tags[:25],
            'model': groq_model,
            'success': True
        }
    except Exception as e:
        logger.warning(f'Groq generation error ({groq_model}): {e}, falling back to Gemini...')
        # Try Gemini fallback
        gemini_fallback = generate_metadata_with_gemini(visual_summary, caption=caption)
        if gemini_fallback.get('success'):
            gemini_fallback['fallback_reason'] = f'groq_failed_used_gemini: {e}'
            return gemini_fallback

        fallback_tags = ['#Shorts', '#ShortsFeed', '#Viral', '#Trending', '#MovieClips', '#Cinema', '#MustWatch']
        gemini_err = gemini_fallback.get('error', 'unavailable')
        return {
            'title': 'Unbelievable Moment Caught on Camera 🎬',
            'description': visual_summary[:200] if visual_summary else 'Watch this incredible scene unfold.',
            'youtube_hashtags': fallback_tags,
            'instagram_hashtags': fallback_tags + ['#Reels', '#ExplorePage'],
            'hashtags': fallback_tags,
            'success': False,
            'error': f'Groq error: {e}. Gemini fallback error: {gemini_err}',
            'fallback_reason': f'groq_error: {e}'
        }


def run_cloud_pipeline(frame_paths: List[str], caption: str = '') -> Dict[str, Any]:
    """
    Executes the full Gemini -> Groq cloud AI pipeline.
    """
    logger.info(f'Running ReelsMob Cloud AI pipeline with {len(frame_paths)} frames...')
    vision_res = analyze_frames_with_gemini(frame_paths, caption=caption)
    visual_summary = vision_res.get('visual_summary', '')
    meta_res = generate_metadata_with_groq(visual_summary, caption=caption)

    return {
        'title': meta_res['title'],
        'description': meta_res['description'],
        'youtube_hashtags': meta_res['youtube_hashtags'],
        'instagram_hashtags': meta_res['instagram_hashtags'],
        'hashtags': meta_res['hashtags'],
        'visual_summary': visual_summary,
        'video_analyzed': vision_res.get('success', False),
        'source_label': 'Based on video analysis' if vision_res.get('success') else 'From caption',
        'provider': f'Cloud AI ({get_gemini_model()} + {get_groq_model()})'
    }
