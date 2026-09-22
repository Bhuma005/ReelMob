"""
cloud_ai.py — High-performance Cloud AI Pipeline for ReelsMob.
Uses:
- Google Gemini 3.6 Flash: Deep video/keyframe visual analysis ($0, zero GPU).
- Groq Qwen 3.6 27B: Sub-second viral title, description & hashtag synthesis.
"""

import os
import re
import json
import time
import base64
import logging
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional

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
    if not raw or raw in ('gemini-2.0-flash', 'gemini-2.5-flash', 'gemini-flash', 'gemini'):
        return 'gemini-3.6-flash'
    return raw


def get_groq_model() -> str:
    """Returns valid Groq model ID, normalizing OpenRouter slugs and legacy identifiers."""
    raw = (os.getenv('GROQ_MODEL') or '').strip().strip("'\"")
    if not raw or raw in ('groq/compound-mini', 'compound-mini', 'groq-compound', 'llama-3.3-70b-versatile'):
        return 'openai/gpt-oss-120b'
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

_MODEL_CACHE_TTL_SECONDS = 300.0
_MODEL_VALIDITY_CACHE: Dict[str, Dict[str, Any]] = {
    "groq": {"timestamp": 0.0, "data": None},
    "gemini": {"timestamp": 0.0, "data": None},
}


def verify_groq_model_active(groq_key: Optional[str] = None, model: Optional[str] = None, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Checks if configured Groq model is active via GET https://api.groq.com/openai/v1/models.
    Cached for 5 minutes unless force_refresh is True.
    """
    key = (groq_key or get_groq_api_key()).strip()
    target_model = (model or get_groq_model()).strip()

    if not key:
        return {
            "valid": None,
            "status": "unconfigured",
            "model": target_model,
            "message": "GROQ_API_KEY not configured"
        }

    now = time.time()
    cache_entry = _MODEL_VALIDITY_CACHE["groq"]
    if not force_refresh and cache_entry["data"] and (now - cache_entry["timestamp"] < _MODEL_CACHE_TTL_SECONDS):
        if cache_entry["data"].get("model") == target_model:
            return cache_entry["data"]

    url = "https://api.groq.com/openai/v1/models"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {key}",
            "User-Agent": STANDARD_USER_AGENT,
            "Accept": "application/json"
        },
        method="GET"
    )

    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = [m.get("id") for m in data.get("data", []) if isinstance(m, dict)]
            if target_model in models:
                res = {
                    "valid": True,
                    "status": "active",
                    "model": target_model,
                    "message": f"Model '{target_model}' is active on Groq"
                }
            else:
                warning_msg = f"WARNING: configured GROQ_MODEL '{target_model}' not found in Groq's active model list — AI generation will fail until this is fixed."
                logger.warning(warning_msg)
                res = {
                    "valid": False,
                    "status": "missing",
                    "model": target_model,
                    "message": warning_msg
                }
    except Exception as exc:
        logger.warning(f"Groq model verification failed: {exc}")
        res = {
            "valid": False,
            "status": "error",
            "model": target_model,
            "message": f"Failed to verify model against Groq API: {str(exc)[:120]}"
        }

    _MODEL_VALIDITY_CACHE["groq"] = {"timestamp": now, "data": res}
    return res


def verify_gemini_model_active(gemini_key: Optional[str] = None, model: Optional[str] = None, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Checks if configured Gemini model is active via GET https://generativelanguage.googleapis.com/v1beta/models.
    Cached for 5 minutes unless force_refresh is True.
    """
    key = (gemini_key or get_gemini_api_key()).strip()
    target_model = (model or get_gemini_model()).strip()

    if not key:
        return {
            "valid": None,
            "status": "unconfigured",
            "model": target_model,
            "message": "GEMINI_API_KEY not configured"
        }

    now = time.time()
    cache_entry = _MODEL_VALIDITY_CACHE["gemini"]
    if not force_refresh and cache_entry["data"] and (now - cache_entry["timestamp"] < _MODEL_CACHE_TTL_SECONDS):
        if cache_entry["data"].get("model") == target_model:
            return cache_entry["data"]

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": STANDARD_USER_AGENT,
            "Accept": "application/json"
        },
        method="GET"
    )

    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_models = [m.get("name", "") for m in data.get("models", []) if isinstance(m, dict)]
            models = [m.replace("models/", "") for m in raw_models] + raw_models
            if target_model in models:
                res = {
                    "valid": True,
                    "status": "active",
                    "model": target_model,
                    "message": f"Model '{target_model}' is active on Gemini"
                }
            else:
                warning_msg = f"WARNING: configured GEMINI_MODEL '{target_model}' not found in Gemini's active model list."
                logger.warning(warning_msg)
                res = {
                    "valid": False,
                    "status": "missing",
                    "model": target_model,
                    "message": warning_msg
                }
    except Exception as exc:
        logger.warning(f"Gemini model verification failed: {exc}")
        res = {
            "valid": False,
            "status": "error",
            "model": target_model,
            "message": f"Failed to verify model against Gemini API: {str(exc)[:120]}"
        }

    _MODEL_VALIDITY_CACHE["gemini"] = {"timestamp": now, "data": res}
    return res


