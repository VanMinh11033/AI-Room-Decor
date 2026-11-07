import time
import pytest
from fastapi import HTTPException, Request

from app.core.config import settings
from app.core.rate_limit import SlidingWindowRateLimiter


def test_sliding_window_rate_limiter_allows_up_to_max():
    limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=10, scope="test")
    key = "test_user_1"

    # Requests 1, 2, 3 should succeed
    for i in range(3):
        allowed, retry_after = limiter.check(key, now=100.0 + i)
        assert allowed is True
        assert retry_after == 0

    # Request 4 in same window must fail
    allowed, retry_after = limiter.check(key, now=103.0)
    assert allowed is False
    assert retry_after > 0


def test_sliding_window_rate_limiter_expires_old_requests():
    limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=5, scope="test")
    key = "test_user_2"

    allowed, _ = limiter.check(key, now=100.0)
    assert allowed is True
    allowed, _ = limiter.check(key, now=101.0)
    assert allowed is True

    # 3rd request at 102s fails
    allowed, retry_after = limiter.check(key, now=102.0)
    assert allowed is False

    # At 106s (window is 101s - 106s, so request at 100s expired)
    allowed, _ = limiter.check(key, now=106.0)
    assert allowed is True


def test_rate_limiter_raises_429_http_exception():
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=60, scope="login")

    # Mock request
    class MockClient:
        host = "192.168.1.100"

    class MockRequest:
        client = MockClient()
        headers = {}
        state = type("State", (), {"force_rate_limit": True})()

    req = MockRequest()

    # Call 1: success
    limiter(req)

    # Call 2: should raise HTTPException with 429
    with pytest.raises(HTTPException) as exc_info:
        limiter(req)

    assert exc_info.value.status_code == 429
    assert "Quá nhiều yêu cầu" in exc_info.value.detail
    assert "Retry-After" in exc_info.value.headers
