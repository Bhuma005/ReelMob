import json
import re
import urllib.request
import logging
import os
from backend.services.cloud_ai import (
    GROQ_API_KEY,
    GEMINI_API_KEY,
    GROQ_MODEL,
    GEMINI_MODEL,
)

logger = logging.getLogger(__name__)

def get_optimal_model() -> str:
    """Return user's chosen high-intelligence cloud model."""
    return GROQ_MODEL

def call_cloud_llm(model: str = None, system_prompt: str = "", user_prompt: str = "", temperature: float = 0.7, max_retries: int = 2) -> dict:
    """
    Call Cloud LLM (Groq groq/compound-mini with Gemini 3.6 Flash fallback)
    with strict JSON enforcement and retries.
    """
    selected_groq_model = model if model and "/" in model else GROQ_MODEL

    # 1. Primary: Groq API
    if GROQ_API_KEY:
        payload = json.dumps({
            "model": selected_groq_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": temperature,
            "max_tokens": 1000
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )

        for attempt in range(max_retries):
            try:
                with urllib.request.urlopen(req, timeout=15.0) as res:
                    result = json.loads(res.read().decode("utf-8"))
                    content = result["choices"][0]["message"]["content"].strip()
                    match = re.search(r"\{.*\}", content, re.DOTALL)
                    if match:
                        content = match.group(0)
                    return json.loads(content)
            except Exception as e:
                logger.warning(f"Groq agent call attempt {attempt+1} failed: {e}")

    # 2. Fallback: Google Gemini API
    if GEMINI_API_KEY:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
        combined_prompt = f"{system_prompt}\n\n{user_prompt}\n\nReturn ONLY valid JSON matching schema."
        payload = json.dumps({
            "contents": [{"parts": [{"text": combined_prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": temperature
            }
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"})

        for attempt in range(max_retries):
            try:
                with urllib.request.urlopen(req, timeout=20.0) as res:
                    data = json.loads(res.read().decode("utf-8"))
                    raw = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    match = re.search(r"\{.*\}", raw, re.DOTALL)
                    if match:
                        raw = match.group(0)
                    return json.loads(raw)
            except Exception as e:
                logger.warning(f"Gemini fallback agent call attempt {attempt+1} failed: {e}")

    logger.warning("Cloud LLM call finished: no response returned or API keys unconfigured.")
    return {}

# Backward-compatibility alias so callers importing call_ollama continue without change
call_ollama = call_cloud_llm