def run_startup_model_self_check() -> Dict[str, Any]:
    """
    Lightweight self-check executed during startup.
    Confirms active model status for configured keys without blocking or crashing on failure.
    """
    results = {}
    if get_groq_api_key():
        results["groq"] = verify_groq_model_active(force_refresh=True)
    if get_gemini_api_key():
        results["gemini"] = verify_gemini_model_active(force_refresh=True)
    return results


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

    # Encode up to 5 frames as base64 JPEG
    for item in frame_paths[:5]:
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

    models_to_try = [gemini_model]
    if 'gemini-3-flash-preview' not in models_to_try:
        models_to_try.append('gemini-3-flash-preview')

    from backend.retry import sync_retry

    last_err = None
    for model_name in models_to_try:
        url = f'https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_key}'
        payload = json.dumps({'contents': [{'parts': parts}]}).encode('utf-8')
        req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json', 'User-Agent': STANDARD_USER_AGENT})

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
            data = sync_retry(_execute, max_retries=2, operation_name=f"gemini_vision_{model_name}")
            raw_text = data['candidates'][0]['content']['parts'][0]['text']
            logger.info(f'Gemini visual analysis completed using {model_name} ({len(raw_text)} chars)')
            return {
                'visual_summary': raw_text.strip(),
                'model': model_name,
                'success': True
            }
        except Exception as e:
            last_err = e
            logger.warning(f"Gemini vision request failed on {model_name}: {e}")
            continue

    logger.error(f'Gemini vision request failed ({gemini_model}): {last_err}')
    return {
        'visual_summary': caption or 'A short video scene',
        'model': gemini_model,
        'success': False,
        'error': str(last_err)
    }


