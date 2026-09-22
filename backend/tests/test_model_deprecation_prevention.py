"""
test_model_deprecation_prevention.py — Tests for Groq & Gemini model deprecation prevention.
Covers:
1. Model resolution and legacy normalization (openai/gpt-oss-120b & gemini-2.0-flash).
2. Groq models-list endpoint self-check (configured model found vs missing/deprecated).
3. Warning logging on missing/deprecated model without app crash.
4. Gemini models-list endpoint self-check.
5. Caching and health endpoint integration (/api/health/detailed and /api/health/ai).
"""

import json
import logging
import io
import urllib.request
import urllib.error
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from backend.services.cloud_ai import (
    get_groq_model,
    get_gemini_model,
    verify_groq_model_active,
    verify_gemini_model_active,
    run_startup_model_self_check,
    _MODEL_VALIDITY_CACHE,
)
from backend.main import app


@pytest.fixture(autouse=True)
def reset_model_cache():
    """Reset the module-level model validity cache before every test."""
    _MODEL_VALIDITY_CACHE["groq"] = {"timestamp": 0.0, "data": None}
    _MODEL_VALIDITY_CACHE["gemini"] = {"timestamp": 0.0, "data": None}
    yield
    _MODEL_VALIDITY_CACHE["groq"] = {"timestamp": 0.0, "data": None}
    _MODEL_VALIDITY_CACHE["gemini"] = {"timestamp": 0.0, "data": None}


class TestModelConfigurationAndNormalization:
    """Verify configurable model IDs and normalization of deprecated identifiers."""

    def test_default_models(self, monkeypatch):
        monkeypatch.delenv("GROQ_MODEL", raising=False)
        monkeypatch.delenv("GEMINI_MODEL", raising=False)
        assert get_groq_model() == "openai/gpt-oss-120b"
        assert get_gemini_model() == "gemini-2.0-flash"

    def test_groq_deprecated_model_normalization(self, monkeypatch):
        # The decommissioned llama-3.3-70b-versatile model must automatically normalize
        monkeypatch.setenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        assert get_groq_model() == "openai/gpt-oss-120b"

        # Legacy compound slugs must also normalize
        monkeypatch.setenv("GROQ_MODEL", "groq/compound-mini")
        assert get_groq_model() == "openai/gpt-oss-120b"

        # Valid custom model must be preserved
        monkeypatch.setenv("GROQ_MODEL", "llama-3.1-8b-instant")
        assert get_groq_model() == "llama-3.1-8b-instant"

    def test_gemini_model_normalization(self, monkeypatch):
        monkeypatch.setenv("GEMINI_MODEL", "gemini-3.6-flash")
        assert get_gemini_model() == "gemini-2.0-flash"

        monkeypatch.setenv("GEMINI_MODEL", "gemini-1.5-pro")
        assert get_gemini_model() == "gemini-1.5-pro"


