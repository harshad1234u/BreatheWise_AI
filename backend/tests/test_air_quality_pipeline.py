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

    from datetime import timedelta
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


@pytest.mark.asyncio
async def test_open_meteo_timestamp_freshness_and_concentration_validation():
    """
    F-14 reproduction: OpenMeteoProvider must parse source timestamps cleanly to aware UTC,
    enforce <=3h live / 3-12h stale / >12h or missing/malformed -> unavailable freshness,
    accept zero concentrations, and reject negative concentrations.
    """
    from datetime import timedelta

    provider = OpenMeteoProvider()
    fixed_now = datetime(2026, 11, 26, 18, 0, tzinfo=timezone.utc)

    async def _run_with_payload(current_dict: dict):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"current": current_dict}
        with patch("app.services.air_quality.open_meteo_provider.httpx.AsyncClient") as mock_client_cls, \
             patch("app.services.air_quality.open_meteo_provider._utc_now", return_value=fixed_now):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client_cls.return_value.__aenter__.return_value = mock_client
            return await provider.get_air_quality("Madurai", 9.9252, 78.1198)

    # 1. Valid UTC timestamp (1h old -> live, source observed_at preserved)
    obs_live = await _run_with_payload({"time": "2026-11-26T17:00", "pm2_5": 15.0, "pm10": 0.0})
    assert obs_live is not None
    assert obs_live.observed_at == datetime(2026, 11, 26, 17, 0, tzinfo=timezone.utc)
    assert obs_live.observed_at.tzinfo == timezone.utc
    assert obs_live.data_status == "live"
    assert obs_live.confidence_score == "moderate"
    assert obs_live.pm10 is not None and obs_live.pm10.value == 0.0

    # 2. Timestamp with explicit +05:30 offset (5h old -> stale, converted to UTC)
    obs_stale = await _run_with_payload({"time": "2026-11-26T18:30+05:30", "pm2_5": 25.0})
    assert obs_stale is not None
    assert obs_stale.observed_at == datetime(2026, 11, 26, 13, 0, tzinfo=timezone.utc)
    assert obs_stale.data_status == "stale"

    # 3. Expired timestamp (>12h old -> unavailable, never stamped live)
    obs_exp = await _run_with_payload({"time": "2026-11-26T04:00Z", "pm2_5": 25.0})
    assert obs_exp is not None
    assert obs_exp.observed_at == datetime(2026, 11, 26, 4, 0, tzinfo=timezone.utc)
    assert obs_exp.data_status == "unavailable"

    # 4. Missing timestamp -> unavailable (not fabricated as live)
    obs_missing_ts = await _run_with_payload({"pm2_5": 25.0})
    assert obs_missing_ts is not None
    assert obs_missing_ts.data_status == "unavailable"

    # 5. Malformed timestamp -> unavailable
    obs_bad_ts = await _run_with_payload({"time": "bad-timestamp", "pm2_5": 25.0})
    assert obs_bad_ts is not None
    assert obs_bad_ts.data_status == "unavailable"

    # 6. Negative & missing concentrations rejected; zero valid
    obs_neg = await _run_with_payload({
        "time": "2026-11-26T17:30Z",
        "pm2_5": -12.5,
        "pm10": 0.0,
        "carbon_monoxide": -200.0,
        "nitrogen_dioxide": None,
    })
    assert obs_neg is not None
    assert obs_neg.pm25 is None
    assert obs_neg.co is None
    assert obs_neg.no2 is None
    assert obs_neg.pm10 is not None and obs_neg.pm10.value == 0.0
    assert obs_neg.index_value == 0
    assert obs_neg.index_category == "Good"


