import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.services.air_quality.city_catalog import city_catalog
from app.services.air_quality.freshness import (
    evaluate_observation_freshness,
    map_us_epa_aqi_to_display_category,
)

client = TestClient(app)


def test_pan_india_catalog_covers_all_28_states_and_8_union_territories():
    meta = city_catalog.summary_metadata()
    assert meta["states_count"] == 28
    assert meta["union_territories_count"] == 8
    assert meta["total_cities"] >= 48


def test_pan_india_catalog_coordinates_unique_and_valid():
    cities = city_catalog.all_cities()
    ids = [c.id for c in cities]
    assert len(ids) == len(set(ids)), "Duplicate city IDs detected"

    for c in cities:
        # India geographic bounding range approx lat 6..37, lng 68..98
        assert 6.0 <= c.latitude <= 37.5, f"Invalid latitude for {c.name}"
        assert 68.0 <= c.longitude <= 98.0, f"Invalid longitude for {c.name}"
        assert c.state.strip() != ""


def test_city_search_state_filter_ut_filter_and_aliases():
    # Alias matching
    assert city_catalog.find_city("bangalore").id == "bengaluru"
    assert city_catalog.find_city("trivandrum").id == "thiruvananthapuram"
    assert city_catalog.find_city("pondicherry").id == "puducherry"
    assert city_catalog.find_city("gurgaon").id == "gurugram"
    assert city_catalog.find_city("nonexistent_town_xyz") is None

    # API search & filters
    r_search = client.get("/api/v1/cities?q=trivandrum")
    assert r_search.status_code == 200
    assert r_search.json()[0]["id"] == "thiruvananthapuram"

    r_state = client.get("/api/v1/cities?state=Tamil%20Nadu")
    assert r_state.status_code == 200
    tn_ids = {c["id"] for c in r_state.json()}
    assert {"chennai", "coimbatore", "madurai"}.issubset(tn_ids)

    r_ut = client.get("/api/v1/cities?region_type=union_territory")
    assert r_ut.status_code == 200
    assert len(r_ut.json()) >= 8

    r_meta = client.get("/api/v1/cities/catalog")
    assert r_meta.status_code == 200
    assert r_meta.json()["states_count"] == 28
    assert r_meta.json()["union_territories_count"] == 8


def test_freshness_prd_v12_exact_boundaries():
    """
    Verify PRD v1.2 Freshness Window strictly:
    - <= 3h: live (2h59m, 3h00m)
    - > 3h and <= 12h: stale (3h01m, 11h59m, 12h00m)
    - > 12h: expired (12h01m)
    - missing / malformed / future: unavailable
    """
    now_utc = datetime(2026, 11, 26, 14, 30, tzinfo=timezone.utc)  # 20:00:00 IST (+05:30)

    # 2h 59m ago (17:01 IST) -> live
    obs, st, note = evaluate_observation_freshness("2026-11-26T17:01:00+05:30", now_utc=now_utc)
    assert obs == datetime(2026, 11, 26, 11, 31, tzinfo=timezone.utc)
    assert st == "live" and note is None

    # Exactly 3h 00m ago (17:00 IST) -> live
    _, st_3h, _ = evaluate_observation_freshness("2026-11-26T17:00:00+05:30", now_utc=now_utc)
    assert st_3h == "live"

    # 3h 01m ago (16:59 IST) -> stale
    _, st_3h1m, note_3h1m = evaluate_observation_freshness("2026-11-26T16:59:00+05:30", now_utc=now_utc)
    assert st_3h1m == "stale" and "3.0h" in note_3h1m

    # 11h 59m ago (08:01 IST) -> stale
    _, st_11h59, _ = evaluate_observation_freshness("2026-11-26T08:01:00+05:30", now_utc=now_utc)
    assert st_11h59 == "stale"

    # Exactly 12h 00m ago (08:00 IST) -> stale
    _, st_12h, _ = evaluate_observation_freshness("2026-11-26T08:00:00+05:30", now_utc=now_utc)
    assert st_12h == "stale"

    # 12h 01m ago (07:59 IST) -> expired
    _, st_12h1m, note_12h1m = evaluate_observation_freshness("2026-11-26T07:59:00+05:30", now_utc=now_utc)
    assert st_12h1m == "expired" and "12h" in note_12h1m

    # UTC 'Z' timestamp
    obs_z, st_z, _ = evaluate_observation_freshness("2026-11-26T13:30:00Z", now_utc=now_utc)
    assert obs_z == datetime(2026, 11, 26, 13, 30, tzinfo=timezone.utc) and st_z == "live"

    # Future timestamp (>30m ahead) -> unavailable
    _, st_future, _ = evaluate_observation_freshness("2026-11-26T22:00:00+05:30", now_utc=now_utc)
    assert st_future == "unavailable"

    # Missing or malformed -> unavailable
    assert evaluate_observation_freshness(None, now_utc=now_utc)[1] == "unavailable"
    assert evaluate_observation_freshness("not-a-timestamp", now_utc=now_utc)[1] == "unavailable"


