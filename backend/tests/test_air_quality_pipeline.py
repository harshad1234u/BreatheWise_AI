import pytest
from app.services.air_quality.data_manager import data_manager, SUPPORTED_CITIES
from app.services.air_quality.open_meteo_provider import OpenMeteoProvider


@pytest.mark.asyncio
async def test_supported_cities_list():
    cities = data_manager.get_supported_cities()
    assert len(cities) >= 4
    city_ids = [c.id for c in cities]
    assert "delhi" in city_ids
    assert "mumbai" in city_ids
    assert "bengaluru" in city_ids


@pytest.mark.asyncio
async def test_unsupported_city_returns_unavailable():
    obs = await data_manager.get_air_quality("atlantis_city")
    assert obs.source_type == "unavailable"
    assert obs.data_status == "unavailable"
    assert obs.index_category == "Unavailable"
    assert obs.index_value is None


@pytest.mark.asyncio
async def test_open_meteo_provider_live_fetch():
    provider = OpenMeteoProvider()
    # Query Delhi coordinates (28.6139, 77.2090)
    obs = await provider.get_air_quality(
        city="Delhi NCR",
        latitude=28.6139,
        longitude=77.2090
    )
    assert obs is not None
    assert obs.source_type == "atmospheric_model"
    assert "Open-Meteo" in obs.data_provider
    assert obs.pm25 is not None
    assert obs.pm25.value >= 0.0
    assert obs.index_type == "atmospheric_model_estimate"
    assert obs.index_category in ["Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"]


@pytest.mark.asyncio
async def test_data_manager_fallback_and_caching():
    # If no WAQI token is set, it falls back to Open-Meteo CAMS seamlessly
    obs1 = await data_manager.get_air_quality("delhi")
    assert obs1.source_type in ["ground_station", "atmospheric_model"]
    assert obs1.data_status in ["live", "stale"]
    assert obs1.index_value is not None

    # Immediate second call should hit in-memory cache
    obs2 = await data_manager.get_air_quality("delhi")
    assert obs2.fetched_at == obs1.fetched_at
