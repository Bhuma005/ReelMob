"""
backend/logging_config.py — Production-grade structured logging for ReelsMob.

Features:
- JSON formatting for production / container environments (LOG_FORMAT=json).
- Human-readable colored/clean formatting for development (LOG_FORMAT=console).
- Request ID context tracking across all asynchronous calls via contextvars.
- Automated secret and credential redaction (API keys, tokens, session cookies).
"""

import os
import re
import json
import logging
import contextvars
from datetime import datetime
from typing import Any, Dict

# Context variable to trace a request ID across async tasks
request_id_ctx_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

# Secret redaction patterns
SECRET_PATTERNS = [
    re.compile(r'(?i)(api[_-]?key|token|secret|password|authorization|cookie|sessionid)=([^\s&,;]+)'),
    re.compile(r'(?i)("?(?:api[_-]?key|token|secret|password|authorization)"?\s*[:=]\s*)"([^"]+)"'),
    re.compile(r'gsk_[a-zA-Z0-9]{20,}'),
    re.compile(r'AQ\.[a-zA-Z0-9_\-]{20,}'),
    re.compile(r'AIzaSy[a-zA-Z0-9_\-]{30,}'),
    re.compile(r'ey[a-zA-Z0-9_\-]{30,}\.ey[a-zA-Z0-9_\-]{30,}\.[a-zA-Z0-9_\-]{30,}'), # JWT
]


def redact_sensitive_data(text: str) -> str:
    """Redacts known API keys, tokens, and credentials from log strings."""
    if not isinstance(text, str) or not text:
        return text
    
    redacted = text
    for pattern in SECRET_PATTERNS:
        # If it's a key-value pattern with group 2 being the secret
        if pattern.groups == 2:
            redacted = pattern.sub(r'\1=••••••••', redacted)
        else:
            redacted = pattern.sub(r'••••••••', redacted)
    return redacted


class SecretRedactingFilter(logging.Filter):
    """Logging filter that injects the current request_id and redacts secrets."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        # Inject request_id from contextvar if not already present
        record.request_id = request_id_ctx_var.get("-")
        
        # Redact message
        if isinstance(record.msg, str):
            record.msg = redact_sensitive_data(record.msg)
            
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: redact_sensitive_data(str(v)) for k, v in record.args.items()}
            elif isinstance(record.args, (list, tuple)):
                record.args = tuple(redact_sensitive_data(str(a)) for a in record.args)
                
        return True


class JsonLogFormatter(logging.Formatter):
    """Outputs machine-readable JSON logs for production aggregators (CloudWatch, Datadog)."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_obj)


class ConsoleLogFormatter(logging.Formatter):
    """Outputs clean, human-readable logs for local development with request ID."""
    
    def format(self, record: logging.LogRecord) -> str:
        req_id = getattr(record, "request_id", "-")
        req_str = f" [req:{req_id}]" if req_id != "-" else ""
        time_str = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        msg = record.getMessage()
        
        base = f"{time_str} [{record.levelname:<5}]{req_str} {record.name}: {msg}"
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


def setup_logging() -> logging.Logger:
    """
    Configures application logging once at startup.
    Reads LOG_LEVEL and LOG_FORMAT from environment.
    """
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = os.getenv("LOG_FORMAT", "console").lower()
    
    log_level = getattr(logging, log_level_str, logging.INFO)
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers to avoid duplicates
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(log_level)
    stream_handler.addFilter(SecretRedactingFilter())
    
    if log_format == "json":
        stream_handler.setFormatter(JsonLogFormatter())
    else:
        stream_handler.setFormatter(ConsoleLogFormatter())
        
    root_logger.addHandler(stream_handler)
    
    # Reduce noise from chatty external libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("googleapiclient").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    
    app_logger = logging.getLogger("reelsmob")
    app_logger.setLevel(log_level)
    return app_logger
