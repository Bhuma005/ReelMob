"""
ai_pipeline.py
Professional YouTube Shorts content generation pipeline.
Implements the full spec: model selection, system prompt, temperature,
retry/validation logic, and structured JSON output.
"""

import json
import re
import urllib.request
from typing import Optional

# ── Model selection ─────────────────────────────────────────────────────────
def _get_best_model() -> str:
    """Return the explicitly targeted model for ReelGrab AI processing."""
    return "qwen2.5:7b"

SYSTEM_PROMPT = """You are ReelGrab's Advanced YouTube Shorts Intelligence Engine.

Your job is to create the strongest possible YouTube Shorts metadata based on the ACTUAL VIDEO CONTENT provided in the input (raw title, description, transcript, comments, views). NEVER ask the user to invent content from nothing.

The goal is: HIGH CLICK APPEAL + HIGH RELEVANCE + STRONG CURIOSITY + CLEAR CONTEXT + SEARCH DISCOVERABILITY

============================================================
1. METADATA REQUIREMENTS
============================================================
- viral_title: A short, punchy, curiosity-driven title under ~60 characters based on the actual video content. NEVER use generic fallbacks like "Video by X" or just rewrite the source username unless the creator is the actual subject.
- optimized_description: 2-4 sentences, natural, includes a soft call-to-action, references the actual plot/content when available.
- youtube_hashtags: 8-15 relevant hashtags optimized for YouTube Shorts discovery (mix of broad + niche tags).
- instagram_hashtags: 15-30 relevant hashtags optimized for Instagram Reels discovery.
- title_candidates: Generate 3 additional title strategies (e.g. search, emotional, curiosity).
- viewer_appeal_score: Score the title (0-100) based on stopping power and curiosity.
- title_reason: Provide 2-3 short reasons why this title is strong (e.g. "Strong curiosity gap", "Clear topic").

============================================================
2. STRICT JSON OUTPUT
============================================================
You must return ONLY valid JSON. No prose, no markdown fences (like ```json), no explanations outside the JSON object.

Example Output Schema:
{
  "viral_title": "She Finally Realized What He Meant ❤️",
  "optimized_description": "Watch as the realization hits! This moment changes everything for their relationship. Subscribe for more emotional movie scenes and daily shorts.",
  "youtube_hashtags": ["#emotional", "#relationships", "#moviescenes", "#heartbreak", "#shorts", "#drama", "#love", "#breakup"],
  "instagram_hashtags": ["#emotional", "#relationships", "#moviescenes", "#heartbreak", "#drama", "#love", "#breakup", "#couplegoals", "#sadedit", "#foryou", "#explorepage", "#viralreels", "#trending", "#cinema", "#movieclips"],
  "title_candidates": [
    { "strategy": "search", "title": "Saddest Movie Scene Breakup" },
    { "strategy": "emotional", "title": "That Goodbye Still Hurts 💔" },
    { "strategy": "curiosity", "title": "No One Expected His Answer..." }
  ],
  "viewer_appeal_score": 91,
  "title_reason": ["Strong curiosity gap", "Emotional hook", "Natural conversational tone"]
}
"""

# Lightweight prompt for small (sub-1B) models where the full system prompt is too heavy
SYSTEM_PROMPT_LITE = """You are a YouTube Shorts copywriter. Given video info, output ONE JSON object only.
RULES: title under 60 chars, 2-sentence description, 5 hashtags mix broad+niche, optimal post time for India.
OUTPUT FORMAT (strict JSON only, no extra text):
{"title":"","description":"","hashtags":[""],"optimal_schedule_time":"","schedule_reasoning":"","confidence_notes":""}"""

# ── Validation helpers ───────────────────────────────────────────────────────
def _count_emojis(text: str) -> int:
    emoji_pattern = re.compile(
        r'[\U00010000-\U0010ffff'
        r'\U0001F600-\U0001F64F'
        r'\U0001F300-\U0001F5FF'
        r'\U0001F680-\U0001F9FF'
        r'\u2600-\u26FF\u2700-\u27BF]',
        flags=re.UNICODE
    )
    return len(emoji_pattern.findall(text))

def _validate_and_fix(parsed: dict, fallback_title: str, scraped_hashtags: list = None) -> dict:
    """Enforce hard rules on the model output and map to old schema for compatibility."""
    title = parsed.get("viral_title") or parsed.get("recommended_title") or parsed.get("title", "")
    title = re.sub(r'\(.*?\)', '', title).strip()
    
    if len(title) > 100:
        title = title[:97].rsplit(' ', 1)[0].rstrip(" :–-") + "…"
        
    if not title:
        title = fallback_title[:97]
        
    description = parsed.get("optimized_description") or parsed.get("description", "")
        
    youtube = parsed.get("youtube_hashtags", [])
    instagram = parsed.get("instagram_hashtags", [])
    
    # Ensure they are lists
    if not isinstance(youtube, list):
        youtube = [str(youtube)] if youtube else []
    if not isinstance(instagram, list):
        instagram = [str(instagram)] if instagram else []
        
    # Lowercase normalize for deduplication
    seen = set()
    if scraped_hashtags:
        for tag in scraped_hashtags:
            norm = tag.lower().strip()
            if not norm.startswith("#"): norm = "#" + norm
            seen.add(norm)
            
    cleaned_youtube = []
    cleaned_instagram = []
    
    for tag in youtube:
        norm = tag.lower().strip()
        if not norm.startswith("#"): norm = "#" + norm
        if norm not in seen:
            seen.add(norm)
            cleaned_youtube.append(tag.strip())
            
    for tag in instagram:
        norm = tag.lower().strip()
        if not norm.startswith("#"): norm = "#" + norm
        if norm not in seen:
            seen.add(norm)
            cleaned_instagram.append(tag.strip())
            
    # Caps
    cleaned_youtube = cleaned_youtube[:15]
    cleaned_instagram = cleaned_instagram[:30]

    compat_parsed = {
        "title": title,
        "description": description,
        "hashtags": cleaned_youtube + cleaned_instagram, # maintain backward compatibility
        "youtube_hashtags": cleaned_youtube,
        "instagram_hashtags": cleaned_instagram,
        "optimal_schedule_time": parsed.get("posting_recommendation", {}).get("time", "19:00"),
        "schedule_reasoning": parsed.get("title_reason", [""])[0] if isinstance(parsed.get("title_reason"), list) and parsed.get("title_reason") else "",
        "confidence_notes": "HIGH",
    }

    parsed.update(compat_parsed)
    return parsed

