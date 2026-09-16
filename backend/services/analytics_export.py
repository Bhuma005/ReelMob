"""
analytics_export.py — Exportable Analytics Report Generator (CSV & PDF).
Generates detailed channel performance reports including rolling averages,
individual video benchmarks, and tag performance in CSV and PDF formats.
Pure Python implementation with zero third-party report dependencies.
"""

import io
import csv
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Literal

from backend.services.analytics_trends import calculate_channel_trends, calculate_performance_by_tag

logger = logging.getLogger("reelsmob.analytics_export")


def generate_analytics_csv(days: int = 30) -> str:
    """
    Generates a structured CSV report containing:
    1. Executive Summary KPIs
    2. Video Performance Table
    3. Tag Performance Table
    """
    trends_data = calculate_channel_trends(days=days)
    tags_data = calculate_performance_by_tag(days=days)

    summary = trends_data.get("summary", {})
    trends = trends_data.get("trends", [])
    tags = tags_data.get("tags", [])

    output = io.StringIO()
    writer = csv.writer(output)

    # 1. Executive Summary Block
    writer.writerow(["# REELSMOB CHANNEL ANALYTICS REPORT"])
    writer.writerow(["# Generated At", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")])
    writer.writerow(["# Timeframe (Days)", summary.get("days", days)])
    writer.writerow(["# Total Videos", summary.get("total_videos", len(trends))])
    writer.writerow(["# Rolling Avg Views", summary.get("rolling_avg_views", 0)])
    writer.writerow(["# Rolling Avg Likes", summary.get("rolling_avg_likes", 0)])
    writer.writerow(["# Rolling Engagement Rate (%)", f"{summary.get('rolling_avg_engagement_rate', 0)}%"])
    writer.writerow(["# Overperforming Videos", summary.get("overperforming_count", 0)])
    writer.writerow(["# Average Videos", summary.get("average_count", 0)])
    writer.writerow(["# Underperforming Videos", summary.get("underperforming_count", 0)])
    writer.writerow([])

    # 2. Video Performance Table
    writer.writerow(["--- VIDEO PERFORMANCE BREAKDOWN ---"])
    writer.writerow([
        "Date",
        "Video ID",
        "Title",
        "Views",
        "Likes",
        "Rolling Avg Views",
        "Difference (%)",
        "Performance"
    ])
    for item in trends:
        writer.writerow([
            item.get("iso_date") or item.get("date"),
            item.get("video_id"),
            item.get("title"),
            item.get("views"),
            item.get("likes"),
            item.get("rolling_avg_views"),
            f"{item.get('diff_pct'):+.1f}%" if item.get("diff_pct") is not None else "0.0%",
            item.get("performance", "average").capitalize()
        ])
    writer.writerow([])

    # 3. Tag Performance Table
    writer.writerow(["--- TAG PERFORMANCE BREAKDOWN ---"])
    writer.writerow([
        "Tag",
        "Video Count",
        "Avg Views",
        "Avg Likes",
        "Avg Engagement Rate (%)",
        "Benchmark Status"
    ])
    for t in tags:
        writer.writerow([
            f"#{t.get('tag')}",
            t.get("video_count"),
            t.get("avg_views"),
            t.get("avg_likes"),
            f"{t.get('avg_engagement_rate', 0):.2f}%",
            t.get("benchmark_status", "average").capitalize()
        ])

    return output.getvalue()


def _sanitize_pdf_text(text: str) -> str:
    """Sanitizes text for standard Type1 Helvetica font in PDF stream."""
    if not text:
        return ""
    # Map common unicode quotes and symbols
    replacements = {
        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
        "\u2013": "-", "\u2014": "--", "\u2026": "...", "\u2022": "*",
        "\xa0": " ", "\t": "    "
    }
    for orig, rep in replacements.items():
        text = text.replace(orig, rep)
    
    # Strip non-ASCII or unrenderable characters for Helvetica
    clean_chars = []
    for ch in text:
        code = ord(ch)
        if 32 <= code <= 126:
            clean_chars.append(ch)
        else:
            clean_chars.append("?")
    sanitized = "".join(clean_chars)
    return sanitized.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def generate_analytics_pdf(days: int = 30) -> bytes:
    """
    Generates a professional multi-section PDF 1.4 document containing:
    - Report Header & Branding
    - Executive Summary Metrics Cards
    - Video Performance Breakdown Table
    - Tag Benchmark Table
    """
    trends_data = calculate_channel_trends(days=days)
    tags_data = calculate_performance_by_tag(days=days)

    summary = trends_data.get("summary", {})
    trends = trends_data.get("trends", [])
    tags = tags_data.get("tags", [])

    commands: List[str] = []

    # Page Header Banner (Dark accent bar)
    commands.append("0.08 0.10 0.16 rg")  # Fill dark slate
    commands.append("40 730 532 50 re f")  # Header rect

    # Title & Subtitle inside header
    commands.append("1.0 1.0 1.0 rg")  # White text
    title_text = _sanitize_pdf_text(f"REELSMOB ANALYTICS REPORT - LAST {days} DAYS")
    commands.append(f"BT /F2 14 Tf 55 756 Td ({title_text}) Tj ET")
    date_text = _sanitize_pdf_text(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} | Format: Executive Performance Summary")
    commands.append(f"BT /F1 8 Tf 55 742 Td ({date_text}) Tj ET")

    # Section 1: Executive KPI Cards
    commands.append("0.15 0.18 0.25 rg")  # Text dark slate
    commands.append("BT /F2 11 Tf 40 705 Td (EXECUTIVE PERFORMANCE SUMMARY) Tj ET")

    # Draw KPI cards container
    commands.append("0.94 0.95 0.98 rg")  # Light gray-blue fill
    commands.append("40 640 532 55 re f")
    commands.append("0.80 0.82 0.88 RG")  # Border
    commands.append("1 w 40 640 532 55 re S")

    # KPI 1: Total Videos
    commands.append("0.2 0.2 0.3 rg")
    commands.append("BT /F1 8 Tf 55 675 Td (TOTAL VIDEOS) Tj ET")
    total_vids = str(summary.get("total_videos", len(trends)))
    commands.append(f"BT /F2 14 Tf 55 655 Td ({_sanitize_pdf_text(total_vids)}) Tj ET")

    # KPI 2: Rolling Avg Views
    commands.append("BT /F1 8 Tf 165 675 Td (ROLLING AVG VIEWS) Tj ET")
    avg_views = f"{summary.get('rolling_avg_views', 0):,.0f}"
    commands.append(f"BT /F2 14 Tf 165 655 Td ({_sanitize_pdf_text(avg_views)}) Tj ET")

    # KPI 3: Rolling Avg Likes
    commands.append("BT /F1 8 Tf 295 675 Td (ROLLING AVG LIKES) Tj ET")
    avg_likes = f"{summary.get('rolling_avg_likes', 0):,.0f}"
    commands.append(f"BT /F2 14 Tf 295 655 Td ({_sanitize_pdf_text(avg_likes)}) Tj ET")

    # KPI 4: Engagement Rate
    commands.append("BT /F1 8 Tf 425 675 Td (ENGAGEMENT RATE) Tj ET")
    eng_rate = f"{summary.get('rolling_avg_engagement_rate', 0):.2f}%"
    commands.append(f"BT /F2 14 Tf 425 655 Td ({_sanitize_pdf_text(eng_rate)}) Tj ET")

    # Section 2: Distribution Benchmark
    commands.append("0.2 0.2 0.3 rg")
    commands.append("BT /F2 11 Tf 40 615 Td (VIDEO PERFORMANCE BENCHMARK) Tj ET")

    dist_text = (
        f"Overperforming: {summary.get('overperforming_count', 0)} videos  |  "
        f"Average: {summary.get('average_count', 0)} videos  |  "
        f"Underperforming: {summary.get('underperforming_count', 0)} videos"
    )
    commands.append(f"BT /F1 9 Tf 40 600 Td ({_sanitize_pdf_text(dist_text)}) Tj ET")

    # Table Header
    commands.append("0.18 0.22 0.30 rg")
    commands.append("40 575 532 18 re f")
    commands.append("1.0 1.0 1.0 rg")
    commands.append("BT /F2 8 Tf 45 581 Td (DATE) Tj ET")
    commands.append("BT /F2 8 Tf 105 581 Td (TITLE) Tj ET")
    commands.append("BT /F2 8 Tf 325 581 Td (VIEWS) Tj ET")
    commands.append("BT /F2 8 Tf 385 581 Td (LIKES) Tj ET")
    commands.append("BT /F2 8 Tf 445 581 Td (DIFF %) Tj ET")
    commands.append("BT /F2 8 Tf 505 581 Td (STATUS) Tj ET")

    # Video rows (up to 15 top records to fit cleanly on page)
    y = 558
    row_count = 0
    for idx, item in enumerate(trends[:15]):
        if y < 150:
            break
        row_count += 1
        # Alternate row background
        if idx % 2 == 1:
            commands.append("0.96 0.97 0.99 rg")
            commands.append(f"40 {y - 4} 532 15 re f")

        commands.append("0.15 0.18 0.22 rg")
        date_str = _sanitize_pdf_text(item.get("iso_date") or item.get("date") or "")
        title_raw = item.get("title") or "Untitled"
        if len(title_raw) > 35:
            title_raw = title_raw[:32] + "..."
        title_str = _sanitize_pdf_text(title_raw)

        v_str = f"{item.get('views', 0):,}"
        l_str = f"{item.get('likes', 0):,}"
        d_val = item.get("diff_pct", 0)
        d_str = f"{d_val:+.1f}%"
        status_str = _sanitize_pdf_text(item.get("performance", "average").capitalize())

        commands.append(f"BT /F1 8 Tf 45 {y} Td ({date_str}) Tj ET")
        commands.append(f"BT /F1 8 Tf 105 {y} Td ({title_str}) Tj ET")
        commands.append(f"BT /F1 8 Tf 325 {y} Td ({v_str}) Tj ET")
        commands.append(f"BT /F1 8 Tf 385 {y} Td ({l_str}) Tj ET")

        # Color diff based on positive/negative
        if d_val > 0:
            commands.append("0.08 0.55 0.25 rg")  # Green
        elif d_val < -10:
            commands.append("0.75 0.20 0.20 rg")  # Red
        else:
            commands.append("0.35 0.40 0.45 rg")  # Neutral
        commands.append(f"BT /F2 8 Tf 445 {y} Td ({d_str}) Tj ET")

        commands.append("0.15 0.18 0.22 rg")
        commands.append(f"BT /F1 8 Tf 505 {y} Td ({status_str}) Tj ET")
        y -= 16

    # Tag Performance Section
    y -= 10
    if tags and y > 80:
        commands.append("0.15 0.18 0.25 rg")
        commands.append(f"BT /F2 10 Tf 40 {y} Td (CONTENT TAG PERFORMANCE LEADERS) Tj ET")
        y -= 16
        commands.append("0.90 0.92 0.95 rg")
        commands.append(f"40 {y - 2} 532 14 re f")
        commands.append("0.2 0.2 0.3 rg")
        commands.append(f"BT /F2 7 Tf 45 {y + 2} Td (TAG) Tj ET")
        commands.append(f"BT /F2 7 Tf 165 {y + 2} Td (VIDEOS) Tj ET")
        commands.append(f"BT /F2 7 Tf 265 {y + 2} Td (AVG VIEWS) Tj ET")
        commands.append(f"BT /F2 7 Tf 385 {y + 2} Td (ENGAGEMENT) Tj ET")
        commands.append(f"BT /F2 7 Tf 485 {y + 2} Td (BENCHMARK) Tj ET")
        y -= 14

        for t in tags[:5]:
            if y < 50:
                break
            commands.append("0.25 0.28 0.32 rg")
            tag_name = _sanitize_pdf_text(f"#{t.get('tag')}")
            cnt_str = str(t.get("video_count", 0))
            avg_v = f"{t.get('avg_views', 0):,.0f}"
            eng_str = f"{t.get('avg_engagement_rate', 0):.2f}%"
            bench = _sanitize_pdf_text(t.get("benchmark_status", "average").capitalize())

            commands.append(f"BT /F1 7 Tf 45 {y} Td ({tag_name}) Tj ET")
            commands.append(f"BT /F1 7 Tf 165 {y} Td ({cnt_str}) Tj ET")
            commands.append(f"BT /F1 7 Tf 265 {y} Td ({avg_v}) Tj ET")
            commands.append(f"BT /F1 7 Tf 385 {y} Td ({eng_str}) Tj ET")
            commands.append(f"BT /F1 7 Tf 485 {y} Td ({bench}) Tj ET")
            y -= 13

    # Footer
    commands.append("0.55 0.60 0.65 rg")
    commands.append("BT /F1 7 Tf 40 25 Td (ReelsMob Platform Analytics - Confidential & Proprietary) Tj ET")
    commands.append("BT /F1 7 Tf 490 25 Td (Page 1 of 1) Tj ET")

    # Assemble PDF stream
    stream_content = "\n".join(commands) + "\n"
    stream_bytes = stream_content.encode("latin1")

    objs: List[bytes] = []
    # 1: Catalog
    objs.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    # 2: Pages
    objs.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    # 3: Page
    objs.append(
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> >>\nendobj\n"
    )
    # 4: Stream
    objs.append(
        b"4 0 obj\n<< /Length " + str(len(stream_bytes)).encode("ascii") + b" >>\nstream\n" +
        stream_bytes + b"\nendstream\nendobj\n"
    )
    # 5: Helvetica Font (F1)
    objs.append(b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")
    # 6: Helvetica-Bold Font (F2)
    objs.append(b"6 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>\nendobj\n")

    pdf = b"%PDF-1.4\n"
    offsets = []
    for obj in objs:
        offsets.append(len(pdf))
        pdf += obj

    xref_pos = len(pdf)
    pdf += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode("ascii")
    for off in offsets:
        pdf += f"{off:010d} 00000 n \n".encode("ascii")

    pdf += (
        f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    ).encode("ascii")

    return pdf