def test_us_epa_display_mapping():
    assert map_us_epa_aqi_to_display_category(40) == "Good"
    assert map_us_epa_aqi_to_display_category(96) == "Moderate"
    assert map_us_epa_aqi_to_display_category(149) == "Unhealthy for Sensitive Groups"
    assert map_us_epa_aqi_to_display_category(175) == "Unhealthy"
    assert map_us_epa_aqi_to_display_category(250) == "Very Unhealthy"
    assert map_us_epa_aqi_to_display_category(350) == "Hazardous"
    assert map_us_epa_aqi_to_display_category(None) == "Unavailable"


@pytest.mark.asyncio
async def test_region_type_strict_validation_concurrency_and_no_shared_coverage_mutation():
    """
    F-15:
    1. Valid region_type ('state', 'union_territory', or omitted) returns 200; invalid value returns 422.
    2. Concurrent requests with different region_type filters remain isolated.
    3. Failed telemetry lookups in DataManager must not mutate shared global catalog availability_status.
    """
    import asyncio
    from unittest.mock import AsyncMock
    from app.services.air_quality.data_manager import AirQualityDataManager

    # Invalid region_type must fail validation with HTTP 422
    r_invalid = client.get("/api/v1/cities?region_type=province")
    assert r_invalid.status_code == 422

    # Valid omitted / state / union_territory continue working
    assert client.get("/api/v1/cities").status_code == 200
    r_st = client.get("/api/v1/cities?region_type=state")
    assert r_st.status_code == 200 and all(c["region_type"] == "state" for c in r_st.json())
    r_ut = client.get("/api/v1/cities?region_type=union_territory")
    assert r_ut.status_code == 200 and all(c["region_type"] == "union_territory" for c in r_ut.json())

    # Simulated failure in one AirQualityDataManager lookup must NOT poison global city_catalog state
    baseline_delhi = city_catalog.find_city("delhi")
    assert baseline_delhi is not None
    baseline_status = baseline_delhi.availability_status

    dm = AirQualityDataManager()
    dm.waqi_provider.get_air_quality = AsyncMock(return_value=None)
    dm.openaq_provider.get_air_quality = AsyncMock(return_value=None)
    dm.open_meteo_provider.get_air_quality = AsyncMock(return_value=None)
    failed_obs = await dm.get_air_quality("delhi")
    assert failed_obs.data_status == "unavailable"

    after_delhi = city_catalog.find_city("delhi")
    assert after_delhi is not None
    assert after_delhi.availability_status == baseline_status
    assert not hasattr(city_catalog, "_observed_coverage")

    # Concurrent region queries do not cross-contaminate
    res_a, res_b = await asyncio.gather(
        asyncio.to_thread(client.get, "/api/v1/cities?region_type=state"),
        asyncio.to_thread(client.get, "/api/v1/cities?region_type=union_territory"),
    )
    assert all(c["region_type"] == "state" for c in res_a.json())
    assert all(c["region_type"] == "union_territory" for c in res_b.json())