@pytest.mark.asyncio
async def test_data_manager_bounded_lru_cache_ttl_and_coalescing():
    """F-07 reproduction: DataManager cache must be bounded LRU/TTL and coalesce concurrent identical keys."""
    import asyncio
    from datetime import timedelta
    from app.schemas.air_quality import NormalizedAirObservation

    manager = AirQualityDataManager(max_cache_entries=2, cache_ttl_seconds=60)

    def _obs(city: str):
        now = datetime.now(timezone.utc)
        return NormalizedAirObservation(
            city=city,
            source_type="ground_station",
            data_provider="WAQI",
            observed_at=now,
            fetched_at=now,
            data_status="live",
            confidence_score="high",
            index_type="provider_index",
            index_value=90,
            index_category="Satisfactory",
            methodology_disclosure="Test",
        )

    async def slow_waqi(city, latitude, longitude, station_id=None):
        await asyncio.sleep(0.03)
        return _obs(city)

    manager.waqi_provider.get_air_quality = AsyncMock(side_effect=slow_waqi)
    manager.openaq_provider.get_air_quality = AsyncMock(return_value=None)
    manager.open_meteo_provider.get_air_quality = AsyncMock(return_value=None)

    # Concurrent calls for same city share 1 upstream call
    results = await asyncio.gather(*[manager.get_air_quality("delhi") for _ in range(5)])
    assert all(r.city == "Delhi NCR" for r in results)
    assert manager.waqi_provider.get_air_quality.call_count == 1
    assert len(manager._in_flight) == 0

    # Caller cancellation must not break peer waiter
    manager.clear_cache()

    async def slower_waqi(city, latitude, longitude, station_id=None):
        await asyncio.sleep(0.08)
        return _obs(city)

    manager.waqi_provider.get_air_quality = AsyncMock(side_effect=slower_waqi)
    t1 = asyncio.create_task(manager.get_air_quality("mumbai"))
    t2 = asyncio.create_task(manager.get_air_quality("mumbai"))
    await asyncio.sleep(0.01)
    t1.cancel()
    with pytest.raises(asyncio.CancelledError):
        await t1
    res_t2 = await t2
    assert res_t2.city == "Mumbai"
    assert len(manager._in_flight) == 0

    # Bounded LRU eviction (max_cache_entries=2)
    manager.clear_cache()
    manager.waqi_provider.get_air_quality = AsyncMock(side_effect=slow_waqi)
    await manager.get_air_quality("delhi")
    await manager.get_air_quality("mumbai")
    await manager.get_air_quality("delhi")  # Refresh delhi as MRU; mumbai becomes LRU
    await manager.get_air_quality("bengaluru")
    assert len(manager._cache) <= 2
    assert "delhi_default" in manager._cache
    assert "bengaluru_default" in manager._cache
    assert "mumbai_default" not in manager._cache

    # TTL expiration triggers fresh fetch
    obs_old, ts_old = manager._cache["delhi_default"]
    manager._cache["delhi_default"] = (obs_old, ts_old - timedelta(seconds=120))
    prev_calls = manager.waqi_provider.get_air_quality.call_count
    await manager.get_air_quality("delhi")
    assert manager.waqi_provider.get_air_quality.call_count == prev_calls + 1


@pytest.mark.asyncio
async def test_data_manager_stale_cache_immutability_and_no_duplicate_suffix():
    """F-07: Repeated stale fallback must never mutate cached objects or append duplicate disclosure text."""
    from datetime import timedelta
    from app.schemas.air_quality import NormalizedAirObservation

    manager = AirQualityDataManager(max_cache_entries=10, cache_ttl_seconds=60)
    now = datetime.now(timezone.utc)
    live_obs = NormalizedAirObservation(
        city="Delhi NCR",
        source_type="ground_station",
        data_provider="WAQI",
        observed_at=now,
        fetched_at=now,
        data_status="live",
        confidence_score="high",
        index_type="provider_index",
        index_value=115,
        index_category="Moderate",
        methodology_disclosure="Base disclosure.",
    )
    manager._cache["delhi_default"] = (live_obs, now - timedelta(seconds=120))
    manager.waqi_provider.get_air_quality = AsyncMock(return_value=None)
    manager.openaq_provider.get_air_quality = AsyncMock(return_value=None)
    manager.open_meteo_provider.get_air_quality = AsyncMock(return_value=None)

    fallback_1 = await manager.get_air_quality("delhi")
    fallback_2 = await manager.get_air_quality("delhi")

    assert fallback_1.source_type == "stale_cache"
    assert fallback_2.source_type == "stale_cache"
    assert fallback_2.methodology_disclosure.count("Serving historical cache") == 1
    # Cached object itself remains untouched
    cached_orig, _ = manager._cache["delhi_default"]
    assert cached_orig.source_type == "ground_station"
    assert cached_orig.methodology_disclosure == "Base disclosure."


