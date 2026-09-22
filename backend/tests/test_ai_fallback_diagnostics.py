"""
backend/tests/test_ai_fallback_diagnostics.py
Comprehensive tests for:
1. Cloud AI model identifier normalization and dynamic key resolution.
2. Direct URL preview frame extraction for un-downloaded reels.
3. Structured fallback_reason propagation through pipeline, job store, and status API.
"""

import os
import json
import base64
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from backend.main import app, AI_JOBS_STORE, execute_ai_analysis_job
from backend.services.cloud_ai import (
    get_gemini_model,
    get_groq_model,
    get_gemini_api_key,
    get_groq_api_key,
    is_cloud_ai_available,
    get_cloud_ai_status,
    generate_metadata_with_groq,
    generate_metadata_with_gemini
)
from backend.video_analyzer import extract_frames_from_url, analyze_video_content


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestCloudAIModelAndKeyResolution:
    """Verify models default to valid native endpoints and env keys strip cleanly."""

    def test_gemini_model_normalization(self, monkeypatch):
        monkeypatch.delenv("GEMINI_MODEL", raising=False)
        assert get_gemini_model() == "gemini-3.6-flash"

        monkeypatch.setenv("GEMINI_MODEL", "gemini-2.0-flash")
        assert get_gemini_model() == "gemini-3.6-flash"

        monkeypatch.setenv("GEMINI_MODEL", "gemini-1.5-pro")
        assert get_gemini_model() == "gemini-1.5-pro"

    def test_groq_model_normalization(self, monkeypatch):
        monkeypatch.delenv("GROQ_MODEL", raising=False)
        assert get_groq_model() == "openai/gpt-oss-120b"

        monkeypatch.setenv("GROQ_MODEL", "groq/compound-mini")
        assert get_groq_model() == "openai/gpt-oss-120b"

        monkeypatch.setenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        assert get_groq_model() == "openai/gpt-oss-120b"

        monkeypatch.setenv("GROQ_MODEL", "llama-3.1-8b-instant")
        assert get_groq_model() == "llama-3.1-8b-instant"

    def test_key_resolution_and_stripping(self, monkeypatch):
        # Gemini key with quotes and trailing spaces
        monkeypatch.setenv("GEMINI_API_KEY", "  'gsk_test_gemini_key_123'  ")
        assert get_gemini_api_key() == "gsk_test_gemini_key_123"

        # Fallback to GOOGLE_API_KEY
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setenv("GOOGLE_API_KEY", "google_fallback_key_456")
        assert get_gemini_api_key() == "google_fallback_key_456"

        # Groq key stripping
        monkeypatch.setenv("GROQ_API_KEY", ' "gsk_groq_key_789" ')
        assert get_groq_api_key() == "gsk_groq_key_789"

    def test_is_cloud_ai_available(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "test_gemini")
        monkeypatch.setenv("GROQ_API_KEY", "test_groq")
        assert is_cloud_ai_available() is True

        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("GROQ_KEY", raising=False)
        assert is_cloud_ai_available() is False

    def test_cloud_ai_status(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "test_gemini")
        monkeypatch.setenv("GROQ_API_KEY", "test_groq")
        status = get_cloud_ai_status()
        assert status["gemini_configured"] is True
        assert status["groq_configured"] is True
        assert status["is_available"] is True
        assert status["gemini_model"] == "gemini-3.6-flash"
        assert status["groq_model"] == "openai/gpt-oss-120b"


