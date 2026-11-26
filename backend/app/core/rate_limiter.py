import ipaddress
import math
import time
from collections import OrderedDict, deque
from threading import Lock
from typing import Deque, Optional, Tuple
from fastapi import HTTPException, Request

from app.core.config import settings


def _normalize_ip(candidate: Optional[str]) -> Optional[str]:
    """Validates and normalizes an IPv4/IPv6 string; returns None if malformed."""
    if not candidate:
        return None
    raw = candidate.strip()
    if not raw:
        return None
    try:
        return str(ipaddress.ip_address(raw))
    except ValueError:
        return None


class InMemorySlidingWindowRateLimiter:
    """
    Thread-safe per-IP sliding-window rate limiter with bounded memory and expired-key pruning.

    Trust Boundary & Proxy Security:
    - By default (`TRUST_PROXY_HEADERS=False` and no `TRUSTED_PROXY_CIDRS`), arbitrary client-supplied
      `X-Forwarded-For`, `True-Client-IP`, and `CF-Connecting-IP` headers are IGNORED so callers
      cannot spoof IPs to bypass rate limiting.
    - When `TRUST_PROXY_HEADERS=True` (for Render's Cloudflare-backed reverse proxy edge) or when the
      socket peer IP matches `TRUSTED_PROXY_CIDRS`, the limiter prefers Render's edge-populated
      `True-Client-IP` / `CF-Connecting-IP`, then validates `X-Forwarded-For` leftmost IP.

    Architecture Limitations:
    - State is stored in process memory and resets on server restart or redeploy.
    - Single-instance / single-worker only: horizontally scaled multi-worker deployments require
      replacing this store with a shared Redis rate-limiter backend.
    """

    def __init__(
        self,
        max_requests: int = 10,
        window_seconds: int = 60,
        max_tracked_keys: int = 2048,
        trust_proxy_headers: Optional[bool] = None,
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.max_tracked_keys = max_tracked_keys
        self.trust_proxy_headers = (
            settings.TRUST_PROXY_HEADERS if trust_proxy_headers is None else trust_proxy_headers
        )
        self._hits: OrderedDict[str, Deque[float]] = OrderedDict()
        self._lock = Lock()

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def tracked_key_count(self) -> int:
        with self._lock:
            return len(self._hits)

    def _is_trusted_proxy_peer(self, socket_ip: Optional[str]) -> bool:
        if self.trust_proxy_headers:
            return True
        if not socket_ip or not settings.TRUSTED_PROXY_CIDRS:
            return False
        try:
            addr = ipaddress.ip_address(socket_ip)
            return any(addr in net for net in settings.TRUSTED_PROXY_CIDRS)
        except ValueError:
            return False

    def extract_client_ip(self, request: Request) -> str:
        """
        Extracts a validated client IP without trusting user-supplied profile IDs or
        unverified forwarding headers.
        """
        raw_socket_host = request.client.host if request.client else None
        socket_ip = _normalize_ip(raw_socket_host)

        if self._is_trusted_proxy_peer(socket_ip):
            # Prefer Render's single-IP edge headers before X-Forwarded-For leftmost IP
            for header_name in ("true-client-ip", "cf-connecting-ip"):
                header_ip = _normalize_ip(request.headers.get(header_name))
                if header_ip:
                    return header_ip

            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                leftmost_ip = _normalize_ip(forwarded.split(",")[0])
                if leftmost_ip:
                    return leftmost_ip

        return socket_ip or "unknown_peer"

    def _prune_expired_locked(self, cutoff: float) -> None:
        stale_keys = []
        for key, bucket in self._hits.items():
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if not bucket:
                stale_keys.append(key)
        for key in stale_keys:
            del self._hits[key]

    def check_and_record(self, client_key: str) -> Tuple[bool, int]:
        """Returns (is_allowed, retry_after_seconds)."""
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            # Opportunistically clean expired keys to prevent unbounded memory growth
            if len(self._hits) >= self.max_tracked_keys // 2:
                self._prune_expired_locked(cutoff)

            bucket = self._hits.get(client_key)
            if bucket is None:
                while len(self._hits) >= self.max_tracked_keys:
                    self._hits.popitem(last=False)
                bucket = deque()
                self._hits[client_key] = bucket
            else:
                self._hits.move_to_end(client_key)
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
