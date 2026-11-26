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

    with patch("app.services.air_quality.air_window.httpx.AsyncClient") as mock_client_cls, \
         patch("app.services.air_quality.air_window._utc_now", return_value=datetime(2026, 11, 25, 18, 30, tzinfo=timezone.utc)):
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

    with patch("app.services.air_quality.air_window.httpx.AsyncClient") as mock_client_cls, \
         patch("app.services.air_quality.air_window._utc_now", return_value=datetime(2026, 11, 25, 18, 30, tzinfo=timezone.utc)):
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


def _make_48h_forecast_payload():
    """Creates a 48h (2-day) Open-Meteo IST payload starting 2026-11-26T00:00."""
    from datetime import timedelta

    base = datetime(2026, 11, 26, 0, 0)
    times = [(base + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(48)]
    # Day 1 past midday/early morning artificially low/high, Day 1 late night + Day 2 vary cleanly
    pm25 = []
    for i in range(48):
        hour = i % 24
        if i < 18:
            # Earlier on Day 1: lowest at 03:00 (15.0) and highest spike at 08:00 (280.0)
            if hour == 3:
                pm25.append(15.0)
            elif hour == 8:
                pm25.append(280.0)
            else:
                pm25.append(90.0)
        else:
            # Upcoming night/Day 2: lowest at i=26 (Day 2 02:00, 35.0), highest at i=32 (Day 2 08:00, 175.0)
            if i == 26:
                pm25.append(35.0)
            elif i == 32:
                pm25.append(175.0)
            else:
                pm25.append(85.0)

    aq_json = {
        "hourly": {
            "time": times,
            "pm2_5": pm25,
            "pm10": [50.0] * 48,
            "ozone": [30.0] * 48,
            "nitrogen_dioxide": [25.0] * 48,
            "sulphur_dioxide": [8.0] * 48,
            "carbon_monoxide": [600.0] * 48,
        }
    }
    weather_json = {
        "hourly": {
            "time": times,
            "wind_speed_10m": [10.0] * 48,
        }
    }
    return aq_json, weather_json


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "ist_hour,ist_min,min_allowed_iso",
    [
        (6, 30, "2026-11-26T06:00"),
        (12, 30, "2026-11-26T12:00"),
        (21, 30, "2026-11-26T21:00"),
    ],
)
async def test_air_window_only_evaluates_upcoming_hours(ist_hour, ist_min, min_allowed_iso):
    """
    F-08 reproduction: at 06:30, 12:30, and 21:30 IST (including crossing midnight),
    neither best_window nor peak_pollution_window may come from past hours of that day.
    """
    from datetime import timedelta

    ist = timezone(timedelta(hours=5, minutes=30))
    mock_now_utc = datetime(2026, 11, 26, ist_hour, ist_min, tzinfo=ist).astimezone(timezone.utc)

    svc = AirWindowService()
    aq_json, weather_json = _make_48h_forecast_payload()
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

        res = await svc.calculate_best_window("delhi", activity="walking", now_utc=mock_now_utc)

    assert res.status == "available"
    assert res.best_window is not None
    assert res.peak_pollution_window is not None
    assert res.best_window.start_iso is not None
    assert res.peak_pollution_window.start_iso is not None
    assert res.best_window.start_iso >= min_allowed_iso
    assert res.peak_pollution_window.start_iso >= min_allowed_iso
    if (ist_hour, ist_min) == (21, 30):
        # Crosses midnight cleanly onto Day 2 upcoming hours
        assert res.best_window.start_iso == "2026-11-27T02:00"
        assert res.peak_pollution_window.start_iso == "2026-11-27T08:00"


@pytest.mark.asyncio
async def test_air_window_insufficient_future_hours_and_tz_aware():
    """F-08: When all forecast hours are in the past (or < duration), return insufficient_data honestly."""
    from datetime import timedelta

    ist = timezone(timedelta(hours=5, minutes=30))
    mock_now_utc = datetime(2026, 11, 26, 23, 30, tzinfo=ist).astimezone(timezone.utc)

    svc = AirWindowService()
    # Single-day payload with tz-aware +05:30 strings only up to 22:00 (all in past relative to 23:30)
    times = [f"2026-11-26T{h:02d}:00+05:30" for h in range(23)]
    aq_json = {
        "hourly": {
            "time": times,
            "pm2_5": [50.0] * 23,
            "pm10": [80.0] * 23,
            "ozone": [30.0] * 23,
            "nitrogen_dioxide": [20.0] * 23,
            "sulphur_dioxide": [5.0] * 23,
            "carbon_monoxide": [500.0] * 23,
        }
    }
    aq_resp = MagicMock()
    aq_resp.status_code = 200
    aq_resp.json.return_value = aq_json
    w_resp = MagicMock()
    w_resp.status_code = 200
    w_resp.json.return_value = {"hourly": {"time": times, "wind_speed_10m": [8.0] * 23}}

    with patch("app.services.air_quality.air_window.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.side_effect = [aq_resp, w_resp]
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        res = await svc.calculate_best_window("delhi", activity="running", now_utc=mock_now_utc)

    assert res.status == "insufficient_data"
    assert res.best_window is None
    assert res.peak_pollution_window is None


@pytest.mark.asyncio
async def test_air_window_bounded_lru_coalescing_and_failure_cleanup():
    """F-07 reproduction: AirWindowService forecast cache must be bounded LRU and coalesce concurrent requests."""
    import asyncio
    from datetime import timedelta

    ist = timezone(timedelta(hours=5, minutes=30))
    mock_now_utc = datetime(2026, 11, 26, 6, 30, tzinfo=ist).astimezone(timezone.utc)
    svc = AirWindowService(max_cache_entries=2, cache_ttl_seconds=60)
    aq_json, weather_json = _make_48h_forecast_payload()

    call_count = 0

    async def delayed_get(url, params=None, **kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.02)
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = aq_json if "air-quality" in str(url) else weather_json
        return resp

    with patch("app.services.air_quality.air_window.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.side_effect = delayed_get
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        # 4 simultaneous identical-city requests share 1 pair of AQ + Weather calls (call_count == 2)
        results = await asyncio.gather(
            *[svc.calculate_best_window("delhi", activity="running", now_utc=mock_now_utc) for _ in range(4)]
        )
        assert all(r.status == "available" for r in results)
        assert call_count == 2
        assert len(svc._in_flight) == 0

        # Bounded LRU check across 3 distinct cities
        await svc.calculate_best_window("mumbai", now_utc=mock_now_utc)
        await svc.calculate_best_window("delhi", now_utc=mock_now_utc)  # refresh delhi
        await svc.calculate_best_window("bengaluru", now_utc=mock_now_utc)
        assert len(svc._forecast_cache) <= 2
        assert "delhi" in svc._forecast_cache
        assert "bengaluru" in svc._forecast_cache
        assert "mumbai" not in svc._forecast_cache

    # Failure cleanup leaves _in_flight empty for next retry
    with patch("app.services.air_quality.air_window.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.TimeoutException("timeout")
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        fail_res = await svc.calculate_best_window("jaipur", now_utc=mock_now_utc)
    assert fail_res.status == "insufficient_data"
    assert len(svc._in_flight) == 0
