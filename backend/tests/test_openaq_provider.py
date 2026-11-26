from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest

from app.services.air_quality.data_manager import AirQualityDataManager
from app.services.air_quality.openaq_provider import OpenAQProvider


def _mock_openaq_client(locations_payload, latest_payload=None, loc_status=200, latest_status=200):
    loc_resp = MagicMock()
    loc_resp.status_code = loc_status
    loc_resp.json.return_value = locations_payload

    latest_resp = MagicMock()
    latest_resp.status_code = latest_status
    latest_resp.json.return_value = latest_payload if latest_payload is not None else {"results": []}

    mock_client = AsyncMock()
    mock_client.get.side_effect = [loc_resp, latest_resp]
    return mock_client


@pytest.mark.asyncio
async def test_openaq_valid_pm25_and_sensors_lookup():
    """Tests 1 & 15: Valid PM2.5 via canonical OpenAQ v3 sensorsId lookup + exact provenance."""
    provider = OpenAQProvider(api_key="test_openaq_key")
    obs_dt = (datetime.now(timezone.utc) - timedelta(minutes=25)).replace(microsecond=0)

    locations_payload = {
        "results": [
            {
                "id": 8118,
                "name": "ITO Delhi - CPCB",
                "distance": 3250,
                "sensors": [
                    {"id": 101, "parameter": {"name": "pm25", "units": "µg/m³"}},
                ],
            }
        ]
    }
    latest_payload = {
        "results": [
            {"sensorsId": 101, "value": 45.0, "datetime": {"utc": obs_dt.isoformat().replace("+00:00", "Z")}}
        ]
    }

    with patch("app.services.air_quality.openaq_provider.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = _mock_openaq_client(locations_payload, latest_payload)
        obs = await provider.get_air_quality("Delhi NCR", 28.6139, 77.2090)

    assert obs is not None
    assert obs.source_type == "ground_station"
    assert obs.data_provider == "OpenAQ Ground Telemetry"
    assert obs.locality_or_station == "ITO Delhi - CPCB"
    assert obs.station_distance_km == 3.25
    assert obs.data_status == "live"
    assert obs.confidence_score == "high"
    assert obs.observed_at == obs_dt
    assert obs.pm25 is not None and obs.pm25.value == 45.0 and obs.pm25.unit == "µg/m³"
    assert obs.index_type == "indicative_particulate_subindex"
    assert obs.index_value == 75


@pytest.mark.asyncio
async def test_openaq_valid_pm10_inline_parameter():
    """Test 2: Valid PM10 observation with inline parameter object."""
    provider = OpenAQProvider(api_key="test_openaq_key")
    obs_dt = (datetime.now(timezone.utc) - timedelta(minutes=45)).replace(microsecond=0)

    locations_payload = {"results": [{"id": 9001, "name": "Bandra West"}]}
    latest_payload = {
        "results": [
            {
                "parameter": {"name": "pm10", "units": "µg/m³"},
                "value": 120.0,
                "datetime": {"utc": obs_dt.isoformat()},
            }
        ]
    }

    with patch("app.services.air_quality.openaq_provider.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = _mock_openaq_client(locations_payload, latest_payload)
        obs = await provider.get_air_quality("Mumbai", 19.076, 72.877)

    assert obs is not None
    assert obs.pm10 is not None and obs.pm10.value == 120.0 and obs.pm10.unit == "µg/m³"
    assert obs.index_category == "Moderate"


@pytest.mark.asyncio
async def test_openaq_supported_unit_conversions():
    """Test 3: Scientifically accurate mg/m³ <-> µg/m³ and ppb/ppm conversions."""
    provider = OpenAQProvider(api_key="test_openaq_key")
    obs_dt = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()

    locations_payload = {"results": [{"id": 77, "name": "Unit Test Station"}]}
    latest_payload = {
        "results": [
            # 0.045 mg/m³ PM2.5 -> 45.0 µg/m³
            {"parameter": {"name": "pm25", "units": "mg/m3"}, "value": 0.045, "datetime": {"utc": obs_dt}},
            # 1200 ug/m3 CO -> 1.2 mg/m³ (CPCB uses mg/m³ for CO!)
            {"parameter": {"name": "co", "units": "ug/m3"}, "value": 1200.0, "datetime": {"utc": obs_dt}},
            # 20 ppb NO2 -> 20 * 46.0055 / 24.45 ≈ 37.6323 µg/m³
            {"parameter": {"name": "no2", "units": "ppb"}, "value": 20.0, "datetime": {"utc": obs_dt}},
            # 1.0 ppm O3 -> 1000 * 48.0 / 24.45 ≈ 1963.1902 µg/m³
            {"parameter": {"name": "o3", "units": "ppm"}, "value": 0.02, "datetime": {"utc": obs_dt}},
            # 5 ppb SO2 -> 5 * 64.066 / 24.45 ≈ 13.1014 µg/m³
            {"parameter": {"name": "so2", "units": "ppb"}, "value": 5.0, "datetime": {"utc": obs_dt}},
            # 10 ppb NH3 -> 10 * 17.031 / 24.45 ≈ 6.9656 µg/m³
            {"parameter": {"name": "nh3", "units": "ppb"}, "value": 10.0, "datetime": {"utc": obs_dt}},
            # Pb in ug/m3
            {"parameter": {"name": "pb", "units": "ug/m3"}, "value": 0.25, "datetime": {"utc": obs_dt}},
        ]
    }

    with patch("app.services.air_quality.openaq_provider.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = _mock_openaq_client(locations_payload, latest_payload)
        obs = await provider.get_air_quality("Delhi NCR", 28.6, 77.2)

    assert obs is not None
    assert obs.pm25 is not None and obs.pm25.value == pytest.approx(45.0, abs=0.01) and obs.pm25.unit == "µg/m³"
    assert obs.co is not None and obs.co.value == pytest.approx(1.2, abs=0.01) and obs.co.unit == "mg/m³"
    assert obs.no2 is not None and obs.no2.value == pytest.approx(20.0 * 46.0055 / 24.45, abs=0.01)
    assert obs.o3 is not None and obs.o3.value == pytest.approx(20.0 * 48.0 / 24.45, abs=0.01)
    assert obs.so2 is not None and obs.so2.value == pytest.approx(5.0 * 64.066 / 24.45, abs=0.01)
    assert obs.nh3 is not None and obs.nh3.value == pytest.approx(10.0 * 17.031 / 24.45, abs=0.01)
    assert obs.pb is not None and obs.pb.value == pytest.approx(0.25, abs=0.001)

    # Verify F-12 source unit preservation & conversion provenance disclosure
    assert obs.no2.source_unit == "ppb" and obs.no2.is_converted is True
    assert obs.o3.source_unit == "ppm" and obs.o3.is_converted is True
    assert obs.pm25.source_unit == "mg/m3" and obs.pm25.is_converted is False
    assert obs.co.source_unit == "ug/m3" and obs.co.is_converted is False
    assert "25°C" in obs.methodology_disclosure
    assert "24.45 L/mol" in obs.methodology_disclosure
    assert "standard-condition approximation" in obs.methodology_disclosure


@pytest.mark.asyncio
async def test_openaq_native_mass_units_omit_conversion_disclosure():
    """Native µg/m³ and mg/m³ measurements must NOT be falsely labelled as converted."""
    provider = OpenAQProvider(api_key="test_openaq_key")
    obs_dt = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    locations_payload = {"results": [{"id": 88, "name": "Native Mass Station"}]}
    latest_payload = {
        "results": [
            {"parameter": {"name": "pm25", "units": "µg/m³"}, "value": 42.0, "datetime": {"utc": obs_dt}},
            {"parameter": {"name": "co", "units": "mg/m³"}, "value": 1.1, "datetime": {"utc": obs_dt}},
        ]
    }
    with patch("app.services.air_quality.openaq_provider.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = _mock_openaq_client(locations_payload, latest_payload)
        obs = await provider.get_air_quality("Mumbai", 19.07, 72.87)

    assert obs is not None
    assert obs.pm25 is not None and obs.pm25.source_unit == "µg/m³" and obs.pm25.is_converted is False
    assert obs.co is not None and obs.co.source_unit == "mg/m³" and obs.co.is_converted is False
    assert "standard-condition approximation" not in obs.methodology_disclosure
    assert "24.45 L/mol" not in obs.methodology_disclosure


@pytest.mark.asyncio
async def test_openaq_rejects_unsupported_and_missing_units():
    """Tests 4 & 5: Unsupported units and missing units are rejected rather than assumed µg/m³."""
    provider = OpenAQProvider(api_key="test_openaq_key")
    obs_dt = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    locations_payload = {"results": [{"id": 55, "name": "Bad Units Station"}]}

    # Unsupported units (ppm for particulate PM2.5, particles/cm³, AQI) + missing unit
    latest_payload = {
        "results": [
            {"parameter": {"name": "pm25", "units": "ppm"}, "value": 12.0, "datetime": {"utc": obs_dt}},
            {"parameter": {"name": "pm10", "units": "particles/cm³"}, "value": 80.0, "datetime": {"utc": obs_dt}},
            {"parameter": {"name": "no2"}, "value": 30.0, "datetime": {"utc": obs_dt}},
            {"parameter": {"name": "so2", "units": ""}, "value": 15.0, "datetime": {"utc": obs_dt}},
        ]
    }

    with patch("app.services.air_quality.openaq_provider.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = _mock_openaq_client(locations_payload, latest_payload)
        obs = await provider.get_air_quality("Pune", 18.5, 73.8)

    assert obs is None


@pytest.mark.asyncio
async def test_openaq_timestamps_utc_offset_stale_expired_missing_malformed_future():
    """Tests 6, 7, 8, 9, 10: Timestamp parsing, timezone offsets, and strict PRD freshness tiers."""
    provider = OpenAQProvider(api_key="test_openaq_key")
    locations_payload = {"results": [{"id": 12, "name": "TS Station"}]}

    # 6 & 7 & 10: Missing, malformed, future (+2h) -> None
    for bad_dt in [
        None,
        "not-a-timestamp",
        (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
    ]:
        payload = {"results": [{"parameter": {"name": "pm25", "units": "µg/m³"}, "value": 35.0}]}
        if bad_dt is not None:
            payload["results"][0]["datetime"] = {"utc": bad_dt}
        with patch("app.services.air_quality.openaq_provider.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value = _mock_openaq_client(locations_payload, payload)
            assert await provider.get_air_quality("Chennai", 13.08, 80.27) is None

    # 8: Explicit +05:30 IST offset 1h ago -> normalized UTC and 'live'
    ist = timezone(timedelta(hours=5, minutes=30))
    obs_ist = (datetime.now(timezone.utc) - timedelta(hours=1)).astimezone(ist).replace(microsecond=0)
    offset_payload = {
        "results": [
            {"parameter": {"name": "pm25", "units": "µg/m³"}, "value": 42.0, "datetime": {"local": obs_ist.isoformat()}}
        ]
    }
    with patch("app.services.air_quality.openaq_provider.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = _mock_openaq_client(locations_payload, offset_payload)
        obs_offset = await provider.get_air_quality("Chennai", 13.08, 80.27)
    assert obs_offset is not None
    assert obs_offset.observed_at == obs_ist.astimezone(timezone.utc)
    assert obs_offset.data_status == "live"

    # 9a: 5h old -> 'stale', confidence='moderate'
    stale_dt = (datetime.now(timezone.utc) - timedelta(hours=5)).replace(microsecond=0)
    stale_payload = {
        "results": [
            {"parameter": {"name": "pm25", "units": "µg/m³"}, "value": 55.0, "datetime": {"utc": stale_dt.isoformat()}}
        ]
    }
    with patch("app.services.air_quality.openaq_provider.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = _mock_openaq_client(locations_payload, stale_payload)
        obs_stale = await provider.get_air_quality("Chennai", 13.08, 80.27)
    assert obs_stale is not None
    assert obs_stale.data_status == "stale"
    assert obs_stale.confidence_score == "moderate"
    assert obs_stale.observed_at == stale_dt

    # 9b: 14h old (>12h expired limit) -> returns None
    expired_dt = (datetime.now(timezone.utc) - timedelta(hours=14)).isoformat()
    expired_payload = {
        "results": [
            {"parameter": {"name": "pm25", "units": "µg/m³"}, "value": 55.0, "datetime": {"utc": expired_dt}}
        ]
    }
    with patch("app.services.air_quality.openaq_provider.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = _mock_openaq_client(locations_payload, expired_payload)
        assert await provider.get_air_quality("Chennai", 13.08, 80.27) is None


@pytest.mark.asyncio
async def test_openaq_negative_nonfinite_zero_and_malformed_failures():
    """Tests 11, 12, 13, 14: Value validation, missing metadata, malformed JSON, network failures."""
    provider = OpenAQProvider(api_key="test_openaq_key")
    obs_dt = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    locations_payload = {"results": [{"id": 99, "name": ""}]}  # blank name falls back gracefully

    # Zero valid, negative/NaN/Inf/bool rejected
    mixed_vals = {
        "results": [
            {"parameter": {"name": "pm25", "units": "µg/m³"}, "value": 0.0, "datetime": {"utc": obs_dt}},
            {"parameter": {"name": "pm10", "units": "µg/m³"}, "value": -12.0, "datetime": {"utc": obs_dt}},
            {"parameter": {"name": "no2", "units": "µg/m³"}, "value": float("nan"), "datetime": {"utc": obs_dt}},
            {"parameter": {"name": "so2", "units": "µg/m³"}, "value": float("inf"), "datetime": {"utc": obs_dt}},
            {"parameter": {"name": "o3", "units": "µg/m³"}, "value": True, "datetime": {"utc": obs_dt}},
        ]
    }
    with patch("app.services.air_quality.openaq_provider.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = _mock_openaq_client(locations_payload, mixed_vals)
        obs = await provider.get_air_quality("Jaipur", 26.9, 75.8)

    assert obs is not None
    assert obs.locality_or_station == "Jaipur OpenAQ Monitor"
    assert obs.pm25 is not None and obs.pm25.value == 0.0
    assert obs.pm10 is None and obs.no2 is None and obs.so2 is None and obs.o3 is None

    # Missing loc_id or malformed JSON
    for bad_loc in [
        {"results": []},
        {"results": [{"name": "No ID"}]},
        "not-a-dict",
    ]:
        with patch("app.services.air_quality.openaq_provider.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value = _mock_openaq_client(bad_loc)
            assert await provider.get_air_quality("Jaipur", 26.9, 75.8) is None

    # Network timeout & HTTP 500 -> None
    with patch("app.services.air_quality.openaq_provider.httpx.AsyncClient") as mock_cls:
        mc = AsyncMock()
        mc.get.side_effect = httpx.TimeoutException("timeout")
        mock_cls.return_value.__aenter__.return_value = mc
        assert await provider.get_air_quality("Jaipur", 26.9, 75.8) is None

    with patch("app.services.air_quality.openaq_provider.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = _mock_openaq_client({}, loc_status=503)
        assert await provider.get_air_quality("Jaipur", 26.9, 75.8) is None

    # Missing API key returns None without network call
    assert await OpenAQProvider(api_key="").get_air_quality("Jaipur", 26.9, 75.8) is None


@pytest.mark.asyncio
async def test_data_manager_handles_openaq_stale_fallback_when_waqi_and_model_unavailable():
    """Preserves stale OpenAQ ground fallback when WAQI and Open-Meteo are unavailable."""
    manager = AirQualityDataManager()
    now = datetime.now(timezone.utc)
    from app.schemas.air_quality import NormalizedAirObservation, PollutantConcentration

    stale_openaq = NormalizedAirObservation(
        city="Jaipur",
        locality_or_station="Jaipur OpenAQ",
        source_type="ground_station",
        data_provider="OpenAQ Ground Telemetry",
        observed_at=now - timedelta(hours=5),
        fetched_at=now,
        data_status="stale",
        confidence_score="moderate",
        index_type="indicative_particulate_subindex",
        index_value=90,
        index_category="Satisfactory",
        methodology_disclosure="OpenAQ stale.",
        pm25=PollutantConcentration(value=54.0, unit="µg/m³", sub_index=90.0),
    )

    manager.waqi_provider.get_air_quality = AsyncMock(return_value=None)
    manager.openaq_provider.get_air_quality = AsyncMock(return_value=stale_openaq)
    manager.open_meteo_provider.get_air_quality = AsyncMock(return_value=None)

    res = await manager.get_air_quality("jaipur")
    assert res.source_type == "ground_station"
    assert res.data_provider == "OpenAQ Ground Telemetry"
    assert res.data_status == "stale"
