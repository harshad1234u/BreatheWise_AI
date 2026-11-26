import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from app.services.air_quality.data_manager import AirQualityDataManager, SUPPORTED_CITIES
from app.services.air_quality.open_meteo_provider import OpenMeteoProvider


@pytest.mark.asyncio
async def test_supported_cities_list():
    manager = AirQualityDataManager()
    cities = manager.get_supported_cities()
    assert len(cities) >= 6
    city_ids = [c.id for c in cities]
    assert "delhi" in city_ids
    assert "mumbai" in city_ids
    assert "bengaluru" in city_ids


@pytest.mark.asyncio
async def test_unsupported_city_returns_unavailable():
    manager = AirQualityDataManager()
    obs = await manager.get_air_quality("atlantis_city")
    assert obs.source_type == "unavailable"
    assert obs.data_status == "unavailable"
    assert obs.index_category == "Unavailable"
    assert obs.index_value is None


@pytest.mark.asyncio
async def test_open_meteo_provider_offline_mocked_fetch():
    provider = OpenMeteoProvider()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "current": {
            "pm2_5": 45.0,
            "pm10": 80.0,
            "nitrogen_dioxide": 30.0,
            "sulphur_dioxide": 8.0,
            "ozone": 40.0,
            "carbon_monoxide": 900.0,
        }
    }

    with patch("app.services.air_quality.open_meteo_provider.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        obs = await provider.get_air_quality("Delhi NCR", 28.6139, 77.2090)

    assert obs is not None
    assert obs.source_type == "atmospheric_model"
    assert "Open-Meteo" in obs.data_provider
    assert obs.pm25 is not None and obs.pm25.value == 45.0
    assert obs.co is not None and obs.co.value == 0.9
    assert obs.index_type == "atmospheric_model_estimate"
    assert obs.index_category in ["Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"]


@pytest.mark.asyncio
async def test_open_meteo_provider_handles_timeout_and_bad_json():
    provider = OpenMeteoProvider()
    with patch("app.services.air_quality.open_meteo_provider.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.TimeoutException("Timed out")
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        assert await provider.get_air_quality("Delhi NCR", 28.6139, 77.2090) is None

    bad_resp = MagicMock()
    bad_resp.status_code = 500
    with patch("app.services.air_quality.open_meteo_provider.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = bad_resp
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        assert await provider.get_air_quality("Delhi NCR", 28.6139, 77.2090) is None


@pytest.mark.asyncio
async def test_data_manager_fallback_and_caching_offline():
    manager = AirQualityDataManager()
    now = datetime.now(timezone.utc)

    from app.schemas.air_quality import NormalizedAirObservation, PollutantConcentration

    model_obs = NormalizedAirObservation(
        city="Delhi NCR",
        locality_or_station="Delhi NCR Regional Atmospheric Grid",
        source_type="atmospheric_model",
        data_provider="Open-Meteo (CAMS Regional Model)",
        observed_at=now,
        fetched_at=now,
        data_status="live",
        confidence_score="moderate",
        index_type="atmospheric_model_estimate",
        index_value=140,
        index_category="Moderate",
        methodology_disclosure="Model estimate",
        pm25=PollutantConcentration(value=72.0, unit="µg/m³", sub_index=140.0),
    )

    manager.waqi_provider.get_air_quality = AsyncMock(return_value=None)
    manager.openaq_provider.get_air_quality = AsyncMock(return_value=None)
    manager.open_meteo_provider.get_air_quality = AsyncMock(return_value=model_obs)

    obs1 = await manager.get_air_quality("delhi")
    assert obs1.source_type == "atmospheric_model"
    assert obs1.index_value == 140
    assert manager.open_meteo_provider.get_air_quality.call_count == 1

    # Immediate second call should hit in-memory cache without re-querying providers
    obs2 = await manager.get_air_quality("delhi")
    assert obs2.fetched_at == obs1.fetched_at
    assert manager.open_meteo_provider.get_air_quality.call_count == 1


@pytest.mark.asyncio
async def test_data_manager_returns_unavailable_when_all_providers_fail():
    manager = AirQualityDataManager()
    manager.waqi_provider.get_air_quality = AsyncMock(return_value=None)
    manager.openaq_provider.get_air_quality = AsyncMock(return_value=None)
    manager.open_meteo_provider.get_air_quality = AsyncMock(return_value=None)

    obs = await manager.get_air_quality("mumbai")
    assert obs.source_type == "unavailable"
    assert obs.data_status == "unavailable"
    assert obs.index_category == "Unavailable"
    assert obs.index_value is None
