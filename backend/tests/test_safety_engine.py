import pytest
from datetime import datetime, timezone
from app.schemas.air_quality import NormalizedAirObservation, PollutantConcentration
from app.schemas.plan import HouseholdProfile
from app.services.safety_engine import safety_engine


def make_test_observation(band: str, pm25_val: float = 25.0, o3_val: float = 20.0) -> NormalizedAirObservation:
    now = datetime.now(timezone.utc)
    return NormalizedAirObservation(
        city="Delhi NCR",
        source_type="ground_station",
        data_provider="WAQI (CPCB)",
        observed_at=now,
        fetched_at=now,
        data_status="live",
        confidence_score="high",
        index_type="indicative_particulate_subindex",
        index_value=150 if band == "Moderate" else (350 if band == "Very Poor" else 25),
        index_category=band,
        methodology_disclosure="Test observation",
        pm25=PollutantConcentration(value=pm25_val, sub_index=pm25_val * 1.5),
        o3=PollutantConcentration(value=o3_val, sub_index=o3_val * 1.2),
    )


def test_safety_engine_good_band():
    obs = make_test_observation("Good", pm25_val=15.0)
    guidance = safety_engine.evaluate(obs)
    assert guidance.band == "Good"
    assert guidance.constraints.outdoor_exertion_level == "unrestricted"
    assert guidance.constraints.respirator_advisory == "none"
    assert guidance.constraints.indoor_mitigation_required is False
    assert "encouraged" in guidance.general_population_guidance


def test_safety_engine_moderate_band():
    obs = make_test_observation("Moderate", pm25_val=75.0)
    guidance = safety_engine.evaluate(obs)
    assert guidance.band == "Moderate"
    assert guidance.constraints.outdoor_exertion_level == "moderate_with_breaks"
    assert guidance.constraints.respirator_advisory == "optional_dust_zones"


def test_safety_engine_poor_band():
    obs = make_test_observation("Poor", pm25_val=110.0)
    guidance = safety_engine.evaluate(obs)
    assert guidance.band == "Poor"
    assert guidance.constraints.outdoor_exertion_level == "light_only"
    assert guidance.constraints.vulnerable_activity_restriction == "indoor_only"
    assert guidance.constraints.respirator_advisory == "n95_advised_prolonged"
    assert guidance.constraints.indoor_mitigation_required is True


def test_safety_engine_severe_band():
    obs = make_test_observation("Severe", pm25_val=320.0)
    guidance = safety_engine.evaluate(obs)
    assert guidance.band == "Severe"
    assert guidance.constraints.outdoor_exertion_level == "avoid_all"
    assert guidance.constraints.respirator_advisory == "n95_strongly_advised"
    assert guidance.constraints.vulnerable_activity_restriction == "strict_shelter"


def test_safety_engine_vulnerability_adaptation():
    obs = make_test_observation("Moderate", pm25_val=75.0)
    profile = HouseholdProfile(
        city="Delhi NCR",
        persona="parent",
        age_groups=["child", "adult"],
        has_respiratory_sensitivity=True,
    )
    guidance = safety_engine.evaluate(obs, profile)
    # Sensitivity tightens vulnerable activity constraint
    assert guidance.constraints.vulnerable_activity_restriction == "indoor_only"
    assert guidance.constraints.respirator_advisory == "n95_advised_prolonged"


def test_safety_engine_dominant_pollutant_identification():
    obs = make_test_observation("Moderate", pm25_val=20.0, o3_val=150.0)
    # O3 sub-index is higher
    guidance = safety_engine.evaluate(obs)
    assert guidance.dominant_pollutant == "O3"
    assert any("ozone" in c.lower() for c in guidance.exposure_concerns)
