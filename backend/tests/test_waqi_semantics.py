import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.air_quality.waqi_provider import WAQIProvider
from app.services.air_quality.map_service import MapService


SAMPLE_WAQI_RESPONSE = {
    "status": "ok",
    "data": {
        "aqi": 96,
        "dominentpol": "pm25",
        "city": {
            "name": "Major Dhyan Chand National Stadium, Delhi, Delhi, India",
            "geo": [28.611281, 77.237738],
        },
        "iaqi": {
            "pm25": {"v": 96},
            "pm10": {"v": 65},
            "no2": {"v": 15.2},
            "so2": {"v": 1.3},
            "co": {"v": 10.9},
            "o3": {"v": 13.8},
            "t": {"v": 27.1},
        },
        "time": {"iso": "2026-11-26T18:00:00+05:30"},
        "attributions": [
            {"name": "Delhi Pollution Control Commitee (Government of NCT of Delhi)"},
            {"name": "CPCB"},
        ],
    },
}


@pytest.mark.asyncio
async def test_waqi_provider_does_not_label_iaqi_as_micrograms_or_run_cpcb_breakpoints():
    """
    WAQI `/feed/` returns US-EPA AQI sub-indices in `iaqi`.
    Ensure WAQIProvider:
    1. Never labels iaqi values as µg/m³ or mg/m³.
    2. Never computes CPCB concentration sub-indices on WAQI iaqi numbers.
    3. Preserves provider_index provenance and honest disclosure.
    """
    provider = WAQIProvider(api_token="test_token")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_WAQI_RESPONSE

    with patch("app.services.air_quality.waqi_provider.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        obs = await provider.get_air_quality("Delhi NCR", 28.6139, 77.2090)

    assert obs is not None
    assert obs.source_type == "ground_station"
    assert obs.index_type == "provider_index"
    assert obs.index_value == 96
    assert "US-EPA" in obs.methodology_disclosure
    assert "omitted" in obs.methodology_disclosure.lower()

    # Every present iaqi field must NOT claim µg/m³ or mg/m³ and must NOT have CPCB sub_index populated
    for field in [obs.pm25, obs.pm10, obs.no2, obs.so2, obs.co, obs.o3]:
        assert field is not None
        assert field.unit == "US-EPA Sub-Index"
        assert "µg/m³" not in field.unit
        assert "mg/m³" not in field.unit
        assert field.sub_index is None

    # Unreported parameters stay None
    assert obs.nh3 is None
    assert obs.pb is None


@pytest.mark.asyncio
async def test_waqi_provider_handles_non_numeric_aqi_gracefully():
    """Ensure WAQI `aqi: '-'` results in unavailable index rather than crashing or fabricating."""
    provider = WAQIProvider(api_token="test_token")
    payload = {
        "status": "ok",
        "data": {
            "aqi": "-",
            "city": {"name": "Offline Sensor Station"},
            "iaqi": {},
            "time": {"iso": "2026-11-26T18:00:00+05:30"},
        },
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = payload

    with patch("app.services.air_quality.waqi_provider.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        obs = await provider.get_air_quality("Delhi NCR", 28.6139, 77.2090)

    assert obs is not None
    assert obs.index_value is None
    assert obs.index_type == "unavailable"
    assert obs.index_category == "Unavailable"


@pytest.mark.asyncio
async def test_map_service_does_not_pass_waqi_iaqi_to_cpcb_breakpoints():
    """
    Verify MapService never treats WAQI `iaqi` sub-indices as raw µg/m³ concentrations
    and never passes them through calculate_sub_index().
    """
    service = MapService()
    service.waqi_token = "test_token"

    bounds_resp = MagicMock()
    bounds_resp.status_code = 200
    bounds_resp.json.return_value = {
        "status": "ok",
        "data": [{"uid": 1234, "lat": 28.61, "lon": 77.23, "station": {"name": "Test Station"}}],
    }

    feed_resp = MagicMock()
    feed_resp.status_code = 200
    feed_resp.json.return_value = SAMPLE_WAQI_RESPONSE

    with patch("app.services.air_quality.map_service.httpx.AsyncClient") as mock_client_cls, \
         patch("app.services.air_quality.map_service.calculate_sub_index") as mock_calc:
        mock_client = AsyncMock()
        mock_client.get.side_effect = [bounds_resp, feed_resp]
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        result = await service.get_city_pollutant_map("delhi", "pm25")

    # CPCB concentration breakpoint calculator MUST NOT be called on WAQI iaqi data
    mock_calc.assert_not_called()
    assert result.summary.total_stations == 1
    assert result.summary.reporting_stations == 0
    assert result.stations[0].concentration is None
    assert result.stations[0].cpcb_sub_index is None
    assert result.stations[0].sub_index_category == "Unavailable"
    assert "US-EPA AQI sub-indices" in result.summary.data_provenance_note