class TestCloudAIGeneration:
    """Verify Groq metadata generation and error fallback behavior."""

    def test_generate_metadata_with_groq_missing_key(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("GROQ_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

        res = generate_metadata_with_groq("Sample visual scene")
        assert res["success"] is False
        assert "fallback_reason" in res
        assert "GROQ_API_KEY not configured" in res["fallback_reason"]

    def test_generate_metadata_with_groq_groq_failure_gemini_success(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "mock_groq_key")
        monkeypatch.setenv("GEMINI_API_KEY", "mock_gemini_key")

        mock_gemini_return = {
            "title": "Gemini Saved The Day 🔥",
            "description": "Scene rescued via Gemini metadata fallback.",
            "youtube_hashtags": ["#Shorts", "#ShortsFeed", "#Viral"],
            "instagram_hashtags": ["#Reels", "#ExplorePage"],
            "hashtags": ["#Shorts", "#Viral", "#Reels"],
            "success": True
        }

        with patch("urllib.request.urlopen", side_effect=RuntimeError("Groq HTTP 404")):
            with patch("backend.services.cloud_ai.generate_metadata_with_gemini", return_value=mock_gemini_return):
                res = generate_metadata_with_groq("Sample scene")
                assert res["success"] is True
                assert res["title"] == "Gemini Saved The Day 🔥"
                assert "groq_failed_used_gemini" in res.get("fallback_reason", "")

    def test_generate_metadata_with_groq_success(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "mock_groq_key")

        mock_groq_resp = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "title": "Incredible Street Performance 🎷",
                        "description": "Watch this musician stun the entire crowd in Paris.",
                        "youtube_hashtags": ["#Shorts", "#ShortsFeed", "#StreetMusic"],
                        "instagram_hashtags": ["#reels", "#viral", "#music"]
                    })
                }
            }]
        }

        mock_resp_obj = MagicMock()
        mock_resp_obj.read.return_value = json.dumps(mock_groq_resp).encode("utf-8")
        mock_resp_obj.__enter__.return_value = mock_resp_obj

        with patch("urllib.request.urlopen", return_value=mock_resp_obj):
            res = generate_metadata_with_groq("Musician playing saxophone on street")
            assert res["success"] is True
            assert res["title"] == "Incredible Street Performance 🎷"
            assert "#Shorts" in res["youtube_hashtags"]
            assert len(res["hashtags"]) >= 4


class TestVideoAnalyzerPreviewExtraction:
    """Verify video_analyzer can extract preview frames from URL even when video isn't downloaded."""

    def test_extract_frames_from_url_with_thumbnail(self):
        mock_info = {
            "thumbnail": "https://example.com/thumb.jpg",
            "thumbnails": [{"url": "https://example.com/thumb.jpg"}]
        }

        fake_jpg_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 300  # Valid dummy JPEG header

        mock_resp = MagicMock()
        mock_resp.read.return_value = fake_jpg_bytes
        mock_resp.__enter__.return_value = mock_resp

        mock_ydl = MagicMock()
        mock_ydl.__enter__.return_value.extract_info.return_value = mock_info

        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
            with patch("urllib.request.urlopen", return_value=mock_resp):
                frames = extract_frames_from_url("https://youtube.com/shorts/test1234")
                assert len(frames) >= 1
                # Check base64 decodable
                decoded = base64.b64decode(frames[0])
                assert len(decoded) > 0

    def test_analyze_video_content_with_url_preview(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "mock_key")
        monkeypatch.setenv("GROQ_API_KEY", "mock_key")

        mock_vision_res = {
            "visual_summary": "A chef chopping fresh vegetables in a busy kitchen.",
            "success": True,
            "model": "gemini-2.0-flash"
        }

        with patch("backend.video_analyzer.find_video_file_for_request", return_value=None):
            with patch("backend.video_analyzer.extract_frames_from_url", return_value=["dummy_b64_frame"]):
                with patch("backend.services.cloud_ai.analyze_frames_with_gemini", return_value=mock_vision_res):
                    res = analyze_video_content(url="https://instagram.com/reel/dummy999/")
                    assert res["video_analyzed"] is True
                    assert res["vision_success"] is True
                    assert res["analysis_source"] == "video_preview"
                    assert "preview frame" in res["source_label"]
                    assert "chef chopping" in res["visual_description"]


