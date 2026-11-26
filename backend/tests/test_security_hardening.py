import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.core.config import parse_allowed_origins, parse_trusted_proxy_cidrs
from app.core.rate_limiter import InMemorySlidingWindowRateLimiter
from app.main import app
from app.api.endpoints.plan import plan_rate_limiter
from app.schemas.air_quality import NormalizedAirObservation
from app.schemas.plan import DailyPlanResponse, HouseholdProfile
from app.services.safety_engine import safety_engine


def _fake_request(client_host="203.0.113.10", headers=None):
    return SimpleNamespace(
        client=SimpleNamespace(host=client_host) if client_host is not None else None,
        headers={k.lower(): v for k, v in (headers or {}).items()},
    )


def test_cors_config_rejects_wildcard_normalizes_and_fails_closed():
    assert parse_allowed_origins("*") == []
    assert parse_allowed_origins("https://breathewiseai-frontend.vercel.app/, *") == [
        "https://breathewiseai-frontend.vercel.app"
    ]
    assert parse_allowed_origins("   ") == []
    assert parse_allowed_origins("https://example.com/") == ["https://example.com"]


def test_cors_middleware_behavior_accepted_vs_rejected_origins():
    client = TestClient(app)

    # Configured dev origin in default settings is http://localhost:3000
    r_ok = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert r_ok.status_code == 200
    assert r_ok.headers.get("access-control-allow-origin") == "http://localhost:3000"

    # Unauthorized origin must NOT receive Access-Control-Allow-Origin
    r_bad = client.get("/health", headers={"Origin": "https://evil-attacker.example"})
    assert r_bad.status_code == 200
    assert "access-control-allow-origin" not in r_bad.headers

    # Preflight from unauthorized origin must fail
    r_opt_bad = client.options(
        "/api/v1/cities",
        headers={
            "Origin": "https://evil-attacker.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r_opt_bad.status_code == 400
    assert "access-control-allow-origin" not in r_opt_bad.headers


def test_rate_limiter_default_10_requests_then_429_and_profile_id_ignored():
    """
    Verify 10 allowed requests pass and 11th returns HTTP 429 with Retry-After,
    even if attacker mutates `profile_id` on every call.
    """
    plan_rate_limiter.reset()
    assert plan_rate_limiter.max_requests == 10
    assert plan_rate_limiter.window_seconds == 60

    mock_obs = NormalizedAirObservation(
        city="Delhi NCR",
        source_type="ground_station",
        data_provider="WAQI",
        observed_at=datetime.now(timezone.utc),
        fetched_at=datetime.now(timezone.utc),
        data_status="live",
        confidence_score="high",
        index_type="provider_index",
        index_value=120,
        index_category="Moderate",
        methodology_disclosure="Test",
    )
    mock_profile = HouseholdProfile(city="delhi", persona="general")
    mock_safety = safety_engine.evaluate(mock_obs, mock_profile)
    mock_plan = DailyPlanResponse(
        plan_id="plan_test",
        generated_at=datetime.now(timezone.utc),
        ai_provider_used="deterministic_fallback",
        is_fallback=True,
        data_provenance=mock_obs,
        household_profile=mock_profile,
        safety_guidance=mock_safety,
        morning=[],
        afternoon=[],
        evening=[],
        indoor_air_suggestions=["Exhaust fan."],
        sustainable_alternatives=["Metro."],
        disclaimer="Advisory only.",
    )

    client = TestClient(app)
    try:
        with patch("app.api.endpoints.plan.data_manager.get_air_quality", new=AsyncMock(return_value=mock_obs)), \
             patch("app.api.endpoints.plan.air_window_service.calculate_best_window", new=AsyncMock(side_effect=RuntimeError("skip"))), \
             patch("app.api.endpoints.plan.ai_manager.generate_plan", new=AsyncMock(return_value=mock_plan)):

            for i in range(10):
                res = client.post(
                    "/api/v1/plan/generate",
                    json={"city": "delhi", "profile": {"city": "delhi", "profile_id": f"spoof_{i}"}},
                )
                assert res.status_code == 200

            res_11 = client.post(
                "/api/v1/plan/generate",
                json={"city": "delhi", "profile": {"city": "delhi", "profile_id": "spoof_11"}},
            )
            assert res_11.status_code == 429
            assert int(res_11.headers["Retry-After"]) >= 1
            assert "Rate limit exceeded" in res_11.json()["detail"]["error"]
    finally:
        plan_rate_limiter.reset()


def test_rate_limiter_ignores_spoofed_forwarded_headers_when_untrusted():
    limiter = InMemorySlidingWindowRateLimiter(max_requests=2, window_seconds=60, trust_proxy_headers=False)

    req_spoof_1 = _fake_request("198.51.100.5", {"x-forwarded-for": "1.1.1.1", "true-client-ip": "2.2.2.2"})
    req_spoof_2 = _fake_request("198.51.100.5", {"x-forwarded-for": "3.3.3.3", "true-client-ip": "4.4.4.4"})

    ip1 = limiter.extract_client_ip(req_spoof_1)
    ip2 = limiter.extract_client_ip(req_spoof_2)
    assert ip1 == "198.51.100.5"
    assert ip2 == "198.51.100.5"


def test_rate_limiter_trusted_proxy_headers_and_malformed_validation():
    limiter = InMemorySlidingWindowRateLimiter(max_requests=2, window_seconds=60, trust_proxy_headers=True)

    # Render True-Client-IP preferred
    req_render = _fake_request("10.0.0.1", {"true-client-ip": "203.0.113.42", "x-forwarded-for": "9.9.9.9, 10.0.0.1"})
    assert limiter.extract_client_ip(req_render) == "203.0.113.42"

    # Fallback to valid leftmost X-Forwarded-For if True-Client-IP absent
    req_xff = _fake_request("10.0.0.1", {"x-forwarded-for": "2001:db8::1, 10.0.0.1"})
    assert limiter.extract_client_ip(req_xff) == "2001:db8::1"

    # Malformed forwarding headers rejected safely -> falls back to socket peer
    req_bad = _fake_request("10.0.0.9", {"true-client-ip": "not-an-ip", "x-forwarded-for": "bad;header"})
    assert limiter.extract_client_ip(req_bad) == "10.0.0.9"

    # Missing client address fallback
    req_missing = _fake_request(None, {})
    assert limiter.extract_client_ip(req_missing) == "unknown_peer"


def test_rate_limiter_trusted_proxy_cidrs():
    cidrs = parse_trusted_proxy_cidrs("10.0.0.0/8, invalid-cidr")
    assert len(cidrs) == 1
    with patch("app.core.rate_limiter.settings.TRUSTED_PROXY_CIDRS", cidrs):
        limiter = InMemorySlidingWindowRateLimiter(trust_proxy_headers=False)
        assert limiter.extract_client_ip(_fake_request("10.1.2.3", {"true-client-ip": "198.51.100.77"})) == "198.51.100.77"
        assert limiter.extract_client_ip(_fake_request("203.0.113.99", {"true-client-ip": "198.51.100.77"})) == "203.0.113.99"


def test_rate_limiter_expired_cleanup_bounded_keys_and_thread_safety():
    limiter = InMemorySlidingWindowRateLimiter(max_requests=5, window_seconds=0.05, max_tracked_keys=10)
    for i in range(15):
        limiter.check_and_record(f"192.0.2.{i}")
    assert limiter.tracked_key_count() <= 10

    time.sleep(0.08)
    # Next request triggers expired pruning and succeeds cleanly
    allowed, _ = limiter.check_and_record("192.0.2.200")
    assert allowed is True
    assert limiter.tracked_key_count() <= 2

    # Concurrent stress check
    concurrent_limiter = InMemorySlidingWindowRateLimiter(max_requests=10, window_seconds=60)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: concurrent_limiter.check_and_record("198.51.100.1"), range(25)))
    allowed_count = sum(1 for ok, _ in results if ok)
    rejected_count = sum(1 for ok, _ in results if not ok)
    assert allowed_count == 10
    assert rejected_count == 15
