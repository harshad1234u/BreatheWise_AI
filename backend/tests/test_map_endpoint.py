import asyncio
import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import app
from app.schemas.air_quality import NormalizedAirObservation, PollutantConcentration
from app.schemas.map import StationMapPoint
from app.services.air_quality.map_service import MapService, map_service


client = TestClient(app)


def _mock_waqi_bounds_and_feed():
    now_iso = datetime.now(timezone.utc).isoformat()
    bounds_resp = MagicMock()
    bounds_resp.status_code = 200
    bounds_resp.json.return_value = {
        "status": "ok",
        "data": [
            {"uid": 101, "lat": 28.61, "lon": 77.23, "station": {"name": "Station A"}},
            {"uid": 102, "lat": 28.65, "lon": 77.20, "station": {"name": "Station B"}},
        ],
    }

    def make_feed(uid, name, lat, lng):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "status": "ok",
            "data": {
                "aqi": 96,
                "city": {"name": name, "geo": [lat, lng]},
                "iaqi": {"pm25": {"v": 96}, "pm10": {"v": 65}, "no2": {"v": 15.2}},
                "time": {"iso": now_iso},
            },
        }
        return resp

    return bounds_resp, [
        make_feed(101, "Station A, Delhi", 28.61, 77.23),
        make_feed(102, "Station B, Delhi", 28.65, 77.20),
    ]


