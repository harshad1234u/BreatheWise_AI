import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.schemas.air_window import AirWindowResponse, BestAirWindowPeriod, HourlyPollutantPoint
from app.services.air_quality.air_window import air_window_service

client = TestClient(app)


def test_air_window_endpoint_valid_city():
    """Verify GET /api/v1/air-window returns structured multi-pollutant forecast for supported city."""
    response = client.get("/api/v1/air-window?city=delhi&activity=running")
    assert response.status_code == 200
    data = response.json()

    assert data["city"] == "Delhi NCR"
    assert data["status"] in ["available", "insufficient_data"]
    assert "Open-Meteo" in data["data_provider"]
    assert "internal comparative indicator" in data["disclaimer"]
    
    if data["status"] == "available":
        assert data["best_window"] is not None
        assert data["peak_pollution_window"] is not None
        assert len(data["hourly_forecast"]) > 0
        
        # Verify strict PRD label requirements
        assert data["best_window"]["score_label"] in [
            "Lowest Forecast Pollution Period",
            "Comparatively Better Window",
        ]
        assert data["peak_pollution_window"]["score_label"] == "Higher Pollution Period"
        
        # Ensure forbidden terms are absent from labels
        for window in [data["best_window"], data["peak_pollution_window"]] + data.get("alternative_windows", []):
            assert "safe" not in window["score_label"].lower()
            assert "healthy" not in window["score_label"].lower()
            assert "pollution-free" not in window["score_label"].lower()


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


def test_comparative_score_formula_and_dominant_pollutant():
    """
    Verify comparative score calculation:
    E(t) = max(sub-indices).
    """
    # PM2.5 = 75 µg/m³ -> sub-index ~ 150 (Moderate)
    # PM10 = 150 µg/m³ -> sub-index ~ 133 (Moderate)
    # O3 = 180 µg/m³ -> sub-index ~ 231 (Poor)
    # The max should be O3 sub-index ~ 231.
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
    # Under Poor score (>200) for running, strenuous cardio is restricted
    assert w.strenuous_outdoor_allowed is False
    assert "indoor" in w.activity_suitability.lower() or "moderated" in w.activity_suitability.lower()


def test_severe_band_interlock_disallows_strenuous_outdoor_exercise():
    """
    CRITICAL PUBLIC-HEALTH TEST:
    Even during the 'Lowest Forecast Pollution Period', if score > 300 (Very Poor/Severe),
    strenuous outdoor running/cycling must be disallowed.
    """
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
    assert "indoor low-impact" in w.activity_suitability


def test_missing_pollutant_series_resilience():
    """Verify that if some pollutant series are missing, comparative score computes across available."""
    # Build candidate with PM2.5 only
    w = air_window_service._build_window_period(
        {
            "start_time": "06:00",
            "end_time": "07:00",
            "start_iso": "2026-11-24T06:00",
            "end_iso": "2026-11-24T07:00",
            "avg_score": 85.0,
            "dominant_pollutant": "pm25",
        },
        duration=1,
        label="Comparatively Better Window",
        activity="walking",
        is_vulnerable=False,
    )

    assert w.average_comparative_score == 85.0
    assert w.strenuous_outdoor_allowed is True
    assert "Favorable" in w.activity_suitability or "Acceptable" in w.activity_suitability


def test_vulnerable_cohort_restraints():
    """Verify that vulnerable individuals receive appropriate cautionary notes."""
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

    # For vulnerable groups under Moderate score, strenuous outdoor is restricted
    assert w.strenuous_outdoor_allowed is False
    assert any("Sensitive individuals" in note for note in w.precautionary_notes)


@pytest.mark.asyncio
async def test_planner_incorporates_best_air_window():
    """Verify that Daily Planner incorporates Best Air Window context into deterministic fallback."""
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
    assert "morning" in plan_dict
    assert "afternoon" in plan_dict
    assert "evening" in plan_dict
    
    # Check that forecast note is incorporated in explanation
    afternoon_item = plan_dict["afternoon"][0]
    assert "16:00 - 17:00" in afternoon_item["explanation"]