class TestAIPipelineDiagnosticsAndFallbackReason:
    """Verify fallback_reason surfaces correctly across the async job and HTTP status endpoints."""

    @pytest.mark.asyncio
    async def test_pipeline_cloud_ai_success(self, client):
        job_id = "test-job-cloud-success"
        AI_JOBS_STORE[job_id] = {"job_id": job_id, "status": "QUEUED", "progress": 5, "current_step": "Queued", "result": None, "error": None}

        mock_video_analysis = {
            "video_analyzed": True,
            "vision_success": True,
            "visual_description": "A close-up of an espresso shot pulling with rich crema.",
            "source_label": "Based on video analysis",
            "analysis_source": "video_visual"
        }

        mock_cloud_meta = {
            "title": "The Perfect Espresso Pull ☕",
            "description": "Watch this satisfying 9-bar espresso extraction.",
            "youtube_hashtags": ["#Shorts", "#Coffee", "#Espresso"],
            "instagram_hashtags": ["#Reels", "#CoffeeLover"],
            "model": "openai/gpt-oss-120b",
            "success": True,
            "fallback_reason": None
        }

        with patch("backend.video_analyzer.analyze_video_content", return_value=mock_video_analysis):
            with patch("backend.services.cloud_ai.is_cloud_ai_available", return_value=True):
                with patch("backend.services.cloud_ai.generate_metadata_with_groq", return_value=mock_cloud_meta):
                    await execute_ai_analysis_job(
                        job_id=job_id,
                        title="",
                        description="",
                        url="https://youtube.com/shorts/coffee999"
                    )

        job = AI_JOBS_STORE[job_id]
        assert job["status"] == "COMPLETED"
        res = job["result"]
        assert res["viral_title"] == "The Perfect Espresso Pull ☕"
        assert res["ai_failed"] is False
        assert res["video_analyzed"] is True
        assert res["confidence_notes"] == "VERY HIGH (Cloud AI)"
        assert res["fallback_reason"] is None

        # Verify status endpoint returns fallback_reason: None
        status_res = client.get(f"/api/analyze/status/{job_id}")
        assert status_res.status_code == 200
        data = status_res.json()
        assert data["status"] == "COMPLETED"
        assert data["fallback_reason"] is None

    @pytest.mark.asyncio
    async def test_pipeline_missing_keys_fallback_reason(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("GROQ_KEY", raising=False)

        job_id = "test-job-missing-keys"
        AI_JOBS_STORE[job_id] = {"job_id": job_id, "status": "QUEUED", "progress": 5, "current_step": "Queued", "result": None, "error": None}

        mock_video_analysis = {
            "video_analyzed": False,
            "vision_success": False,
            "visual_description": "",
            "source_label": "From caption — video analysis unavailable",
            "analysis_source": "caption_fallback"
        }

        with patch("backend.video_analyzer.analyze_video_content", return_value=mock_video_analysis):
            await execute_ai_analysis_job(
                job_id=job_id,
                title="Video by mani.__.me",
                description="Original Instagram attribution text",
                url="https://instagram.com/reel/sample999"
            )

        job = AI_JOBS_STORE[job_id]
        assert job["status"] == "COMPLETED"
        res = job["result"]
        assert res["ai_failed"] is True
        assert res["confidence_notes"] == "FALLBACK"
        # Verify fallback_reason clearly indicates unconfigured keys
        assert res["fallback_reason"] is not None
        assert "unconfigured" in res["fallback_reason"] or "missing" in res["fallback_reason"]

        # Verify status endpoint surfaces fallback_reason at top level
        status_res = client.get(f"/api/analyze/status/{job_id}")
        assert status_res.status_code == 200
        data = status_res.json()
        assert data["status"] == "COMPLETED"
        assert data["fallback_reason"] is not None
        assert "GEMINI_API_KEY" in data["fallback_reason"] or "Cloud AI" in data["fallback_reason"]

    @pytest.mark.asyncio
    async def test_pipeline_groq_failure_surfaces_fallback_reason(self, client, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "test_gemini")
        monkeypatch.setenv("GROQ_API_KEY", "test_groq")

        job_id = "test-job-groq-failure"
        AI_JOBS_STORE[job_id] = {"job_id": job_id, "status": "QUEUED", "progress": 5, "current_step": "Queued", "result": None, "error": None}

        mock_video_analysis = {
            "video_analyzed": False,
            "vision_success": False,
            "visual_description": "",
            "source_label": "From caption — video analysis unavailable",
            "analysis_source": "caption_fallback"
        }

        mock_failed_groq = {
            "title": "Unbelievable Moment",
            "description": "Fallback description",
            "youtube_hashtags": ["#Shorts"],
            "instagram_hashtags": ["#Reels"],
            "hashtags": ["#Shorts", "#Reels"],
            "success": False,
            "error": "Groq model 'groq/compound-mini' not found: HTTP 404",
            "fallback_reason": "groq_error: HTTP 404 model not found"
        }

        # Groq fails, and MasterAgent will trigger fallback
        with patch("backend.video_analyzer.analyze_video_content", return_value=mock_video_analysis):
            with patch("backend.services.cloud_ai.is_cloud_ai_available", return_value=True):
                with patch("backend.services.cloud_ai.generate_metadata_with_groq", return_value=mock_failed_groq):
                    with patch("backend.agents.master_agent.MasterAgent.run", side_effect=RuntimeError("Ollama offline")):
                        await execute_ai_analysis_job(
                            job_id=job_id,
                            title="Video by artist",
                            description="Caption text here",
                            url="https://instagram.com/reel/artist999"
                        )

        job = AI_JOBS_STORE[job_id]
        assert job["status"] == "COMPLETED"
        res = job["result"]
        assert res["ai_failed"] is True
        assert res["fallback_reason"] is not None
        assert ("groq" in res["fallback_reason"].lower() or "ollama" in res["fallback_reason"].lower() or "masteragent" in res["fallback_reason"].lower())

        # Verify status endpoint exposes fallback_reason
        status_res = client.get(f"/api/analyze/status/{job_id}")
        assert status_res.status_code == 200
        data = status_res.json()
        assert data["fallback_reason"] is not None

    @pytest.mark.asyncio
    async def test_pipeline_fast_path_timeout_graceful_degradation(self, client, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "test_gemini")
        monkeypatch.setenv("GROQ_API_KEY", "test_groq")
        # Set short timeout to trigger fast-path degradation
        monkeypatch.setenv("VIDEO_ANALYSIS_TIMEOUT_SECONDS", "0.01")

        job_id = "test-job-fast-path-timeout"
        AI_JOBS_STORE[job_id] = {"job_id": job_id, "status": "QUEUED", "progress": 5, "current_step": "Queued", "result": None, "error": None}

        # Simulate slow frame extraction
        import time
        def _slow_analyzer(*args, **kwargs):
            time.sleep(0.05)
            return {"video_analyzed": True}

        mock_cloud_meta = {
            "title": "Lightweight Fallback Hook 🔥",
            "description": "Synthesized from caption after fast-path timeout.",
            "youtube_hashtags": ["#Shorts", "#Viral", "#Trending"],
            "instagram_hashtags": ["#Reels"],
            "model": "openai/gpt-oss-120b",
            "success": True,
            "fallback_reason": None
        }

        with patch("backend.video_analyzer.analyze_video_content", side_effect=_slow_analyzer):
            with patch("backend.services.cloud_ai.is_cloud_ai_available", return_value=True):
                with patch("backend.services.cloud_ai.generate_metadata_with_groq", return_value=mock_cloud_meta):
                    await execute_ai_analysis_job(
                        job_id=job_id,
                        title="",
                        description="Exciting dance reel in the subway",
                        url="https://youtube.com/shorts/dance999"
                    )

        job = AI_JOBS_STORE[job_id]
        assert job["status"] == "COMPLETED"
        res = job["result"]
        # In lightweight mode with Cloud AI available, title was successfully synthesized from caption
        assert res["viral_title"] == "Lightweight Fallback Hook 🔥"
        assert res["ai_failed"] is False
        assert res["fallback_reason"] == "video_analysis_timeout_lightweight_mode"
        assert "timeout" in res["confidence_notes"].lower() or "lightweight" in res["confidence_notes"].lower()

        # Status endpoint confirms graceful degradation
        status_res = client.get(f"/api/analyze/status/{job_id}")
        assert status_res.status_code == 200
        data = status_res.json()
        assert data["fallback_reason"] == "video_analysis_timeout_lightweight_mode"


class TestViralMetadataPromptingAndFormatting:
    """Verify high-CTR title limits, tag normalization, and few-shot prompt inclusion."""

    def test_enforce_title_length_under_60_chars(self):
        from backend.services.cloud_ai import _enforce_title_length

        short_title = "He Almost Missed The Ledge 😱"
        assert _enforce_title_length(short_title) == short_title

        long_title = "This Is An Extremely Long YouTube Shorts Title That Exceeds Sixty Characters Easily And Should Be Trimmed"
        cleaned = _enforce_title_length(long_title)
        assert len(cleaned) <= 60
        assert cleaned.endswith("...")

        assert _enforce_title_length("") == "Wait Until You See This 🎬"

    def test_format_tags_ensures_broad_tags_and_prefixes(self):
        from backend.services.cloud_ai import _format_tags

        raw_tags = ["Shorts", "parkour", "#stunt", "parkour", "danger "]
        formatted = _format_tags(raw_tags, ["#Shorts", "#ShortsFeed", "#Viral"])

        assert "#Shorts" in formatted
        assert "#ShortsFeed" in formatted
        assert "#Viral" in formatted
        assert "#parkour" in formatted
        assert "#stunt" in formatted
        assert all(t.startswith("#") for t in formatted)
        # Deduplication
        assert formatted.count("#parkour") == 1

    def test_groq_viral_prompt_generation_and_length_enforcement(self, monkeypatch):
        from backend.services.cloud_ai import generate_metadata_with_groq, VIRAL_METADATA_SYSTEM_PROMPT

        # Verify few-shot examples exist in prompt
        assert "FEW-SHOT BENCHMARKS" in VIRAL_METADATA_SYSTEM_PROMPT
        assert "CRITICAL TITLE RULES" in VIRAL_METADATA_SYSTEM_PROMPT
        assert "STRICTLY UNDER 60 CHARACTERS" in VIRAL_METADATA_SYSTEM_PROMPT

        monkeypatch.setenv("GROQ_API_KEY", "test_groq_key")
        mock_response = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "title": "Why Chefs Never Cut Onions Like This 🧅",
                        "description": "5 seconds is all it took. Watch this knife skill.\n\nCould you chop this fast? Comment below 👇",
                        "youtube_hashtags": ["Shorts", "CookingHacks", "ChefLife"],
                        "instagram_hashtags": ["Reels", "Foodie", "ViralChef"]
                    })
                }
            }]
        }

        mock_resp_obj = MagicMock()
        mock_resp_obj.read.return_value = json.dumps(mock_response).encode("utf-8")
        mock_resp_obj.__enter__.return_value = mock_resp_obj

        with patch("urllib.request.urlopen", return_value=mock_resp_obj):
            res = generate_metadata_with_groq("Chef chopping vegetables")
            assert res["success"] is True
            assert len(res["title"]) <= 60
            assert res["title"] == "Why Chefs Never Cut Onions Like This 🧅"
            assert "#Shorts" in res["youtube_hashtags"]
            assert "#ShortsFeed" in res["youtube_hashtags"]
            assert len(res["hashtags"]) >= 5


