import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone
from app.schemas.air_quality import NormalizedAirObservation, PollutantConcentration
from app.schemas.plan import HouseholdProfile
from app.services.safety_engine import safety_engine
from app.services.ai.ai_manager import AIManager
from app.services.ai.validator import (
    validate_and_guardrail_ai_plan,
    generate_deterministic_fallback_plan
)


def get_mock_observation(band: str = "Poor") -> NormalizedAirObservation:
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
        index_value=240,
        index_category=band,
        methodology_disclosure="Test observation",
        pm25=PollutantConcentration(value=105.0, sub_index=240.0),
    )


def get_mock_valid_ai_json():
    return {
        "morning": [
            {
                "period": "morning",
                "time_window": "07:00 AM - 08:30 AM",
                "activity": "Morning indoor stretch & commute",
                "location_type": "indoor",
                "intensity": "light",
                "explanation": "Cold inversion traps particulate matter.",
                "precautions": "Keep windows closed",
                "data_context_used": "PM2.5 105 µg/m³"
            }
        ],
        "afternoon": [
            {
                "period": "afternoon",
                "time_window": "01:30 PM - 03:00 PM",
                "activity": "Midday ventilation & desk work",
                "location_type": "indoor",
                "intensity": "light",
                "explanation": "Solar warming causes temporary dispersion.",
                "precautions": "Brief window opening",
                "data_context_used": "Moderate afternoon dispersion"
            }
        ],
        "evening": [
            {
                "period": "evening",
                "time_window": "06:30 PM - 08:00 PM",
                "activity": "Metro commute & family dinner",
                "location_type": "transit",
                "intensity": "light",
                "explanation": "Peak traffic rush increases roadside particulate count.",
                "precautions": "Wear N95 mask during transit",
                "data_context_used": "Evening rush hour"
            }
        ],
        "indoor_air_suggestions": [
            "Practice damp wet-mopping rather than dry broom sweeping.",
            "Operate kitchen exhaust fan during tadka frying."
        ],
        "sustainable_alternatives": [
            "Use the Metro rather than an open two-wheeler."
        ]
    }


def test_validator_with_valid_json():
    obs = get_mock_observation("Poor")
    profile = HouseholdProfile(city="Delhi NCR", persona="parent")
    safety = safety_engine.evaluate(obs, profile)

    raw_json = get_mock_valid_ai_json()
    validated = validate_and_guardrail_ai_plan(raw_json, obs, profile, safety)
    assert validated is not None
    assert len(validated["morning"]) == 1
    assert len(validated["afternoon"]) == 1
    assert len(validated["evening"]) == 1
    assert len(validated["indoor_air_suggestions"]) == 2


def test_validator_guardrail_overrules_unsafe_outdoor_running():
    obs = get_mock_observation("Very Poor")
    profile = HouseholdProfile(city="Delhi NCR", persona="athlete")
    safety = safety_engine.evaluate(obs, profile)

    # Simulate rogue LLM suggesting a 10km outdoor sprint in Very Poor air
    raw_json = get_mock_valid_ai_json()
    raw_json["morning"][0] = {
        "period": "morning",
        "time_window": "06:00 AM - 07:30 AM",
        "activity": "10km Outdoor Tempo Run",
        "location_type": "outdoor",
        "intensity": "high",
        "explanation": "Get your cardio in.",
        "precautions": None,
        "data_context_used": "Morning routine"
    }

    validated = validate_and_guardrail_ai_plan(raw_json, obs, profile, safety)
    assert validated is not None
    morning_rec = validated["morning"][0]
    # The guardrail MUST have rewritten the activity to indoor low-intensity
    assert morning_rec["location_type"] == "indoor"
    assert morning_rec["intensity"] == "light"
    assert "Substituted" in morning_rec["activity"]
    assert "Safety Engine Guardrail" in morning_rec["precautions"]


def test_validator_rejects_malformed_json():
    obs = get_mock_observation("Moderate")
    profile = HouseholdProfile(city="Delhi NCR")
    safety = safety_engine.evaluate(obs, profile)

    # Missing required periods
    bad_json = {"morning": []}
    assert validate_and_guardrail_ai_plan(bad_json, obs, profile, safety) is None


def test_deterministic_fallback_generator():
    obs = get_mock_observation("Severe")
    profile = HouseholdProfile(city="Delhi NCR", commute_mode="two_wheeler")
    safety = safety_engine.evaluate(obs, profile)

    fallback = generate_deterministic_fallback_plan(obs, profile, safety)
    assert "morning" in fallback
    assert "afternoon" in fallback
    assert "evening" in fallback
    assert len(fallback["indoor_air_suggestions"]) >= 2
    assert len(fallback["sustainable_alternatives"]) >= 1
    # Check that mask note was applied for two wheeler commute
    assert "N95" in fallback["evening"][0]["precautions"]


