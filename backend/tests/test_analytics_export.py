"""
test_analytics_export.py — Tests for CSV and PDF Analytics Reports Export.
Verifies format validation with Literal['csv', 'pdf'], response headers,
and report content structure.
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.analytics_export import generate_analytics_csv, generate_analytics_pdf

client = TestClient(app)


def test_generate_analytics_csv():
    csv_text = generate_analytics_csv(days=30)
    assert isinstance(csv_text, str)
    assert "# REELSMOB CHANNEL ANALYTICS REPORT" in csv_text
    assert "# Total Videos" in csv_text
    assert "--- VIDEO PERFORMANCE BREAKDOWN ---" in csv_text
    assert "Date,Video ID,Title,Views,Likes,Rolling Avg Views,Difference (%),Performance" in csv_text
    assert "--- TAG PERFORMANCE BREAKDOWN ---" in csv_text
    assert "Tag,Video Count,Avg Views,Avg Likes,Avg Engagement Rate (%),Benchmark Status" in csv_text


def test_generate_analytics_pdf():
    pdf_bytes = generate_analytics_pdf(days=30)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-1.4")
    assert b"%%EOF" in pdf_bytes
    assert b"/Helvetica" in pdf_bytes
    assert b"REELSMOB ANALYTICS REPORT" in pdf_bytes


def test_export_endpoint_csv():
    res = client.get("/api/dashboard/analytics/export?format=csv&days=14")
    assert res.status_code == 200
    assert "text/csv" in res.headers.get("content-type", "")
    assert 'attachment; filename="reelsmob_analytics_14d.csv"' in res.headers.get("content-disposition", "")
    assert "# REELSMOB CHANNEL ANALYTICS REPORT" in res.text


def test_export_endpoint_pdf():
    res = client.get("/api/dashboard/analytics/export?format=pdf&days=30")
    assert res.status_code == 200
    assert "application/pdf" in res.headers.get("content-type", "")
    assert 'attachment; filename="reelsmob_analytics_30d.pdf"' in res.headers.get("content-disposition", "")
    assert res.content.startswith(b"%PDF-1.4")


def test_export_endpoint_invalid_format_literal():
    # Only Literal['csv', 'pdf'] is allowed — any other format should trigger 422
    res = client.get("/api/dashboard/analytics/export?format=xlsx")
    assert res.status_code == 422
    data = res.json()
    assert "detail" in data


def test_export_endpoint_default_csv():
    res = client.get("/api/dashboard/analytics/export")
    assert res.status_code == 200
    assert "text/csv" in res.headers.get("content-type", "")
    assert 'attachment; filename="reelsmob_analytics_30d.csv"' in res.headers.get("content-disposition", "")