VIRAL_METADATA_SYSTEM_PROMPT = (
    "You are the world's top YouTube Shorts and Instagram Reels growth strategist and viral copywriter.\n"
    "Your job is to transform raw visual video footage and caption notes into ultra-high CTR (Click-Through Rate) and high-retention metadata.\n\n"
    "### CRITICAL TITLE RULES (YouTube Shorts & Reels):\n"
    "1. LENGTH: STRICTLY UNDER 60 CHARACTERS. Mobile feeds truncate titles longer than 60 characters.\n"
    "2. FIRST 3 WORDS HOOK: Place the primary curiosity or emotional hook in the first 2-4 words.\n"
    "3. BAN GENERIC PHRASES: NEVER use filler like 'Must Watch', 'Amazing Video', 'Incredible Scene', 'Wait For It', 'Check This Out'.\n"
    "4. TOP-PERFORMING SHORT-FORM PATTERNS:\n"
    "   - Bold Curiosity / Unfinished Story: 'He thought nobody saw this...', 'The ending changed everything'\n"
    "   - Question Hook: 'Why did he do this?', 'Did you notice the detail at 0:02?'\n"
    "   - High Stakes / Tension: 'Neither driver would back down', 'He had 3 seconds to decide'\n"
    "   - Specificity / Numbers: 'This 1 mistake cost everything', '3 seconds before disaster'\n"
    "5. EMOJIS: Maximum 1-2 relevant emojis at the end.\n\n"
    "### DESCRIPTION RULES (Structured 2-4 Short Sections):\n"
    "1. LINE 1 (ABOVE-THE-FOLD HOOK): A captivating 1-sentence hook (under 120 chars) visible before the viewer clicks '...more'.\n"
    "2. BODY (1-2 SHORT PARAGRAPHS): Synthesize the core tension, action, or context from visual footage and caption. Explain what makes this moment memorable.\n"
    "3. CALL TO ACTION (CTA): End with an engaging question or natural CTA (e.g. 'What would you have done? Comment below 👇', 'Subscribe for daily thrilling clips 🔔').\n\n"
    "### HASHTAG RULES:\n"
    "1. YouTube: 7 to 15 hashtags. Dynamic mix of 2-3 broad tags (#Shorts, #ShortsFeed, #Viral) + 5-10 specific niche tags derived directly from visual and caption entities (subjects, emotion, genre).\n"
    "2. Instagram: 12 to 22 hashtags. Mix of broad (#Reels, #ExplorePage, #ViralReels) + targeted niche tags.\n\n"
    "### FEW-SHOT BENCHMARKS (Study these before generating):\n"
    "Example 1 (Action / Danger):\n"
    "- Footage: Man leaps between two tall buildings and barely catches the edge with one hand.\n"
    "- Mediocre: 'Must Watch Amazing Rooftop Jump Scene 🔥' (Boring, generic)\n"
    "- Viral Title: 'He Almost Missed The Ledge 😱'\n"
    "- Description: 'One slip and it\\'s over. Watch how close this rooftop jump was to total disaster.\\n\\nWould you ever attempt something this reckless? Let us know in the comments 👇\\n\\nSubscribe for more edge-of-your-seat moments!'\n\n"
    "Example 2 (Skills / Food / Curiosity):\n"
    "- Footage: Street chef slices an entire bag of onions in 5 seconds using an unconventional blade angle.\n"
    "- Mediocre: 'Incredible Chef Cutting Onion Video' (Dull description)\n"
    "- Viral Title: 'Why Chefs Never Cut Onions Like This 🧅'\n"
    "- Description: '5 seconds is all it took. This street food master uses a knife technique that culinary schools strictly forbid.\\n\\nHave you ever seen chopping speed like this?\\n\\nFollow for more daily street food skills!'\n\n"
    "Example 3 (Conflict / Drama / Standoff):\n"
    "- Footage: Two SUV drivers meet head-on on a one-lane mountain bridge and neither backs down.\n"
    "- Mediocre: 'Crazy Car Standoff on Narrow Bridge' (Generic phrase)\n"
    "- Viral Title: 'Neither Driver Refused To Back Up 💀'\n"
    "- Description: 'A complete standoff 500 feet in the air. Neither driver budged an inch on this single-lane bridge pass.\\n\\nWho was in the right here? Tell us your verdict below 👇\\n\\nDrop a like if you wouldn\\'t survive this bridge!'\n\n"
    "Return ONLY a valid JSON object matching this schema:\n"
    "{\n"
    "  \"title\": \"<High-CTR viral title strictly under 60 chars>\",\n"
    "  \"description\": \"<Structured 2-4 short paragraphs with hook, scene context, and CTA>\",\n"
    "  \"youtube_hashtags\": [\"#Shorts\", \"#ShortsFeed\", \"#Viral\", ... 5-10 niche tags],\n"
    "  \"instagram_hashtags\": [\"#Reels\", \"#ExplorePage\", ... 10-18 niche tags]\n"
    "}"
)


def _format_tags(tags: Any, default_broad: List[str]) -> List[str]:
    """Ensures hashtags are clean, well-formed with '#', and deduplicated."""
    if not isinstance(tags, list):
        tags = [str(tags)]
    cleaned: List[str] = []
    for t in tags:
        if not t:
            continue
        tag = str(t).strip().replace(" ", "").replace("\n", "")
        if not tag.startswith("#"):
            tag = f"#{tag}"
        if len(tag) > 1 and tag not in cleaned:
            cleaned.append(tag)
    for broad in default_broad:
        if broad not in cleaned and broad.lower() not in [c.lower() for c in cleaned]:
            cleaned.insert(0, broad)
    return cleaned


