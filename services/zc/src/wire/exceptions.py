"""
exceptions.py — Structured exception hierarchy

Every error the CLI can raise deliberately (as opposed to an unexpected
bug) should be one of these, not a bare Exception/RuntimeError. This lets
callers (main.py's CLI dispatch, tests, and any future API/service wrapper
around this codebase) catch precisely what they mean to catch, and lets
logging_config's exception hook report an `error_code` field that's stable
across versions instead of a raw message string that changes with wording.

Design notes:
- All exceptions carry an `error_code` (stable, machine-readable, safe to
  log/alert on) and an optional `details` dict for structured context.
- __str__ never includes secrets. Call sites are responsible for not
  putting an API key, token, or file content into `details` — see
  security.py's `redact()` for scrubbing free-text messages.
- Retryable vs. non-retryable is encoded via `RETRYABLE` on the class,
  consumed by resilience.retry() so retry policy lives with the error
  taxonomy instead of being re-decided ad hoc at every call site.
"""
from __future__ import annotations


class AICoderError(Exception):
    """Base class for all deliberate (expected, handled) errors in this app."""

    error_code: str = "AICODER_ERROR"
    RETRYABLE: bool = False

    def __init__(self, message: str, *, details: dict | None = None, cause: BaseException | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.__cause__ = cause

    def to_dict(self) -> dict:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class ConfigError(AICoderError):
    """Missing or invalid configuration (API key, malformed config file, ...)."""
    error_code = "CONFIG_ERROR"


class AuthenticationError(AICoderError):
    """API key rejected (HTTP 401)."""
    error_code = "AUTH_ERROR"


class RateLimitError(AICoderError):
    """HTTP 429 — caller should back off. Retryable by definition."""
    error_code = "RATE_LIMIT"
    RETRYABLE = True

    def __init__(self, message: str, *, retry_after: float | None = None, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class TransientAPIError(AICoderError):
    """5xx / network timeouts / connection resets — safe to retry."""
    error_code = "TRANSIENT_API_ERROR"
    RETRYABLE = True


class APIError(AICoderError):
    """Non-retryable 4xx from the Anthropic API (bad request, not found, ...)."""
    error_code = "API_ERROR"

    def __init__(self, message: str, *, status_code: int | None = None, **kwargs):
        super().__init__(message, **kwargs)
        self.status_code = status_code


class RefusalError(AICoderError):
    """Model declined the request (`stop_reason == "refusal"`). Not retryable —
    retrying the identical request will refuse again."""
    error_code = "MODEL_REFUSAL"


class ValidationError(AICoderError):
    """Bad input from the caller/user — file path, argument, or payload shape."""
    error_code = "VALIDATION_ERROR"


class SecurityError(AICoderError):
    """A security control rejected the operation (path traversal, disallowed
    scheme, secret detected in output, etc). Never retryable — retrying
    without changing the input will trip the same control again."""
    error_code = "SECURITY_ERROR"


class CircuitOpenError(AICoderError):
    """resilience.CircuitBreaker is open; the call was short-circuited
    without hitting the network at all."""
    error_code = "CIRCUIT_OPEN"
