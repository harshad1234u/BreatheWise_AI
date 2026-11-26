import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
import httpx

from app.main import app
from app.services.air_quality.air_window import AirWindowService, air_window_service

client = TestClient(app)


def _make_hourly_payload(include_wind: bool = True, include_pm25: bool = True, include_o3: bool = True):
    times = [f"2026-11-26T{h:02d}:00" for h in range(24)]
    aq_json = {
        "hourly": {
            "time": times,
            "pm2_5": ([120.0 if h < 8 else (35.0 if 13 <= h <= 16 else 95.0) for h in range(24)] if include_pm25 else [None] * 24),
            "pm10": [110.0 if h < 8 else (60.0 if 13 <= h <= 16 else 105.0) for h in range(24)],
            "ozone": ([25.0 if h < 12 else 55.0 for h in range(24)] if include_o3 else [None] * 24),
            "nitrogen_dioxide": [40.0] * 24,
            "sulphur_dioxide": [12.0] * 24,
            "carbon_monoxide": [900.0] * 24,
        }
    }
    weather_json = {
        "hourly": {
            "time": times,
            "wind_speed_10m": [11.5] * 24 if include_wind else [],
        }
    }
    return aq_json, weather_json


def test_air_window_endpoint_valid_city_offline():
    """Verify GET /api/v1/air-window deterministically with mocked Open-Meteo payloads."""
    air_window_service._forecast_cache.clear()
    aq_json, weather_json = _make_hourly_payload()

    aq_resp = MagicMock()
    aq_resp.status_code = 200
    aq_resp.json.return_value = aq_json

    w_resp = MagicMock()
    w_resp.status_code = 200
    w_resp.json.return_value = weather_json

    with patch("app.services.air_quality.air_window.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.side_effect = [aq_resp, w_resp]
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        response = client.get("/api/v1/air-window?city=delhi&activity=running")

    assert response.status_code == 200
    data = response.json()

    assert data["city"] == "Delhi NCR"
    assert data["status"] == "available"
    assert "Open-Meteo" in data["data_provider"]
    assert "internal comparative indicator" in data["disclaimer"]
    assert data["best_window"] is not None
    assert data["peak_pollution_window"] is not None
    assert len(data["hourly_forecast"]) == 24
    assert data["best_window"]["score_label"] in [
        "Lowest Forecast Pollution Period",
        "Comparatively Better Window",
    ]
    assert data["peak_pollution_window"]["score_label"] == "Higher Pollution Period"

    for window in [data["best_window"], data["peak_pollution_window"]] + data.get("alternative_windows", []):
        assert "safe" not in window["score_label"].lower()
        assert "healthy" not in window["score_label"].lower()
        assert "pollution-free" not in window["score_label"].lower()

    air_window_service._forecast_cache.clear()


def test_air_window_endpoint_empty_city_returns_400():
    """Verify empty or blank city returns HTTP 400 validation error."""
    response = client.get("/api/v1/air-window?city=%20%20")
    assert response.status_code == 400
    assert "cannot be empty" in response.json()["detail"]


def test_air_window_endpoint_unsupported_city():
    """Verify unsupported city returns status='unavailable' with descriptive disclaimer."""
    response = client.get("/api/v1/air-window?city=atlantis_city")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unavailable"
    assert data["data_provenance_type"] == "unavailable"
    assert "not supported" in data["disclaimer"].lower()


@pytest.mark.asyncio
async def test_air_window_missing_wind_and_pm25_graceful_fallback():
    """Verify missing PM2.5, missing O3, or failed weather fetch does not crash scoring."""
    svc = AirWindowService()
    aq_json, _ = _make_hourly_payload(include_wind=False, include_pm25=False, include_o3=False)

    aq_resp = MagicMock()
    aq_resp.status_code = 200
    aq_resp.json.return_value = aq_json

    with patch("app.services.air_quality.air_window.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.side_effect = [aq_resp, httpx.TimeoutException("Weather timeout")]
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        res = await svc.calculate_best_window("delhi", activity="walking")

    assert res.status == "available"
    assert res.best_window is not None
    assert res.hourly_forecast[0].pm25 is None
    assert res.hourly_forecast[0].o3 is None
    assert res.hourly_forecast[0].wind_speed is None


@pytest.mark.asyncio
async def test_air_window_provider_timeout_returns_insufficient_data():
    """Verify Open-Meteo AQ HTTP failure or timeout returns insufficient_data cleanly."""
    svc = AirWindowService()
    with patch("app.services.air_quality.air_window.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.TimeoutException("AQ timeout")
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        res = await svc.calculate_best_window("delhi", activity="running")

    assert res.status == "insufficient_data"
    assert res.best_window is None


def test_comparative_score_formula_and_dominant_pollutant():
    w = air_window_service._build_window_period(
        {
            "start_time": "14:00",
            "end_time": "15:00",
            "start_iso": "2026-11-24T14:00",
            "end_iso": "2026-11-24T15:00",
            "avg_score": 231.2,
            "dominant_pollutant": "o3",
        },
        duration=1,
        label="Lowest Forecast Pollution Period",
        activity="running",
        is_vulnerable=False,
    )

    assert w.average_comparative_score == 231.2
    assert w.dominant_pollutant == "o3"
    assert w.score_label == "Lowest Forecast Pollution Period"
    assert w.strenuous_outdoor_allowed is False


def test_severe_band_interlock_disallows_strenuous_outdoor_exercise():
    w = air_window_service._build_window_period(
        {
            "start_time": "15:00",
            "end_time": "16:00",
            "start_iso": "2026-11-24T15:00",
            "end_iso": "2026-11-24T16:00",
            "avg_score": 380.0,
            "dominant_pollutant": "pm25",
        },
        duration=1,
        label="Lowest Forecast Pollution Period",
        activity="running",
        is_vulnerable=False,
    )

    assert w.strenuous_outdoor_allowed is False
    assert "Very Poor or Severe" in w.activity_suitability
    assert "NOT recommended" in w.activity_suitability


def test_vulnerable_cohort_restraints():
    w = air_window_service._build_window_period(
        {
            "start_time": "07:00",
            "end_time": "08:00",
            "start_iso": "2026-11-24T07:00",
            "end_iso": "2026-11-24T08:00",
            "avg_score": 140.0,
            "dominant_pollutant": "pm10",
        },
        duration=1,
        label="Lowest Forecast Pollution Period",
        activity="walking",
        is_vulnerable=True,
    )

    assert w.strenuous_outdoor_allowed is False
    assert any("Sensitive individuals" in note for note in w.precautionary_notes)


@pytest.mark.asyncio
async def test_planner_incorporates_best_air_window():
    from app.services.ai.validator import generate_deterministic_fallback_plan
    from app.services.safety_engine import safety_engine
    from app.schemas.air_quality import NormalizedAirObservation
    from app.schemas.plan import HouseholdProfile

    obs = NormalizedAirObservation(
        city="Delhi NCR",
        source_type="ground_station",
        data_provider="WAQI (CPCB Feed)",
        observed_at=datetime.now(timezone.utc),
        fetched_at=datetime.now(timezone.utc),
        data_status="live",
        confidence_score="high",
        index_type="indicative_particulate_subindex",
        index_value=175,
        index_category="Moderate",
        methodology_disclosure="Test",
    )
    profile = HouseholdProfile(city="delhi", persona="general")
    safety = safety_engine.evaluate(obs, profile)

    window_ctx = {
        "start_time": "16:00",
        "end_time": "17:00",
        "average_comparative_score": 90.0,
        "score_label": "Lowest Forecast Pollution Period",
    }

    plan_dict = generate_deterministic_fallback_plan(obs, profile, safety, air_window_context=window_ctx)
    assert "16:00 - 17:00" in plan_dict["afternoon"][0]["explanation"]
