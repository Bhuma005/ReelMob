import os
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to inject standard HTTP security headers on all responses.
    Enforces X-Content-Type-Options, X-Frame-Options, and Referrer-Policy unconditionally.
    Enforces HSTS (Strict-Transport-Security) only in production when served over HTTPS.
    """
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        env = os.getenv("ENVIRONMENT", "development").strip().lower()
        is_https = (
            request.url.scheme == "https"
            or request.headers.get("x-forwarded-proto", "").lower() == "https"
        )
        if env == "production" and is_https:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response