def _call_ollama(model: str, user_prompt: str, temperature: float = 0.8, max_retries: int = 2) -> dict:
    """Call Ollama with retry + strict JSON validation."""
    # Use lighter system prompt for tiny models
    system = SYSTEM_PROMPT_LITE if "0.5b" in model else SYSTEM_PROMPT
    timeout = 90.0 if "0.5b" in model else 300.0

    payload = {
        "model": model,
        "system": system,
        "prompt": user_prompt,
        "format": "json",
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": 400 if "0.5b" in model else 512,
        }
    }

    last_err = None
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:11434/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                method="POST",
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as res:
                result = json.loads(res.read())
                raw = result.get("response", "{}")
                # Strip any accidental markdown fences
                raw = re.sub(r"^```[a-z]*\n?", "", raw.strip())
                raw = re.sub(r"\n?```$", "", raw.strip())
                return json.loads(raw)
        except json.JSONDecodeError as e:
            last_err = e
            payload["prompt"] = user_prompt + "\n\nIMPORTANT: Return ONLY valid JSON, nothing else."
        except Exception as e:
            last_err = e
            break

    print(f"Ollama call failed after {max_retries} attempts: {last_err}")
    return {}

# ── Public API ───────────────────────────────────────────────────────────────
def generate_shorts_content(
    video_title: str,
    video_description: str,
    hashtags: Optional[list] = None,
    duration_seconds: Optional[int] = None,
    transcript: Optional[str] = None,
    detected_genre: Optional[str] = None,
    detected_language: Optional[str] = "English",
    key_moments: Optional[str] = None,
    channel_niche: Optional[str] = None,
    target_region: Optional[str] = "India",
    temperature: float = 0.8,
) -> dict:
    """
    Full pipeline: select model → build prompt → call Ollama → validate → return.
    Returns a dict with: title, description, hashtags, optimal_schedule_time,
    schedule_reasoning, confidence_notes.
    """
    model = _get_best_model()
    print(f"[AI Pipeline] Using model: {model}")

    # Auto-detect genre from title/description if not provided
    if not detected_genre:
        combined = (video_title + " " + video_description).lower()
        if any(w in combined for w in ["thriller", "survival", "game", "mystery", "dark"]):
            detected_genre = "thriller"
        elif any(w in combined for w in ["romance", "love", "heart", "crush", "dating"]):
            detected_genre = "romance"
        elif any(w in combined for w in ["comedy", "funny", "laugh", "humor", "prank"]):
            detected_genre = "comedy"
        elif any(w in combined for w in ["tutorial", "how to", "learn", "tips", "guide"]):
            detected_genre = "tutorial"
        else:
            detected_genre = "drama"

    # Detect language from description
    if not detected_language:
        detected_language = "English"

    user_prompt = f"""video_duration_seconds: {duration_seconds or 'unknown'}
transcript_or_captions: {(transcript or video_description or '')[:600]}
detected_genre: {detected_genre}
detected_language: {detected_language}
key_moments: {key_moments or 'not available'}
channel_niche: {channel_niche or 'entertainment / drama'}
target_audience_region: {target_region}

Additional context:
Original video title: {video_title}
Original hashtags: {', '.join(hashtags or [])}

Generate the JSON output now."""

    fallback_title = video_title[:97] if video_title else "Watch This Short"
    parsed = _call_ollama(model, user_prompt, temperature)
    
    ai_failed = not parsed or (not parsed.get("viral_title") and not parsed.get("title"))
    parsed = _validate_and_fix(parsed, fallback_title, scraped_hashtags=hashtags)
    parsed["ai_failed"] = ai_failed

    # Guaranteed fallbacks for missing fields
    if not parsed.get("title"):
        parsed["title"] = fallback_title
    if not parsed.get("description"):
        parsed["description"] = (
            f"{video_description[:150].strip()}. "
            "Subscribe for more content like this."
        )
    if not parsed.get("optimal_schedule_time"):
        parsed["optimal_schedule_time"] = "07:00 PM"
    if not parsed.get("schedule_reasoning"):
        parsed["schedule_reasoning"] = "Evening hours (6–9 PM) show peak Shorts engagement."
    if not parsed.get("youtube_hashtags") and not parsed.get("instagram_hashtags"):
        # If AI failed to generate hashtags, fallback to scraped
        fallback_tags = ["#Shorts", "#Viral", "#Trending", "#fyp", "#explore", "#foryou", "#video"]
        parsed["youtube_hashtags"] = hashtags[:15] if hashtags else fallback_tags
        parsed["instagram_hashtags"] = hashtags[:30] if hashtags else fallback_tags
    if not parsed.get("confidence_notes"):
        parsed["confidence_notes"] = f"Generated by {model}."
    else:
        # Always ensure model name is in the notes
        if model not in parsed["confidence_notes"]:
            parsed["confidence_notes"] = f"Generated by {model}. " + parsed["confidence_notes"]

    return parsed
