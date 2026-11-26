import json
from typing import Any, Dict, Optional
from app.schemas.air_quality import NormalizedAirObservation
from app.schemas.plan import HouseholdProfile, StructuredSafetyGuidance


def build_system_prompt() -> str:
    return (
        "You are BreatheWise AI's daily lifestyle planning engine, specialized in urban Indian air quality.\n"
        "Your task is to translate verified outdoor environmental data and deterministic public-health safety constraints "
        "into a practical, schedule-oriented daily routine for an Indian household.\n\n"
        "CRITICAL OPERATIONAL RULES:\n"
        "1. DATA INTEGRITY: You MUST NOT invent, alter, or fabricate any AQI or pollutant values. Use only the provided environmental data.\n"
        "2. SAFETY FIRST: You MUST STRICTLY respect the provided 'Safety Constraints'. Never recommend outdoor strenuous running or heavy exertion when constraints restrict it.\n"
        "3. THREE CORE PILLARS:\n"
        "   - Pillar 1: Pollution-aware daily routines (Morning, Afternoon, Evening) timed around diurnal air variations.\n"
        "   - Pillar 2: Indian indoor air intelligence (wet mopping vs dry sweeping, high-heat tadka cooking exhaust, kitchen door management).\n"
        "   - Pillar 3: Sustainable mobility alternatives explaining exposure vs emissions trade-offs without unsupported numerical savings.\n"
        "4. NO MEDICAL CLAIMS: Do not diagnose, prescribe medications, or declare an activity unconditionally 'safe'.\n"
        "5. OUTPUT FORMAT: Respond ONLY with a valid JSON object matching the requested schema. No conversational preamble or markdown code fences outside JSON."
    )


def build_user_prompt(
    obs: NormalizedAirObservation,
    profile: HouseholdProfile,
    safety: StructuredSafetyGuidance,
    air_window_context: Optional[dict] = None
) -> str:
    env_summary = {
        "city": obs.city,
        "source_type": obs.source_type,
        "data_provider": obs.data_provider,
        "index_category": obs.index_category,
        "index_value": obs.index_value,
        "dominant_pollutant": safety.dominant_pollutant,
        "pm25": f"{obs.pm25.value} {obs.pm25.unit}" if obs.pm25 else "Unavailable",
        "pm10": f"{obs.pm10.value} {obs.pm10.unit}" if obs.pm10 else "Unavailable",
        "o3": f"{obs.o3.value} {obs.o3.unit}" if obs.o3 else "Unavailable",
    }

    profile_summary = {
        "persona": profile.persona,
        "age_groups": profile.age_groups,
        "has_respiratory_sensitivity": profile.has_respiratory_sensitivity,
        "commute_mode": profile.commute_mode,
        "has_air_purifier": profile.has_air_purifier,
        "kitchen_ventilation_type": profile.kitchen_ventilation_type,
        "activity_preferences": profile.activity_preferences or ["Daily commuting", "Morning walk", "Home cooking"],
    }

    safety_constraints = {
        "band": safety.constraints.calculated_band,
        "outdoor_exertion_level": safety.constraints.outdoor_exertion_level,
        "vulnerable_activity_restriction": safety.constraints.vulnerable_activity_restriction,
        "ventilation_guidance": safety.constraints.ventilation_guidance,
        "respirator_advisory": safety.constraints.respirator_advisory,
        "fallback_indoor_activity": safety.constraints.fallback_indoor_activity,
    }

    forecast_section = ""
    if air_window_context:
        forecast_section = (
            f"\n\n=== HOURLY FORECAST & BEST AIR WINDOW CONTEXT ===\n"
            f"{json.dumps(air_window_context, indent=2)}\n"
            f"GUIDANCE: Consider the comparatively better window when scheduling outdoor transit or errands, but NEVER recommend outdoor running/cycling if safety constraints prohibit it.\n"
        )

    return (
        f"Generate a personalized daily plan based on the following verified context:\n\n"
        f"=== VERIFIED ENVIRONMENTAL DATA ===\n"
        f"{json.dumps(env_summary, indent=2)}\n\n"
        f"=== HOUSEHOLD PROFILE ===\n"
        f"{json.dumps(profile_summary, indent=2)}\n\n"
        f"=== MANDATORY PUBLIC-HEALTH SAFETY CONSTRAINTS ===\n"
        f"{json.dumps(safety_constraints, indent=2)}"
        f"{forecast_section}\n\n"
        f"Generate a JSON object with this exact structure:\n"
        "{\n"
        '  "morning": [\n'
        '    {\n'
        '      "period": "morning",\n'
        '      "time_window": "e.g. 06:30 AM - 08:30 AM",\n'
        '      "activity": "Brief action title",\n'
        '      "location_type": "indoor" | "outdoor" | "transit",\n'
        '      "intensity": "none" | "light" | "moderate" | "high",\n'
        '      "explanation": "Why this is recommended considering morning inversion/traffic",\n'
        '      "precautions": "Precautions e.g. respirator or indoor alternative",\n'
        '      "data_context_used": "e.g. Morning PM2.5 / CPCB Category"\n'
        '    }\n'
        '  ],\n'
        '  "afternoon": [...],\n'
        '  "evening": [...],\n'
        '  "indoor_air_suggestions": [\n'
        '    "Practical advice on wet mopping vs dry sweeping, kitchen tadka exhaust, or ventilation timing"\n'
        '  ],\n'
        '  "sustainable_alternatives": [\n'
        '    "Practical sustainable transit/routine alternative with exposure trade-off rationale"\n'
        '  ]\n'
        "}"
    )
