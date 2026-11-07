import time
from collections import defaultdict, deque
from threading import Lock
from typing import Callable

from fastapi import HTTPException, Request, status

from app.core.config import settings


class SlidingWindowRateLimiter:
    """
    Thread-safe in-memory Sliding Window Rate Limiter.

    NOTE ON MULTI-WORKER DEPLOYMENTS:
    This rate limiter maintains state in-memory per worker process.
    On single-worker/single-container hosting (such as Render Free tier),
    this provides effective defense against spam, DoS, and quota depletion.
    For multi-worker or multi-node production clusters, a distributed Redis
    store is recommended to share request counts across worker processes.
    """

    def __init__(self, max_requests: int, window_seconds: int, scope: str = "default") -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.scope = scope
        self._history: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def _resolve_client_key(self, request: Request) -> str:
        # Check if user is authenticated in request.state
        user = getattr(request.state, "user", None)
        if user and getattr(user, "id", None):
            return f"{self.scope}:user:{user.id}"

        # Otherwise resolve IP
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        elif request.client and request.client.host:
            client_ip = request.client.host
        else:
            client_ip = "127.0.0.1"
        return f"{self.scope}:ip:{client_ip}"

    def check(self, key: str, now: float | None = None, max_override: int | None = None) -> tuple[bool, int]:
        now = now or time.time()
        window_start = now - self.window_seconds
        allowed_max = max_override or self.max_requests

        with self._lock:
            timestamps = self._history[key]
            # Prune timestamps outside current sliding window
            while timestamps and timestamps[0] < window_start:
                timestamps.popleft()

            if len(timestamps) >= allowed_max:
                # Calculate retry_after seconds based on oldest timestamp in window
                oldest = timestamps[0]
                retry_after = max(1, int(oldest + self.window_seconds - now))
                return False, retry_after

            timestamps.append(now)
            return True, 0

    def reset(self) -> None:
        with self._lock:
            self._history.clear()

    def __call__(self, request: Request) -> None:
        # Skip rate limiting during automated test suite unless explicitly enabled
        if settings.is_testing and not getattr(request.state, "force_rate_limit", False):
            return

        if not settings.rate_limit_enabled:
            return

        key = self._resolve_client_key(request)
        # In local development mode, relax limits by 10x so paired programming and manual demo testing are not blocked
        dev_override = self.max_requests * 10 if settings.app_env.lower() == "development" else None
        allowed, retry_after = self.check(key, max_override=dev_override)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Quá nhiều yêu cầu ({self.scope}). Vui lòng thử lại sau {retry_after} giây.",
                headers={"Retry-After": str(retry_after)},
            )


# Standard rate limiters for sensitive endpoints
auth_rate_limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=60, scope="auth")
room_upload_rate_limiter = SlidingWindowRateLimiter(max_requests=10, window_seconds=300, scope="room_upload")
room_analyze_rate_limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=300, scope="room_analyze")
design_generation_rate_limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=300, scope="design_generation")