def test_map_endpoint_valid_pollutant_delhi_offline():
    """Verify GET /api/v1/map/pollutants returns valid schema offline via mocked WAQI feeds."""
    map_service.clear_cache()
    orig_token = map_service.waqi_token
    map_service.waqi_token = "test_token"

    bounds_resp, feed_resps = _mock_waqi_bounds_and_feed()
    try:
        with patch("app.services.air_quality.map_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = [bounds_resp, *feed_resps]
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            response = client.get("/api/v1/map/pollutants?city=delhi&pollutant=pm25")

        assert response.status_code == 200
        data = response.json()
        assert data["selected_city"] == "Delhi NCR"
        assert data["selected_pollutant"] == "pm25"
        assert data["unit"] == "µg/m³"
        assert data["summary"]["total_stations"] == 2
        assert data["summary"]["reporting_stations"] == 2
        assert data["summary"]["measurement_mode"] == "provider_index"
        assert data["summary"]["avg_provider_index"] == 96.0
        assert data["summary"]["avg_concentration"] is None
        assert data["stations"][0]["source_type"] == "ground_station"
        assert data["stations"][0]["measurement_type"] == "provider_index"
        assert data["stations"][0]["provider_index"] == 96.0
        assert data["stations"][0]["concentration"] is None
        assert data["stations"][0]["cpcb_sub_index"] is None
    finally:
        map_service.waqi_token = orig_token
        map_service.clear_cache()


def test_map_endpoint_invalid_pollutant_returns_400():
    """Verify invalid pollutant query parameter returns HTTP 400 validation error."""
    response = client.get("/api/v1/map/pollutants?city=delhi&pollutant=invalid_unknown")
    assert response.status_code == 400
    data = response.json()
    assert "Invalid pollutant parameter" in data["detail"]
    assert "pm25" in data["detail"]


def test_map_endpoint_unsupported_city():
    """Verify unsupported city returns 0 stations and clear informative provenance note."""
    response = client.get("/api/v1/map/pollutants?city=atlantis&pollutant=pm25")
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["total_stations"] == 0
    assert data["summary"]["reporting_stations"] == 0
    assert "not supported" in data["summary"]["data_provenance_note"].lower()


@pytest.mark.asyncio
async def test_map_cache_reuses_raw_city_snapshot_across_pollutant_switches():
    """
    Phase 1 Cache Proof:
    1. First request (pm25) fetches bounds + stations once.
    2. Subsequent requests for pm10 / no2 reuse the cached city snapshot with 0 new HTTP calls.
    """
    svc = MapService(cache_ttl_seconds=600)
    svc.waqi_token = "test_token"
    bounds_resp, feed_resps = _mock_waqi_bounds_and_feed()

    with patch("app.services.air_quality.map_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.side_effect = [bounds_resp, *feed_resps]
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        res_pm25 = await svc.get_city_pollutant_map("delhi", "pm25")
        first_call_count = mock_client.get.call_count
        assert first_call_count == 3  # 1 bounds + 2 station feeds

        res_pm10 = await svc.get_city_pollutant_map("delhi", "pm10")
        res_no2 = await svc.get_city_pollutant_map("delhi", "no2")

        assert mock_client.get.call_count == first_call_count  # ZERO additional HTTP calls!
        assert res_pm25.selected_pollutant == "pm25"
        assert res_pm10.selected_pollutant == "pm10"
        assert res_no2.selected_pollutant == "no2"
        assert res_pm10.summary.total_stations == 2


@pytest.mark.asyncio
async def test_map_cache_expiration_triggers_fresh_fetch_and_city_isolation():
    """Verify expired cache entries trigger fresh fetches and separate cities never collide."""
    svc = MapService(cache_ttl_seconds=60)
    svc.waqi_token = "test_token"
    bounds_resp1, feeds1 = _mock_waqi_bounds_and_feed()
    bounds_resp2, feeds2 = _mock_waqi_bounds_and_feed()
    bounds_resp3, feeds3 = _mock_waqi_bounds_and_feed()

    with patch("app.services.air_quality.map_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.side_effect = [
            bounds_resp1, *feeds1,
            bounds_resp2, *feeds2,
            bounds_resp3, *feeds3,
        ]
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        await svc.get_city_pollutant_map("delhi", "pm25")
        assert mock_client.get.call_count == 3

        # Different city must NOT share delhi cache
        await svc.get_city_pollutant_map("mumbai", "pm25")
        assert mock_client.get.call_count == 6

        # Force expire delhi cache entry
        old_ts, snap = svc._city_cache["delhi"]
        svc._city_cache["delhi"] = (old_ts - timedelta(seconds=120), snap)

        await svc.get_city_pollutant_map("delhi", "pm10")
        assert mock_client.get.call_count == 9


@pytest.mark.asyncio
async def test_map_cache_coalesces_concurrent_requests_for_same_city():
    """Verify concurrent uncached requests for the same city trigger only ONE upstream fetch."""
    svc = MapService(cache_ttl_seconds=600)
    svc.waqi_token = "test_token"
    fetch_count = 0

    async def slow_snapshot(city_meta):
        nonlocal fetch_count
        fetch_count += 1
        await asyncio.sleep(0.05)
        return {
            "fetched_at": datetime.now(timezone.utc),
            "ground_stations": [],
            "model_observation": None,
        }

    svc._fetch_raw_city_snapshot = slow_snapshot

    results = await asyncio.gather(
        svc.get_city_pollutant_map("delhi", "pm25"),
        svc.get_city_pollutant_map("delhi", "pm10"),
        svc.get_city_pollutant_map("delhi", "no2"),
    )
    assert fetch_count == 1
    assert [r.selected_pollutant for r in results] == ["pm25", "pm10", "no2"]


@pytest.mark.asyncio
async def test_map_model_fallback_caches_per_city_and_computes_subindex():
    """When WAQI returns no stations, model fallback preserves raw µg/m³ & caches per city."""
    svc = MapService(cache_ttl_seconds=600)
    svc.waqi_token = ""  # Force Open-Meteo fallback
    now = datetime.now(timezone.utc)
    mock_obs = NormalizedAirObservation(
        city="Delhi NCR",
        source_type="atmospheric_model",
        data_provider="Open-Meteo CAMS",
        observed_at=now,
        fetched_at=now,
        data_status="live",
        confidence_score="moderate",
        index_type="atmospheric_model_estimate",
        index_value=120,
        index_category="Moderate",
        methodology_disclosure="Model estimate",
        pm25=PollutantConcentration(value=66.0, unit="µg/m³"),
        pm10=PollutantConcentration(value=120.0, unit="µg/m³"),
        nh3=None,
    )
    svc.open_meteo_provider.get_air_quality = AsyncMock(return_value=mock_obs)

    r_pm25 = await svc.get_city_pollutant_map("delhi", "pm25")
    r_pm10 = await svc.get_city_pollutant_map("delhi", "pm10")
    r_nh3 = await svc.get_city_pollutant_map("delhi", "nh3")

    assert svc.open_meteo_provider.get_air_quality.call_count == 1
    assert r_pm25.stations[0].concentration == 66.0
    assert r_pm25.stations[0].cpcb_sub_index is not None
    assert r_pm10.stations[0].concentration == 120.0
    assert r_nh3.stations[0].concentration is None
    assert r_nh3.stations[0].sub_index_category == "Unavailable"


@pytest.mark.asyncio
async def test_map_service_stale_reading_classification():
    now = datetime.now(timezone.utc)
    old_time = now.replace(year=now.year - 1)
    mock_point = StationMapPoint(
        station_id="test_stale_1",
        station_name="Historical Stale Station",
        latitude=28.6,
        longitude=77.2,
        concentration=None,
        cpcb_sub_index=None,
        sub_index_category="Unavailable",
        observed_at=old_time,
        data_provider="WAQI (Official CPCB Ground Feed)",
        source_type="ground_station",
        freshness_status="stale",
        quality_confidence="moderate",
    )
    assert mock_point.freshness_status == "stale"


@pytest.mark.asyncio
async def test_guwahati_repro_two_stations_and_mixed_availability():
    """
    Tests G & H: Reproduce Guwahati scenario (2 WAQI stations), partial pollutant availability
    across all 8 pollutants, and expired ground data triggering Open-Meteo model fallback.
    """
    svc = MapService(cache_ttl_seconds=600)
    svc.waqi_token = "test_token"
    now_iso = datetime.now(timezone.utc).isoformat()
    stale_iso = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()

    bounds_resp = MagicMock()
    bounds_resp.status_code = 200
    bounds_resp.json.return_value = {
        "status": "ok",
        "data": [
            {"uid": 501, "lat": 26.18, "lon": 91.74, "station": {"name": "Guwahati A"}},
            {"uid": 502, "lat": 26.15, "lon": 91.71, "station": {"name": "Guwahati B"}},
        ],
    }

    feed1 = MagicMock()
    feed1.status_code = 200
    feed1.json.return_value = {
        "status": "ok",
        "data": {
            "aqi": 50,
            "city": {"name": "Guwahati Station 1", "geo": [26.18, 91.74]},
            "iaqi": {"pm25": {"v": 50}, "pm10": {"v": 42}, "no2": {"v": 14}},
            "time": {"iso": stale_iso},
            "attributions": [{"name": "Pollution Control Board Assam"}],
        },
    }

    feed2 = MagicMock()
    feed2.status_code = 200
    feed2.json.return_value = {
        "status": "ok",
        "data": {
            "aqi": 72,
            "city": {"name": "Guwahati Station 2", "geo": [26.15, 91.71]},
            "iaqi": {"pm10": {"v": 60}},  # pm25 intentionally missing!
            "time": {"iso": now_iso},
            "attributions": [{"name": "WAQI"}],
        },
    }

    with patch("app.services.air_quality.map_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.side_effect = [bounds_resp, feed1, feed2]
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        # All 8 pollutants tested against cached snapshot
        r_pm25 = await svc.get_city_pollutant_map("guwahati", "pm25")
        assert r_pm25.summary.total_stations == 2
        assert r_pm25.summary.reporting_stations == 1
        assert r_pm25.summary.unavailable_stations == 1
        assert r_pm25.summary.stale_stations == 1
        assert r_pm25.summary.avg_provider_index == 50.0
        assert r_pm25.stations[0].provider_index == 50.0
        assert r_pm25.stations[0].freshness_status == "stale"
        assert r_pm25.stations[1].measurement_type == "unavailable"

        # pm10 reported by both stations -> avg (42 + 60)/2 = 51.0
        r_pm10 = await svc.get_city_pollutant_map("guwahati", "pm10")
        assert r_pm10.summary.reporting_stations == 2
        assert r_pm10.summary.avg_provider_index == 51.0

        for p in ["no2", "o3", "so2", "co", "nh3", "pb"]:
            rp = await svc.get_city_pollutant_map("guwahati", p)
            assert rp.selected_pollutant == p
            assert rp.summary.avg_concentration is None


@pytest.mark.asyncio
async def test_expired_ground_stations_trigger_model_fallback_on_map():
    """Verify PRD v1.2 >12h expired ground stations trigger Open-Meteo model fallback."""
    svc = MapService(cache_ttl_seconds=600)
    svc.waqi_token = "test_token"
    expired_iso = (datetime.now(timezone.utc) - timedelta(hours=15)).isoformat()
    now = datetime.now(timezone.utc)

    bounds_resp = MagicMock()
    bounds_resp.status_code = 200
    bounds_resp.json.return_value = {"status": "ok", "data": [{"uid": 777, "lat": 26.1, "lon": 91.7}]}
    feed_exp = MagicMock()
    feed_exp.status_code = 200
    feed_exp.json.return_value = {
        "status": "ok",
        "data": {"aqi": 80, "city": {"name": "Old Station", "geo": [26.1, 91.7]}, "iaqi": {"pm25": {"v": 80}}, "time": {"iso": expired_iso}},
    }

    svc.open_meteo_provider.get_air_quality = AsyncMock(
        return_value=NormalizedAirObservation(
            city="Guwahati",
            source_type="atmospheric_model",
            data_provider="Open-Meteo CAMS",
            observed_at=now,
            fetched_at=now,
            data_status="live",
            confidence_score="moderate",
            index_type="atmospheric_model_estimate",
            index_value=70,
            index_category="Satisfactory",
            methodology_disclosure="Model estimate",
            pm25=PollutantConcentration(value=42.0, unit="µg/m³"),
        )
    )

    with patch("app.services.air_quality.map_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.side_effect = [bounds_resp, feed_exp]
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        res = await svc.get_city_pollutant_map("guwahati", "pm25")

    assert res.summary.model_stations == 1
    assert res.summary.measurement_mode == "model_estimate"
    assert res.stations[-1].measurement_type == "model_estimate"
    assert res.stations[-1].concentration == 42.0
