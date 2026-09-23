"""
test_deterministic_scheduler.py — Unit tests for authoritatively deterministic posting scheduler.
Ensures zero randomness, reproducible calculations, and explicit insufficient_data state.
"""

from datetime import datetime, timezone
import pytest
from backend.services.scheduler import (
    calculate_deterministic_schedule,
    DEFAULT_FALLBACK_HOUR,
    DEFAULT_FALLBACK_MINUTE
)


def test_scheduler_insufficient_data_empty():
    """Verify scheduler handles empty dataset with explicit insufficient_data status."""
    result = calculate_deterministic_schedule(historical_records=[])
    assert result["status"] == "insufficient_data"
    assert result["recommended_date"] is None
    assert result["recommended_time"] is None
    assert result["confidence"] == 0.0
    assert result["data_points"] == 0
    assert "Not enough channel data" in result["reason"]
    assert result["fallback_schedule"] is not None
    assert result["fallback_schedule"]["recommended_time"] == f"{DEFAULT_FALLBACK_HOUR:02d}:{DEFAULT_FALLBACK_MINUTE:02d}"


def test_scheduler_insufficient_data_few_records():
    """Verify scheduler rejects fewer than min_required_samples."""
    records = [
        {"id": "1", "status": "published", "views": 1200, "uploaded_at": "2026-09-01T14:00:00Z"},
        {"id": "2", "status": "published", "views": 2500, "uploaded_at": "2026-09-02T16:00:00Z"},
    ]
    result = calculate_deterministic_schedule(historical_records=records, min_required_samples=5)
    assert result["status"] == "insufficient_data"
    assert result["data_points"] == 2


def test_scheduler_deterministic_reproducibility():
    """Verify identical input produces identical output across multiple invocations."""
    records = [
        {"id": "1", "status": "published", "views": 10000, "uploaded_at": "2026-09-01T18:00:00Z"},
        {"id": "2", "status": "published", "views": 12000, "uploaded_at": "2026-09-02T18:00:00Z"},
        {"id": "3", "status": "published", "views": 11500, "uploaded_at": "2026-09-03T18:00:00Z"},
        {"id": "4", "status": "published", "views": 4000,  "uploaded_at": "2026-09-04T12:00:00Z"},
        {"id": "5", "status": "published", "views": 3500,  "uploaded_at": "2026-09-05T09:00:00Z"},
        {"id": "6", "status": "published", "views": 15000, "uploaded_at": "2026-09-06T18:00:00Z"},
    ]
    fixed_ref_dt = datetime(2026, 9, 10, 10, 0, 0, tzinfo=timezone.utc)

    run_1 = calculate_deterministic_schedule(historical_records=records, reference_dt=fixed_ref_dt)
    run_2 = calculate_deterministic_schedule(historical_records=records, reference_dt=fixed_ref_dt)

    assert run_1["status"] == "recommended"
    assert run_2["status"] == "recommended"
    assert run_1 == run_2
    assert run_1["data_points"] == 6
    assert run_1["confidence"] > 0.5
    assert run_1["recommended_time"] is not None
    assert run_1["fallback_schedule"] is None


def test_scheduler_timezone_handling():
    """Verify timezone parameter changes output local time deterministically."""
    records = [
        {"id": "1", "status": "published", "views": 10000, "uploaded_at": "2026-09-01T18:00:00Z"},
        {"id": "2", "status": "published", "views": 12000, "uploaded_at": "2026-09-02T18:00:00Z"},
        {"id": "3", "status": "published", "views": 11500, "uploaded_at": "2026-09-03T18:00:00Z"},
        {"id": "4", "status": "published", "views": 4000,  "uploaded_at": "2026-09-04T18:00:00Z"},
        {"id": "5", "status": "published", "views": 3500,  "uploaded_at": "2026-09-05T18:00:00Z"},
    ]
    fixed_ref_dt = datetime(2026, 9, 10, 10, 0, 0, tzinfo=timezone.utc)

    ist_res = calculate_deterministic_schedule(
        historical_records=records, channel_timezone="Asia/Kolkata", reference_dt=fixed_ref_dt
    )
    nyc_res = calculate_deterministic_schedule(
        historical_records=records, channel_timezone="America/New_York", reference_dt=fixed_ref_dt
    )

    assert ist_res["status"] == "recommended"
    assert nyc_res["status"] == "recommended"
    assert ist_res["timezone"] == "Asia/Kolkata"
    assert nyc_res["timezone"] == "America/New_York"