class TestGroqModelSelfCheck:
    """Verify startup self-check querying Groq models list endpoint."""

    def test_groq_unconfigured_skips_gracefully(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("GROQ_KEY", raising=False)
        result = verify_groq_model_active()
        assert result["valid"] is None
        assert result["status"] == "unconfigured"

    def test_groq_configured_model_found_no_warning(self, monkeypatch, caplog):
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test123")
        monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-120b")

        mock_payload = {
            "object": "list",
            "data": [
                {"id": "llama-3.1-8b-instant", "object": "model"},
                {"id": "openai/gpt-oss-120b", "object": "model"}
            ]
        }

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with caplog.at_level(logging.WARNING):
            with patch("urllib.request.urlopen", return_value=mock_resp):
                res = verify_groq_model_active(force_refresh=True)

        assert res["valid"] is True
        assert res["status"] == "active"
        assert "not found" not in caplog.text

    def test_groq_configured_model_missing_logs_loud_warning(self, monkeypatch, caplog):
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test123")
        monkeypatch.setenv("GROQ_MODEL", "deprecated-future-model")

        mock_payload = {
            "object": "list",
            "data": [
                {"id": "llama-3.1-8b-instant", "object": "model"},
                {"id": "openai/gpt-oss-120b", "object": "model"}
            ]
        }

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with caplog.at_level(logging.WARNING):
            with patch("urllib.request.urlopen", return_value=mock_resp):
                res = verify_groq_model_active(force_refresh=True)

        assert res["valid"] is False
        assert res["status"] == "missing"
        expected_warning = "WARNING: configured GROQ_MODEL 'deprecated-future-model' not found in Groq's active model list — AI generation will fail until this is fixed."
        assert expected_warning in caplog.text

    def test_groq_api_error_handles_gracefully(self, monkeypatch, caplog):
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test123")
        with caplog.at_level(logging.WARNING):
            with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
                url="https://api.groq.com/openai/v1/models",
                code=401,
                msg="Unauthorized",
                hdrs={},
                fp=io.BytesIO(b'{"error": "invalid_api_key"}')
            )):
                res = verify_groq_model_active(force_refresh=True)

        assert res["valid"] is False
        assert res["status"] == "error"
        assert "Groq model verification failed" in caplog.text

    def test_groq_caching_avoids_repeated_network_calls(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test123")
        monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-120b")

        mock_payload = {
            "object": "list",
            "data": [{"id": "openai/gpt-oss-120b", "object": "model"}]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            res1 = verify_groq_model_active()
            res2 = verify_groq_model_active()
            assert res1["valid"] is True
            assert res2["valid"] is True
            assert mock_urlopen.call_count == 1  # Reused from cache


class TestGeminiModelSelfCheck:
    """Verify self-check querying Gemini models list endpoint."""

    def test_gemini_unconfigured_skips_gracefully(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        result = verify_gemini_model_active()
        assert result["valid"] is None
        assert result["status"] == "unconfigured"

    def test_gemini_configured_model_found(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "ai_gemini_test")
        monkeypatch.setenv("GEMINI_MODEL", "gemini-2.0-flash")

        mock_payload = {
            "models": [
                {"name": "models/gemini-2.0-flash", "displayName": "Gemini 2.0 Flash"},
                {"name": "models/gemini-1.5-pro", "displayName": "Gemini 1.5 Pro"}
            ]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            res = verify_gemini_model_active(force_refresh=True)

        assert res["valid"] is True
        assert res["status"] == "active"


class TestStartupSelfCheckAndHealthSurfacing:
    """Verify startup self-check runner and /api/health/detailed surfacing."""

    def test_run_startup_model_self_check_does_not_crash(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test123")
        monkeypatch.setenv("GEMINI_API_KEY", "ai_gemini_test")

        with patch("backend.services.cloud_ai.verify_groq_model_active", return_value={"valid": True, "status": "active"}), \
             patch("backend.services.cloud_ai.verify_gemini_model_active", return_value={"valid": True, "status": "active"}):
            results = run_startup_model_self_check()

        assert "groq" in results
        assert "gemini" in results
        assert results["groq"]["status"] == "active"

    def test_health_detailed_surfaces_model_validity(self, monkeypatch):
        client = TestClient(app)
        monkeypatch.setenv("GEMINI_API_KEY", "ai_gemini_test")
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test123")

        mock_groq_status = {"valid": True, "status": "active", "model": "openai/gpt-oss-120b"}
        mock_gemini_status = {"valid": True, "status": "active", "model": "gemini-2.0-flash"}

        with patch("backend.services.cloud_ai.verify_groq_model_active", return_value=mock_groq_status), \
             patch("backend.services.cloud_ai.verify_gemini_model_active", return_value=mock_gemini_status):
            res = client.get("/api/health/detailed")

        assert res.status_code == 200
        data = res.json()
        ai_dep = data["dependencies"]["ai"]
        assert "models" in ai_dep
        assert ai_dep["models"]["groq"]["status"] == "active"
        assert ai_dep["models"]["gemini"]["status"] == "active"

    def test_health_ai_reflects_dynamic_models_and_warning(self, monkeypatch):
        client = TestClient(app)
        monkeypatch.setenv("GEMINI_API_KEY", "ai_gemini_test")
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test123")
        monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-120b")
        monkeypatch.setenv("GEMINI_MODEL", "gemini-2.0-flash")

        mock_groq_warning = {"valid": False, "status": "missing", "model": "openai/gpt-oss-120b"}
        mock_gemini_ok = {"valid": True, "status": "active", "model": "gemini-2.0-flash"}

        with patch("backend.services.cloud_ai.verify_groq_model_active", return_value=mock_groq_warning), \
             patch("backend.services.cloud_ai.verify_gemini_model_active", return_value=mock_gemini_ok):
            res = client.get("/api/health/ai")

        assert res.status_code == 200
        data = res.json()
        assert data["available"] is True
        assert data["status"] == "model_warning"
        assert "openai/gpt-oss-120b (metadata)" in data["models"]
        assert data["model_status"]["groq"]["valid"] is False
