import math
import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque, Dict, Tuple
from fastapi import HTTPException, Request


class InMemorySlidingWindowRateLimiter:
    """
    Lightweight thread-safe per-IP sliding-window rate limiter.

    Architecture Limitation:
    State is stored in process memory, which protects single-instance deployments
    (such as a single Render web worker). Multi-worker or horizontally scaled
    deployments should replace this store with a shared Redis backend.
    """

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    @staticmethod
    def extract_client_ip(request: Request) -> str:
        """
        Derives client IP from reverse-proxy X-Forwarded-For header (leftmost hop)
        or direct socket peer address. Never uses user-supplied profile IDs.
        """
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            first_hop = forwarded.split(",")[0].strip()
            if first_hop:
                return first_hop
        if request.client and request.client.host:
            return request.client.host
        return "unknown"

    def check_and_record(self, client_key: str) -> Tuple[bool, int]:
        """Returns (is_allowed, retry_after_seconds)."""
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            bucket = self._hits[client_key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= self.max_requests:
                oldest = bucket[0]
                retry_after = max(1, int(math.ceil(self.window_seconds - (now - oldest))))
                return False, retry_after

            bucket.append(now)
            return True, 0


def enforce_plan_rate_limit(request: Request, limiter: InMemorySlidingWindowRateLimiter) -> None:
    client_ip = limiter.extract_client_ip(request)
    allowed, retry_after = limiter.check_and_record(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded for daily plan generation.",
                "retry_after_seconds": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )
