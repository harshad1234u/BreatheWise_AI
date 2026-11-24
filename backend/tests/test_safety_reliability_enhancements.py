import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

from app.schemas.air_quality import NormalizedAirObservation, PollutantConcentration
from app.schemas.plan import HouseholdProfile, DailyPlanResponse
from app.services.safety_engine import safety_engine
from app.services.ai.validator import (
    validate_and_guardrail_ai_plan,
    generate_deterministic_fallback_plan
)
from app.services.ai.ai_manager import AIManager
from app.services.ai.groq_provider import GroqProvider
from app.services.ai.gemini_provider import GeminiProvider


def make_obs(band: str, pm25_val: float = 180.0, data_status: str = "live", age_hours: float = 0.5):
    obs_time = datetime.now(timezone.utc) - timedelta(hours=age_hours)
    return NormalizedAirObservation(
        city="Delhi NCR",
        locality_or_station="Anand Vihar, Delhi",
        source_type="ground_station",
        data_provider="WAQI (Official CPCB Ground Feed)",
        observed_at=obs_time,
        fetched_at=datetime.now(timezone.utc),
        data_status=data_status,
        confidence_score="high" if data_status == "live" else "low",
        index_type="indicative_particulate_subindex",
        index_value=340 if band == "Very Poor" else 150,
        index_category=band,
        methodology_disclosure="Test observation",
        pm25=PollutantConcentration(value=pm25_val, sub_index=340.0),
        pm10=PollutantConcentration(value=190.0, sub_index=160.0),
        nh3=None,  # Unmonitored
        pb=None,   # Unmonitored
    )


def test_indoor_cooking_ventilation_conflict_resolution():
    """Verify that during Poor/Very Poor air, cooking guidance mandates kitchen exhaust, not pure sealed home."""
    obs = make_obs("Very Poor", pm25_val=220.0)
    profile = HouseholdProfile(
        city="Delhi NCR",
        persona="parent",
        kitchen_ventilation_type="exhaust_fan"
    )
    guidance = safety_engine.evaluate(obs, profile)
    # Must not advise complete window sealing without addressing cooking exhaust
    assert "exhaust" in guidance.indoor_cooking_guidance.lower() or "exhaust" in guidance.indoor_ventilation_guidance.lower()
    assert "agarbatti" in guidance.indoor_cooking_guidance.lower() or "incense" in guidance.indoor_cooking_guidance.lower()


def test_missing_pollutant_concentrations_unfabricated():
    """Verify that unmonitored pollutants (NH3, Pb) remain None and are not fabricated as 0."""
    obs = make_obs("Moderate")
    assert obs.nh3 is None
    assert obs.pb is None
    # Dominant pollutant calculation must not crash with missing values
    dominant = safety_engine.identify_dominant_pollutant(obs)
    assert dominant == "PM2.5"


def test_stale_environmental_observations_provenance():
    """Verify stale observations (>3h old) retain accurate provenance and status."""
    obs = make_obs("Very Poor", age_hours=4.5, data_status="stale")
    assert obs.data_status == "stale"
    assert obs.confidence_score == "low"
    assert "CPCB" in obs.data_provider


def test_rejection_of_unsupported_medical_advice():
    """Verify validator strips unauthorized medical drug advice."""
    obs = make_obs("Very Poor")
    profile = HouseholdProfile(city="Delhi NCR", persona="general")
    guidance = safety_engine.evaluate(obs, profile)

    raw_json = {
        "morning": [{
            "period": "morning",
            "time_window": "07:00 AM - 08:00 AM",
            "activity": "Morning Routine",
            "location_type": "indoor",
            "intensity": "light",
            "explanation": "Take steroid inhaler dosage before breakfast.",
            "precautions": "Take steroid medication."
        }],
        "afternoon": [{
            "period": "afternoon",
            "time_window": "01:00 PM - 02:00 PM",
            "activity": "Lunch",
            "location_type": "indoor",
            "intensity": "none",
            "explanation": "Normal indoor rest.",
            "precautions": None
        }],
        "evening": [{
            "period": "evening",
            "time_window": "06:00 PM - 07:00 PM",
            "activity": "Evening Rest",
            "location_type": "indoor",
            "intensity": "none",
            "explanation": "Rest indoors.",
            "precautions": None
        }],
        "indoor_air_suggestions": ["Keep kitchen ventilated."],
        "sustainable_alternatives": ["Take Metro."]
    }

    validated = validate_and_guardrail_ai_plan(raw_json, obs, profile, guidance)
    assert validated is not None
    morning = validated["morning"][0]
    # Injected safety disclaimer must replace steroid prescription
    assert "steroid" not in morning["explanation"].lower()
    assert "steroid" not in (morning["precautions"] or "").lower()
    assert "physician" in morning["explanation"].lower() or "physician" in (morning["precautions"] or "").lower()