@pytest.mark.asyncio
async def test_ai_manager_groq_success():
    obs = get_mock_observation("Moderate")
    profile = HouseholdProfile(city="Delhi NCR")
    safety = safety_engine.evaluate(obs, profile)

    mock_groq = AsyncMock()
    mock_groq.generate_plan_json = AsyncMock(return_value=get_mock_valid_ai_json())

    mock_gemini = AsyncMock()
    mock_gemini.generate_plan_json = AsyncMock(return_value=None)

    manager = AIManager(groq_provider=mock_groq, gemini_provider=mock_gemini)
    res = await manager.generate_plan(obs, profile, safety)

    assert res.ai_provider_used == "groq"
    assert res.is_fallback is False
    assert len(res.morning) == 1
    mock_groq.generate_plan_json.assert_called_once()
    mock_gemini.generate_plan_json.assert_not_called()


@pytest.mark.asyncio
async def test_ai_manager_gemini_fallback():
    obs = get_mock_observation("Moderate")
    profile = HouseholdProfile(city="Delhi NCR")
    safety = safety_engine.evaluate(obs, profile)

    # Groq fails (returns None)
    mock_groq = AsyncMock()
    mock_groq.generate_plan_json = AsyncMock(return_value=None)

    # Gemini succeeds
    mock_gemini = AsyncMock()
    mock_gemini.generate_plan_json = AsyncMock(return_value=get_mock_valid_ai_json())

    manager = AIManager(groq_provider=mock_groq, gemini_provider=mock_gemini)
    res = await manager.generate_plan(obs, profile, safety)

    assert res.ai_provider_used == "gemini"
    assert res.is_fallback is True
    mock_groq.generate_plan_json.assert_called_once()
    mock_gemini.generate_plan_json.assert_called_once()


@pytest.mark.asyncio
async def test_ai_manager_both_fail_triggers_deterministic():
    obs = get_mock_observation("Severe")
    profile = HouseholdProfile(city="Delhi NCR")
    safety = safety_engine.evaluate(obs, profile)

    # Both fail
    mock_groq = AsyncMock()
    mock_groq.generate_plan_json = AsyncMock(return_value=None)

    mock_gemini = AsyncMock()
    mock_gemini.generate_plan_json = AsyncMock(return_value=None)

    manager = AIManager(groq_provider=mock_groq, gemini_provider=mock_gemini)
    res = await manager.generate_plan(obs, profile, safety)

    assert res.ai_provider_used == "deterministic_fallback"
    assert res.is_fallback is True
    assert len(res.morning) >= 1
    assert "Safety" in res.disclaimer or "Advisory" in res.disclaimer


def test_validator_enforces_light_only_indoor_only_and_avoid_all():
    """F-02: Enforce Poor (light_only), Moderate+sensitivity (indoor_only), and Severe (avoid_all)."""
    # 1. Poor AQI -> light_only must overrule outdoor moderate/high and strenuous outdoor activities
    obs_poor = get_mock_observation("Poor")
    profile_general = HouseholdProfile(city="Delhi NCR", persona="general")
    safety_poor = safety_engine.evaluate(obs_poor, profile_general)
    assert safety_poor.constraints.outdoor_exertion_level == "light_only"

    plan_poor = get_mock_valid_ai_json()
    plan_poor["morning"][0] = {
        "period": "morning",
        "time_window": "06:30 AM - 07:30 AM",
        "activity": "Outdoor Morning Run",
        "location_type": "outdoor",
        "intensity": "moderate",
        "explanation": "Light jog outside.",
        "precautions": None,
        "data_context_used": "Poor PM2.5",
    }
    plan_poor["afternoon"][0] = {
        "period": "afternoon",
        "time_window": "02:00 PM - 03:00 PM",
        "activity": "Indoor Yoga Stretching",
        "location_type": "indoor",
        "intensity": "light",
        "explanation": "Valid indoor activity remains preserved.",
        "precautions": None,
        "data_context_used": "Indoor",
    }
    res_poor = validate_and_guardrail_ai_plan(plan_poor, obs_poor, profile_general, safety_poor)
    assert res_poor is not None
    assert res_poor["morning"][0]["location_type"] == "indoor"
    assert res_poor["morning"][0]["intensity"] == "light"
    assert "Substituted" in res_poor["morning"][0]["activity"]
    # Valid indoor activity must remain untouched
    assert res_poor["afternoon"][0]["activity"] == "Indoor Yoga Stretching"
    assert res_poor["afternoon"][0]["location_type"] == "indoor"

    # 2. Moderate AQI + respiratory sensitivity -> indoor_only must block outdoor exercise
    obs_mod = get_mock_observation("Moderate")
    obs_mod.index_value = 150
    profile_asthma = HouseholdProfile(
        city="Delhi NCR", persona="parent", age_groups=["child", "adult"], has_respiratory_sensitivity=True
    )
    safety_mod_vuln = safety_engine.evaluate(obs_mod, profile_asthma)
    assert safety_mod_vuln.constraints.vulnerable_activity_restriction == "indoor_only"

    plan_mod = get_mock_valid_ai_json()
    plan_mod["morning"][0] = {
        "period": "morning",
        "time_window": "07:00 AM - 08:00 AM",
        "activity": "Outdoor Jogging",
        "location_type": "outdoor",
        "intensity": "moderate",
        "explanation": "Jog in park.",
        "precautions": None,
        "data_context_used": "Moderate",
    }
    res_mod = validate_and_guardrail_ai_plan(plan_mod, obs_mod, profile_asthma, safety_mod_vuln)
    assert res_mod is not None
    assert res_mod["morning"][0]["location_type"] == "indoor"
    assert "Substituted" in res_mod["morning"][0]["activity"]

    # 3. Severe AQI -> avoid_all must overrule even "light" outdoor exercise
    obs_sev = get_mock_observation("Severe")
    obs_sev.index_value = 430
    profile_runner = HouseholdProfile(city="Delhi NCR", persona="athlete")
    safety_sev = safety_engine.evaluate(obs_sev, profile_runner)
    assert safety_sev.constraints.outdoor_exertion_level == "avoid_all"

    plan_sev = get_mock_valid_ai_json()
    plan_sev["morning"][0] = {
        "period": "morning",
        "time_window": "07:00 AM - 07:30 AM",
        "activity": "Outdoor Park Walk",
        "location_type": "outdoor",
        "intensity": "light",
        "explanation": "Short walk outside.",
        "precautions": None,
        "data_context_used": "Severe",
    }
    res_sev = validate_and_guardrail_ai_plan(plan_sev, obs_sev, profile_runner, safety_sev)
    assert res_sev is not None
    assert res_sev["morning"][0]["location_type"] == "indoor"
    assert "Substituted" in res_sev["morning"][0]["activity"]