def _enforce_title_length(raw_title: str) -> str:
    """Enforces strict < 60 chars limit for YouTube Shorts / Reels titles."""
    title = (raw_title or "").strip().strip("\"'")
    if len(title) > 60:
        truncated = title[:57].rsplit(" ", 1)[0] + "..."
        if len(truncated) <= 60:
            title = truncated
        else:
            title = title[:60]
    return title or "Wait Until You See This 🎬"


def generate_metadata_with_gemini(visual_summary: str, caption: str = '') -> Dict[str, Any]:
    """Fallback generator using Gemini if Groq is unavailable."""
    gemini_key = get_gemini_api_key()
    if not gemini_key:
        return {'success': False, 'error': 'GEMINI_API_KEY not configured'}

    gemini_model = get_gemini_model()
    models_to_try = [gemini_model]
    if 'gemini-3-flash-preview' not in models_to_try:
        models_to_try.append('gemini-3-flash-preview')

    prompt = (
        f"{VIRAL_METADATA_SYSTEM_PROMPT}\n\n"
        f"Visual analysis from video:\n{visual_summary}\n\n"
        f"Caption context:\n{caption}\n\n"
        "Generate the viral JSON metadata now."
    )
    payload = json.dumps({
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {'responseMimeType': 'application/json', 'temperature': 0.7}
    }).encode('utf-8')

    from backend.retry import sync_retry

    last_err = None
    for model_name in models_to_try:
        url = f'https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_key}'
        req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json', 'User-Agent': STANDARD_USER_AGENT})

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
            data = sync_retry(_call_gemini_meta, max_retries=2, operation_name=f"gemini_metadata_{model_name}")
            raw = data['candidates'][0]['content']['parts'][0]['text']
            parsed = json.loads(raw)
            title = _enforce_title_length(parsed.get('title', 'Wait Until You See This 🎬'))
            yt_tags = _format_tags(parsed.get('youtube_hashtags', []), ['#Shorts', '#ShortsFeed', '#Viral'])
            ig_tags = _format_tags(parsed.get('instagram_hashtags', []), ['#Reels', '#ExplorePage'])
            all_tags = list(dict.fromkeys(yt_tags + ig_tags))
            return {
                'title': title,
                'description': parsed.get('description', visual_summary[:250]),
                'youtube_hashtags': yt_tags[:15],
                'instagram_hashtags': ig_tags[:30],
                'hashtags': all_tags[:25],
                'model': model_name,
                'success': True
            }
        except Exception as e:
            last_err = e
            logger.warning(f"Gemini metadata attempt failed on {model_name}: {e}")
            continue

    logger.error(f'Gemini metadata fallback failed ({gemini_model}): {last_err}')
    return {'success': False, 'error': str(last_err)}


