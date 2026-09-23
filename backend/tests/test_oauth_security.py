"""
test_oauth_security.py — Unit tests for OAuth redirect URI allowlisting and Host header validation.
"""

from unittest.mock import MagicMock
import pytest
from backend.youtube_auth import is_allowed_redirect_uri, _get_redirect_uri, _get_public_base_url


def test_is_allowed_redirect_uri():
    """Verify that only authorized origins and redirect paths are permitted."""
    # Allowed localhost / 127.0.0.1
    assert is_allowed_redirect_uri("http://localhost:8000/auth/callback")
    assert is_allowed_redirect_uri("http://localhost:5173/api/auth/youtube/callback")
    assert is_allowed_redirect_uri("http://127.0.0.1:8000/auth/callback")

    # Allowed production domains
    assert is_allowed_redirect_uri("https://reelmob.onrender.com/auth/callback")
    assert is_allowed_redirect_uri("https://reelmob.app/auth/callback")
    assert is_allowed_redirect_uri("https://api.reelmob.app/auth/callback")

    # Blocked unauthorized / malicious domains
    assert not is_allowed_redirect_uri("https://evil.com/auth/callback")
    assert not is_allowed_redirect_uri("https://attacker-reelmob.com/auth/callback")
    assert not is_allowed_redirect_uri("https://localhost.evil.com/auth/callback")
    assert not is_allowed_redirect_uri("http://192.168.1.100/auth/callback")
    assert not is_allowed_redirect_uri("javascript:alert(1)")
    assert not is_allowed_redirect_uri("")
    assert not is_allowed_redirect_uri(None)


def test_override_uri_blocks_unauthorized_target(monkeypatch):
    """Verify that an unauthorized override_uri parameter is rejected and falls back safely."""
    monkeypatch.delenv("GOOGLE_REDIRECT_URI", raising=False)
    monkeypatch.delenv("REDIRECT_URI", raising=False)
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://reelmob.onrender.com")

    # Attacker tries to steal code via query parameter
    result = _get_redirect_uri(override_uri="https://evil-attacker.com/steal-code")

    # Result must NOT be the attacker URL
    assert result != "https://evil-attacker.com/steal-code"
    assert "reelmob.onrender.com" in result


def test_override_uri_allows_authorized_target():
    """Verify that an authorized override_uri parameter is accepted."""
    result = _get_redirect_uri(override_uri="http://localhost:5173/auth/callback")
    assert result == "http://localhost:5173/auth/callback"


def test_public_base_url_rejects_untrusted_host_header(monkeypatch):
    """Verify that untrusted Host headers are rejected to prevent Host header injection."""
    monkeypatch.delenv("GOOGLE_REDIRECT_URI", raising=False)
    monkeypatch.delenv("REDIRECT_URI", raising=False)
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://reelmob.onrender.com")

    mock_request = MagicMock()
    mock_request.headers = {
        "x-forwarded-proto": "https",
        "x-forwarded-host": "attacker-spoofed-domain.com"
    }
    mock_request.url.scheme = "https"

    base_url = _get_public_base_url(mock_request)
    assert base_url == "https://reelmob.onrender.com"
    assert "attacker-spoofed-domain.com" not in base_url