def test_validator_case_insensitive_unsafe_and_medical_claims_all_fields():
    """F-02: Remove mixed-case unsafe claims and medical claims across all textual plan fields."""
    obs = get_mock_observation("Poor")
    profile = HouseholdProfile(city="Delhi NCR", persona="general")
    safety = safety_engine.evaluate(obs, profile)

    raw_json = get_mock_valid_ai_json()
    raw_json["morning"][0]["activity"] = "Take Steroid Inhaler Dosage Before Work"
    raw_json["morning"][0]["explanation"] = "This window is Completely Safe with Zero Pollution."
    raw_json["morning"][0]["precautions"] = "This is a SAFE HOUR and you can Prescribe extra inhaler."
    raw_json["indoor_air_suggestions"] = [
        "Opening windows at noon provides Completely Safe indoor air.",
        "Take antibiotic pills if coughing starts.",
    ]
    raw_json["sustainable_alternatives"] = [
        "Cycling outdoors is 100% Safe and Zero Pollution today.",
        "Use closed Metro rail.",
    ]

    validated = validate_and_guardrail_ai_plan(raw_json, obs, profile, safety)
    assert validated is not None
    m = validated["morning"][0]
    assert "steroid" not in m["activity"].lower()
    assert "completely safe" not in m["explanation"].lower()
    assert "zero pollution" not in m["explanation"].lower()
    assert "safe hour" not in (m["precautions"] or "").lower()
    assert "prescribe extra inhaler" not in (m["precautions"] or "").lower()
    assert "physician-prescribed" in (m["precautions"] or "").lower()

    indoor_joined = " ".join(validated["indoor_air_suggestions"]).lower()
    assert "completely safe" not in indoor_joined
    assert "antibiotic" not in indoor_joined

    sust_joined = " ".join(validated["sustainable_alternatives"]).lower()
    assert "100% safe" not in sust_joined
    assert "zero pollution" not in sust_joined
    assert "metro" in sust_joined


def test_deterministic_fallback_respects_poor_and_vulnerable_moderate():
    """F-02: Deterministic fallback never emits moderate outdoor exercise under light_only or indoor_only."""
    obs_poor = get_mock_observation("Poor")
    prof_gen = HouseholdProfile(city="Delhi NCR", persona="general")
    safety_poor = safety_engine.evaluate(obs_poor, prof_gen)
    fb_poor = generate_deterministic_fallback_plan(obs_poor, prof_gen, safety_poor)
    assert fb_poor["morning"][0]["intensity"] != "high"
    assert not (fb_poor["morning"][0]["location_type"] == "outdoor" and fb_poor["morning"][0]["intensity"] == "moderate")

    obs_mod = get_mock_observation("Moderate")
    obs_mod.index_value = 150
    prof_vuln = HouseholdProfile(city="Delhi NCR", persona="parent", has_respiratory_sensitivity=True)
    safety_vuln = safety_engine.evaluate(obs_mod, prof_vuln)
    fb_vuln = generate_deterministic_fallback_plan(obs_mod, prof_vuln, safety_vuln)
    assert fb_vuln["morning"][0]["location_type"] == "indoor"