def generate_metadata_with_groq(visual_summary: str, caption: str = '') -> Dict[str, Any]:
    """
    Calls Groq to synthesize a winning high-CTR viral title,
    structured compelling description, and dynamic hashtags based on visual evidence.
    """
    groq_key = get_groq_api_key()
    if not groq_key:
        logger.warning('Groq metadata skipped: GROQ_API_KEY not configured. Trying Gemini fallback...')
        gemini_fallback = generate_metadata_with_gemini(visual_summary, caption=caption)
        if gemini_fallback.get('success'):
            gemini_fallback['fallback_reason'] = 'groq_unconfigured_used_gemini'
            return gemini_fallback
        return {
            'title': 'Wait Until You See This 🎬',
            'description': visual_summary[:250] if visual_summary else 'Watch this incredible scene unfold.',
            'youtube_hashtags': ['#Shorts', '#ShortsFeed', '#Viral'],
            'instagram_hashtags': ['#Reels', '#ExplorePage'],
            'hashtags': ['#Shorts', '#ShortsFeed', '#Viral', '#Reels'],
            'success': False,
            'error': 'GROQ_API_KEY not configured',
            'fallback_reason': 'GROQ_API_KEY not configured'
        }

    groq_model = get_groq_model()

    user_prompt = f'Visual footage analysis from Gemini:\n{visual_summary}\n\n'
    if caption:
        user_prompt += f'Caption context: {caption}\n\n'
    user_prompt += 'Generate the viral JSON metadata now.'

    models_to_try = [groq_model]
    if 'qwen/qwen3.8-27b' not in models_to_try:
        models_to_try.append('qwen/qwen3.8-27b')

    from backend.retry import sync_retry

    last_groq_error = None
    for model_name in models_to_try:
        payload_dict = {
            'model': model_name,
            'messages': [
                {'role': 'system', 'content': VIRAL_METADATA_SYSTEM_PROMPT},
                {'role': 'user', 'content': user_prompt}
            ],
            'response_format': {'type': 'json_object'},
            'temperature': 0.7,
            'max_tokens': 4096
        }
        if 'gpt-oss' in model_name:
            payload_dict['reasoning_effort'] = 'low'

        payload = json.dumps(payload_dict).encode('utf-8')
        req = urllib.request.Request(
            'https://api.groq.com/openai/v1/chat/completions',
            data=payload,
            headers={
                'Authorization': f'Bearer {groq_key}',
                'Content-Type': 'application/json',
                'User-Agent': STANDARD_USER_AGENT
            }
        )

        def _call_groq():
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    return json.loads(resp.read().decode('utf-8'))
            except urllib.error.HTTPError as he:
                try:
                    err_text = he.read().decode('utf-8', errors='ignore')
                except Exception:
                    err_text = str(he)
                raise RuntimeError(f"Groq API error ({he.code}): {err_text}") from he

        try:
            data = sync_retry(_call_groq, max_retries=2, operation_name=f"groq_metadata_{model_name.replace('/', '_')}")
            content = data['choices'][0]['message']['content'].strip()
            
            # Extract JSON block
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                content = match.group(0)

            parsed = json.loads(content)
            title = _enforce_title_length(parsed.get('title', 'Wait Until You See This 🎬'))
            yt_tags = _format_tags(parsed.get('youtube_hashtags', []), ['#Shorts', '#ShortsFeed', '#Viral'])
            ig_tags = _format_tags(parsed.get('instagram_hashtags', []), ['#Reels', '#ExplorePage'])
            all_tags = list(dict.fromkeys(yt_tags + ig_tags))

            return {
                'title': title,
                'description': parsed.get('description', visual_summary[:250]),
                'youtube_hashtags': yt_tags[:15],
                'instagram_hashtags': ig_tags[:30],
                'hashtags': all_tags[:25],
                'model': model_name,
                'success': True
            }
        except Exception as e:
            last_groq_error = e
            logger.warning(f"Groq generation attempt with {model_name} failed: {e}")
            continue

    logger.warning(f'Groq generation error ({groq_model}): {last_groq_error}, falling back to Gemini...')
    # Try Gemini fallback
    gemini_fallback = generate_metadata_with_gemini(visual_summary, caption=caption)
    if gemini_fallback.get('success'):
        gemini_fallback['fallback_reason'] = f'groq_failed_used_gemini: {last_groq_error}'
        return gemini_fallback

    fallback_tags = ['#Shorts', '#ShortsFeed', '#Viral', '#Trending', '#MovieClips', '#Cinema', '#MustWatch']
    gemini_err = gemini_fallback.get('error', 'unavailable')
    return {
        'title': 'Wait Until You See This 🎬',
        'description': visual_summary[:250] if visual_summary else 'Watch this incredible scene unfold.',
        'youtube_hashtags': fallback_tags,
        'instagram_hashtags': fallback_tags + ['#Reels', '#ExplorePage'],
        'hashtags': fallback_tags,
        'success': False,
        'error': f'Groq error: {last_groq_error}. Gemini fallback error: {gemini_err}',
        'fallback_reason': f'groq_error: {last_groq_error}'
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