def test_avoidance_of_mandatory_blanket_respirator_language():
    """Verify transit inside enclosed Metro does not enforce unconditional mandatory respirator."""
    obs = make_obs("Very Poor")
    profile = HouseholdProfile(city="Delhi NCR", commute_mode="metro_train")
    guidance = safety_engine.evaluate(obs, profile)

    raw_json = {
        "morning": [{
            "period": "morning",
            "time_window": "08:00 AM - 09:00 AM",
            "activity": "Commute to Office",
            "location_type": "transit",
            "intensity": "light",
            "explanation": "Travel via Delhi Metro AC train.",
            "precautions": None
        }],
        "afternoon": [{
            "period": "afternoon",
            "time_window": "01:00 PM - 02:00 PM",
            "activity": "Lunch",
            "location_type": "indoor",
            "intensity": "none",
            "explanation": "Indoor cafeteria.",
            "precautions": None
        }],
        "evening": [{
            "period": "evening",
            "time_window": "06:00 PM - 07:00 PM",
            "activity": "Return Commute",
            "location_type": "transit",
            "intensity": "light",
            "explanation": "Return home via Metro.",
            "precautions": None
        }],
        "indoor_air_suggestions": ["Clean surfaces with damp mop."],
        "sustainable_alternatives": ["Use Metro train."]
    }

    validated = validate_and_guardrail_ai_plan(raw_json, obs, profile, guidance)
    assert validated is not None
    morning = validated["morning"][0]
    # For enclosed Metro, must NOT say "MUST wear N95"
    assert "must wear n95" not in (morning["precautions"] or "").lower()


def test_ai_generated_unsafe_recommendation_overruled():
    """Verify that extreme outdoor exercise hallucinated by an LLM is forcefully rewritten."""
    obs = make_obs("Very Poor", pm25_val=350.0)
    profile = HouseholdProfile(city="Delhi NCR", persona="athlete")
    guidance = safety_engine.evaluate(obs, profile)

    raw_json = {
        "morning": [{
            "period": "morning",
            "time_window": "06:00 AM - 07:30 AM",
            "activity": "Outdoor 15km Cross-Country Marathon",
            "location_type": "outdoor",
            "intensity": "high",
            "explanation": "Cardio is great for stamina.",
            "precautions": None
        }],
        "afternoon": [{
            "period": "afternoon",
            "time_window": "01:00 PM - 02:00 PM",
            "activity": "Rest",
            "location_type": "indoor",
            "intensity": "none",
            "explanation": "Rest.",
            "precautions": None
        }],
        "evening": [{
            "period": "evening",
            "time_window": "06:00 PM - 07:00 PM",
            "activity": "Dinner",
            "location_type": "indoor",
            "intensity": "none",
            "explanation": "Dinner.",
            "precautions": None
        }],
        "indoor_air_suggestions": ["Keep windows closed."],
        "sustainable_alternatives": ["Use public transport."]
    }

    validated = validate_and_guardrail_ai_plan(raw_json, obs, profile, guidance)
    assert validated is not None
    m = validated["morning"][0]
    assert m["location_type"] == "indoor"
    assert m["intensity"] == "light"
    assert "Substituted" in m["activity"]
    assert "Safety Engine Guardrail" in m["precautions"]


@pytest.mark.asyncio
async def test_groq_and_gemini_independent_failures():
    """Verify individual provider failures cascade gracefully without crashing."""
    obs = make_obs("Moderate")
    profile = HouseholdProfile(city="Delhi NCR")
    guidance = safety_engine.evaluate(obs, profile)

    mock_groq = GroqProvider()
    mock_gemini = GeminiProvider()

    # Case A: Groq fails, Gemini succeeds
    with patch.object(mock_groq, "generate_plan_json", return_value=None), \
         patch.object(mock_gemini, "generate_plan_json", return_value={
             "morning": [{"period": "morning", "time_window": "8am", "activity": "Walk", "location_type": "indoor", "intensity": "light", "explanation": "ok"}],
             "afternoon": [{"period": "afternoon", "time_window": "1pm", "activity": "Work", "location_type": "indoor", "intensity": "none", "explanation": "ok"}],
             "evening": [{"period": "evening", "time_window": "6pm", "activity": "Relax", "location_type": "indoor", "intensity": "none", "explanation": "ok"}],
             "indoor_air_suggestions": ["Mop with damp cloth."],
             "sustainable_alternatives": ["Carpool."]
         }):
        manager = AIManager(groq_provider=mock_groq, gemini_provider=mock_gemini)
        plan = await manager.generate_plan(obs, profile, guidance)
        assert plan.ai_provider_used == "gemini"
        assert plan.is_fallback is True

    # Case B: Both fail, Pure-Python deterministic engine succeeds
    with patch.object(mock_groq, "generate_plan_json", return_value=None), \
         patch.object(mock_gemini, "generate_plan_json", return_value=None):
        manager2 = AIManager(groq_provider=mock_groq, gemini_provider=mock_gemini)
        plan2 = await manager2.generate_plan(obs, profile, guidance)
        assert plan2.ai_provider_used == "deterministic_fallback"
        assert plan2.is_fallback is True
        assert len(plan2.morning) > 0
        assert len(plan2.afternoon) > 0
        assert len(plan2.evening) > 0
