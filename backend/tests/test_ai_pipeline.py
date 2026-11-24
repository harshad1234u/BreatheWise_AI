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
