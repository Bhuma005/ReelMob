import pytest
from starlette.testclient import TestClient
from backend.main import app

@pytest.fixture
def client():
    return TestClient(app)

def test_security_headers_in_development(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    client = TestClient(app, base_url="http://testserver")

    response = client.get("/api/health/ai")
    assert response.status_code == 200

    # Required baseline security headers
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    # HSTS must NOT be set in development (even if request is simulated over https)
    assert "Strict-Transport-Security" not in response.headers

    # Also verify with base_url="https://testserver" in development
    https_client = TestClient(app, base_url="https://testserver")
    https_res = https_client.get("/api/health/ai")
    assert https_res.status_code == 200
    assert "Strict-Transport-Security" not in https_res.headers

def test_security_headers_in_production_https(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CORS_ORIGINS", "https://app.reelsmob.com")

    https_client = TestClient(app, base_url="https://testserver")
    response = https_client.get("/api/health/ai")
    assert response.status_code == 200

    # All baseline headers present
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    # Strict-Transport-Security MUST be present in production over HTTPS
    assert response.headers.get("Strict-Transport-Security") == "max-age=31536000; includeSubDomains"

def test_security_headers_in_production_forwarded_proto(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CORS_ORIGINS", "https://app.reelsmob.com")

    # In cloud environments (e.g. behind reverse proxies or load balancers), x-forwarded-proto indicates HTTPS
    http_client = TestClient(app, base_url="http://testserver")
    response = http_client.get("/api/health/ai", headers={"x-forwarded-proto": "https"})
    assert response.status_code == 200

    assert response.headers.get("Strict-Transport-Security") == "max-age=31536000; includeSubDomains"

def test_security_headers_in_production_plain_http(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CORS_ORIGINS", "https://app.reelsmob.com")

    # Plain HTTP without forwarded-proto should NOT emit HSTS to avoid browser caching issues on local plain HTTP
    http_client = TestClient(app, base_url="http://testserver")
    response = http_client.get("/api/health/ai")
    assert response.status_code == 200

    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "Strict-Transport-Security" not in response.headers