@pytest.mark.asyncio
async def test_data_manager_ignores_unavailable_model_over_stale_ground_and_deep_copies():
    """
    F-07 / F-14 Batch 2.1 remediation:
    1. When WAQI returns a valid stale (e.g. 5h) ground observation, OpenAQ is None, and
       Open-Meteo returns data_status='unavailable', DataManager must return/cache the stale
       ground observation rather than discarding it for the unavailable model observation.
    2. When neither ground source yields anything, a valid stale model observation is accepted,
       whereas an unavailable model observation is never cached.
    3. Cache hits and returns must use deep copies so mutating nested PollutantConcentration fields
       does not corrupt the cache.
    """
    from datetime import timedelta
    from app.schemas.air_quality import NormalizedAirObservation, PollutantConcentration

    manager = AirQualityDataManager(max_cache_entries=10, cache_ttl_seconds=60)
    now = datetime.now(timezone.utc)
    stale_waqi = NormalizedAirObservation(
        city="Delhi NCR",
        source_type="ground_station",
        data_provider="WAQI",
        observed_at=now - timedelta(hours=5),
        fetched_at=now,
        data_status="stale",
        freshness_note="Data is 5.0h old.",
        confidence_score="moderate",
        index_type="provider_index",
        index_value=180,
        index_category="Moderate",
        pm25=PollutantConcentration(value=84.0, unit="µg/m³"),
        methodology_disclosure="Stale WAQI.",
    )
    unavailable_model = NormalizedAirObservation(
        city="Delhi NCR",
        source_type="atmospheric_model",
        data_provider="Open-Meteo CAMS",
        observed_at=now,
        fetched_at=now,
        data_status="unavailable",
        confidence_score="unverified",
        index_type="atmospheric_model_estimate",
        index_value=None,
        index_category="Unavailable",
        methodology_disclosure="Model unavailable.",
    )
    stale_model = NormalizedAirObservation(
        city="Mumbai",
        source_type="atmospheric_model",
        data_provider="Open-Meteo CAMS",
        observed_at=now - timedelta(hours=4),
        fetched_at=now,
        data_status="stale",
        confidence_score="low",
        index_type="atmospheric_model_estimate",
        index_value=95,
        index_category="Moderate",
        pm25=PollutantConcentration(value=41.0, unit="µg/m³"),
        methodology_disclosure="Stale model.",
    )

    manager.waqi_provider.get_air_quality = AsyncMock(return_value=stale_waqi)
    manager.openaq_provider.get_air_quality = AsyncMock(return_value=None)
    manager.open_meteo_provider.get_air_quality = AsyncMock(return_value=unavailable_model)

    res = await manager.get_air_quality("delhi")
    assert res.source_type == "ground_station"
    assert res.data_provider == "WAQI"
    assert res.data_status == "stale"
    assert manager._cache["delhi_default"][0].source_type == "ground_station"

    # Mutating nested PollutantConcentration on returned copy must NOT affect subsequent cache hit
    assert res.pm25 is not None
    res.pm25.value = 999.0
    cached_hit = await manager.get_air_quality("delhi")
    assert cached_hit.pm25 is not None
    assert cached_hit.pm25.value == 84.0

    # Stale atmospheric model IS accepted when no stale ground station exists
    manager.waqi_provider.get_air_quality = AsyncMock(return_value=None)
    manager.openaq_provider.get_air_quality = AsyncMock(return_value=None)
    manager.open_meteo_provider.get_air_quality = AsyncMock(return_value=stale_model)
    mumbai_res = await manager.get_air_quality("mumbai")
    assert mumbai_res.source_type == "atmospheric_model"
    assert mumbai_res.data_status == "stale"
    assert "mumbai_default" in manager._cache

    # Unavailable model with no ground/stale-cache fallback must not be cached
    manager.open_meteo_provider.get_air_quality = AsyncMock(return_value=unavailable_model)
    chennai_res = await manager.get_air_quality("chennai")
    assert chennai_res.data_status == "unavailable"
    assert "chennai_default" not in manager._cache
