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

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')

GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-3.6-flash')
GROQ_MODEL = os.getenv('GROQ_MODEL', 'groq/compound-mini')
STANDARD_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'


def is_cloud_ai_available() -> bool:
    """Returns True if both Gemini and Groq keys are configured."""
    return bool(GEMINI_API_KEY and GROQ_API_KEY)


def analyze_frames_with_gemini(frame_paths: List[str], caption: str = '') -> Dict[str, Any]:
    """
    Sends keyframe images to Google Gemini 3.6 Flash for visual & emotional analysis.
    """
    if not GEMINI_API_KEY:
        raise ValueError('GEMINI_API_KEY not configured.')

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

    url = f'https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}'
    payload = json.dumps({'contents': [{'parts': parts}]}).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json', 'User-Agent': STANDARD_USER_AGENT})

    from backend.retry import sync_retry

    def _execute():
        with urllib.request.urlopen(req, timeout=25) as resp:
            return json.loads(resp.read().decode('utf-8'))

    try:
        data = sync_retry(_execute, max_retries=3, operation_name="gemini_vision")
        raw_text = data['candidates'][0]['content']['parts'][0]['text']
        logger.info(f'Gemini visual analysis completed ({len(raw_text)} chars)')
        return {
            'visual_summary': raw_text.strip(),
            'success': True
        }
    except Exception as e:
        logger.error(f'Gemini vision request failed: {e}')
        return {
            'visual_summary': caption or 'A short video scene',
            'success': False,
            'error': str(e)
        }


def generate_metadata_with_gemini(visual_summary: str, caption: str = '') -> Dict[str, Any]:
    """Fallback generator using Gemini 3.6 Flash if Groq is unavailable."""
    if not GEMINI_API_KEY:
        return {}
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}'
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
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode('utf-8'))

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
            'success': True
        }
    except Exception as e:
        logger.error(f'Gemini metadata fallback failed: {e}')
        return {}


def generate_metadata_with_groq(visual_summary: str, caption: str = '') -> Dict[str, Any]:
    """
    Calls Groq (groq/compound-mini) to synthesize a single winning viral title,
    compelling description, and high-CTR hashtags based on visual evidence.
    """
    if not GROQ_API_KEY:
        raise ValueError('GROQ_API_KEY not configured.')

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
        'model': GROQ_MODEL,
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
            'Authorization': f'Bearer {GROQ_API_KEY}',
            'Content-Type': 'application/json',
            'User-Agent': STANDARD_USER_AGENT
        }
    )

    from backend.retry import sync_retry

    def _call_groq():
        with urllib.request.urlopen(req, timeout=12) as resp:
            return json.loads(resp.read().decode('utf-8'))

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
            'success': True
        }
    except Exception as e:

        logger.warning(f'Groq generation error: {e}, falling back to Gemini...')
        # Try Gemini fallback
        gemini_fallback = generate_metadata_with_gemini(visual_summary, caption=caption)
        if gemini_fallback.get('success'):
            return gemini_fallback

        fallback_tags = ['#Shorts', '#ShortsFeed', '#Viral', '#Trending', '#MovieClips', '#Cinema', '#MustWatch']
        return {
            'title': 'Unbelievable Moment Caught on Camera 🎬',
            'description': visual_summary[:200] if visual_summary else 'Watch this incredible scene unfold.',
            'youtube_hashtags': fallback_tags,
            'instagram_hashtags': fallback_tags + ['#Reels', '#ExplorePage'],
            'hashtags': fallback_tags,
            'success': False,
            'error': str(e)
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
        'provider': 'Cloud AI (Gemini 3.6 Flash + Groq Qwen 3.6)'
    }
