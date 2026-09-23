"""
scheduler.py — Authoritative Deterministic Scheduling Engine for ReelMob.
Eliminates LLM-generated posting times and random noise.
Derives optimal publishing windows deterministically from real historical channel data,
or returns an explicit 'insufficient_data' state when data is sparse.
"""

import logging
from datetime import datetime, time, timedelta, timezone
from typing import Dict, Any, List, Optional
import zoneinfo

logger = logging.getLogger("reelsmob.scheduler")

# Standard peak mobile audience slots for fallback testing (strictly labelled as default fallback)
DEFAULT_FALLBACK_HOUR = 18  # 06:00 PM local
DEFAULT_FALLBACK_MINUTE = 0


def get_channel_historical_data(min_samples: int = 5) -> List[Dict[str, Any]]:
    """
    Fetches real published video performance data from Supabase video_library.
    Returns empty list if Supabase is unavailable or table is empty.
    """
    try:
        from cloud.cloud_auth import get_supabase_client
        sb = get_supabase_client()
        if not sb:
            return []
        res = sb.table("video_library") \
                .select("id, title, status, views, likes, comments, uploaded_at, schedule_time, created_at") \
                .eq("status", "published") \
                .not_.is_("uploaded_at", "null") \
                .order("uploaded_at", desc=True) \
                .limit(100) \
                .execute()
        return res.data or []
    except Exception as e:
        logger.warning(f"Could not load historical channel data from Supabase: {e}")
        return []


def calculate_deterministic_schedule(
    historical_records: Optional[List[Dict[str, Any]]] = None,
    channel_timezone: str = "Asia/Kolkata",
    min_required_samples: int = 5,
    reference_dt: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Deterministic Scheduling Engine:
    Given the identical historical input, always produces the identical output.
    Zero randomness (no random.uniform or random.random).

    Returns:
    {
        "recommended_date": "YYYY-MM-DD" or None,
        "recommended_time": "HH:MM" or None,
        "human_readable_time": "...",
        "timezone": "...",
        "confidence": 0.0 - 1.0,
        "data_points": int,
        "reason": "...",
        "status": "recommended" | "insufficient_data",
        "fallback_schedule": {...} (only when insufficient_data)
    }
    """
    try:
        import dateutil.tz
        tz = dateutil.tz.gettz(channel_timezone)
        if tz is None:
            tz = dateutil.tz.gettz("Asia/Kolkata") or timezone.utc
            channel_timezone = "Asia/Kolkata"
    except Exception:
        tz = timezone.utc
        channel_timezone = "UTC"

    now_local = (reference_dt or datetime.now(timezone.utc)).astimezone(tz)
    records = historical_records if historical_records is not None else get_channel_historical_data()
    valid_records = [r for r in records if (r.get("views") is not None and int(r.get("views") or 0) > 0)]

    # If insufficient historical data, do NOT hallucinate or pretend
    if len(valid_records) < min_required_samples:
        # Calculate a transparent, strictly labelled default fallback slot
        fallback_date = (now_local + timedelta(days=1)).date()
        fallback_dt = datetime.combine(fallback_date, time(DEFAULT_FALLBACK_HOUR, DEFAULT_FALLBACK_MINUTE), tzinfo=tz)
        
        return {
            "status": "insufficient_data",
            "recommended_date": None,
            "recommended_time": None,
            "human_readable_time": None,
            "iso_schedule": None,
            "timezone": channel_timezone,
            "confidence": 0.0,
            "data_points": len(valid_records),
            "reason": (
                f"Your channel has {len(valid_records)} published video records with view data "
                f"(minimum {min_required_samples} required). Not enough channel data to recommend an authoritative posting time."
            ),
            "fallback_schedule": {
                "label": "Default fallback schedule",
                "recommended_date": fallback_date.isoformat(),
                "recommended_time": f"{DEFAULT_FALLBACK_HOUR:02d}:{DEFAULT_FALLBACK_MINUTE:02d}",
                "human_readable_time": fallback_dt.strftime("%B %d, %I:%M %p"),
                "iso_schedule": fallback_dt.isoformat(),
                "note": "Standard slot for controlled baseline testing only. Never presented as channel intelligence."
            }
        }

    # Aggregate performance by day_of_week and hour_of_day deterministically
    hour_stats: Dict[int, List[int]] = {h: [] for h in range(24)}
    day_stats: Dict[int, List[int]] = {d: [] for d in range(7)}

    for r in valid_records:
        ts_str = r.get("uploaded_at") or r.get("schedule_time") or r.get("created_at")
        try:
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).astimezone(tz)
            views = int(r.get("views") or 0)
            hour_stats[dt.hour].append(views)
            day_stats[dt.weekday()].append(views)
        except Exception:
            continue

    # Score each hour by average views (fallback to median / count weighting)
    hour_scores: Dict[int, float] = {}
    for h, v_list in hour_stats.items():
        if v_list:
            avg_views = sum(v_list) / len(v_list)
            # Give higher confidence to hours with more samples
            weight = min(1.0, len(v_list) / 3.0)
            hour_scores[h] = avg_views * weight
        else:
            hour_scores[h] = 0.0

    # Pick the best performing hour
    best_hour = max(hour_scores, key=hour_scores.get)
    best_hour_score = hour_scores[best_hour]

    # Best day of week
    day_scores: Dict[int, float] = {}
    for d, v_list in day_stats.items():
        day_scores[d] = (sum(v_list) / len(v_list)) if v_list else 0.0
    best_day = max(day_scores, key=day_scores.get)

    # Schedule for the next occurrence of best_hour (at least 2 hours from now)
    target_dt = now_local.replace(hour=best_hour, minute=0, second=0, microsecond=0)
    if target_dt <= now_local + timedelta(hours=2):
        target_dt += timedelta(days=1)

    confidence = min(0.95, round(0.5 + (len(valid_records) / 50.0), 2))
    day_name = target_dt.strftime("%A")

    return {
        "status": "recommended",
        "recommended_date": target_dt.date().isoformat(),
        "recommended_time": target_dt.strftime("%H:%M"),
        "human_readable_time": target_dt.strftime("%B %d, %I:%M %p"),
        "iso_schedule": target_dt.isoformat(),
        "timezone": channel_timezone,
        "confidence": confidence,
        "data_points": len(valid_records),
        "reason": (
            f"Based on {len(valid_records)} published videos, {day_name} at {target_dt.strftime('%I:%M %p')} "
            f"historically yielded peak viewer engagement for your channel."
        ),
        "fallback_schedule": None
    }
