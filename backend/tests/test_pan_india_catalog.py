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


def test_freshness_timezone_conversion_live_stale_expired_and_invalid():
    now_utc = datetime(2026, 11, 26, 14, 30, tzinfo=timezone.utc)  # 20:00 IST

    # 1. Live IST (+05:30) timestamp 1 hour ago (19:00 IST = 13:30 UTC)
    obs, status, note = evaluate_observation_freshness("2026-11-26T19:00:00+05:30", now_utc=now_utc)
    assert obs == datetime(2026, 11, 26, 13, 30, tzinfo=timezone.utc)
    assert status == "live"
    assert note is None

    # 2. Stale timestamp 5 hours ago (>3h, <=24h)
    obs_stale, status_stale, note_stale = evaluate_observation_freshness("2026-11-26T15:00:00+05:30", now_utc=now_utc)
    assert status_stale == "stale"
    assert "5.0h old" in note_stale

    # 3. Expired timestamp >24h old
    obs_exp, status_exp, note_exp = evaluate_observation_freshness("2026-11-24T19:00:00+05:30", now_utc=now_utc)
    assert status_exp == "expired"
    assert "expired" in note_exp.lower()

    # 4. Missing or invalid timestamp must NEVER return 'live'
    obs_miss, status_miss, _ = evaluate_observation_freshness(None, now_utc=now_utc)
    assert obs_miss is None
    assert status_miss == "unavailable"

    obs_bad, status_bad, _ = evaluate_observation_freshness("not-a-timestamp", now_utc=now_utc)
    assert obs_bad is None
    assert status_bad == "unavailable"


def test_us_epa_display_mapping():
    assert map_us_epa_aqi_to_display_category(40) == "Good"
    assert map_us_epa_aqi_to_display_category(96) == "Moderate"
    assert map_us_epa_aqi_to_display_category(149) == "Moderate (Sensitive)"
    assert map_us_epa_aqi_to_display_category(175) == "Poor"
    assert map_us_epa_aqi_to_display_category(250) == "Very Poor"
    assert map_us_epa_aqi_to_display_category(350) == "Severe"
    assert map_us_epa_aqi_to_display_category(None) == "Unavailable"
