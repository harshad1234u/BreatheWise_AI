from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api.endpoints.plan import plan_rate_limiter
from app.schemas.air_quality import NormalizedAirObservation, PollutantConcentration
from app.schemas.air_window import AirWindowResponse, BestAirWindowPeriod


@pytest.mark.asyncio
async def test_generate_plan_endpoint_offline_integration():
    """
    Offline API integration test for POST /api/v1/plan/generate.
    Mocks environmental telemetry, Best Air Window, and AI providers so default pytest runs 100% offline.
    """
    plan_rate_limiter.reset()
    now = datetime.now(timezone.utc)

    mock_obs = NormalizedAirObservation(
        city="Delhi NCR",
        locality_or_station="Anand Vihar, Delhi",
        source_type="ground_station",
        data_provider="WAQI (Official CPCB Ground Feed)",
        observed_at=now,
        fetched_at=now,
        data_status="live",
        confidence_score="high",
        index_type="provider_index",
        index_value=240,
        index_category="Poor",
        methodology_disclosure="Provider Index (240, US-EPA AQI scale) reported by WAQI.",
        pm25=PollutantConcentration(value=240.0, unit="US-EPA Sub-Index", sub_index=None),
    )
    mock_aw = AirWindowResponse(
        city="Delhi NCR",
        activity="general_outdoor",
        duration_hours=1,
        generated_at=now,
        status="available",
        best_window=BestAirWindowPeriod(
            start_time="15:00",
            end_time="16:00",
            duration_hours=1,
            average_comparative_score=145.0,
            score_label="Lowest Forecast Pollution Period",
            dominant_pollutant="pm25",
            strenuous_outdoor_allowed=False,
            activity_suitability="Moderate outdoor movement only.",
        ),
    )

    transport = ASGITransport(app=app)
    try:
        with patch("app.api.endpoints.plan.data_manager.get_air_quality", new=AsyncMock(return_value=mock_obs)), \
             patch("app.api.endpoints.plan.air_window_service.calculate_best_window", new=AsyncMock(return_value=mock_aw)), \
             patch("app.services.ai.groq_provider.GroqProvider.generate_plan_json", new=AsyncMock(return_value=None)), \
             patch("app.services.ai.gemini_provider.GeminiProvider.generate_plan_json", new=AsyncMock(return_value=None)):

            async with AsyncClient(transport=transport, base_url="http://test") as client:
                payload = {
                    "city": "delhi",
                    "profile": {
                        "display_name": "Test Delhi Family",
                        "city": "delhi",
                        "persona": "parent",
                        "age_groups": ["child", "adult"],
                        "has_respiratory_sensitivity": True,
                        "commute_mode": "two_wheeler",
                        "has_air_purifier": True,
                        "kitchen_ventilation_type": "exhaust_fan",
                    },
                }
                response = await client.post("/api/v1/plan/generate", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "plan_id" in data
        assert data["ai_provider_used"] == "deterministic_fallback"
        assert data["is_fallback"] is True
        assert "morning" in data and len(data["morning"]) >= 1
        assert "afternoon" in data and len(data["afternoon"]) >= 1
        assert "evening" in data and len(data["evening"]) >= 1
        assert "indoor_air_suggestions" in data
        assert "sustainable_alternatives" in data
        assert "safety_guidance" in data
        assert data["data_provenance"]["city"] == "Delhi NCR"
    finally:
        plan_rate_limiter.reset()
