"""
Structured-ish logging for the backend. Deliberately simple — a formatted
stdlib logger, not a full observability stack (see RISKON_ARCHITECTURE.md,
"Do not overengineer"). Two rules that matter more than the format:
  1. The Anthropic API key is NEVER logged, anywhere, under any level —
     `log_ai_request()` below is the only place AI-call metadata is logged,
     and it takes explicit named fields, not a raw request/response dump.
  2. No stack trace or internal exception detail is ever handed to a client;
     it's fine (expected) for it to appear here, server-side only.
"""
import logging
import sys
import time

from backend.config import settings

_configured = False


def configure_logging() -> None:
    global _configured
    if _configured:
        return
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    _configured = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)


_ai_logger = get_logger("riskon.ai")


def log_ai_request(*, request_type: str, record_id: str, model: str, started_at: float,
                    success: bool, validation_ok: bool | None = None, error: str | None = None) -> None:
    """The one function that logs AI-call metadata — request type, record id,
    timestamp, success/failure, model used, latency, validation result. Never
    passed the API key, the raw prompt, or the raw response; callers only
    ever supply the fields named in the signature above."""
    latency_ms = round((time.time() - started_at) * 1000)
    if success:
        _ai_logger.info(
            "ai_request type=%s record_id=%s model=%s latency_ms=%s validation_ok=%s",
            request_type, record_id, model, latency_ms, validation_ok,
        )
    else:
        _ai_logger.warning(
            "ai_request_failed type=%s record_id=%s model=%s latency_ms=%s error=%s",
            request_type, record_id, model, latency_ms, error,
        )
