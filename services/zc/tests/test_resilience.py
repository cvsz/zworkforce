"""tests/test_resilience.py"""
import pytest

from wire.exceptions import APIError, CircuitOpenError, TransientAPIError
from wire.resilience import CircuitBreaker, retry


def test_retry_succeeds_after_transient_failures():
    calls = {"n": 0}
    sleeps = []

    @retry(max_attempts=3, base_delay=0.01, sleep=sleeps.append)
    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise TransientAPIError("temporary")
        return "ok"

    assert flaky() == "ok"
    assert calls["n"] == 3
    assert len(sleeps) == 2  # slept before attempt 2 and 3


def test_retry_gives_up_after_max_attempts():
    calls = {"n": 0}

    @retry(max_attempts=2, base_delay=0.01, sleep=lambda s: None)
    def always_fails():
        calls["n"] += 1
        raise TransientAPIError("still broken")

    with pytest.raises(TransientAPIError):
        always_fails()
    assert calls["n"] == 2


def test_retry_does_not_retry_non_retryable_errors():
    calls = {"n": 0}

    @retry(max_attempts=5, base_delay=0.01, sleep=lambda s: None)
    def bad_request():
        calls["n"] += 1
        raise APIError("400 bad request", status_code=400)

    with pytest.raises(APIError):
        bad_request()
    assert calls["n"] == 1  # no retries attempted


def test_retry_respects_explicit_retry_after():
    from wire.exceptions import RateLimitError
    sleeps = []
    calls = {"n": 0}

    @retry(max_attempts=2, sleep=sleeps.append)
    def rate_limited():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RateLimitError("429", retry_after=5.0)
        return "ok"

    assert rate_limited() == "ok"
    assert sleeps == [5.0]


def test_circuit_breaker_opens_after_threshold():
    breaker = CircuitBreaker(failure_threshold=2, reset_timeout=60)

    @retry(max_attempts=1, breaker=breaker, sleep=lambda s: None)
    def always_fails():
        raise TransientAPIError("down")

    for _ in range(2):
        with pytest.raises(TransientAPIError):
            always_fails()

    assert breaker.state == "open"
    with pytest.raises(CircuitOpenError):
        breaker.before_call()


def test_circuit_breaker_closes_on_success():
    breaker = CircuitBreaker(failure_threshold=1, reset_timeout=0)
    breaker.on_failure()
    assert breaker.state == "open"
    breaker.before_call()  # reset_timeout=0 -> immediately half-open
    assert breaker.state == "half_open"
    breaker.on_success()
    assert breaker.state == "closed"
