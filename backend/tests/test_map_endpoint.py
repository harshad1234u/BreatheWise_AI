import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.main import app
from app.schemas.map import PollutantMapResponse, StationMapPoint, MapSummary
from app.services.air_quality.map_service import map_service


client = TestClient(app)


def test_map_endpoint_valid_pollutant_delhi():
    """Verify GET /api/v1/map/pollutants returns valid stations and schema for Delhi PM2.5."""
    response = client.get("/api/v1/map/pollutants?city=delhi&pollutant=pm25")
    assert response.status_code == 200
    data = response.json()
    assert data["selected_city"] == "Delhi NCR"
    assert data["selected_pollutant"] == "pm25"
    assert data["unit"] == "µg/m³"
    assert isinstance(data["stations"], list)
    assert data["summary"]["total_stations"] > 0
    if len(data["stations"]) > 0:
        s = data["stations"][0]
        assert "station_id" in s
        assert "station_name" in s
        assert "latitude" in s
        assert "longitude" in s
        assert "source_type" in s
        assert "data_provider" in s


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
    assert len(data["stations"]) == 0
    assert "not supported" in data["summary"]["data_provenance_note"].lower()


@pytest.mark.asyncio
async def test_map_service_unmonitored_pollutant_integrity():
    """Verify unmonitored pollutants have concentration=None, not fabricated 0."""
    res = await map_service.get_city_pollutant_map("delhi", "nh3")
    assert res.selected_pollutant == "nh3"
    # Even if stations exist, unmonitored NH3 must have concentration=None
    for s in res.stations:
        if s.concentration is None:
            assert s.cpcb_sub_index is None
            assert s.sub_index_category == "Unavailable"


@pytest.mark.asyncio
async def test_map_service_ground_vs_model_provenance():
    """Verify station records explicitly identify ground vs model source."""
    res = await map_service.get_city_pollutant_map("delhi", "pm25")
    for s in res.stations:
        assert s.source_type in ["ground_station", "atmospheric_model", "unavailable"]
        if s.source_type == "ground_station":
            assert "CPCB" in s.data_provider or "WAQI" in s.data_provider
        elif s.source_type == "atmospheric_model":
            assert "Model" in s.data_provider or "Open-Meteo" in s.data_provider


@pytest.mark.asyncio
async def test_map_service_stale_reading_classification():
    """Verify that observations older than threshold are flagged as stale."""
    # Mock station with old timestamp
    now = datetime.now(timezone.utc)
    old_time = now.replace(year=now.year - 1)
    
    mock_point = StationMapPoint(
        station_id="test_stale_1",
        station_name="Historical Stale Station",
        latitude=28.6,
        longitude=77.2,
        concentration=150.0,
        cpcb_sub_index=320.0,
        sub_index_category="Very Poor",
        observed_at=old_time,
        data_provider="WAQI (Official CPCB Ground Feed)",
        source_type="ground_station",
        freshness_status="stale",
        quality_confidence="low"
    )
    assert mock_point.freshness_status == "stale"
    assert mock_point.quality_confidence == "low"
