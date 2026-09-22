"""
analysis_service.py — Shared, host-agnostic AI video analysis pipeline for ReelsMob.

Callable both locally within backend/main.py (FastAPI background worker)
and headlessly in backend/scripts/run_analysis_job.py (GitHub Actions 2-CPU worker).
Contains no coupling to FastAPI requests, BackgroundTasks, or HTTP lifecycle.
"""

import os
import re
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Callable

import backend.video_analyzer as video_analyzer
import backend.services.cloud_ai as cloud_ai
from backend.agents.master_agent import MasterAgent, backfill_hashtags
from backend.agents.base import AgentState

logger = logging.getLogger("reelsmob.analysis_service")


async def run_video_analysis(
    video_url: str = "",
    raw_title: str = "",
    raw_description: str = "",
    video_path: str = "",
    progress_callback: Optional[Callable[[int, str], None]] = None,
    timeout_seconds: Optional[float] = None
) -> Dict[str, Any]:
    """
    Executes complete end-to-end video analysis:
      1. Keyframe extraction and visual analysis (Gemini Flash)
      2. Viral metadata synthesis (Groq LPU / Gemini)
      3. MasterAgent reasoning and resilient deterministic fallback handling
    
    Returns the complete result dictionary ready for client consumption.
    """
    def _notify(pct: int, msg: str):
        if progress_callback:
            try:
                progress_callback(pct, msg)
            except Exception as pe:
                logger.debug(f"Progress callback notification error: {pe}")

    if timeout_seconds is None:
        timeout_seconds = float(os.getenv("VIDEO_ANALYSIS_TIMEOUT_SECONDS", "60.0"))

    timed_out = False
    _notify(20, "Extracting video frames and inspecting visual scene...")

    try:
        video_analysis = await asyncio.wait_for(
            asyncio.to_thread(
                video_analyzer.analyze_video_content,
                video_path=video_path,
                url=video_url,
                raw_title=raw_title,
                raw_description=raw_description,
                progress_callback=progress_callback,
                skip_audio=True
            ),
            timeout=timeout_seconds
        )
    except asyncio.TimeoutError:
        logger.warning(
            f"Video frame analysis timed out after {timeout_seconds}s. "
            f"Degrading gracefully to lightweight caption mode."
        )
        timed_out = True
        video_analysis = {
            "video_analyzed": False,
            "vision_success": False,
            "audio_success": False,
            "visual_description": "",
            "analysis_source": "caption_fallback",
            "source_label": "From caption — video analysis timed out",
            "fallback_reason": "video_analysis_timeout_lightweight_mode"
        }
        _notify(60, "Frame extraction timed out; switching to lightweight caption analysis...")

    _notify(70, "Synthesizing viral titles, description & tags with Cloud AI...")

    # ── 1. Priority: ReelsMob Cloud AI (Gemini + Groq) ─────────────────────────
    cloud_meta = None
    fallback_reason: Optional[str] = "video_analysis_timeout_lightweight_mode" if timed_out else None

    try:
        if cloud_ai.is_cloud_ai_available():
            logger.info("⚡ Using ReelsMob Cloud AI (Groq + Gemini) for metadata generation...")
            visual_summary = video_analysis.get("visual_description", "") or raw_description or raw_title
            cloud_meta = await asyncio.to_thread(
                cloud_ai.generate_metadata_with_groq,
                visual_summary=visual_summary,
                caption=raw_description
            )
            if not cloud_meta or not cloud_meta.get("success"):
                fallback_reason = (
                    (cloud_meta or {}).get("fallback_reason") or
                    (cloud_meta or {}).get("error") or
                    "Cloud AI metadata generation unsuccessful"
                )
                logger.warning(f"Cloud AI generation unsuccessful: {fallback_reason}")
        else:
            missing_keys = []
            if not cloud_ai.get_gemini_api_key():
                missing_keys.append("GEMINI_API_KEY")
            if not cloud_ai.get_groq_api_key():
                missing_keys.append("GROQ_API_KEY")
            fallback_reason = f"Cloud AI unconfigured: missing {', '.join(missing_keys)}"
            logger.warning(fallback_reason)
    except Exception as e:
        fallback_reason = f"Cloud AI metadata generation attempt error: {e}"
        logger.warning(fallback_reason)

    if cloud_meta and cloud_meta.get("success"):
        best_title = cloud_meta.get("title") or raw_title or "Must Watch Viral Scene 🔥"
        desc = cloud_meta.get("description") or raw_description or ""
        youtube_tags = cloud_meta.get("youtube_hashtags", ["#Shorts", "#ShortsFeed", "#Viral"])
        instagram_tags = cloud_meta.get("instagram_hashtags", ["#Reels", "#Viral"])

        source_label = video_analysis.get("source_label") or "Based on video analysis"
        analysis_source = video_analysis.get("analysis_source") or "video_visual"
        video_analyzed = video_analysis.get("video_analyzed", True)
        cloud_sub_fallback = cloud_meta.get("fallback_reason") or (fallback_reason if timed_out else None)

        raw_result = {
            "title": best_title,
            "description": desc,
            "youtube_hashtags": youtube_tags,
            "instagram_hashtags": instagram_tags,
            "title_candidates": [{"title": best_title, "strategy": "Cloud AI Viral Hook", "score": 98}],
            "viewer_appeal_score": 96,
            "title_reason": [
                "Video-grounded visual hook" if not timed_out else "Fast-path context hook",
                "High CTR algorithm match"
            ],
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
            "fallback_reason": cloud_sub_fallback,
            "provider": f"ReelsMob Cloud AI ({cloud_meta.get('model', 'Groq/Gemini')})"
        }

        _notify(100, "AI optimization complete (Cloud AI)")
        return {
            "viral_title": best_title,
            "optimized_description": desc,
            "youtube": youtube_tags,
            "instagram": instagram_tags,
            "analysis": (
                "Generated via ReelsMob Cloud AI using video visual inspection and viral synthesis."
                if not timed_out else
                "Generated via ReelsMob Cloud AI using lightweight caption context (video analysis timed out)."
            ),
            "confidence_notes": "VERY HIGH (Cloud AI)" if not timed_out else "HIGH (Lightweight Cloud AI)",
            "scheduled_time": "07:30 PM",
            "raw_result": raw_result,
            "ai_failed": False,
            "source_label": source_label,
            "analysis_source": analysis_source,
            "video_analyzed": video_analyzed,
            "fallback_reason": cloud_sub_fallback
        }

    # ── 2. Cloud AI Fallback / Deterministic or Agent Execution ───────────────
    cloud_keys_present = bool(cloud_ai.get_groq_api_key() or cloud_ai.get_gemini_api_key())
    if not cloud_keys_present:
        if not fallback_reason:
            fallback_reason = "Cloud AI keys unconfigured (GEMINI_API_KEY and GROQ_API_KEY missing)"
        logger.warning(f"Using deterministic fallback metadata. Reason: {fallback_reason}")
        fallback_title = raw_title or "Trending Reel"
        fallback_desc = raw_description or "Watch this trending video! #Shorts #Viral"
        fallback_tags = ["#Shorts", "#Viral", "#Trending", "#Reel"]

        raw_result = {
            "title": fallback_title,
            "description": fallback_desc,
            "youtube_hashtags": fallback_tags,
            "instagram_hashtags": fallback_tags,
            "title_candidates": [{"strategy": "Original", "title": fallback_title}],
            "viewer_appeal_score": 75,
            "title_reason": ["Deterministic fallback (Cloud AI unconfigured)"],
            "posting_recommendation": {
                "human_readable_time": "07:30 PM",
                "reason": "Standard peak evening engagement slot."
            },
            "ai_failed": True,
            "fallback": True,
            "fallback_reason": fallback_reason,
            "source_label": "From caption — video analysis unavailable",
            "analysis_source": "caption_fallback",
            "video_analyzed": False
        }

        _notify(100, "AI completed with fallback metadata")
        return {
            "viral_title": fallback_title,
            "optimized_description": fallback_desc,
            "youtube": fallback_tags,
            "instagram": fallback_tags,
            "analysis": f"Generated using deterministic fallback ({fallback_reason}).",
            "confidence_notes": "FALLBACK",
            "scheduled_time": "07:30 PM",
            "raw_result": raw_result,
            "ai_failed": True,
            "fallback_reason": fallback_reason,
            "source_label": "From caption — video analysis unavailable",
            "analysis_source": "caption_fallback",
            "video_analyzed": False
        }

    # Agent execution fallback
    agent = MasterAgent()
    initial_state = AgentState({
        "raw_title": raw_title or "",
        "raw_description": raw_description or "",
        "transcript_text": video_analysis.get("audio_transcript") or raw_description or "",
        "audio_transcript": video_analysis.get("audio_transcript") or "",
        "visual_description": video_analysis.get("visual_description") or "",
        "analysis_source": video_analysis.get("analysis_source") or "caption_fallback",
        "source_label": video_analysis.get("source_label") or "From caption — video analysis unavailable",
        "video_analyzed": video_analysis.get("video_analyzed", False),
        "url": video_url or ""
    })

    try:
        final_state = await asyncio.wait_for(
            asyncio.to_thread(agent.run, initial_state),
            timeout=120.0
        )
    except Exception as e:
        fallback_reason = f"MasterAgent execution fallback: {e}"
        logger.warning(f"AI execution fallback due to: {fallback_reason}")
        desc_clean = re.sub(r'#\w+', '', raw_description or '').strip()
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
                "fallback_reason": fallback_reason,
                "source_label": "From caption — video analysis unavailable",
                "analysis_source": "caption_fallback",
                "video_analyzed": False
            },
            "posting": {"scheduled_time": "19:30", "score": 95, "reason": "Standard peak evening engagement slot."}
        })

    metadata = final_state.get("metadata", {})
    posting = final_state.get("posting", {})
    analytics = final_state.get("analytics", {})

    best_title = metadata.get("best_title") or raw_title or "Untitled Reel"
    desc = metadata.get("description") or raw_description or ""
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
        "fallback_reason": fallback_reason or metadata.get("fallback_reason"),
        "source_label": source_label,
        "analysis_source": analysis_source,
        "video_analyzed": video_analyzed,
        "visual_description": video_analysis.get("visual_description", ""),
        "audio_transcript": video_analysis.get("audio_transcript", ""),
        "vision_hint": video_analysis.get("vision_hint"),
        "agent_workflow_state": final_state.data if hasattr(final_state, "data") else final_state
    }

    _notify(100, "AI optimization complete")
    return {
        "viral_title": best_title,
        "optimized_description": desc,
        "youtube": youtube_tags,
        "instagram": instagram_tags,
        "analysis": analytics.get("reasoning", posting.get("reason", "Optimized based on audience peak activity.")),
        "confidence_notes": posting.get("confidence", "HIGH"),
        "scheduled_time": posting.get("human_readable_time", "07:30 PM"),
        "raw_result": raw_result,
        "ai_failed": ai_failed,
        "fallback_reason": fallback_reason or metadata.get("fallback_reason"),
        "source_label": source_label,
        "analysis_source": analysis_source,
        "video_analyzed": video_analyzed,
        "vision_hint": video_analysis.get("vision_hint")
    }
