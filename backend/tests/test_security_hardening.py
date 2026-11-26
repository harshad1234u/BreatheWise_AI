from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.core.config import parse_allowed_origins
from app.core.rate_limiter import InMemorySlidingWindowRateLimiter
from app.main import app
from app.api.endpoints.plan import plan_rate_limiter
from app.schemas.air_quality import NormalizedAirObservation
from app.schemas.plan import DailyPlanResponse, HouseholdProfile
from app.services.safety_engine import safety_engine


def test_cors_config_rejects_wildcard_and_handles_empty_fail_closed():
    """Verify parse_allowed_origins never allows '*' and returns [] when empty."""
    assert parse_allowed_origins("*") == []
    assert parse_allowed_origins("https://breathewiseai-frontend.vercel.app, *") == [
        "https://breathewiseai-frontend.vercel.app"
    ]
    assert parse_allowed_origins("   ") == []
    assert parse_allowed_origins("https://example.com/") == ["https://example.com"]


def test_rate_limiter_allows_normal_traffic_and_returns_429_when_exceeded():
    """
    Verify POST /api/v1/plan/generate permits normal guest requests and returns HTTP 429
    with Retry-After when the per-IP sliding window limit is exceeded, ignoring spoofed profile_id.
    """
    original_max = plan_rate_limiter.max_requests
    plan_rate_limiter.max_requests = 2
    plan_rate_limiter.reset()

    mock_obs = NormalizedAirObservation(
        city="Delhi NCR",
        source_type="ground_station",
        data_provider="WAQI (Official CPCB Ground Feed)",
        observed_at=datetime.now(timezone.utc),
        fetched_at=datetime.now(timezone.utc),
        data_status="live",
        confidence_score="high",
        index_type="provider_index",
        index_value=120,
        index_category="Moderate",
        methodology_disclosure="Test observation",
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
        indoor_air_suggestions=["Run exhaust fan while cooking."],
        sustainable_alternatives=["Use closed Metro transit."],
        disclaimer="Advisory only.",
    )

    client = TestClient(app)
    try:
        with patch("app.api.endpoints.plan.data_manager.get_air_quality", new=AsyncMock(return_value=mock_obs)), \
             patch("app.api.endpoints.plan.air_window_service.calculate_best_window", new=AsyncMock(side_effect=RuntimeError("skip"))), \
             patch("app.api.endpoints.plan.ai_manager.generate_plan", new=AsyncMock(return_value=mock_plan)):

            # Request 1 & 2 succeed (even with changing profile_id)
            r1 = client.post("/api/v1/plan/generate", json={"city": "delhi", "profile": {"city": "delhi", "profile_id": "guest_a"}})
            r2 = client.post("/api/v1/plan/generate", json={"city": "delhi", "profile": {"city": "delhi", "profile_id": "guest_b"}})
            assert r1.status_code == 200
            assert r2.status_code == 200

            # Request 3 from same IP (despite new spoofed profile_id) must be rejected with HTTP 429
            r3 = client.post("/api/v1/plan/generate", json={"city": "delhi", "profile": {"city": "delhi", "profile_id": "guest_c"}})
            assert r3.status_code == 429
            assert "Retry-After" in r3.headers
            assert int(r3.headers["Retry-After"]) >= 1
            assert "Rate limit exceeded" in r3.json()["detail"]["error"]
    finally:
        plan_rate_limiter.max_requests = original_max
        plan_rate_limiter.reset()


def test_rate_limiter_unit_window():
    limiter = InMemorySlidingWindowRateLimiter(max_requests=2, window_seconds=60)
    assert limiter.check_and_record("1.2.3.4") == (True, 0)
    assert limiter.check_and_record("1.2.3.4") == (True, 0)
    allowed, retry = limiter.check_and_record("1.2.3.4")
    assert allowed is False
    assert retry >= 1
    # Separate IP still allowed
    assert limiter.check_and_record("5.6.7.8") == (True, 0)
